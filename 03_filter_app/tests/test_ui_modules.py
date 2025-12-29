"""
Tests for the modular UI components.

Tests console handlers, profile handlers, chart handlers, and map handlers.
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestProfileHandlers:
    """Tests for profile management handlers."""

    def test_get_profiles_directory(self):
        """Test that profiles directory can be retrieved."""
        from ui.profile_handlers import get_profiles_directory
        
        profiles_dir = get_profiles_directory()
        assert profiles_dir is not None
        assert isinstance(profiles_dir, Path)

    def test_list_profiles_returns_list(self):
        """Test that list_profiles returns a list."""
        from ui.profile_handlers import list_profiles
        
        profiles = list_profiles()
        assert isinstance(profiles, list)

    def test_get_profile_config_structure(self):
        """Test that profile config has correct structure."""
        from ui.profile_handlers import get_profile_config
        
        config = get_profile_config(
            provider='openrouter',
            model='gemini-2.5-flash',
            api_key='sk-test-key-12345',
            excel_path='test.xlsx',
            sheet_name='Datos',
            start_index=0,
            end_index=100,
            output_path='output.xlsx'
        )
        
        assert 'provider' in config
        assert 'model' in config
        assert 'api_key_preview' in config
        assert config['provider'] == 'openrouter'
        assert 'test-key' in config['api_key_preview']


class TestChartHandlers:
    """Tests for chart generation handlers."""

    def test_chart_style_constants(self):
        """Test that chart style constants are defined."""
        from ui.chart_handlers import CHART_STYLE
        
        assert 'bg_color' in CHART_STYLE
        assert 'text_color' in CHART_STYLE
        assert 'colors' in CHART_STYLE
        assert isinstance(CHART_STYLE['colors'], list)
        assert len(CHART_STYLE['colors']) >= 5

    def test_configure_chart_style(self):
        """Test that configure_chart_style runs without error."""
        from ui.chart_handlers import configure_chart_style
        
        # Should not raise
        configure_chart_style()


class TestMapHandlers:
    """Tests for map generation handlers."""

    def test_get_map_output_directory(self):
        """Test that map output directory can be retrieved."""
        from ui.map_handlers import get_map_output_directory
        
        maps_dir = get_map_output_directory()
        assert maps_dir is not None
        assert isinstance(maps_dir, Path)


class TestConsoleHandlers:
    """Tests for console handler classes."""

    def test_console_redirector_import(self):
        """Test that ConsoleRedirector can be imported."""
        from ui.console_handlers import ConsoleRedirector
        
        assert ConsoleRedirector is not None

    def test_text_widget_handler_import(self):
        """Test that TextWidgetHandler can be imported."""
        from ui.console_handlers import TextWidgetHandler
        
        assert TextWidgetHandler is not None


class TestModuleImports:
    """Tests for module imports from __init__.py."""

    def test_ui_module_imports(self):
        """Test that all exports from ui module are accessible."""
        from ui import (
            ConsoleRedirector,
            TextWidgetHandler,
            list_profiles,
            save_profile,
            load_profile,
            configure_chart_style,
            CHART_STYLE,
            generate_heatmap,
            open_map_in_browser
        )
        
        assert ConsoleRedirector is not None
        assert TextWidgetHandler is not None
        assert callable(list_profiles)
        assert callable(save_profile)
        assert callable(load_profile)
        assert callable(configure_chart_style)
        assert isinstance(CHART_STYLE, dict)
        assert callable(generate_heatmap)
        assert callable(open_map_in_browser)
