"""
Tests para el módulo config_loader.

Verifica la carga correcta de configuración YAML y validación de campos.
"""

import pytest
import os
import sys

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestConfigLoader:
    """Tests para la carga de configuración."""

    def test_yaml_file_exists(self):
        """Verificar que el archivo clasificaciones.yaml existe."""
        yaml_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'src', 'core', 'clasificaciones.yaml'
        )
        assert os.path.exists(yaml_path), "clasificaciones.yaml no encontrado"

    def test_yaml_is_valid(self):
        """Verificar que el YAML es válido y puede ser parseado."""
        import yaml
        
        yaml_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'src', 'core', 'clasificaciones.yaml'
        )
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None
                assert isinstance(config, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"Error parseando YAML: {e}")

    def test_required_sections_exist(self):
        """Verificar que las secciones requeridas existen en el YAML."""
        import yaml
        
        yaml_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'src', 'core', 'clasificaciones.yaml'
        )
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Verificar secciones principales
        required_sections = ['tipos_conflicto', 'tipos_accion']
        for section in required_sections:
            assert section in config, f"Sección '{section}' no encontrada en YAML"


class TestEnvironmentConfig:
    """Tests para la configuración de entorno."""
    
    def test_env_example_exists(self):
        """Verificar que .env.example existe."""
        env_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '.env.example'
        )
        assert os.path.exists(env_path), ".env.example no encontrado"
    
    def test_env_example_has_api_key_placeholder(self):
        """Verificar que .env.example tiene placeholder para API key."""
        env_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '.env.example'
        )
        
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'OPENROUTER_API_KEY' in content, "OPENROUTER_API_KEY no está en .env.example"


class TestRequirements:
    """Tests para verificar dependencias."""
    
    def test_requirements_exists(self):
        """Verificar que requirements.txt existe."""
        req_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'requirements.txt'
        )
        assert os.path.exists(req_path), "requirements.txt no encontrado"
    
    def test_critical_dependencies_listed(self):
        """Verificar que las dependencias críticas están listadas."""
        req_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'requirements.txt'
        )
        
        with open(req_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        critical_deps = ['pandas', 'pydantic', 'tenacity', 'openai']
        for dep in critical_deps:
            assert dep in content, f"Dependencia crítica '{dep}' no está en requirements.txt"
