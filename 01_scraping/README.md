# Fase 1: Web Scraping de Google News

## Objetivo

Definir combinaciones de palabras clave que capturen conflictos socioambientales vinculados a la transición energética en Chile, y ejecutar el scraping de Google News para obtener los metadatos de las noticias relevantes.

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `scraper.py` | Script principal de scraping con Selenium |
| `keywords_transicion.py` | 461 combinaciones de búsqueda booleana |
| `database_manager.py` | Gestión centralizada de datos (Excel, CSV, JSON) |

---

## Diseño de Keywords

El archivo `keywords_transicion.py` contiene **461 combinaciones de búsqueda booleana** organizadas en categorías temáticas.

### Estructura de las Queries

Las búsquedas combinan tres elementos fundamentales:

1. **Tipo de proyecto o industria**: litio, termoeléctrica, hidroeléctrica, parque eólico
2. **Localidades específicas afectadas**: comunas, provincias, localidades
3. **Términos de conflicto**: contaminación, cierre, rechaza, denuncia, demanda, multa

### Constantes de Conflicto

```python
# Constante básica (5 términos más frecuentes en títulos reales)
CONF = '(contaminación OR cierre OR rechaza OR denuncia OR conflicto)'

# Constante extendida (incluye acciones legales)
CONF_FULL = '(contaminación OR cierre OR rechaza OR denuncia OR demanda OR multa OR daño OR conflicto OR protesta OR tribunal OR ordena OR sanciona)'

# Alerta/riesgo
ALERTA = '(amenaza OR alerta OR riesgo OR crisis OR emergencia)'

# Acción legal
LEGAL = '(tribunal ambiental OR recurso de protección OR demanda OR SMA OR SEA OR fallo OR multa)'
```

### Ejemplo de Query

```python
# Litio + Localidad + Conflicto
'"litio" AND (\"San Pedro de Atacama\" OR \"Toconao\" OR \"Peine\") AND agua'

# Termoeléctrica + Zona de sacrificio
'"zona de sacrificio" AND (\"Quintero\" OR \"Puchuncaví\")'

# Hidroeléctrica + Cuenca específica
'"HidroAysén" AND (\"Cochrane\" OR \"Chile Chico\" OR \"Puerto Aysén\")'
```

### Distribución por Categorías

| Categoría | Keywords | Descripción |
|-----------|----------|-------------|
| Litio | 12 | Salares y comunidades atacameñas |
| Termoeléctricas | 27 | Zonas de sacrificio (Quintero, Tocopilla, Mejillones) |
| Hidroeléctricas | 42 | Ríos y cuencas (HidroAysén, Alto Maipo, Ralco) |
| Minería de cobre | 32 | Valles y comunidades (Dominga, Pascua Lama, Pelambres) |
| Energía solar | 13 | Desierto de Atacama |
| Energía eólica | 27 | Costa y cordillera |
| Hidrógeno verde | 13 | Puertos y zonas estratégicas (Magallanes) |
| Baterías/Almacenamiento | 6 | Sistemas de almacenamiento energético |
| Biocombustibles | 4 | Biodiésel, bioetanol, biomasa |
| Electromovilidad | 5 | Transporte eléctrico |
| Geotermia | 12 | Cordillera (Tolhuaca, Cerro Pabellón) |
| Transmisión | 14 | Líneas de alta tensión (Cardones-Polpaico) |
| Puertos energéticos | 6 | GNL, hidrógeno verde |
| Redes inteligentes | 4 | Smart grid, medidores |
| Generación distribuida | 5 | Paneles solares, net billing |
| Descarbonización | 5 | Cierre de termoeléctricas |
| Transición justa | 6 | Reconversión laboral |
| Eficiencia energética | 3 | Aislación, etiquetado |
| Comunidades energéticas | 4 | Cooperativas, autoconsumo |
| Áreas protegidas | 10 | Parques nacionales, reservas |
| Pueblos originarios | 14 | Mapuche, atacameños, diaguitas |
| Institucional | 28 | SEIA, tribunales, SMA |
| Cuencas críticas | 12 | Copiapó, Huasco, Elqui |
| Glaciares | 10 | Protección glaciar |
| Bofedales | 5 | Humedales altoandinos |
| Patrimonio | 7 | Sitios arqueológicos |
| Actores | 49 | Empresas, ONGs, comunidades |
| Eventos | 32 | Política pública, desastres |
| **TOTAL** | **461** | |

### Categorías Excluidas

Durante la depuración se eliminaron categorías NO vinculadas a transición energética:

-  Agropecuaria (purines, planteles porcinos/avícolas)
-  Forestal-Celulosa (sin componente energético)
-  Acuicultura (salmonicultura)
-  Portuaria tradicional (no energética)
-  Inmobiliarios
-  Vertederos
-  Áridos

---

## Funcionamiento Técnico del Scraper

El script `scraper.py` implementa la clase `EnhancedTemporalScraper` con las siguientes características:

### Configuración del Driver

4 estrategias de fallback para maximizar compatibilidad:

```python
# 1. Ruta directa al chromedriver
direct_path = r"C:\Users\...\chromedriver.exe"

# 2. undetected-chromedriver (anti-detección)
uc.Chrome(options=options, version_main=131)

# 3. webdriver-manager (descarga automática)
ChromeDriverManager().install()

# 4. Configuración mínima
webdriver.Chrome(options=options)
```

### Rotación de User-Agents

7 User-Agents diferentes que rotan cada 10 queries:

```python
self.user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    # ... 5 más
]
```

### Sistema de Pausas

- **Entre queries**: 4-8 segundos (aleatorio)
- **Cada 10 queries**: 15-25 segundos (pausa extendida)
- **Guardado incremental**: Cada 50 queries

### Scroll Infinito

Para cada búsqueda, el script ejecuta scroll hasta que no aparezcan más artículos:

```python
# Máximo 200 scrolls como límite de seguridad
max_scrolls = 200
```

### Detección de CAPTCHA

El sistema detecta patrones de CAPTCHA y aplica backoff exponencial:

```python
if "unusual traffic" in page_source or "captcha" in page_source.lower():
    wait_time = 60 * (2 ** retry_count)  # Backoff exponencial
```

---

## Datos Extraídos

Por cada noticia encontrada, se almacenan los siguientes campos:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `id_noticia` | Identificador único secuencial | 1, 2, 3... |
| `titulo` | Título de la noticia | "Conflicto por proyecto..." |
| `descripcion` | Descripción breve de Google News | Extracto del artículo |
| `fuente` | Medio de comunicación | "La Tercera", "Cooperativa" |
| `fecha_scraping` | Fecha y hora de extracción | "2025-01-15 14:30:00" |
| `enlace` | URL de Google News (encriptada) | "<https://news.google.com/read/>..." |
| `query_original` | Keyword que encontró la noticia | '"litio" AND "Atacama"' |
| `periodo_scraping` | Identificador del período | "2025_S1" |
| `content_hash` | Hash MD5 (título+URL) | "a1b2c3d4..." |

---

## Deduplicación

El sistema implementa deduplicación mediante hash MD5:

```python
import hashlib
content_hash = hashlib.md5(f"{titulo}{url}".encode('utf-8')).hexdigest()

if content_hash not in existing_hashes:
    # Agregar noticia
    existing_hashes.add(content_hash)
```

---

## Ejecución

```bash
cd 01_scraping
python scraper.py
```

### Parámetros Opcionales

El scraper puede configurarse editando las variables al inicio del script:

```python
# Modo headless (sin ventana visible)
headless = True

# Cantidad máxima de scrolls por query
max_scrolls = 200

# Tiempo entre queries (segundos)
delay_min, delay_max = 4, 8

# Guardado incremental cada N queries
save_frequency = 50
```

---

## Output

- **Archivo**: `conflictos_transicion_energetica.xlsx`
- **Hoja**: "Datos"
- **Cantidad esperada**: ~25,000 noticias (dependiendo de período y keywords)

---

## Dependencias

```bash
pip install selenium undetected-chromedriver webdriver-manager pandas openpyxl
```

### Software Adicional

- **Google Chrome**: Versión compatible con chromedriver
- **chromedriver**: Se descarga automáticamente con webdriver-manager

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| CAPTCHA frecuentes | Aumentar pausas, usar headless=False |
| Driver no inicia | Actualizar Chrome, verificar ruta |
| Pocos resultados | Verificar que las queries retornan en Google News |
| Duplicados | Normal, se eliminan con content_hash |

