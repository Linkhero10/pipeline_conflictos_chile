"""
observabilidad.py - Métricas y Trazabilidad para Análisis con IA
Nivel: AI Architect

Este módulo proporciona:
1. Tracking de llamadas a la API (latencia, tokens, costos)
2. Logging estructurado con contexto
3. Métricas de rendimiento
4. Dashboard básico en consola

Integración futura: LangSmith, Weights & Biases, Arize Phoenix
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class LlamadaAPI:
    """Registro de una llamada a la API"""
    timestamp: str
    modelo: str
    provider: str
    tokens_input: int = 0
    tokens_output: int = 0
    latencia_ms: float = 0
    costo_estimado: float = 0
    exitosa: bool = True
    error: Optional[str] = None
    noticia_id: Optional[int] = None
    resultado_excluir: Optional[bool] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricasSession:
    """Métricas agregadas de una sesión de procesamiento"""
    inicio: str = field(default_factory=lambda: datetime.now().isoformat())
    fin: Optional[str] = None
    total_llamadas: int = 0
    llamadas_exitosas: int = 0
    llamadas_fallidas: int = 0
    tokens_totales: int = 0
    costo_total: float = 0
    latencia_promedio_ms: float = 0
    noticias_incluidas: int = 0
    noticias_excluidas: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


# Precios por 1M tokens (Actualizado Diciembre 2024)
# Fuente: OpenRouter / Google AI / Anthropic pricing pages
PRECIOS_MODELOS = {
    # Gemini 3.0 Flash (último modelo)
    'google/gemini-3.0-flash': {'input': 0.50, 'output': 3.00},
    'gemini-3.0-flash': {'input': 0.50, 'output': 3.00},
    
    # Gemini 2.x (modelos anteriores)
    'google/gemini-2.5-flash-preview-05-20': {'input': 0.15, 'output': 0.60},
    'google/gemini-2.5-pro-preview': {'input': 1.25, 'output': 5.00},
    'google/gemini-2.0-flash-001': {'input': 0.10, 'output': 0.40},
    'gemini-2.0-flash-exp': {'input': 0.10, 'output': 0.40},
    
    # Anthropic Claude
    'anthropic/claude-opus-4.5': {'input': 5.00, 'output': 25.00},
    'claude-opus-4.5': {'input': 5.00, 'output': 25.00},
    'anthropic/claude-opus-4': {'input': 15.00, 'output': 75.00},
    'anthropic/claude-sonnet-4': {'input': 3.00, 'output': 15.00},
    
    # OpenAI
    'openai/gpt-4-turbo': {'input': 10.00, 'output': 30.00},
    'openai/gpt-4o': {'input': 2.50, 'output': 10.00},
    'openai/gpt-4o-mini': {'input': 0.15, 'output': 0.60},
    
    # Default (conservador)
    'default': {'input': 0.50, 'output': 1.50}
}


class PresupuestoExcedidoError(Exception):
    """Excepción lanzada cuando se excede el presupuesto máximo de la sesión"""
    pass


class TrackerObservabilidad:
    """
    Tracker de observabilidad para llamadas a la API
    
    Uso:
        tracker = TrackerObservabilidad()
        tracker.set_presupuesto_max(5.0)  # USD máximo por sesión
        
        with tracker.track_llamada(modelo='gemini-flash', noticia_id=123):
            resultado = api.generate(...)
        
        tracker.imprimir_resumen()
    
    Circuit Breaker:
        Si el costo acumulado excede PRESUPUESTO_MAX_SESION, lanza PresupuestoExcedidoError
    """
    
    # Presupuesto máximo por defecto (USD) - Circuit Breaker de seguridad
    # NOTA: Desactivado por defecto (valor muy alto) ya que el límite acumulativo no tiene sentido práctico
    # El costo por noticia es ~$0.0005, por lo que 20,000 noticias = ~$10 USD
    PRESUPUESTO_MAX_SESION = 1000.0  # Prácticamente sin límite
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        # Singleton thread-safe
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._inicializado = False
        return cls._instance
    
    def __init__(self):
        if self._inicializado:
            return
        
        self.llamadas: List[LlamadaAPI] = []
        self.metricas = MetricasSession()
        self.logs_dir = Path('logs/observabilidad')
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._presupuesto_max = self.PRESUPUESTO_MAX_SESION
        self._circuit_breaker_activo = True
        self._inicializado = True
    
    def set_presupuesto_max(self, usd: float):
        """Configura el presupuesto máximo para la sesión (Circuit Breaker)"""
        self._presupuesto_max = usd
    
    def desactivar_circuit_breaker(self):
        """Desactiva el Circuit Breaker (usar con precaución)"""
        self._circuit_breaker_activo = False
    
    def _verificar_presupuesto(self):
        """Verifica si se excedió el presupuesto y lanza excepción si es así"""
        if not self._circuit_breaker_activo:
            return
        
        if self.metricas.costo_total >= self._presupuesto_max:
            raise PresupuestoExcedidoError(
                f"🚨 PRESUPUESTO EXCEDIDO: ${self.metricas.costo_total:.4f} USD "
                f"(límite: ${self._presupuesto_max:.2f} USD). "
                f"Procesadas {self.metricas.total_llamadas} noticias. "
                f"Ejecuta tracker.set_presupuesto_max(nuevo_limite) para continuar."
            )
    
    def track_llamada(self, modelo: str, provider: str = 'openrouter', 
                      noticia_id: Optional[int] = None):
        """Context manager para trackear una llamada a la API"""
        return _TrackerContext(self, modelo, provider, noticia_id)
    
    def registrar_llamada(self, llamada: LlamadaAPI):
        """Registra una llamada completada"""
        self.llamadas.append(llamada)
        self.metricas.total_llamadas += 1
        
        if llamada.exitosa:
            self.metricas.llamadas_exitosas += 1
            if llamada.resultado_excluir is not None:
                if llamada.resultado_excluir:
                    self.metricas.noticias_excluidas += 1
                else:
                    self.metricas.noticias_incluidas += 1
        else:
            self.metricas.llamadas_fallidas += 1
        
        self.metricas.tokens_totales += llamada.tokens_input + llamada.tokens_output
        self.metricas.costo_total += llamada.costo_estimado
        
        # Actualizar latencia promedio
        if self.metricas.llamadas_exitosas > 0:
            total_latencia = sum(l.latencia_ms for l in self.llamadas if l.exitosa)
            self.metricas.latencia_promedio_ms = total_latencia / self.metricas.llamadas_exitosas
        
        # Circuit Breaker: verificar presupuesto después de cada llamada
        self._verificar_presupuesto()
    
    def calcular_costo(self, modelo: str, tokens_input: int, tokens_output: int) -> float:
        """Calcula costo estimado de una llamada"""
        precios = PRECIOS_MODELOS.get(modelo, PRECIOS_MODELOS['default'])
        costo = (tokens_input * precios['input'] / 1_000_000 + 
                 tokens_output * precios['output'] / 1_000_000)
        return round(costo, 6)
    
    def imprimir_resumen(self):
        """Imprime resumen de métricas en consola"""
        m = self.metricas
        
        print("\n" + "="*60)
        print("📊 MÉTRICAS DE OBSERVABILIDAD")
        print("="*60)
        print(f"⏱️  Sesión: {m.inicio[:19]} → {m.fin[:19] if m.fin else 'En curso'}")
        print("-"*60)
        print(f"📞 Total llamadas:     {m.total_llamadas:,}")
        print(f"   ✅ Exitosas:        {m.llamadas_exitosas:,}")
        print(f"   ❌ Fallidas:        {m.llamadas_fallidas:,}")
        print("-"*60)
        print(f"📰 Noticias procesadas:")
        print(f"   ✅ Incluidas:       {m.noticias_incluidas:,}")
        print(f"   ❌ Excluidas:       {m.noticias_excluidas:,}")
        print("-"*60)
        print(f"🎯 Rendimiento:")
        print(f"   Tokens totales:     {m.tokens_totales:,}")
        print(f"   Latencia promedio:  {m.latencia_promedio_ms:.0f} ms")
        print(f"   💰 Costo estimado:  ${m.costo_total:.4f}")
        print("="*60)
    
    def exportar_logs(self) -> Path:
        """Exporta logs a archivo JSON"""
        self.metricas.fin = datetime.now().isoformat()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = self.logs_dir / f'observabilidad_{timestamp}.json'
        
        data = {
            'metricas': self.metricas.to_dict(),
            'llamadas': [l.to_dict() for l in self.llamadas]
        }
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Logs exportados: {log_path}")
        return log_path
    
    def reset(self):
        """Reinicia métricas para nueva sesión"""
        self.llamadas = []
        self.metricas = MetricasSession()


class _TrackerContext:
    """Context manager para tracking de llamadas"""
    
    def __init__(self, tracker: TrackerObservabilidad, modelo: str, 
                 provider: str, noticia_id: Optional[int]):
        self.tracker = tracker
        self.modelo = modelo
        self.provider = provider
        self.noticia_id = noticia_id
        self.inicio = None
        self.llamada = None
    
    def __enter__(self):
        self.inicio = time.perf_counter()
        self.llamada = LlamadaAPI(
            timestamp=datetime.now().isoformat(),
            modelo=self.modelo,
            provider=self.provider,
            noticia_id=self.noticia_id
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        fin = time.perf_counter()
        self.llamada.latencia_ms = (fin - self.inicio) * 1000
        
        if exc_type is not None:
            self.llamada.exitosa = False
            self.llamada.error = str(exc_val)
        
        self.tracker.registrar_llamada(self.llamada)
        return False  # No suprimir excepciones
    
    def set_tokens(self, tokens_input: int, tokens_output: int):
        """Establece conteo de tokens después de la llamada"""
        self.llamada.tokens_input = tokens_input
        self.llamada.tokens_output = tokens_output
        self.llamada.costo_estimado = self.tracker.calcular_costo(
            self.modelo, tokens_input, tokens_output
        )
    
    def set_resultado(self, excluir: bool):
        """Establece resultado de clasificación"""
        self.llamada.resultado_excluir = excluir


class LoggerEstructurado:
    """
    Logger estructurado para análisis posterior
    
    Formato: JSON lines (un JSON por línea)
    Útil para importar a sistemas de análisis (ELK, Grafana Loki, etc.)
    """
    
    def __init__(self, log_file: str = 'logs/structured.jsonl'):
        self.log_path = Path(log_file)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, evento: str, **datos):
        """Registra un evento estructurado"""
        registro = {
            'timestamp': datetime.now().isoformat(),
            'evento': evento,
            **datos
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')
    
    def log_clasificacion(self, noticia_id: int, resultado: dict, 
                          latencia_ms: float, modelo: str):
        """Log específico para clasificaciones"""
        self.log(
            'clasificacion',
            noticia_id=noticia_id,
            excluir=resultado.get('excluir'),
            motivo=resultado.get('motivo_exclusion'),
            tipo_conflicto=resultado.get('tipo_conflicto'),
            tipo_accion=resultado.get('tipo_accion'),
            latencia_ms=round(latencia_ms, 2),
            modelo=modelo,
            requiere_revision=resultado.get('requiere_revision_manual', False)
        )


# Instancia global (singleton)
tracker = TrackerObservabilidad()
structured_logger = LoggerEstructurado()


def integrar_con_analizador():
    """
    Ejemplo de cómo integrar el tracker con AnalizadorIA
    
    En filtrador_analisis.py, modificar _llamar_api_simple:
    
    from .observabilidad import tracker
    
    def _llamar_api_simple(self, prompt: str) -> str:
        with tracker.track_llamada(
            modelo=self.model_name, 
            provider=self.provider
        ) as ctx:
            response = self.client.chat.completions.create(...)
            
            # Si la API devuelve conteo de tokens
            if hasattr(response, 'usage'):
                ctx.set_tokens(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            return response.choices[0].message.content
    """
    pass


# Ejemplo de uso
if __name__ == '__main__':
    # Simular algunas llamadas
    for i in range(5):
        with tracker.track_llamada(
            modelo='google/gemini-2.5-flash-preview-05-20',
            provider='openrouter',
            noticia_id=i+1
        ) as ctx:
            time.sleep(0.1)  # Simular latencia
            ctx.set_tokens(1000, 500)
            ctx.set_resultado(i % 2 == 0)  # Alternar incluir/excluir
    
    tracker.imprimir_resumen()
    tracker.exportar_logs()
