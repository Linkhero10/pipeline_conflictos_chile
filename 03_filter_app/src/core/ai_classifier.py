"""
analisis_ia.py - Módulo de análisis con IA (Gemini/OpenRouter)
Versión 4.0 - Con Pydantic, Chain of Thought y Tenacity
"""

import json
import logging
import re
import time
import pandas as pd
import unicodedata
from typing import Dict, Any, Optional, Literal

# Pydantic para validación de respuestas de IA
try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    ValidationError = Exception  # Fallback

# Tenacity para reintentos robustos
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False

from .config_loader import (
    TIPOS_CONFLICTO, TIPOS_ACCION, 
    TIPOS_ACTOR_DEMANDANTE, TIPOS_ACTOR_DEMANDADO,
    TIPOS_SECTOR_ECONOMICO, REGIONES_CHILE,
    ESCALAS_CONFLICTO, TIPOS_VINCULO_TRANSICION,
    SECTORES_ALIAS, PROMPT_COMPONENTS, MOTIVOS_EXCLUSION
)
from .maptu_clasificacion import MapeoTipos, MapeoRegion
from .observabilidad import TrackerObservabilidad, LoggerEstructurado
from .cache_manager import ResponseCache  # ✅ Importar Cache Manager

# Inicializar tracker global (singleton)
tracker = TrackerObservabilidad()
structured_logger = LoggerEstructurado()

logger = logging.getLogger(__name__)

# ============================================================================
# MODELOS PYDANTIC PARA VALIDACIÓN DE RESPUESTAS DE IA
# ============================================================================

if PYDANTIC_AVAILABLE:
    class ClasificacionBase(BaseModel):
        """Modelo base para respuestas de IA"""
        razonamiento_paso_a_paso: Optional[str] = Field(None, description="Chain of Thought")
        excluir: bool
        motivo_exclusion: Optional[str] = None
        resumen: Optional[str] = Field(None, max_length=800)
        palabras_clave: Optional[str] = Field(None, max_length=200)
        tono_emocional: Optional[str] = Field(None, max_length=200)
        region: Optional[str] = None
        provincia: Optional[str] = None
        comuna: Optional[str] = None
        localidad: Optional[str] = None
        requiere_revision_manual: bool = False
        
        @field_validator('motivo_exclusion')
        @classmethod
        def validar_motivo(cls, v, info):
            if info.data.get('excluir') and not v:
                raise ValueError('Si se excluye, debe haber motivo_exclusion')
            return v

    class ClasificacionExcluida(ClasificacionBase):
        """Modelo para noticias excluidas"""
        explicacion_exclusion: Optional[str] = Field(None, max_length=200)
        tipo_conflicto: Optional[str] = None
        tipo_accion: Optional[str] = None
        actor_demandante: Optional[str] = None
        actor_demandado: Optional[str] = None
        justificacion_transicion: Optional[str] = None
        notas: Optional[str] = None

    class ClasificacionIncluida(ClasificacionBase):
        """Modelo para noticias incluidas"""
        tipo_conflicto: str
        explicacion_conflicto: Optional[str] = Field(None, max_length=150)
        tipo_accion: str
        explicacion_accion: Optional[str] = Field(None, max_length=150)
        actor_demandante: str
        actor_demandante_especifico: Optional[str] = None
        explicacion_demandante: Optional[str] = Field(None, max_length=150)
        actor_demandado: str
        actor_demandado_especifico: Optional[str] = None
        explicacion_demandado: Optional[str] = Field(None, max_length=150)
        proyecto_especifico: Optional[str] = None
        escala_conflicto: Optional[str] = None
        sector_economico: Optional[str] = None
        vinculo_transicion: Optional[str] = None
        justificacion_transicion: Optional[str] = Field(None, min_length=40, max_length=250)
        notas: Optional[str] = None
        
        @field_validator('justificacion_transicion')
        @classmethod
        def validar_justificacion(cls, v, info):
            if not info.data.get('excluir') and (not v or len(v) < 40):
                raise ValueError('justificacion_transicion debe tener mínimo 40 caracteres')
            return v


class AnalizadorIA:
    """Gestiona el análisis de noticias con IA"""
    
    def __init__(self, api_key: str, provider: str = "google"):
        """
        Args:
            api_key: API Key del provider
            provider: "google", "abacus" o "openrouter"
        """
        self.provider = provider
        
        # CRÍTICO: Validar que la API key no esté vacía
        if not api_key or api_key.strip() == '':
            raise ValueError(f"❌ API Key vacía para provider '{provider}'. Verifica tu archivo .env")
        
        if provider == "abacus":
            from openai import OpenAI
            self.client = OpenAI(
                base_url="https://routellm.abacus.ai/v1",
                api_key=api_key
            )
            self.model_name = "gemini-3-flash-preview"
        elif provider == "openrouter":
            from openai import OpenAI
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/fondecyt-filtrador",
                    "X-Title": "FONDECYT Filtrador de Conflictos"
                }
            )
            self.model_name = "google/gemini-3-flash-preview"
        else:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')  # Google nativo usa 2.0, OpenRouter usa 3.0
            self.client = None
            self.model_name = None
        
        # Validar coherencia de mapeos al iniciar
        self._validar_coherencia_mapeos()
        
        # Inicializar caché de respuestas
        try:
            self.cache = ResponseCache()
            logger.info("Caché de respuestas inicializado")
        except Exception as e:
            logger.warning(f"No se pudo inicializar caché: {e}")
            self.cache = None
    
    def _validar_coherencia_mapeos(self):
        """
        Valida que los mapeos en MapeoTipos estén sincronizados
        con las listas de tipos válidos en config
        """
        errores = []
        
        # Validar que todos los mapeos de conflictos apunten a tipos válidos
        for original, mapeado in MapeoTipos.CONFLICTOS.items():
            if mapeado and mapeado not in TIPOS_CONFLICTO:
                errores.append(f"Conflicto: '{original}' → '{mapeado}' ('{mapeado}' no está en TIPOS_CONFLICTO)")
        
        # Validar que todos los mapeos de acciones apunten a tipos válidos
        for original, mapeado in MapeoTipos.ACCIONES.items():
            if mapeado and mapeado not in TIPOS_ACCION:
                errores.append(f"Acción: '{original}' → '{mapeado}' ('{mapeado}' no está en TIPOS_ACCION)")
        
        # Validar que todos los mapeos de demandantes apunten a tipos válidos
        for original, mapeado in MapeoTipos.DEMANDANTES.items():
            if mapeado and mapeado not in TIPOS_ACTOR_DEMANDANTE:
                errores.append(f"Demandante: '{original}' → '{mapeado}' ('{mapeado}' no está en TIPOS_ACTOR_DEMANDANTE)")
        
        # Validar que todos los mapeos de demandados apunten a tipos válidos
        for original, mapeado in MapeoTipos.DEMANDADOS.items():
            if mapeado and mapeado not in TIPOS_ACTOR_DEMANDADO:
                errores.append(f"Demandado: '{original}' → '{mapeado}' ('{mapeado}' no está en TIPOS_ACTOR_DEMANDADO)")
        
        if errores:
            logger.warning("⚠️ ERRORES DE COHERENCIA EN MAPEOS:")
            for error in errores:
                logger.warning(f"  - {error}")
            logger.warning("⚠️ Corrige estos mapeos en mapeos_clasificacion.py o filtrador_config.py")
        else:
            logger.info("✅ Validación de coherencia de mapeos completada - Sin errores")
    
    def _resultado_sin_contenido(self, noticia: dict, razon: str) -> dict:
        """
        Genera resultado estándar para noticias sin contenido suficiente
        
        Args:
            noticia: Dict con datos de la noticia (para logging)
            razon: Explicación de por qué se excluye
        """
        return {
            'excluir': True,
            'motivo_exclusion': 'Motivo 12: Sin contenido',
            'explicacion_exclusion': razon,
            'tipo_conflicto': None,
            'tipo_accion': None,
            'actor_demandante': None,
            'actor_demandado': None,
            'resumen': None,
            'noticia': '',
            'requiere_revision_manual': False,
            'region': None,
            'provincia': None,
            'comuna': None,
            'localidad': None,
            'sector_economico': None,
            'justificacion_transicion': None,
            'notas': None  # No agregar notas a noticias excluidas
        }
    
    def analizar_noticia(self, noticia: dict) -> Dict[str, Any]:
        """
        Analiza una noticia según criterios FONDECYT
        
        Returns:
            dict con clasificación completa
        """
        # Validar fecha
        fecha = noticia.get('Fecha_Extraida_ISO', '') or noticia.get('fecha', '')
        if fecha and not self._validar_fecha(fecha):
            return self._resultado_error(f'Fecha inválida: {fecha}')
        
        # Obtener título y contenido
        titulo = str(noticia.get('titulo', '')).strip()
        contenido = str(noticia.get('Contenido_Completo') or 
                      noticia.get('contenido_extraido') or 
                      noticia.get('noticia') or  # Columna usada en el Excel filtrado
                      noticia.get('contenido', '')).strip()
        
        # =====================================================================
        # PREFILTRO: Detecta patrones sospechosos (la IA sigue analizando)
        # Si detecta patrón, se marcará para revisión manual DESPUÉS del análisis
        # =====================================================================
        alerta_prefiltro = self._verificar_alerta_prefiltro(titulo, contenido)
        
        # Limpiar valores NaN o strings 'nan', 'none', 'null'
        if pd.isna(titulo) or titulo.lower() in ['nan', 'none', 'null', '']:
            titulo = ''
        if pd.isna(contenido) or contenido.lower() in ['nan', 'none', 'null', '']:
            contenido = ''
        
        # Validar que haya contenido mínimo
        if not contenido or len(contenido) < 200:
            logger.warning(f"⚠️ Noticia sin contenido: {titulo[:60]}...")
            return self._resultado_sin_contenido(
                noticia,
                'Contenido muy breve o vacío'
            )
        
        # Si el contenido es igual al título, limpiar
        if contenido == titulo:
            contenido = ''
        
        # Si el contenido es muy similar al título (>80% similar) Y es corto, limpiar
        if contenido and titulo and len(contenido) < 500:  # Solo si es corto
            tokens_titulo = set(titulo.lower().split())
            if tokens_titulo:  # Protección contra división por cero
                similitud = len(set(contenido.lower().split()) & tokens_titulo) / len(tokens_titulo)
                if similitud > 0.8:
                    logger.info(f"Contenido similar al título ({similitud:.1%}) y corto ({len(contenido)} chars), limpiando")
                    contenido = ''
        
        # Validar nuevamente después de limpieza
        if not contenido or len(contenido) < 200:
            logger.info(f"⚠️ Contenido muy breve ({len(contenido)} chars): {titulo[:60]}...")
            return {
                'excluir': True,
                'motivo_exclusion': 'Motivo 12: Sin contenido',
                'explicacion_exclusion': f'Contenido insuficiente ({len(contenido)} caracteres)',
                'tipo_conflicto': None,
                'tipo_accion': None,
                'actor_demandante': None,
                'actor_demandado': None,
                'resumen': None,
                'noticia': contenido,
                'requiere_revision_manual': False,
                'region': None,
                'provincia': None,
                'comuna': None,
                'localidad': None,
                'sector_economico': None,
                'justificacion_transicion': None,
                'notas': None  # No agregar notas a noticias excluidas
            }
        
        # Construir texto para análisis
        texto_completo = self._construir_texto_analisis(titulo, contenido, noticia)
        
        # Crear prompt
        prompt = self._crear_prompt_analisis(texto_completo, noticia)
        
        try:
            # Llamar a la API con reintentos (tenacity si disponible)
            respuesta_api = self._llamar_api_con_reintentos(prompt)
            texto = respuesta_api['texto']
            
            # Guardar métricas de la llamada
            tokens_in = respuesta_api.get('tokens_input', 0)
            tokens_out = respuesta_api.get('tokens_output', 0)
            latencia = respuesta_api.get('latencia_ms', 0)
            costo = self._calcular_costo(tokens_in, tokens_out, respuesta_api.get('modelo', self.model_name))
            
            metricas_api = {
                'tokens_input': tokens_in,
                'tokens_output': tokens_out,
                'tokens_totales': tokens_in + tokens_out,
                'latencia_ms': latencia,
                'modelo_usado': respuesta_api.get('modelo', self.model_name),
                'costo_estimado': costo
            }
            
            # Registrar en tracker de observabilidad
            from datetime import datetime
            from .observabilidad import LlamadaAPI
            llamada = LlamadaAPI(
                timestamp=datetime.now().isoformat(),
                modelo=self.model_name,
                provider=self.provider,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                latencia_ms=latencia,
                costo_estimado=costo,
                exitosa=True,
                noticia_id=noticia.get('id_noticia'),
                resultado_excluir=None  # Se actualizará después de parsear
            )
            tracker.registrar_llamada(llamada)
            
        except Exception as e:
            logger.error(f"Error en análisis: {e}")
            return {
                'excluir': True,
                'motivo_exclusion': 'Motivo 13: Error de procesamiento',
                'explicacion_exclusion': 'Error de procesamiento - Requiere revisión manual',
                'tipo_conflicto': None,
                'tipo_accion': None,
                'actor_demandante': None,
                'actor_demandado': None,
                'resumen': None,
                'noticia': '',
                'requiere_revision_manual': True,
                'region': None,
                'provincia': None,
                'comuna': None,
                'localidad': None,
                'sector_economico': None,
                'justificacion_transicion': None,
                'notas': None,
                # Métricas vacías en caso de error
                'tokens_input': 0,
                'tokens_output': 0,
                'tokens_totales': 0,
                'latencia_ms': 0,
                'modelo_usado': self.model_name,
                'costo_estimado': 0
            }
        
        # Parsear respuesta
        json_texto = self._extraer_json(texto)
        resultado = self._parsear_json_seguro(json_texto)
        
        # Agregar métricas al resultado
        resultado.update(metricas_api)
        
        # Validar y normalizar (envuelto en try-catch adicional)
        try:
            # Intentar validación Pydantic primero (si disponible)
            if PYDANTIC_AVAILABLE:
                try:
                    resultado = self._validar_con_pydantic(resultado)
                except ValidationError:
                    # Fallback a validación manual si Pydantic falla
                    logger.info("Fallback a validación manual")
                    resultado = self._validar_clasificacion(resultado)
            else:
                resultado = self._validar_clasificacion(resultado)
            
            resultado = self._validar_coherencia(resultado)
            resultado = self._normalizar_resultado(resultado)
        except Exception as validation_error:
            logger.error(f"Error en validación: {validation_error}")
            # Retornar resultado básico sin validación
            resultado.setdefault('excluir', True)
            resultado.setdefault('motivo_exclusion', 'Motivo 13: Error de procesamiento')
            resultado.setdefault('explicacion_exclusion', 'Error en validación - Requiere revisión manual')
            resultado.setdefault('requiere_revision_manual', True)
        
        # =====================================================================
        # APLICAR ALERTA DEL PREFILTRO (si fue detectado patrón sospechoso)
        # NUEVA LÓGICA: Si hay alerta Y la IA no identificó acción clara → EXCLUIR
        # =====================================================================
        if alerta_prefiltro:
            tipo_accion = resultado.get('tipo_accion', '')
            accion_verificable = tipo_accion and tipo_accion not in [
                'Requiere verificación', 'No identificada', '', None,
                'Sin acción específica', 'Pendiente de verificación'
            ]
            
            # Si la IA NO identificó una acción contenciosa clara → EXCLUIR
            if not accion_verificable and not resultado.get('excluir', False):
                logger.info(f"🚫 PREFILTRO ESTRICTO: Alerta detectada + sin acción clara → Excluir")
                resultado['excluir'] = True
                resultado['motivo_exclusion'] = 'Motivo 9: Anuncio sin oposición'
                resultado['explicacion_exclusion'] = f'Prefiltro: {alerta_prefiltro}. La IA no identificó acción contenciosa verificable.'
                resultado['requiere_revision_manual'] = False
                resultado['tipo_conflicto'] = None
                resultado['tipo_accion'] = None
                resultado['actor_demandante'] = None
                resultado['actor_demandado'] = None
            else:
                # La IA SÍ identificó acción clara → mantener pero marcar para revisión
                resultado['requiere_revision_manual'] = True
                nota_prefiltro = f"⚠️ PREFILTRO: {alerta_prefiltro} - ADVERTENCIA: La IA puede alucinar conflictos en este tipo de noticias. Se recomienda leer la noticia original para verificar si realmente existe una acción contenciosa."
                notas_actuales = resultado.get('notas') or ''
                resultado['notas'] = f"{nota_prefiltro}\n{notas_actuales}".strip() if notas_actuales else nota_prefiltro
                logger.info(f"⚠️ Noticia marcada para revisión manual por prefiltro: {alerta_prefiltro}")
        
        return resultado
    
    def _llamar_api_con_reintentos(self, prompt: str) -> dict:
        """
        Llama a la API con reintentos, verificando caché primero.
        Devuelve dict con 'texto' y métricas de uso.
        """
        # 1. Verificar caché
        if self.cache:
            modelo_key = self.model_name or "gemini-default"
            cached = self.cache.get(prompt, modelo_key)
            if cached:
                logger.info("⚡ Respuesta recuperada del caché (sin costo API)")
                cached['cached'] = True
                return cached
        
        # 2. Llamar API
        if TENACITY_AVAILABLE:
            resultado = self._llamar_api_tenacity(prompt)
        else:
            resultado = self._llamar_api_simple(prompt)
            
        # 3. Guardar en caché
        if self.cache and resultado:
            modelo_key = self.model_name or "gemini-default"
            self.cache.set(prompt, modelo_key, resultado)
            
        return resultado
    
    def _llamar_api_simple(self, prompt: str) -> dict:
        """
        Llamada simple a la API sin reintentos sofisticados.
        Devuelve dict con 'texto' y métricas de uso.
        """
        import time
        inicio = time.perf_counter()
        
        if self.provider in ["abacus", "openrouter"]:
            params = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 8192
            }
            if self.provider == "abacus":
                params["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**params)
            latencia_ms = (time.perf_counter() - inicio) * 1000
            
            # Extraer métricas de uso si están disponibles
            tokens_input = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
            tokens_output = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0
            
            return {
                'texto': response.choices[0].message.content,
                'tokens_input': tokens_input,
                'tokens_output': tokens_output,
                'latencia_ms': round(latencia_ms, 2),
                'modelo': self.model_name
            }
        else:
            # Gemini nativo (Google AI)
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'top_p': 0.9,
                    'top_k': 40,
                    'max_output_tokens': 8192,
                    'response_mime_type': 'application/json',
                },
                request_options={'timeout': 120}
            )
            latencia_ms = (time.perf_counter() - inicio) * 1000
            
            # Gemini devuelve usage_metadata
            tokens_input = 0
            tokens_output = 0
            if hasattr(response, 'usage_metadata'):
                tokens_input = getattr(response.usage_metadata, 'prompt_token_count', 0)
                tokens_output = getattr(response.usage_metadata, 'candidates_token_count', 0)
            
            return {
                'texto': response.text,
                'tokens_input': tokens_input,
                'tokens_output': tokens_output,
                'latencia_ms': round(latencia_ms, 2),
                'modelo': self.model_name
            }
    
    def _llamar_api_tenacity(self, prompt: str) -> dict:
        """Llamada a la API con reintentos usando tenacity."""
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=30),
            reraise=True
        )
        def _llamar_con_retry():
            return self._llamar_api_simple(prompt)
        
        return _llamar_con_retry()
    
    def _calcular_costo(self, tokens_input: int, tokens_output: int, modelo: str) -> float:
        """
        Calcula el costo estimado de una llamada a la API.
        Precios por 1M tokens (OpenRouter, Diciembre 2024).
        """
        PRECIOS = {
            # Gemini 3 (producción)
            'google/gemini-3-flash-preview': {'input': 0.10, 'output': 0.40},
            'gemini-3-flash-preview': {'input': 0.10, 'output': 0.40},  # Abacus format
            # Gemini 2.5
            'google/gemini-2.5-flash-preview-05-20': {'input': 0.15, 'output': 0.60},
            'google/gemini-2.5-pro-preview': {'input': 1.25, 'output': 5.00},
            # Claude
            'anthropic/claude-opus-4': {'input': 15.00, 'output': 75.00},
            'anthropic/claude-sonnet-4': {'input': 3.00, 'output': 15.00},
            # OpenAI
            'openai/gpt-4-turbo': {'input': 10.00, 'output': 30.00},
        }
        
        precios = PRECIOS.get(modelo, {'input': 0.50, 'output': 1.50})
        costo = (tokens_input * precios['input'] / 1_000_000 + 
                 tokens_output * precios['output'] / 1_000_000)
        return round(costo, 6)
    
    def _construir_texto_analisis(self, titulo: str, contenido: str, noticia: dict) -> str:
        """Construye el texto completo para análisis (sin truncado)"""
        texto = f"{titulo}\n\n"
        
        if contenido:
            # Enviar contenido completo - Gemini 2.5 Flash tiene contexto de 1M tokens
            texto += f"Contenido:\n{contenido}"
        
        return texto
    
    def _generar_instrucciones_contextuales(self, titulo: str, contenido: str) -> str:
        """
        SISTEMA DE INYECCIÓN DE PROMPTS CONTEXTUALES
        Detecta patrones en título/contenido y genera instrucciones adicionales
        para evitar falsos positivos específicos.
        """
        instrucciones = []
        texto_analisis = f"{titulo} {contenido}".lower()
        
        # =====================================================================
        # PATRÓN 1: ARTÍCULOS DE ANÁLISIS/OPINIÓN
        # Títulos como "Luces y sombras", "Por qué...", "Análisis:", "Columna:"
        # =====================================================================
        patrones_analisis = [
            'luces y sombras', 'luces y sombras del', 'análisis:', 'columna:', 'editorial:',
            'por qué el', 'por qué la', 'por qué chile', 'por qué el litio',
            'sigue perdiendo', 'pierde competitividad', 'enfrenta desafíos',
            'balance de', 'reflexión sobre', 'una mirada a', 'el dilema de',
            'crónica de', 'la historia de', 'el futuro del', 'el desafío del'
        ]
        if any(p in texto_analisis for p in patrones_analisis):
            instrucciones.append("""
⚠️ ALERTA: POSIBLE ARTÍCULO DE ANÁLISIS/OPINIÓN
Esta noticia tiene características de artículo analítico o columna de opinión.
REGLA ESTRICTA: Los artículos de análisis NO son conflictos aunque mencionen problemas.
- Si es una columna de opinión → EXCLUIR (Motivo 9)
- Si es un análisis de situación sin acción contenciosa específica → EXCLUIR (Motivo 9)
- SOLO incluir si menciona una acción contenciosa CONCRETA Y ESPECÍFICA (protesta, recurso, denuncia)
""")
        
        # =====================================================================
        # PATRÓN 2: ACUERDOS Y AVANCES ADMINISTRATIVOS
        # "Avanza el pacto", "El detalle de los pagos", "Autorizan cuota"
        # =====================================================================
        patrones_acuerdos = [
            'avanza el pacto', 'avanza el acuerdo', 'avanza acuerdo',
            'el detalle de los pagos', 'detalle del acuerdo',
            'autorizan cuota', 'autoriza extracción', 'aprueba acuerdo',
            'ratifica acuerdo', 'firma convenio', 'firman convenio',
            'pacta codelco-sqm', 'acuerdo codelco-sqm', 'pacta codelco',
            'avanza el pacto codelco', 'avanza pacto codelco'
        ]
        if any(p in texto_analisis for p in patrones_acuerdos):
            instrucciones.append("""
⚠️ ALERTA: POSIBLE NOTICIA DE AVANCE ADMINISTRATIVO
Esta noticia parece informar sobre avances de acuerdos o autorizaciones.
REGLA ESTRICTA: Los avances administrativos sin oposición NO son conflictos.
- Si solo informa sobre pagos/términos de un acuerdo → EXCLUIR (Motivo 9)
- Si solo informa sobre autorizaciones aprobadas → EXCLUIR (Motivo 9)
- SOLO incluir si hay actores OPONIÉNDOSE activamente al avance
""")
        
        # =====================================================================
        # PATRÓN 3: INVERSIONES EMPRESARIALES
        # "Invertirá US$", "Anuncia inversión", "Proyecto de inversión"
        # =====================================================================
        patrones_inversion = [
            'invertirá us$', 'invertirá usd', 'anuncia inversión',
            'proyecto de inversión', 'millones en proyecto',
            'millones de dólares en', 'nueva planta de',
            'invertirá us$ 600 millones', 'invertirá us$600 millones',
            'invertirá 600 millones', 'us$ 600 millones', 'us$600 millones'
        ]
        if any(p in texto_analisis for p in patrones_inversion):
            instrucciones.append("""
⚠️ ALERTA: POSIBLE ANUNCIO DE INVERSIÓN
Esta noticia parece ser un anuncio de inversión empresarial.
REGLA ESTRICTA: Los anuncios de inversión NO son conflictos por sí solos.
- Si solo anuncia una inversión sin oposición → EXCLUIR (Motivo 9)
- Si es un comunicado de prensa empresarial → EXCLUIR (Motivo 4)
- SOLO incluir si hay comunidades/ONGs OPONIÉNDOSE activamente a la inversión
""")
        
        # =====================================================================
        # PATRÓN 4: LITIO Y SALAR DE ATACAMA
        # Instrucciones específicas para noticias de litio
        # =====================================================================
        patrones_litio = [
            'litio', 'salar de atacama', 'sqm', 'albemarle', 'codelco',
            'oro blanco', 'mineral crítico', 'salmuera'
        ]
        if any(p in texto_analisis for p in patrones_litio):
            instrucciones.append("""
⚠️ CONTEXTO: NOTICIA SOBRE LITIO/SALAR DE ATACAMA
El litio es un tema frecuente con muchas noticias NO conflictivas.
FILTRO ESTRICTO para litio:
- RSE de SQM/Albemarle (clínicas, ferias, convenios) → EXCLUIR (Motivo 4)
- Anuncios de estrategia nacional sin oposición → EXCLUIR (Motivo 9)
- Informes de producción/ventas → EXCLUIR (Motivo 9)
- Acuerdos Codelco-SQM sin oposición activa → EXCLUIR (Motivo 9)
SOLO INCLUIR si hay:
- Comunidades lickanantay/atacameñas EN OPOSICIÓN ACTIVA
- Recurso judicial interpuesto
- Protesta/toma de terreno
- Sanción de SMA por incumplimiento
- Denuncia formal ante autoridades
""")
        
        # =====================================================================
        # PATRÓN 5: DIFICULTADES EMPRESARIALES SIN CONFLICTO SOCIAL
        # "tropieza con", "enfrenta problemas", "dudas de inversionistas"
        # =====================================================================
        patrones_dificultades = [
            'tropieza con', 'enfrenta problemas', 'dudas de inversionistas',
            'retraso en proyecto', 'dificultades para', 'no ha concretado'
        ]
        if any(p in texto_analisis for p in patrones_dificultades):
            instrucciones.append("""
⚠️ ALERTA: POSIBLES DIFICULTADES EMPRESARIALES
Esta noticia puede tratar sobre problemas de negocios, NO conflicto social.
REGLA ESTRICTA: Dificultades empresariales/de inversión NO son conflictos socioambientales.
- Si es sobre problemas de financiamiento → EXCLUIR (Motivo 9)
- Si es sobre retrasos de proyecto sin oposición social → EXCLUIR (Motivo 9)
- SOLO incluir si las dificultades son CAUSADAS por oposición de comunidades/ONGs
""")
        
        if instrucciones:
            return "\n<contextual_warnings>\n" + "\n".join(instrucciones) + "\n</contextual_warnings>\n"
        return ""
    
    def _verificar_exclusion_automatica(self, titulo: str, contenido: str) -> Optional[dict]:
        """
        PREFILTRO DETERMINISTA - Excluye automáticamente falsos positivos conocidos
        SIN enviar a la IA. Esto es 100% confiable.
        
        IMPORTANTE: Solo excluye si NO hay acciones contenciosas en el contenido.
        """
        texto_completo = f"{titulo} {contenido}".lower()
        
        # Palabras que indican acción contenciosa REAL - si aparecen, NO excluir automáticamente
        palabras_accion_contenciosa = [
            'recurso de protección', 'recurso judicial', 'demanda', 'demandaron',
            'protesta', 'protestaron', 'marcha', 'manifestación', 'bloqueo',
            'toma', 'tomaron', 'ocupación', 'denuncia', 'denunciaron', 'denunció',
            'sanción', 'sancionó', 'multa', 'multó', 'sma sanciona', 'sma multa',
            'tribunal', 'corte suprema', 'corte de apelaciones', 'juzgado',
            'interpuso', 'interpusieron', 'presentó recurso', 'presentaron recurso',
            'se oponen', 'rechazan', 'rechazaron', 'oposición'
        ]
        
        # Si hay acciones contenciosas en el texto, NO excluir automáticamente
        tiene_accion_contenciosa = any(ac in texto_completo for ac in palabras_accion_contenciosa)
        
        # =====================================================================
        # PATRÓN 1: ARTÍCULOS DE ANÁLISIS/OPINIÓN (EXCLUSIÓN SOLO SI NO HAY ACCIÓN)
        # =====================================================================
        patrones_analisis = [
            'luces y sombras', 'luces y sombras del', 'análisis:', 'columna:', 'editorial:',
            'sigue perdiendo', 'pierde competitividad', 'enfrenta desafíos',
            'balance de', 'reflexión sobre', 'una mirada a'
        ]
        # Solo excluir si tiene patrón de análisis Y NO tiene acción contenciosa
        if any(p in texto_completo for p in patrones_analisis) and not tiene_accion_contenciosa:
            logger.info(f"🚫 EXCLUSIÓN AUTOMÁTICA: Artículo de análisis/opinión sin acción contenciosa")
            return {
                'excluir': True,
                'motivo_exclusion': 'Motivo 9: Anuncio sin oposición',
                'explicacion_exclusion': 'Artículo de análisis/opinión sin acción contenciosa específica',
                'tipo_conflicto': None,
                'tipo_accion': None,
                'actor_demandante': None,
                'actor_demandado': None,
                'resumen': None,
                'noticia': contenido,
                'requiere_revision_manual': False,
                'region': None,
                'provincia': None,
                'comuna': None,
                'localidad': None,
                'sector_economico': None,
                'justificacion_transicion': None,
                'notas': None
            }
        
        # =====================================================================
        # PATRÓN 2: AVANCES ADMINISTRATIVOS SIN OPOSICIÓN (EXCLUSIÓN AUTOMÁTICA)
        # =====================================================================
        patrones_acuerdos = [
            'avanza el pacto', 'avanza el acuerdo', 'avanza acuerdo',
            'el detalle de los pagos', 'detalle del acuerdo',
            'autorizan cuota', 'autoriza extracción', 'aprueba acuerdo',
            'ratifica acuerdo', 'firma convenio', 'firman convenio',
            'pacta codelco-sqm', 'acuerdo codelco-sqm', 'pacta codelco',
            'avanza el pacto codelco', 'avanza pacto codelco'
        ]
        # Solo excluir si NO hay acciones contenciosas
        if any(p in texto_completo for p in patrones_acuerdos) and not tiene_accion_contenciosa:
            logger.info(f"🚫 EXCLUSIÓN AUTOMÁTICA: Avance administrativo sin oposición detectado")
            return {
                'excluir': True,
                'motivo_exclusion': 'Motivo 9: Anuncio sin oposición',
                'explicacion_exclusion': 'Avance administrativo o acuerdo sin oposición activa',
                'tipo_conflicto': None,
                'tipo_accion': None,
                'actor_demandante': None,
                'actor_demandado': None,
                'resumen': None,
                'noticia': contenido,
                'requiere_revision_manual': False,
                'region': None,
                'provincia': None,
                'comuna': None,
                'localidad': None,
                'sector_economico': None,
                'justificacion_transicion': None,
                'notas': None
            }
        
        # =====================================================================
        # PATRÓN 3: ANUNCIOS DE INVERSIÓN SIN OPOSICIÓN (EXCLUSIÓN AUTOMÁTICA)
        # =====================================================================
        patrones_inversion = [
            'invertirá us$', 'invertirá usd', 'anuncia inversión',
            'proyecto de inversión', 'millones en proyecto',
            'millones de dólares en', 'nueva planta de',
            'invertirá us$ 600 millones', 'invertirá us$600 millones',
            'invertirá 600 millones', 'us$ 600 millones', 'us$600 millones'
        ]
        # Solo excluir si NO hay acciones contenciosas
        if any(p in texto_completo for p in patrones_inversion) and not tiene_accion_contenciosa:
            logger.info(f"🚫 EXCLUSIÓN AUTOMÁTICA: Anuncio de inversión sin oposición detectado")
            return {
                'excluir': True,
                'motivo_exclusion': 'Motivo 9: Anuncio sin oposición',
                'explicacion_exclusion': 'Anuncio de inversión sin oposición social',
                'tipo_conflicto': None,
                'tipo_accion': None,
                'actor_demandante': None,
                'actor_demandado': None,
                'resumen': None,
                'noticia': contenido,
                'requiere_revision_manual': False,
                'region': None,
                'provincia': None,
                'comuna': None,
                'localidad': None,
                'sector_economico': None,
                'justificacion_transicion': None,
                'notas': None
            }
        
        # No se activa exclusión automática
        return None
    
    def _verificar_alerta_prefiltro(self, titulo: str, contenido: str) -> Optional[str]:
        """
        Detecta patrones sospechosos que requieren revisión manual.
        NO bloquea el análisis de IA, solo retorna una alerta para agregar después.
        
        TRANSVERSAL A TODOS LOS SECTORES:
        - Minería (litio, cobre, oro, plata, hierro)
        - Energía (solar, eólica, hidroeléctrica, termoeléctrica, hidrógeno verde)
        - Agua (derechos de agua, desalación, riego)
        - Forestal (celulosa, plantaciones, incendios)
        - Salmonicultura (pisciculturas, concesiones acuícolas)
        - Infraestructura (puertos, carreteras, líneas de transmisión)
        
        Returns:
            str con la alerta si se detecta patrón sospechoso, None si no.
        """
        texto_completo = f"{titulo} {contenido}".lower()
        
        # =====================================================================
        # PATRONES DE ANÁLISIS/OPINIÓN (transversal a todos los sectores)
        # =====================================================================
        patrones_analisis = [
            # Formato editorial
            'luces y sombras', 'análisis:', 'columna:', 'editorial:', 'opinión:',
            'reflexión sobre', 'una mirada a', 'balance de', 'perspectivas de',
            # Lenguaje de análisis económico
            'sigue perdiendo', 'pierde competitividad', 'enfrenta desafíos',
            'panorama del sector', 'futuro del', 'tendencias en',
            # Preguntas retóricas en títulos
            'por qué el', '¿hacia dónde va', '¿qué pasará con',
            '¿cuál es el futuro', 'el dilema de'
        ]
        
        # =====================================================================
        # PATRONES DE AVANCES ADMINISTRATIVOS/ACUERDOS (transversal)
        # =====================================================================
        patrones_acuerdos = [
            # Avances genéricos
            'avanza el pacto', 'avanza el acuerdo', 'avanza acuerdo',
            'avanza proyecto', 'avanza iniciativa', 'avanza tramitación',
            # Detalles administrativos
            'el detalle de los pagos', 'detalle del acuerdo', 'términos del contrato',
            # Aprobaciones sin oposición
            'autorizan cuota', 'aprueba acuerdo', 'ratifica acuerdo',
            'aprueba proyecto', 'autoriza operación', 'otorga permiso',
            'concede licencia', 'aprueba evaluación', 'resuelve favorablemente',
            # Consultas cerradas
            'consulta indígena ratifica', 'consulta culmina exitosamente',
            'cierra consulta', 'finaliza proceso de consulta'
        ]
        
        # =====================================================================
        # PATRONES DE ANUNCIOS DE INVERSIÓN (transversal a todos los sectores)
        # =====================================================================
        patrones_inversion = [
            # Montos de inversión
            'invertirá us$', 'invertirá usd', 'invertirán us$', 'invertirán usd',
            'inversión de us$', 'inversión de usd', 'millones de dólares',
            'millones en proyecto', 'millones en inversión',
            # Anuncios corporativos
            'anuncia inversión', 'anuncia proyecto', 'anuncia construcción',
            'anuncia ampliación', 'anuncia expansión',
            # Nuevas instalaciones
            'nueva planta de', 'nuevo proyecto de', 'nueva central',
            'nuevo parque eólico', 'nuevo parque solar', 'nueva línea de transmisión',
            # Inauguraciones positivas
            'inaugura planta', 'inaugura proyecto', 'pone en marcha',
            'entra en operación', 'inicia operaciones'
        ]
        
        # =====================================================================
        # PATRONES ESPECÍFICOS POR SECTOR (complementarios)
        # =====================================================================
        patrones_sector_energia = [
            'inauguran parque eólico', 'inauguran parque solar',
            'nueva capacidad instalada', 'megawatts de capacidad',
            'entró en operación comercial', 'generación récord'
        ]
        
        patrones_sector_agua = [
            'inauguran planta desaladora', 'nueva planta de tratamiento',
            'ampliación de embalse', 'mejoras en infraestructura hídrica'
        ]
        
        patrones_sector_forestal = [
            'inauguran planta de celulosa', 'nueva línea de producción',
            'certificación fsc obtenida', 'récord de producción forestal'
        ]
        
        patrones_sector_salmon = [
            'nueva concesión acuícola', 'inauguran centro de cultivo',
            'récord de cosecha', 'expansión de operaciones acuícolas'
        ]
        
        # Combinar patrones sectoriales
        patrones_sectoriales = (patrones_sector_energia + patrones_sector_agua + 
                                patrones_sector_forestal + patrones_sector_salmon)
        
        # =====================================================================
        # DETECCIÓN DE PATRÓN SOSPECHOSO
        # =====================================================================
        patron_detectado = None
        
        if any(p in texto_completo for p in patrones_analisis):
            patron_detectado = "Artículo de análisis/opinión detectado"
        elif any(p in texto_completo for p in patrones_acuerdos):
            patron_detectado = "Avance administrativo/acuerdo detectado"
        elif any(p in texto_completo for p in patrones_inversion):
            patron_detectado = "Anuncio de inversión detectado"
        elif any(p in texto_completo for p in patrones_sectoriales):
            patron_detectado = "Anuncio sectorial positivo detectado"
        
        return patron_detectado
    
    def _crear_prompt_analisis(self, texto: str, noticia: dict) -> str:
        """Crea el prompt para análisis de IA"""
        fecha = noticia.get('Fecha_Extraida_ISO', '') or noticia.get('fecha', '')
        medio = noticia.get('medio', 'N/A')
        titulo = str(noticia.get('titulo', '')).lower()
        
        # =====================================================================
        # SISTEMA DE INYECCIÓN DE PROMPTS CONTEXTUALES
        # Detecta patrones y agrega instrucciones específicas para evitar falsos positivos
        # =====================================================================
        instrucciones_contextuales = self._generar_instrucciones_contextuales(titulo, texto)
        
        # =====================================================================
        # CONSTRUIR PROMPT DINÁMICAMENTE DESDE YAML (SSOT - Single Source of Truth)
        # =====================================================================
        
        # Listas de categorías
        lista_conflictos = '\n'.join([f'- "{t}"' for t in TIPOS_CONFLICTO])
        lista_acciones = '\n'.join([f'- "{t}"' for t in TIPOS_ACCION])
        lista_demandantes = '\n'.join([f'- "{t}"' for t in TIPOS_ACTOR_DEMANDANTE])
        lista_demandados = '\n'.join([f'- "{t}"' for t in TIPOS_ACTOR_DEMANDADO])
        lista_escalas = ' | '.join(ESCALAS_CONFLICTO)
        # Excluir alias dinámicamente usando SECTORES_ALIAS desde YAML
        lista_sectores = ' | '.join([s for s in TIPOS_SECTOR_ECONOMICO.keys() if s not in SECTORES_ALIAS])
        lista_vinculos = ' | '.join(TIPOS_VINCULO_TRANSICION)
        
        # Componentes del prompt desde YAML
        rol = PROMPT_COMPONENTS.get('rol', 'Analista experto en clasificación de conflictos socioambientales.')
        def_transicion = PROMPT_COMPONENTS.get('definicion_transicion', '')
        def_accion = PROMPT_COMPONENTS.get('definicion_accion', '')
        regla_oro = PROMPT_COMPONENTS.get('regla_oro', '')
        validacion_minerales = PROMPT_COMPONENTS.get('validacion_minerales', '')
        anti_bias = PROMPT_COMPONENTS.get('anti_bias', '')
        instrucciones = PROMPT_COMPONENTS.get('instrucciones', '')
        output_excluir = PROMPT_COMPONENTS.get('output_excluir', '{}')
        output_incluir = PROMPT_COMPONENTS.get('output_incluir', '{}')
        negative_constraints = PROMPT_COMPONENTS.get('negative_constraints', '')
        
        # Construir lista de motivos dinámicamente desde YAML
        lista_motivos = '\n'.join([
            f'{m.get("codigo", i+1)}. "{m.get("formato", f"Motivo {i+1}")}"' 
            for i, m in enumerate(MOTIVOS_EXCLUSION)
        ])
        
        return f"""<role>{rol}</role>

<definition name="transicion_energetica">
{def_transicion}
</definition>

<definition name="accion_contenciosa">
{def_accion}
</definition>

<rule name="regla_oro">
{regla_oro}
</rule>

<validation name="minerales_criticos">
{validacion_minerales}
</validation>

<exclusion_motives>
FORMATO OBLIGATORIO: "Motivo X: Nombre"

{lista_motivos}
</exclusion_motives>

<negative_constraints>
{negative_constraints}
</negative_constraints>

<classification_lists>
TIPOS DE CONFLICTO ({len(TIPOS_CONFLICTO)} tipos) - usar nombre EXACTO:
{lista_conflictos}

TIPOS DE ACCIÓN ({len(TIPOS_ACCION)} tipos):
{lista_acciones}

ACTORES DEMANDANTE ({len(TIPOS_ACTOR_DEMANDANTE)} tipos):
{lista_demandantes}

ACTORES DEMANDADO ({len(TIPOS_ACTOR_DEMANDADO)} tipos):
{lista_demandados}

ESCALAS: {lista_escalas}

SECTORES: {lista_sectores}

VÍNCULO TRANSICIÓN: {lista_vinculos}
</classification_lists>

<news>
Medio: {medio}
Fecha de referencia: {fecha}

{texto}
</news>
{instrucciones_contextuales}
<anti_bias>
{anti_bias}
</anti_bias>

<instructions>
{instrucciones}
</instructions>

<output_format>
Si EXCLUIR:
{output_excluir}

Si INCLUIR:
{output_incluir}
</output_format>"""
    
    def _extraer_json(self, texto: str) -> str:
        """Extrae JSON de texto con markdown"""
        texto = re.sub(r'```json\s*', '', texto)
        texto = re.sub(r'```\s*', '', texto)
        
        inicio = texto.find('{')
        fin = texto.rfind('}')
        
        if inicio != -1 and fin != -1 and fin > inicio:
            return texto[inicio:fin+1]
        
        return texto
    
    def _parsear_json_seguro(self, texto: str) -> dict:
        """Parsea JSON con múltiples estrategias"""
        # Estrategia 1: Directo
        try:
            return json.loads(texto)
        except:
            pass
        
        # Estrategia 2: Limpiar espacios
        try:
            texto_limpio = re.sub(r'\s+', ' ', texto)
            return json.loads(texto_limpio)
        except:
            pass
        
        # Estrategia 3: Reparar comillas
        try:
            texto_reparado = texto.replace("'", '"')
            return json.loads(texto_reparado)
        except:
            pass
        
        # Estrategia 4: Extracción manual
        resultado = {}
        
        match_excluir = re.search(r'"excluir"\s*:\s*(true|false)', texto, re.IGNORECASE)
        if match_excluir:
            resultado['excluir'] = match_excluir.group(1).lower() == 'true'
        
        for campo in ['motivo_exclusion', 'tipo_conflicto', 'tipo_accion', 
                      'actor_demandante', 'actor_demandado', 'resumen']:
            match = re.search(rf'"{campo}"\s*:\s*"([^"]*)"', texto)
            resultado[campo] = match.group(1) if match else None
        
        if resultado:
            return resultado
        
        raise json.JSONDecodeError("No se pudo parsear JSON", texto, 0)
    
    def _validar_con_pydantic(self, resultado: dict) -> dict:
        """
        Valida la respuesta de IA usando Pydantic (si está disponible).
        Retorna el diccionario validado o lanza ValidationError.
        """
        if not PYDANTIC_AVAILABLE:
            return resultado  # Fallback a validación manual
        
        try:
            if resultado.get('excluir'):
                modelo = ClasificacionExcluida.model_validate(resultado)
            else:
                modelo = ClasificacionIncluida.model_validate(resultado)
            
            # Log del razonamiento para debugging
            if modelo.razonamiento_paso_a_paso:
                logger.debug(f"CoT: {modelo.razonamiento_paso_a_paso[:100]}...")
            
            return modelo.model_dump()
        except ValidationError as e:
            logger.warning(f"Validación Pydantic falló: {e.error_count()} errores")
            for error in e.errors():
                logger.debug(f"  - {error['loc']}: {error['msg']}")
            # Re-lanzar para manejo superior
            raise
    
    def _validar_clasificacion(self, resultado: dict) -> dict:
        """Valida tipos de clasificación"""
        if resultado.get('excluir'):
            return resultado
        
        tipos_invalidos = []
        
        tipo_conflicto = resultado.get('tipo_conflicto')
        if tipo_conflicto and tipo_conflicto not in TIPOS_CONFLICTO:
            # Usar clase MapeoTipos centralizada
            tipo_mapeado, fue_mapeado = MapeoTipos.mapear_conflicto(tipo_conflicto)
            
            if fue_mapeado:
                logger.info(f"Mapeando conflicto '{tipo_conflicto}' → '{tipo_mapeado}'")
                resultado['tipo_conflicto'] = tipo_mapeado
            else:
                logger.warning(f"Tipo conflicto inválido: {tipo_conflicto}")
                tipos_invalidos.append(f"conflicto '{tipo_conflicto}'")
                resultado['tipo_conflicto'] = None
                resultado['requiere_revision_manual'] = True
        
        tipo_accion = resultado.get('tipo_accion')
        if tipo_accion and tipo_accion not in TIPOS_ACCION:
            # Usar clase MapeoTipos centralizada
            tipo_mapeado, fue_mapeado, es_exclusion = MapeoTipos.mapear_accion(tipo_accion)
            
            if fue_mapeado:
                if es_exclusion:
                    # Caso especial: "Malestar sin acción" → Exclusión Motivo 7
                    logger.warning(f"Acción '{tipo_accion}' indica exclusión por Motivo 7")
                    resultado['excluir'] = True
                    resultado['motivo_exclusion'] = 'Motivo 7: Malestar sin acción'
                    resultado['explicacion_exclusion'] = 'No hay acción contenciosa específica'
                    return resultado
                else:
                    logger.info(f"Mapeando acción '{tipo_accion}' → '{tipo_mapeado}'")
                    resultado['tipo_accion'] = tipo_mapeado
            else:
                logger.warning(f"Tipo acción inválido: {tipo_accion}")
                tipos_invalidos.append(f"acción '{tipo_accion}'")
                resultado['tipo_accion'] = None
                resultado['requiere_revision_manual'] = True
        
        actor_demandante = resultado.get('actor_demandante')
        if actor_demandante and actor_demandante not in TIPOS_ACTOR_DEMANDANTE:
            # Usar clase MapeoTipos centralizada
            tipo_mapeado, fue_mapeado = MapeoTipos.mapear_demandante(actor_demandante)
            
            if fue_mapeado:
                logger.info(f"Mapeando demandante '{actor_demandante}' → '{tipo_mapeado}'")
                resultado['actor_demandante'] = tipo_mapeado
            else:
                logger.warning(f"Actor demandante inválido: {actor_demandante}")
                tipos_invalidos.append(f"demandante '{actor_demandante}'")
                resultado['actor_demandante'] = None
                resultado['requiere_revision_manual'] = True
        
        actor_demandado = resultado.get('actor_demandado')
        if actor_demandado and actor_demandado not in TIPOS_ACTOR_DEMANDADO:
            # Usar clase MapeoTipos centralizada
            tipo_mapeado, fue_mapeado, requiere_revision = MapeoTipos.mapear_demandado(actor_demandado)
            
            if fue_mapeado:
                if requiere_revision:
                    # Caso especial: "Múltiple" → Revisión manual
                    logger.warning(f"Actor demandado '{actor_demandado}' no válido - requiere actor principal específico")
                    tipos_invalidos.append(f"demandado '{actor_demandado}' (usar actor principal)")
                    resultado['actor_demandado'] = None
                    resultado['requiere_revision_manual'] = True
                    if not resultado.get('notas'):
                        resultado['notas'] = 'Múltiples demandados: elegir actor principal'
                else:
                    logger.info(f"Mapeando demandado '{actor_demandado}' → '{tipo_mapeado}'")
                    resultado['actor_demandado'] = tipo_mapeado
            else:
                logger.warning(f"Actor demandado inválido: {actor_demandado}")
                tipos_invalidos.append(f"demandado '{actor_demandado}'")
                resultado['actor_demandado'] = None
                resultado['requiere_revision_manual'] = True
        
        # Agregar nota si hay tipos inválidos
        if tipos_invalidos:
            nota_tipos = f"Tipos no reconocidos: {', '.join(tipos_invalidos)}"
            # Si ya hay nota, concatenar
            if resultado.get('notas'):
                resultado['notas'] = f"{resultado['notas']}; {nota_tipos}"
            else:
                resultado['notas'] = nota_tipos
        
        return resultado
    
    def _validar_coherencia(self, resultado: dict) -> dict:
        """Valida coherencia lógica - ULTRA RIGUROSO para evitar falsos positivos"""
        if not resultado.get('excluir'):
            # CRÍTICO: Si falta actor_demandado → EXCLUIR (no es conflicto real)
            if not resultado.get('actor_demandado'):
                logger.warning("⚠️ EXCLUIR: Falta actor_demandado - no hay contra quién se dirija la acción")
                resultado['excluir'] = True
                resultado['motivo_exclusion'] = 'Motivo 7: Malestar sin acción'
                resultado['explicacion_exclusion'] = 'No hay actor demandado identificable contra quien se dirija la acción'
                resultado['notas'] = None
                return resultado
            
            # CRÍTICO: Si falta actor_demandante → EXCLUIR
            if not resultado.get('actor_demandante'):
                logger.warning("⚠️ EXCLUIR: Falta actor_demandante - no hay quién realice la acción")
                resultado['excluir'] = True
                resultado['motivo_exclusion'] = 'Motivo 7: Malestar sin acción'
                resultado['explicacion_exclusion'] = 'No hay actor demandante identificable que realice la acción'
                resultado['notas'] = None
                return resultado
            
            # Validar campos obligatorios restantes (tipo_conflicto, tipo_accion)
            for campo in ['tipo_conflicto', 'tipo_accion']:
                if not resultado.get(campo):
                    logger.warning(f"Falta {campo} en noticia incluida")
                    resultado['requiere_revision_manual'] = True
            
            # CRÍTICO: Validar justificacion_transicion
            justificacion = resultado.get('justificacion_transicion', '').strip()
            if not justificacion:
                logger.warning("⚠️ Noticia incluida SIN justificación de transición energética - EXCLUIR")
                resultado['excluir'] = True
                resultado['motivo_exclusion'] = 'Motivo 3: No conflicto'
                resultado['explicacion_exclusion'] = 'IA no pudo justificar relación con transición energética'
                resultado['notas'] = None  # No agregar notas a noticias excluidas
                return resultado
            
            # Validar longitud mínima de justificación (al menos 40 caracteres para ser específica)
            if len(justificacion) < 40:
                logger.warning(f"⚠️ Justificación muy breve ({len(justificacion)} chars): {justificacion}")
                resultado['requiere_revision_manual'] = True
                nota_adicional = f'Justificación muy breve ({len(justificacion)} chars), requiere validación'
                if resultado.get('notas'):
                    resultado['notas'] = f"{resultado['notas']}; {nota_adicional}"
                else:
                    resultado['notas'] = nota_adicional
        
        # Validar sector económico con lista dinámica desde config
        SECTORES_VALIDOS = list(TIPOS_SECTOR_ECONOMICO.keys())
        sector_economico = resultado.get('sector_economico')
        if sector_economico and sector_economico not in SECTORES_VALIDOS:
            # Usar MapeoTipos centralizado para normalizar sectores
            sector_mapeado, fue_mapeado = MapeoTipos.mapear_sector(sector_economico)
            if fue_mapeado:
                logger.info(f"Mapeando sector '{sector_economico}' → '{sector_mapeado}'")
                resultado['sector_economico'] = sector_mapeado
            else:
                logger.warning(f"Sector económico no válido: {sector_economico}")
                resultado['sector_economico'] = None
        
        return resultado
    
    def _normalizar_resultado(self, resultado: dict) -> dict:
        """Normaliza y completa el resultado"""
        # Normalizar región (usando clase externa MapeoRegion)
        if resultado.get('region'):
            region_norm = MapeoRegion.normalizar(resultado['region'], REGIONES_CHILE)
            if region_norm:
                resultado['region'] = region_norm
        
        # Asegurar campos requeridos
        resultado.setdefault('requiere_revision_manual', False)
        
        # Si no tiene el campo 'excluir', es un error
        if 'excluir' not in resultado:
            logger.error(f"Resultado sin campo 'excluir': {resultado}")
            resultado['excluir'] = True
            resultado['motivo_exclusion'] = 'Motivo 13: Error de procesamiento - falta campo excluir'
            resultado['requiere_revision_manual'] = True
            resultado['notas'] = None  # No agregar notas a noticias excluidas
            return resultado
        
        # Si se excluye pero no tiene motivo, asignar error
        if resultado.get('excluir') is True and not resultado.get('motivo_exclusion'):
            logger.warning("Noticia excluida sin motivo_exclusion")
            resultado['motivo_exclusion'] = 'Motivo 13: Error de procesamiento - falta motivo'
            resultado['requiere_revision_manual'] = True
            resultado['notas'] = None  # No agregar notas a noticias excluidas
        
        # Si NO se excluye, limpiar motivo_exclusion y validar justificacion_transicion
        if resultado.get('excluir') is False:
            resultado['motivo_exclusion'] = None
            
            # Asegurar que justificacion_transicion existe
            if 'justificacion_transicion' not in resultado or not resultado.get('justificacion_transicion'):
                logger.warning("Noticia incluida sin justificacion_transicion - agregando nota")
                resultado['justificacion_transicion'] = 'Sin justificación proporcionada'
                resultado['requiere_revision_manual'] = True
                if not resultado.get('notas'):
                    resultado['notas'] = 'Falta justificación de vínculo con transición energética'
        else:
            # Si se excluye, limpiar justificacion_transicion
            resultado['justificacion_transicion'] = None
        
        # CRÍTICO: Si requiere revisión manual pero no tiene notas, agregar nota genérica
        # SOLO para noticias INCLUIDAS (excluir=false)
        if resultado.get('requiere_revision_manual') and not resultado.get('notas') and not resultado.get('excluir'):
            # Intentar inferir razón basado en campos faltantes
            razones = []
            for campo in ['tipo_conflicto', 'tipo_accion', 'actor_demandante', 'actor_demandado']:
                if not resultado.get(campo):
                    razones.append(f"falta {campo}")
            
            if razones:
                resultado['notas'] = f"Revisión requerida: {', '.join(razones)}"
            else:
                resultado['notas'] = 'Requiere validación manual - verificar clasificación'
            
            logger.info(f"Nota automática agregada: {resultado['notas']}")
        
        # Limpiar notas de noticias excluidas
        if resultado.get('excluir'):
            resultado['notas'] = None
        
        return resultado
    
    def _validar_fecha(self, fecha: str) -> bool:
        """Valida que la fecha esté en rango razonable"""
        if not fecha:
            return True
        
        try:
            fecha_dt = pd.to_datetime(fecha)
            hoy = pd.Timestamp.now()
            
            # Solo validar que no sea fecha futura (BBDD tiene noticias desde años 90)
            if fecha_dt.year > hoy.year + 1:
                return False
            
            return True
        except:
            return False
    
    def _resultado_error(self, mensaje: str) -> dict:
        """Retorna estructura de error"""
        return {
            'excluir': True,
            'motivo_exclusion': 'Motivo 13: Error de procesamiento',
            'explicacion_exclusion': mensaje,
            'requiere_revision_manual': True,
            'tipo_conflicto': None,
            'tipo_accion': None,
            'actor_demandante': None,
            'actor_demandado': None,
            'resumen': None,
            'region': None,
            'provincia': None,
            'comuna': None,
            'localidad': None,
            'sector_economico': None,
            'justificacion_transicion': None,
            'notas': None
        }
