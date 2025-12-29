# Fase 2: Enriquecimiento de URLs (Google Colab)

## Objetivo

Convertir las URLs encriptadas de Google News a URLs reales y extraer el contenido completo de cada noticia. Esta fase se ejecuta en **Google Colab** porque cada sesión utiliza una IP diferente, lo que permite evitar bloqueos por parte de Google News.

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `codigo_final.py` | Script principal de enriquecimiento (resolución URLs + extracción contenido) |
| `sistema_colab_coordinado.py` | Coordinador para distribuir trabajo entre múltiples instancias de Colab |
| `recuperar_urls_cache.py` | Recuperación de URLs desde caché SQLite en caso de interrupción |

---

## Problema de las URLs de Google News

Las URLs obtenidas en Fase 1 tienen formatos encriptados:

```
https://news.google.com/read/CBMiXWh0dHBzOi8vd3d3Lm...
https://news.google.com/rss/articles/CBMiYWh0dHBzOi8...
```

Estas URLs no permiten acceso directo al contenido del artículo. El script `codigo_final.py` las resuelve a sus destinos finales (ej: `https://www.emol.com/noticias/...`).

## Estrategias de Resolución

El script utiliza múltiples métodos en orden de prioridad:

1. **googlenewsdecoder** - Librería especializada en decodificar URLs de Google News
2. **Decodificación Base64** - Extracción de URL desde tokens CBM/CAE
3. **RSS Feed** - Resolución vía feed RSS de Google News
4. **Seguimiento de redirecciones HTTP** - Fallback básico

## Extracción de Contenido

Una vez resuelta la URL, se extrae el contenido con:

1. **trafilatura** - Extractor especializado en contenido web (prioridad)
2. **newspaper3k** - Librería alternativa para artículos

---

## Columnas Añadidas al Excel

El script agrega la hoja "Datos_enriquecidos" con las siguientes columnas:

| Campo | Descripción |
|-------|-------------|
| `URL_Directa` | URL real del artículo (resuelta) |
| `Metodo_Resolucion` | Método usado: gnewsdecoder, redirect, rss, base64 |
| `Titulo_Extraido` | Título extraído desde la página real |
| `Contenido_Completo` | Texto completo del artículo |
| `Autor` | Autor del artículo (si está disponible) |
| `Fecha_Extraida_ISO` | Fecha de publicación en formato ISO |
| `Palabras` | Conteo de palabras del contenido |
| `Estado_Procesamiento` | exitoso, sin_contenido, url_no_resuelta |
| `Hash_Contenido` | MD5 del contenido para deduplicación |
| `Fuente_Dominio` | Dominio del sitio (ej: emol.com, biobiochile.cl) |

---

## Ejecución en Google Colab

### Preparación

1. Subir archivos a Google Drive:
   - `conflictos_transicion_energetica.xlsx` (de Fase 1)
   - `codigo_final.py`

2. Crear un nuevo notebook en [Google Colab](https://colab.research.google.com/)

### Celda 1: Configuración Inicial

```python
# Montar Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Instalar dependencias (silencioso)
!pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser -q

# Copiar archivos de Drive a memoria local (más rápido que trabajar directamente en Drive)
!cp "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx" /content/datos.xlsx
!cp "/content/drive/MyDrive/scraper/codigo_final.py" /content/
print(" Listo")
```

### Celda 2: Ejecutar Tanda (500 noticias)

```python
# TANDA 1: Filas 1-500
# Ajustar --start-from según el progreso actual
!python /content/codigo_final.py --excel /content/datos.xlsx --start-from 1 --limit 500 --save-frequency 50 --use-cache

# Guardar progreso a Drive
!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
print(" Tanda 1 guardada")
```

### Celda 3: Segunda Tanda (misma sesión)

```python
# TANDA 2: Filas 501-1000
!python /content/codigo_final.py --excel /content/datos.xlsx --start-from 501 --limit 500 --save-frequency 50 --use-cache

!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
print(" Tanda 2 guardada")
```

### Celda 4: Tercera Tanda (opcional)

```python
# TANDA 3: Filas 1001-1500
!python /content/codigo_final.py --excel /content/datos.xlsx --start-from 1001 --limit 500 --save-frequency 50 --use-cache

!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
print(" Tanda 3 guardada")
```

### Celda de Verificación

```python
# Verificar progreso actual
import pandas as pd
df = pd.read_excel('/content/datos.xlsx', sheet_name='Datos_enriquecidos')

# Ver las últimas filas procesadas
print(f"Total filas: {len(df)}")
print(f"Filas con URL_Directa: {df['URL_Directa'].notna().sum()}")

# Verificar filas específicas (ajustar rango)
print("\nVerificación filas 501-504:")
for i in range(500, 504):
    url = df.iloc[i].get('URL_Directa', 'NO EXISTE')
    estado = df.iloc[i].get('Estado_Procesamiento', 'N/A')
    print(f"  Fila {i+1}: Estado={estado}, URL={str(url)[:60]}...")
```

---

## Ejemplo Completo de Sesión

Una sesión típica procesa 2-3 tandas de 500 noticias:

```python
# CELDA 1: SETUP
from google.colab import drive
drive.mount('/content/drive')
!pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser -q
!cp "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx" /content/datos.xlsx
!cp "/content/drive/MyDrive/scraper/codigo_final.py" /content/
print(" Listo")

# CELDA 2: TANDA 11 (ejemplo: filas 17597-18096)
!python /content/codigo_final.py --excel /content/datos.xlsx --start-from 17597 --limit 500 --save-frequency 50 --use-cache
!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
print(" Tanda 11 guardada")

# CELDA 3: TANDA 12 (filas 18097-18596)
!python /content/codigo_final.py --excel /content/datos.xlsx --start-from 18097 --limit 500 --save-frequency 50 --use-cache
!cp /content/datos.xlsx "/content/drive/MyDrive/scraper/conflictos_transicion_energetica.xlsx"
print(" Tanda 12 guardada")

# CELDA 4: VERIFICACIÓN
import pandas as pd
df = pd.read_excel('/content/datos.xlsx', sheet_name='Datos_enriquecidos')

print("Filas 17597-17600:")
for i in range(17596, 17600):
    url = df.iloc[i].get('URL_Directa', 'NO EXISTE')
    print(f"  Fila {i+1}: URL_Directa = '{url}'")
```

---

## Parámetros del Script

| Parámetro | Descripción | Valor Recomendado |
|-----------|-------------|-------------------|
| `--excel` | Archivo Excel de entrada/salida | datos.xlsx |
| `--start-from` | Fila desde donde comenzar (1-indexed) | Según progreso |
| `--limit` | Cantidad de filas a procesar por tanda | 500 |
| `--save-frequency` | Guardar progreso cada N filas | 50 |
| `--use-cache` | Usar caché SQLite para evitar reprocesar | Siempre activar |
| `--workers` | Número de workers paralelos | 1 (recomendado) |

---

## Recomendaciones

1. **Tandas de 500**: Evita límites y timeouts de Google News
2. **Guardar después de cada tanda**: `!cp` al Drive previene pérdida de datos
3. **Nueva sesión = nueva IP**: Si hay bloqueos, reconectar el runtime
4. **Verificar progreso**: Revisar que las URLs se están resolviendo correctamente
5. **Backup antes de continuar**: El script sobrescribe el Excel

---

## Uso con Múltiples Colabs Simultáneos

Para acelerar el proceso, se puede usar `sistema_colab_coordinado.py` que distribuye el trabajo:

```python
# En Colab 1:
!python sistema_colab_coordinado.py --worker-id 1

# En Colab 2:
!python sistema_colab_coordinado.py --worker-id 2

# Ver estadísticas:
!python sistema_colab_coordinado.py --stats

# Fusionar resultados al final:
!python sistema_colab_coordinado.py --merge
```

Cada worker procesa un rango fijo de filas y guarda en archivo separado para evitar conflictos.

---

## Dependencias

```bash
pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| URLs no resueltas | Reconectar runtime (nueva IP) |
| Timeout frecuentes | Reducir `--limit` a 250 |
| Caché corrupto | Eliminar `news_enrichment_cache.db` |
| Excel no se guarda | Verificar permisos en Drive |

