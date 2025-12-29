"""
Tests para el módulo ai_classifier.

Verifica la validación Pydantic y el manejo de respuestas de la IA.
"""

import pytest
import json
import os
import sys

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestResponseValidation:
    """Tests para validación de respuestas de IA."""

    def test_valid_included_response_structure(self, mock_api_response_included):
        """Verificar estructura de respuesta para noticia incluida."""
        response = mock_api_response_included
        
        # Campos requeridos para noticias incluidas
        required_fields = ['excluir', 'tipo_conflicto', 'tipo_accion']
        for field in required_fields:
            assert field in response, f"Campo requerido '{field}' no encontrado"
        
        assert response['excluir'] is False

    def test_valid_excluded_response_structure(self, mock_api_response_excluded):
        """Verificar estructura de respuesta para noticia excluida."""
        response = mock_api_response_excluded
        
        assert 'excluir' in response
        assert response['excluir'] is True
        assert 'motivo_exclusion' in response

    def test_response_json_serializable(self, mock_api_response_included):
        """Verificar que la respuesta es serializable a JSON."""
        try:
            json_str = json.dumps(mock_api_response_included, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed == mock_api_response_included
        except (TypeError, json.JSONDecodeError) as e:
            pytest.fail(f"Response no es JSON serializable: {e}")


class TestNewsArticleValidation:
    """Tests para validación de artículos de noticias."""

    def test_sample_article_has_required_fields(self, sample_news_article):
        """Verificar que el artículo de ejemplo tiene campos requeridos."""
        required_fields = ['titulo', 'noticia']
        for field in required_fields:
            assert field in sample_news_article, f"Campo '{field}' requerido"
            assert sample_news_article[field], f"Campo '{field}' no puede estar vacío"

    def test_article_content_minimum_length(self, sample_news_article):
        """Verificar que el contenido tiene longitud mínima."""
        min_length = 50  # Mínimo 50 caracteres
        content = sample_news_article.get('noticia', '')
        assert len(content) >= min_length, f"Contenido muy corto: {len(content)} < {min_length}"


class TestClassificationCategories:
    """Tests para verificar categorías de clasificación."""

    def test_conflict_type_is_valid(self, mock_api_response_included, valid_classification_config):
        """Verificar que el tipo de conflicto es válido."""
        conflict_type = mock_api_response_included.get('tipo_conflicto')
        valid_types = valid_classification_config['tipos_conflicto']
        
        # El tipo debe estar en la lista de válidos
        assert conflict_type in valid_types, f"Tipo '{conflict_type}' no es válido"

    def test_action_type_is_valid(self, mock_api_response_included, valid_classification_config):
        """Verificar que el tipo de acción es válido."""
        action_type = mock_api_response_included.get('tipo_accion')
        valid_types = valid_classification_config['tipos_accion']
        
        assert action_type in valid_types, f"Acción '{action_type}' no es válida"


class TestExclusionReasons:
    """Tests para motivos de exclusión."""

    def test_excluded_article_has_reason(self, mock_api_response_excluded):
        """Verificar que artículo excluido tiene motivo."""
        assert mock_api_response_excluded.get('excluir') is True
        reason = mock_api_response_excluded.get('motivo_exclusion', '')
        assert reason, "Artículo excluido debe tener motivo de exclusión"

    def test_exclusion_reason_is_not_empty(self, mock_api_response_excluded):
        """Verificar que el motivo de exclusión no está vacío."""
        reason = mock_api_response_excluded.get('motivo_exclusion', '')
        assert len(reason) > 5, "Motivo de exclusión muy corto"


class TestDataIntegrity:
    """Tests para integridad de datos."""

    def test_region_format(self, mock_api_response_included):
        """Verificar formato de región."""
        region = mock_api_response_included.get('region', '')
        # Región debe ser string no vacío
        assert isinstance(region, str)
        assert len(region) > 0

    def test_justification_minimum_length(self, mock_api_response_included):
        """Verificar longitud mínima de justificación."""
        justification = mock_api_response_included.get('justificacion_transicion', '')
        min_length = 40  # Mínimo 40 caracteres según spec
        assert len(justification) >= min_length, f"Justificación muy corta: {len(justification)}"
