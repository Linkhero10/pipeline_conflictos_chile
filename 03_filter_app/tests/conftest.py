"""
Fixtures compartidas para tests del pipeline de filtrado.
"""

import pytest
import sys
import os

# Agregar src al path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def sample_news_article() -> dict:
    """Fixture con un articulo de noticia de ejemplo."""
    return {
        'id_noticia': 1,
        'titulo': 'Comunidad de Quintero denuncia contaminacion por termoeléctrica',
        'noticia': 'Los habitantes de la zona de sacrificio de Quintero-Puchuncaví '
                   'denunciaron ante el Tribunal Ambiental la contaminación producida '
                   'por las termoeléctricas de la zona. La comunidad exige el cierre '
                   'de las plantas y la reparación del daño ambiental.',
        'fuente': 'La Tercera',
        'fecha': '2024-01-15',
        'enlace': 'https://example.com/noticia/1'
    }


@pytest.fixture
def sample_excluded_article() -> dict:
    """Fixture con un articulo que deberia ser excluido."""
    return {
        'id_noticia': 2,
        'titulo': 'Inauguran nuevo parque solar en Atacama sin incidentes',
        'noticia': 'El Presidente inauguró un nuevo parque solar de 100MW en el '
                   'desierto de Atacama. La ceremonia contó con la presencia de '
                   'autoridades locales y representantes de la empresa.',
        'fuente': 'Emol',
        'fecha': '2024-02-20',
        'enlace': 'https://example.com/noticia/2'
    }


@pytest.fixture
def mock_api_response_included() -> dict:
    """Fixture con una respuesta de API para noticia incluida."""
    return {
        'excluir': False,
        'tipo_conflicto': 'Contaminación por diversas industrias',
        'tipo_accion': 'Recurso judicial',
        'actor_demandante': 'Comunidades locales',
        'actor_demandado': 'Empresas privadas',
        'sector_economico': 'Energía',
        'region': 'Valparaíso',
        'comuna': 'Quintero',
        'justificacion_transicion': 'El conflicto se vincula con la transición energética '
                                    'debido a las demandas por cierre de termoeléctricas.',
        'resumen': 'Comunidad denuncia contaminación por termoeléctricas.'
    }


@pytest.fixture
def mock_api_response_excluded() -> dict:
    """Fixture con una respuesta de API para noticia excluida."""
    return {
        'excluir': True,
        'motivo_exclusion': 'No hay acción contenciosa'
    }


@pytest.fixture
def valid_classification_config() -> dict:
    """Fixture con configuración de clasificación válida."""
    return {
        'tipos_conflicto': [
            'Apertura/Operación de proyecto energético',
            'Contaminación por diversas industrias',
            'Conflicto por minerales críticos'
        ],
        'tipos_accion': [
            'Recurso judicial',
            'Protesta',
            'Denuncia a autoridades'
        ],
        'actores_demandantes': [
            'Comunidades locales',
            'ONGs ambientales',
            'Pueblos originarios'
        ]
    }
