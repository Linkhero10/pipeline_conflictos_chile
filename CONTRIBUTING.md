# Guía de Contribución

Gracias por tu interés en contribuir a este proyecto.

## Configuración del Entorno de Desarrollo

1. Clona el repositorio:

   ```bash
   git clone https://github.com/Linkhero10/pipeline_conflictos_chile.git
   cd pipeline_conflictos_chile
   ```

2. Crea un entorno virtual:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Instala las dependencias:

   ```bash
   cd 03_filter_app
   pip install -r requirements.txt
   ```

4. Ejecuta los tests:

   ```bash
   python -m pytest tests/ -v
   ```

## Estilo de Código

- Sigue las guías de estilo PEP 8
- Usa type hints para parámetros y valores de retorno
- Agrega docstrings a todas las funciones y clases públicas
- Longitud máxima de línea: 120 caracteres

## Testing

Todas las nuevas funcionalidades deben incluir tests. Ejecuta la suite de tests antes de enviar cambios:

```bash
python -m pytest tests/ -v --tb=short
```

## Estructura del Proyecto

```
pipeline_conflictos_chile/
├── 01_scraping/          # Fase 1: Web scraping de Google News
├── 02_enrichment/        # Fase 2: Enriquecimiento de URLs
├── 03_filter_app/        # Fase 3: Clasificación con IA
│   ├── src/
│   │   ├── core/         # Lógica de negocio
│   │   └── ui/           # Interfaz gráfica
│   └── tests/            # Tests automatizados
└── 04_interactive_map/   # Fase 4: Mapa interactivo
```

## Pull Requests

1. Haz fork del repositorio
2. Crea una rama para tu feature (`git checkout -b mi-nueva-feature`)
3. Realiza tus cambios
4. Ejecuta los tests
5. Envía un pull request

## Convenciones de Commits

Usa mensajes de commit descriptivos:

- `feat: Agregar nueva funcionalidad X`
- `fix: Corregir error en Y`
- `refactor: Reorganizar código de Z`
- `test: Agregar tests para W`
- `docs: Actualizar documentación`

## Licencia

Al contribuir, aceptas que tus contribuciones estarán sujetas a la licencia del proyecto.
Consulta LICENSE.md para más detalles.

## Contacto

Para preguntas sobre licencias comerciales o uso empresarial, contacta a: <felipeams2002@gmail.com>
