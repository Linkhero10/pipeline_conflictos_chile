# Fase 4: Mapa Interactivo de Conflictos

## Objetivo

Generar un mapa interactivo de conflictos socioambientales en Chile que permita visualizar geográficamente la distribución de los casos clasificados, con filtros por tipo de conflicto, actores y período temporal.

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `generador_mapas.py` | Generador principal con múltiples capas, estilos y configuraciones |
| `mapa_interactivo.py` | Configuración y personalización del mapa |
| `generar_mapa_real.py` | Script de ejecución para generar el mapa final |

---

## Input

El mapa se genera a partir del archivo Excel filtrado de la Fase 3:

- `conflictos_transicion_energetica_filtrado.xlsx`
- Hoja: "Datos_filtrados" (conflictos válidos clasificados)

### Campos Utilizados

| Campo | Uso en el Mapa |
|-------|----------------|
| `region` | Ubicación geográfica (coordenadas) |
| `comuna` | Ubicación más precisa |
| `tipo_conflicto` | Color y capa del marcador |
| `tipo_accion` | Información en popup |
| `actor_demandante` | Información en popup |
| `actor_demandado` | Información en popup |
| `titulo` | Título en popup |
| `fuente` | Fuente en popup |
| `fecha` | Fecha en popup |
| `justificacion_transicion` | Descripción en popup |

---

## Características del Mapa

### Capas por Tipo de Conflicto

El mapa organiza los conflictos en capas separadas que se pueden activar/desactivar:

| Capa | Color | Tipos de Conflicto |
|------|-------|-------------------|
| Termoeléctricas | Rojo | Carbón, gas natural, zonas de sacrificio |
| Hidroeléctricas | Azul | Represas, centrales de pasada |
| Minería | Naranja | Cobre, litio, minerales críticos |
| Solar | Amarillo | Plantas fotovoltaicas, CSP |
| Eólica | Verde claro | Parques eólicos |
| Hidrógeno Verde | Verde oscuro | Proyectos H2V |
| Transmisión | Púrpura | Líneas de alta tensión |
| Hídricos | Celeste | Conflictos por agua |
| Otros | Gris | Sin clasificar |

### Tipos de Marcadores

- **CircleMarker**: Círculos de radio fijo (más rápido)
- **Marker con ícono**: Íconos personalizados por tipo
- **Clusters**: Agrupación automática al hacer zoom out

### Popups Informativos

Cada marcador incluye un popup con:

```html
<div class="popup-content">
    <h4>{título}</h4>
    <p><b>Tipo:</b> {tipo_conflicto}</p>
    <p><b>Acción:</b> {tipo_accion}</p>
    <p><b>Demandante:</b> {actor_demandante}</p>
    <p><b>Demandado:</b> {actor_demandado}</p>
    <p><b>Fuente:</b> {fuente}</p>
    <p><b>Fecha:</b> {fecha}</p>
    <p>{justificacion}</p>
    <a href="{url}" target="_blank">Ver noticia</a>
</div>
```

### Controles Interactivos

- **LayerControl**: Activar/desactivar capas por tipo
- **Zoom**: Navegación con scroll
- **Búsqueda**: Buscar por ubicación (opcional)
- **Fullscreen**: Modo pantalla completa
- **MiniMap**: Mapa de referencia en esquina

---

## Geocodificación

Las noticias se geolocalizan usando:

1. **Comunas de Chile**: Base de datos de coordenadas por comuna
2. **Regiones**: Centroide regional si no hay comuna
3. **Patrones en texto**: Extracción de topónimos del contenido

```python
# Ejemplo de coordenadas por comuna
COMUNAS_CHILE = {
    "Quintero": (-32.7667, -71.5333),
    "Puchuncaví": (-32.7167, -71.4167),
    "San Pedro de Atacama": (-22.9083, -68.2000),
    "Toconao": (-23.1833, -68.0000),
    # ... más de 300 comunas
}
```

---

## Ejecución

### Modo Simple

```bash
cd 04_interactive_map
python generar_mapa_real.py
```

### Con Parámetros

```bash
python generar_mapa_real.py --input ../datos_filtrados.xlsx --output mapa.html --cluster
```

### Parámetros Disponibles

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--input` | Archivo Excel de entrada | Auto-detectado |
| `--output` | Archivo HTML de salida | `mapa_conflictos_interactivo.html` |
| `--cluster` | Activar clustering de marcadores | False |
| `--heatmap` | Agregar capa de calor | False |
| `--no-layers` | Sin control de capas | False |

---

## Output

- **Archivo**: `mapa_conflictos_interactivo.html`
- **Tamaño**: Variable (puede superar 100 MB con muchos puntos)
- **Formato**: HTML autocontenido (no requiere servidor)

### Visualización

Abrir directamente en navegador:

```bash
# Windows
start mapa_conflictos_interactivo.html

# Linux/Mac
open mapa_conflictos_interactivo.html
```

O servir localmente:

```bash
python -m http.server 8000
# Abrir http://localhost:8000/mapa_conflictos_interactivo.html
```

---

## Personalización

### Cambiar Estilo Base del Mapa

```python
# En generador_mapas.py
TILE_LAYERS = {
    "CartoDB Positron": "cartodbpositron",  # Claro, minimalista
    "CartoDB Dark": "cartodbdark_matter",   # Oscuro
    "OpenStreetMap": "openstreetmap",        # Detallado
    "Stamen Terrain": "Stamen Terrain",      # Relieve
}
```

### Cambiar Colores por Tipo

```python
COLORES_CONFLICTO = {
    "termoeléctrica": "#e74c3c",    # Rojo
    "hidroeléctrica": "#3498db",     # Azul
    "minería": "#f39c12",            # Naranja
    "solar": "#f1c40f",              # Amarillo
    "eólica": "#2ecc71",             # Verde claro
    "hidrógeno": "#27ae60",          # Verde oscuro
    "transmisión": "#9b59b6",        # Púrpura
    "hídrico": "#1abc9c",            # Turquesa
    "otro": "#95a5a6",               # Gris
}
```

### Agregar Capas Adicionales

```python
# Ejemplo: Agregar capa de áreas protegidas
geojson_snaspe = "https://url/snaspe.geojson"
folium.GeoJson(geojson_snaspe, name="Áreas Protegidas").add_to(mapa)
```

---

## Dependencias

```bash
pip install pandas folium branca openpyxl
```

### Dependencias Opcionales

```bash
# Para mapas de calor
pip install folium[heatmap]

# Para clustering avanzado
pip install folium-markercluster

# Para exportar como imagen
pip install selenium
```

---

## Notas Técnicas

### Rendimiento

- **< 1,000 puntos**: Carga instantánea
- **1,000 - 5,000 puntos**: Recomendado usar clustering
- **> 5,000 puntos**: Considerar simplificar o dividir por período

### Compatibilidad

- Chrome, Firefox, Edge, Safari (modernos)
- Funciona offline (HTML autocontenido)
- Responsive (adaptable a móvil)

### Tamaño del Archivo

El HTML puede ser grande porque incluye:

- Datos de cada punto (título, popup, etc.)
- Librería Leaflet embebida
- Estilos CSS
- JavaScript de interactividad

Para reducir tamaño:

```python
# Comprimir tooltips
popup_content = titulo[:100]  # Truncar a 100 caracteres
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| Mapa no carga | Verificar que el HTML tiene datos |
| Puntos en ubicación incorrecta | Revisar coordenadas de comunas |
| Muy lento | Activar clustering, reducir puntos |
| Popups no se ven | Verificar campos en Excel |

