"""
Tests for processing controller and results manager.

Tests the extracted UI components for processing and results handling.
"""

import pytest
import os
import sys
from datetime import timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestProcessingController:
    """Tests for the processing controller."""

    def test_format_time_delta_seconds(self):
        """Test formatting timedelta with seconds only."""
        from ui.processing_controller import format_time_delta
        
        td = timedelta(seconds=45)
        result = format_time_delta(td)
        assert result == "45s"

    def test_format_time_delta_minutes(self):
        """Test formatting timedelta with minutes."""
        from ui.processing_controller import format_time_delta
        
        td = timedelta(minutes=5, seconds=30)
        result = format_time_delta(td)
        assert result == "5m 30s"

    def test_format_time_delta_hours(self):
        """Test formatting timedelta with hours."""
        from ui.processing_controller import format_time_delta
        
        td = timedelta(hours=2, minutes=15, seconds=45)
        result = format_time_delta(td)
        assert result == "2h 15m 45s"

    def test_validate_processing_config_valid(self, tmp_path):
        """Test validation with valid config."""
        from ui.processing_controller import validate_processing_config
        
        # Create temp file
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")
        
        is_valid, msg = validate_processing_config(
            excel_path=str(test_file),
            api_key="sk-test-key-1234567890",
            start_index=0,
            end_index=100
        )
        
        assert is_valid
        assert msg == ""

    def test_validate_processing_config_missing_file(self):
        """Test validation with missing file."""
        from ui.processing_controller import validate_processing_config
        
        is_valid, msg = validate_processing_config(
            excel_path="/nonexistent/file.xlsx",
            api_key="sk-test-key-1234567890",
            start_index=0,
            end_index=100
        )
        
        assert not is_valid
        assert "no encontrado" in msg.lower()

    def test_validate_processing_config_invalid_api_key(self, tmp_path):
        """Test validation with invalid API key."""
        from ui.processing_controller import validate_processing_config
        
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")
        
        is_valid, msg = validate_processing_config(
            excel_path=str(test_file),
            api_key="short",
            start_index=0,
            end_index=100
        )
        
        assert not is_valid
        assert "api" in msg.lower()

    def test_validate_processing_config_invalid_range(self, tmp_path):
        """Test validation with invalid index range."""
        from ui.processing_controller import validate_processing_config
        
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")
        
        is_valid, msg = validate_processing_config(
            excel_path=str(test_file),
            api_key="sk-test-key-1234567890",
            start_index=100,
            end_index=50  # End < Start
        )
        
        assert not is_valid
        assert "mayor" in msg.lower()


class TestResultsManager:
    """Tests for the results manager."""

    def test_results_manager_init(self):
        """Test ResultsManager initialization."""
        from ui.results_manager import ResultsManager
        
        manager = ResultsManager()
        
        assert manager.df_all is None
        assert manager.df_filtered is None
        assert manager.current_file is None
        assert manager.available_sheets == []

    def test_get_column_display_mapping(self):
        """Test column display mapping."""
        from ui.results_manager import get_column_display_mapping
        
        mapping = get_column_display_mapping()
        
        assert 'titulo' in mapping
        assert mapping['titulo'] == 'Título'
        assert 'region' in mapping
        assert 'tipo_conflicto' in mapping

    def test_format_article_for_display(self):
        """Test article formatting."""
        from ui.results_manager import format_article_for_display
        
        article = {
            'titulo': 'Test Article',
            'tipo_conflicto': 'Contaminación',
            'region': 'Valparaíso',
            'enlace': 'https://example.com'
        }
        
        result = format_article_for_display(article)
        
        assert 'Test Article' in result
        assert 'Contaminación' in result
        assert 'Valparaíso' in result
        assert 'https://example.com' in result


class TestUIStyles:
    """Tests for UI styles module."""

    def test_colors_defined(self):
        """Test that color constants are defined."""
        from ui.ui_styles import COLORS
        
        assert 'bg_primary' in COLORS
        assert 'text_primary' in COLORS
        assert 'accent_blue' in COLORS
        assert 'success' in COLORS
        assert 'error' in COLORS

    def test_fonts_defined(self):
        """Test that font constants are defined."""
        from ui.ui_styles import FONTS
        
        assert 'default' in FONTS
        assert 'heading' in FONTS
        assert 'monospace' in FONTS
        
        # Check font tuple structure
        assert len(FONTS['default']) >= 2

    def test_get_tag_colors(self):
        """Test tag colors configuration."""
        from ui.ui_styles import get_tag_colors
        
        tags = get_tag_colors()
        
        assert 'INFO' in tags
        assert 'SUCCESS' in tags
        assert 'ERROR' in tags
        assert 'WARNING' in tags
        
        assert 'foreground' in tags['INFO']
