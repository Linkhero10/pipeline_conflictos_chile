# Arquitectura V4.0 - Nivel AI Architect

## Resumen de Evolución

| Versión | Nivel | Características |
|---------|-------|-----------------|
| v1.0 | Script básico | Hardcoded, sin validación |
| v2.0 | Script mejorado | Mapeos, logs básicos |
| v3.0 | Ingeniero de Datos | YAML SSOT, modularización |
| **v4.0** | **AI Architect** | Pydantic, Tenacity, CoT, Evaluación, Observabilidad |

---

## Componentes Implementados

### 1. Validación con Pydantic

**Archivo:** `filtrador_analisis1.py`

```python
from pydantic import BaseModel, Field, field_validator

class ClasificacionIncluida(BaseModel):
    tipo_conflicto: str
    justificacion_transicion: Optional[str] = Field(None, min_length=40)
    
    @field_validator('justificacion_transicion')
    def validar_justificacion(cls, v, info):
        if not info.data.get('excluir') and (not v or len(v) < 40):
            raise ValueError('mínimo 40 caracteres')
        return v
```

**Beneficio:** La IA está obligada a cumplir un contrato de datos. Si alucina, el código lo rechaza.

### 2. Reintentos con Tenacity

**Archivo:** `filtrador_analisis1.py`

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30)
)
def _llamar_api_tenacity(self, prompt):
    return self._llamar_api_simple(prompt)
```

**Beneficio:** Si la API falla (timeout, 503, etc.), el código espera y reintenta automáticamente.

### 3. Chain of Thought Mejorado

**Archivo:** `clasificaciones.yaml`

```yaml
output_incluir: |
    {
        "razonamiento_paso_a_paso": "1. ACTORES: Identifiqué a [X] contra [Y]. 
                                     2. ACCIÓN: [Acción] (es contenciosa porque...). 
                                     3. VÍNCULO: Transición por [Razón]. 
                                     4. CATEGORIZACIÓN: Es [Tipo] y NO [Otro] porque [Diferencia].",
        ...
    }
```

**Beneficio:** Forzar "Es X y NO Y porque..." reduce alucinaciones taxonómicas.

### 4. Sistema de Evaluación (Golden Dataset)

**Archivo:** `evaluador_golden.py`

```python
evaluador = EvaluadorGolden(api_key)

# Generar gold standard con modelo premium
evaluador.generar_golden_dataset(noticias, modelo='claude-opus')

# Evaluar modelo de producción
resultado = evaluador.evaluar_modelo()
evaluador.imprimir_resumen()
```

**Output:**

```
📊 RESUMEN DE EVALUACIÓN
Modelo evaluado: gemini-2.5-flash
Gold Standard:   claude-opus
✅ Accuracy Global: 92.5%
Por campo:
   excluir                    95.0%
   tipo_conflicto             88.0%
   tipo_accion                90.0%
```

### 5. Observabilidad y Métricas

**Archivo:** `observabilidad.py`

```python
from .observabilidad import tracker

with tracker.track_llamada(modelo='gemini-flash', noticia_id=123) as ctx:
    resultado = api.generate(...)
    ctx.set_tokens(1000, 500)
    ctx.set_resultado(resultado['excluir'])

tracker.imprimir_resumen()
```

**Output:**

```
📊 MÉTRICAS DE OBSERVABILIDAD
📞 Total llamadas:     1,500
   ✅ Exitosas:        1,485
   ❌ Fallidas:        15
📰 Noticias:
   ✅ Incluidas:       312
   ❌ Excluidas:       1,173
🎯 Rendimiento:
   Latencia promedio:  850 ms
   💰 Costo estimado:  $0.45
```

---

## Límites de OpenRouter

| Tipo | Límite |
|------|--------|
| Modelos `:free` | 20 req/min, 50-1000 req/día |
| Modelos pagos | Sin límite explícito (DDoS protection) |
| **Recomendación** | 10-20 requests concurrentes máximo |

---

## Próximos Pasos para Nivel "ML Engineer"

### A. Async para Velocidad (Prioridad Media)

```python
import asyncio
import aiohttp

async def analizar_batch(noticias: List[dict], max_concurrent: int = 10):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def analizar_una(noticia):
        async with semaphore:
            return await self._llamar_api_async(noticia)
    
    return await asyncio.gather(*[analizar_una(n) for n in noticias])
```

**Impacto:** De 5 horas → 30 minutos para 10,000 noticias

### B. Integración con LangSmith/W&B (Prioridad Baja)

```python
from langsmith import Client
client = Client()

with client.trace("clasificar_noticia") as trace:
    resultado = analizar_noticia(noticia)
    trace.log_output(resultado)
```

**Beneficio:** Dashboard visual de costos, latencia, errores

### C. Fine-tuning del Modelo (Futuro)

Si el Golden Dataset crece a 200+ ejemplos, considerar fine-tuning de un modelo más pequeño (Gemma, Llama) para reducir costos.

---

## Estructura de Archivos V4

```
src/core/
├── clasificaciones.yaml      # SSOT - Definiciones y prompt
├── config_loader.py          # Carga YAML (Fail Fast)
├── ai_classifier.py          # Análisis IA (Pydantic + Tenacity)
├── mapeos_clasificacion.py   # Mapeos de tipos
├── observabilidad.py         # Métricas y tracking
├── excel_processor.py        # Procesamiento de Excel
├── stats_generator.py        # Generación de estadísticas
├── pipeline_orchestrator.py  # Orquestación principal
├── core_utils.py             # Utilidades
└── reprocesamiento.py        # Re-análisis de noticias
```

---

## Columnas del Excel de Salida

### Datos Principales

| Columna | Descripción |
|---------|-------------|
| `id_noticia` | Identificador único |
| `fecha` | Fecha de la noticia |
| `titulo` | Título de la noticia |
| `fuente` | Medio de comunicación |
| `noticia` | Contenido completo |
| `resumen` | Resumen generado por IA |
| `link_noticia` | URL de la noticia |

### Clasificación

| Columna | Descripción |
|---------|-------------|
| `excluir` | True/False - Si fue excluida |
| `motivo_exclusion` | Motivo si fue excluida |
| `tipo_conflicto` | Categoría del conflicto |
| `tipo_accion` | Tipo de acción contenciosa |
| `actor_demandante` | Quién protesta/demanda |
| `actor_demandado` | Contra quién |
| `sector_economico` | Sector económico afectado |
| `justificacion_transicion` | Vínculo con transición energética |

### Geografía

| Columna | Descripción |
|---------|-------------|
| `region` | Región de Chile |
| `provincia` | Provincia |
| `comuna` | Comuna |
| `localidad` | Localidad específica |

### Métricas de IA ⭐ NUEVO

| Columna | Descripción |
|---------|-------------|
| `tokens_input` | Tokens enviados a la API |
| `tokens_output` | Tokens recibidos |
| `tokens_totales` | Total de tokens |
| `latencia_ms` | Tiempo de respuesta en ms |
| `modelo_usado` | Modelo de IA utilizado |
| `costo_estimado_usd` | Costo estimado en USD |

---

## Comandos Útiles

```bash
# Verificar sintaxis
python -m py_compile filtrador_analisis.py

# Ejecutar evaluación
python -c "
from src.core.evaluador_golden import EvaluadorGolden
import os
evaluador = EvaluadorGolden(os.getenv('OPENROUTER_API_KEY'))
# evaluador.generar_golden_dataset(noticias, modelo='claude-opus')
"

# Ver métricas de observabilidad
python -c "
from src.core.observabilidad import tracker
tracker.imprimir_resumen()
"
```

---

## Dependencias Adicionales

```bash
pip install pydantic tenacity
# Opcionales para observabilidad avanzada:
# pip install langsmith wandb arize-phoenix
```

---

## Autor

Sistema desarrollado para proyecto FONDECYT - Análisis de Conflictos Socioambientales en Transición Energética
