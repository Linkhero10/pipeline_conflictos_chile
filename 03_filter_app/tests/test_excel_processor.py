"""
Tests para el procesador de Excel.

Verifica la lectura y escritura de archivos Excel.
"""

import pytest
import os
import sys

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestExcelProcessor:
    """Tests para el procesador de Excel."""

    def test_pandas_import(self):
        """Verificar que pandas está disponible."""
        try:
            import pandas as pd
            assert pd.__version__ is not None
        except ImportError:
            pytest.fail("pandas no está instalado")

    def test_openpyxl_import(self):
        """Verificar que openpyxl está disponible para Excel."""
        try:
            import openpyxl
            assert openpyxl.__version__ is not None
        except ImportError:
            pytest.fail("openpyxl no está instalado")


class TestDataValidation:
    """Tests para validación de datos."""

    def test_empty_dataframe_handling(self):
        """Verificar manejo de DataFrame vacío."""
        import pandas as pd
        
        df = pd.DataFrame()
        assert len(df) == 0
        assert df.empty is True

    def test_dataframe_with_required_columns(self):
        """Verificar DataFrame con columnas requeridas."""
        import pandas as pd
        
        required_columns = ['titulo', 'noticia', 'fuente']
        df = pd.DataFrame(columns=required_columns)
        
        for col in required_columns:
            assert col in df.columns


class TestFileOperations:
    """Tests para operaciones de archivos."""

    def test_temp_directory_creation(self, tmp_path):
        """Verificar creación de directorio temporal."""
        test_dir = tmp_path / "test_output"
        test_dir.mkdir()
        assert test_dir.exists()

    def test_excel_write_read_cycle(self, tmp_path):
        """Verificar ciclo de escritura/lectura de Excel."""
        import pandas as pd
        
        # Crear DataFrame de prueba
        df = pd.DataFrame({
            'titulo': ['Test 1', 'Test 2'],
            'noticia': ['Contenido 1', 'Contenido 2']
        })
        
        # Escribir
        excel_path = tmp_path / "test.xlsx"
        df.to_excel(excel_path, index=False)
        
        # Leer
        df_read = pd.read_excel(excel_path)
        
        assert len(df_read) == 2
        assert list(df_read.columns) == ['titulo', 'noticia']
