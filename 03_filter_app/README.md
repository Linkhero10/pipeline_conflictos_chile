# Filtrador FONDECYT - Análisis de Conflictos Socioambientales

Sistema inteligente de filtrado de noticias usando IA para identificar conflictos socioambientales relacionados con la transición energética en Chile.

## Inicio Rápido

### 1. Instalación

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd 03_filter_app

# Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración

1. Copia el archivo de ejemplo de configuración:

   ```bash
   copy .env.example .env
   ```

2. Edita `.env` y agrega tu API Key:

   ```
   OPENROUTER_API_KEY=sk-or-v1-tu-clave-aqui
   ```

   Obtener API Key: Regístrate en [OpenRouter.ai](https://openrouter.ai/) para obtener créditos gratuitos.

### 3. Ejecutar la Aplicación

**Opción A - Doble clic (Windows):**
Ejecuta `iniciar_aplicacion.bat`

**Opción B - Terminal:**

```bash
python main.py
```

## Características

- **Análisis con IA**: Clasifica automáticamente noticias usando modelos como Gemini 2.5 Flash
- **Validación con Pydantic**: Garantiza la calidad de las respuestas de la IA
- **Reintentos automáticos**: Usa Tenacity para manejar errores de API
- **Interfaz gráfica**: Aplicación Tkinter fácil de usar
- **Generación de mapas**: Visualiza conflictos geográficamente

## Estructura del Proyecto

```
03_filter_app/
├── iniciar_aplicacion.bat   # Script de inicio (Windows)
├── main.py                  # Punto de entrada
├── requirements.txt         # Dependencias
├── .env.example             # Plantilla de configuración
├── src/
│   ├── core/                # Lógica de negocio
│   │   ├── ai_classifier.py # Motor de IA
│   │   ├── pipeline_orchestrator.py
│   │   └── ...
│   └── ui/                  # Interfaz gráfica
│       ├── app.py
│       └── tabs/
```

## Seguridad

- No suba su archivo `.env` a GitHub
- El archivo `.gitignore` ya está configurado para excluirlo
- Use `.env.example` como plantilla para otros usuarios

## Salida

El sistema genera archivos Excel con:

- Noticias classificadas (incluidas/excluidas)
- Tipo de conflicto
- Actores involucrados
- Ubicación geográfica
- Métricas de la IA (tokens, latencia, costo)

## Licencia

Este software está protegido por derechos de autor. Consulte el archivo `LICENSE.md` en la raíz del repositorio.

Para licencias comerciales, contactar: <felipeams2002@gmail.com>
