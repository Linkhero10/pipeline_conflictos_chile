# Contributing to Pipeline Conflictos Chile

Thank you for your interest in contributing to this project.

## Development Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/Linkhero10/pipeline_conflictos_chile.git
   cd pipeline_conflictos_chile
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:

   ```bash
   cd 03_filter_app
   pip install -r requirements.txt
   ```

4. Run tests:

   ```bash
   python -m pytest tests/ -v
   ```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Add docstrings to all public functions and classes
- Maximum line length: 120 characters

## Testing

All new features should include tests. Run the test suite before submitting changes:

```bash
python -m pytest tests/ -v --tb=short
```

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

By contributing, you agree that your contributions will be subject to the project's license.
See LICENSE.md for details.

## Contact

For questions about licensing or commercial use, contact: <felipeams2002@gmail.com>
