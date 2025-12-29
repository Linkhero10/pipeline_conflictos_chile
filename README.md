# Pipeline de Construcción de Base de Datos de Conflictos Socioambientales

Sistema completo para la recolección, enriquecimiento, clasificación y visualización de noticias sobre conflictos socioambientales vinculados a la transición energética en Chile.

## Introducción

Este repositorio contiene el código desarrollado para la construcción automatizada de una base de datos de noticias sobre conflictos socioambientales en Chile. El sistema implementa cuatro fases secuenciales que transforman búsquedas de palabras clave en Google News en una base de datos estructurada, clasificada y visualizada geográficamente.

---

## Arquitectura del Sistema

```
PIPELINE COMPLETO
─────────────────────────────────────────────────────────────────────────────

  FASE 1: SCRAPING (Local)
  01_scraping/
  ├── scraper_main.py        - Scraping de Google News Chile
  ├── search_keywords.py     - 461 keywords de búsqueda booleana
  └── database_handler.py    - Gestión de base de datos Excel
        │
        ▼  Output: Excel hoja "Datos" (~25,000 noticias)

  FASE 2: ENRICHMENT (Google Colab)
  02_enrichment/
  ├── url_resolver.py        - Resolución URLs + Extracción contenido
  ├── colab_coordinator.py   - Coordinador multi-worker
  └── cache_recovery.py      - Recuperación de caché SQLite
        │
        ▼  Output: Excel hoja "Datos_enriquecidos"

  FASE 3: FILTRADO CON IA (Local)
  03_filter_app/
  ├── main.py                - Aplicación de escritorio (Tkinter)
  ├── src/core/ai_classifier.py - Clasificación con Gemini 2.5 Flash
  └── src/core/clasificaciones.yaml - Categorías de clasificación
        │
        ▼  Output: Excel filtrado (~3,000 noticias clasificadas)

  FASE 4: VISUALIZACIÓN
  04_interactive_map/
  ├── map_engine.py          - Motor de generación de mapas Folium
  ├── map_config.py          - Configuración del mapa
  └── map_generator.py       - Script de ejecución
        │
        ▼  Output: mapa_conflictos_interactivo.html

─────────────────────────────────────────────────────────────────────────────
```

---

## Fase 1: Web Scraping de Google News

### Objetivo

Definir combinaciones de palabras clave que capturen conflictos socioambientales vinculados a la transición energética en Chile, y ejecutar el scraping de Google News para obtener los metadatos de las noticias.

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `scraper_main.py` | Script principal de scraping con Selenium |
| `search_keywords.py` | 461 combinaciones de búsqueda booleana |
| `database_handler.py` | Gestión centralizada de datos (Excel, CSV, JSON) |

### Diseño de Keywords

El archivo `search_keywords.py` contiene **461 combinaciones de búsqueda booleana** organizadas en categorías temáticas.

**Distribución de Keywords por Categoría:**

| Categoría | Cantidad |
|-----------|----------|
| Litio (Salares y comunidades atacameñas) | 12 |
| Termoeléctricas (Zonas de sacrificio) | 27 |
| Hidroeléctricas (Ríos y cuencas) | 42 |
| Minería de cobre (Valles y comunidades) | 32 |
| Energía solar (Desierto de Atacama) | 13 |
| Energía eólica (Costa y cordillera) | 27 |
| Hidrógeno verde | 13 |
| Geotermia | 12 |
| Transmisión eléctrica | 14 |
| Pueblos originarios | 14 |
| Actores (Empresas, ONGs, Comunidades) | 49 |
| Otros (institucionales, eventos, cuencas, etc.) | 246 |
| **TOTAL** | **461** |

### Ejecución

```bash
cd 01_scraping
python scraper_main.py
```

**Output:** `conflictos_transicion_energetica.xlsx` (hoja "Datos")

### Dependencias

```bash
pip install selenium undetected-chromedriver webdriver-manager pandas openpyxl
```

---

## Fase 2: Enriquecimiento de URLs (Google Colab)

### Objetivo

Convertir las URLs encriptadas de Google News a URLs reales y extraer el contenido completo de cada noticia. Esta fase se ejecuta en **Google Colab** porque cada sesión utiliza una IP diferente, evitando bloqueos.

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `url_resolver.py` | Script principal de enriquecimiento |
| `colab_coordinator.py` | Coordinador para múltiples instancias de Colab |
| `cache_recovery.py` | Recuperación de URLs desde caché SQLite |

### Ejecución en Google Colab

El procesamiento se realiza en **tandas de 500 noticias** para evitar límites de Google News.

```python
# CELDA 1: CONFIGURACIÓN INICIAL
from google.colab import drive
drive.mount('/content/drive')
!pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser -q
!cp "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx" /content/datos.xlsx
!cp "/content/drive/MyDrive/scraper/url_resolver.py" /content/

# CELDA 2: EJECUTAR TANDA (filas 1-500)
!python /content/url_resolver.py --excel /content/datos.xlsx --start-from 1 --limit 500

# GUARDAR
!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
```

### Dependencias (se instalan en Colab)

```bash
pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser
```

---

## Fase 3: Filtrado con Inteligencia Artificial

### Objetivo

Clasificar automáticamente cada noticia según criterios metodológicos, determinando si corresponde a un conflicto socioambiental vinculado a la transición energética.

### Aplicación de Escritorio

El filtrado se realiza mediante una aplicación de escritorio con interfaz Tkinter ubicada en `03_filter_app/`.

### Modelo de IA

El sistema utiliza **Gemini 2.5 Flash** vía OpenRouter. Configurar API Key en `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-tu-api-key-aqui
```

### Ejecución

```bash
cd 03_filter_app
pip install -r requirements.txt
python main.py
```

En Windows, también puede ejecutarse con: `iniciar_aplicacion.bat`

### Archivos de Salida

El archivo de salida (`*_filtrado.xlsx`) contiene hojas: `Datos_completos`, `Datos_filtrados`, `Datos_excluidos`, `Revision_manual`, `Contenido_Manual`.

---

## Fase 4: Mapa Interactivo

### Objetivo

Generar un mapa interactivo de calor que visualiza la distribución geográfica de los conflictos socioambientales en Chile.

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `map_engine.py` | Motor principal de generación con múltiples niveles (regiones, provincias, comunas) |
| `map_config.py` | Configuración y estilos del mapa |
| `map_generator.py` | Script de ejecución |

### Ejecución

```bash
cd 04_interactive_map
python map_generator.py <ruta_al_excel_filtrado>
```

**Output:** `mapa_conflictos_interactivo.html`

### Dependencias

```bash
pip install pandas folium
```

---

## Resultados Esperados

| Fase | Input | Output | Cantidad |
|------|-------|--------|----------|
| 1. Scraping | 461 keywords | Excel "Datos" | ~25,000 noticias |
| 2. Enrichment | URLs Google News | Excel "Datos_enriquecidos" | ~25,000 + metadatos |
| 3. Filtrado | Noticias enriquecidas | Excel filtrado | ~3,000 clasificadas |
| 4. Mapa | Noticias clasificadas | HTML interactivo | 1 mapa web |

---

## Estructura del Repositorio

```
pipeline_conflictos_chile/
├── 01_scraping/
│   ├── scraper_main.py
│   ├── search_keywords.py
│   ├── database_handler.py
│   └── README.md
├── 02_enrichment/
│   ├── url_resolver.py
│   ├── colab_coordinator.py
│   ├── cache_recovery.py
│   └── README.md
├── 03_filter_app/
│   ├── main.py
│   ├── iniciar_aplicacion.bat
│   ├── requirements.txt
│   ├── src/
│   │   ├── core/
│   │   └── ui/
│   └── README.md
├── 04_interactive_map/
│   ├── map_engine.py
│   ├── map_config.py
│   ├── map_generator.py
│   └── README.md
├── data/
│   └── geojson/
├── .gitignore
├── LICENSE.md
└── README.md
```

---

## Instalación Rápida

```bash
# Clonar repositorio
git clone <url-del-repo>
cd pipeline_conflictos_chile

# Para Fase 3 (Filtrado con IA)
cd 03_filter_app
pip install -r requirements.txt
copy .env.example .env   # Agregar API Key
python main.py
```

---

## Datos

Los archivos Excel con los datos procesados están disponibles en la sección **Releases** de este repositorio debido a su tamaño.

---

## Licencia

Este software está protegido por derechos de autor. Consulte el archivo `LICENSE.md` para más información.

Para licencias comerciales, contactar: <felipeams2002@gmail.com>

---

## Contexto del Proyecto

Proyecto desarrollado en el marco de investigación FONDECYT sobre análisis de conflictos socioambientales vinculados a la transición energética en Chile.

Universidad de Chile
