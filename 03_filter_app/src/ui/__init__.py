"""
UI module for the Filter Application.

This module contains all user interface components including:
- Main application (app.py)
- Console handlers for logging redirection
- Chart generation handlers
- Profile management handlers
- Map generation handlers
- Various UI tabs and utilities
"""

from .console_handlers import ConsoleRedirector, TextWidgetHandler
from .profile_handlers import (
    list_profiles,
    save_profile,
    load_profile,
    delete_profile,
    get_profile_config
)
from .chart_handlers import (
    configure_chart_style,
    create_empty_chart,
    create_pie_chart,
    create_bar_chart,
    create_timeline_chart,
    save_charts_to_png,
    CHART_STYLE
)
from .map_handlers import (
    generate_heatmap,
    open_map_in_browser,
    save_map_copy,
    get_last_generated_map
)
from .utils import ToolTip

__all__ = [
    # Console
    'ConsoleRedirector',
    'TextWidgetHandler',
    # Profiles
    'list_profiles',
    'save_profile',
    'load_profile',
    'delete_profile',
    'get_profile_config',
    # Charts
    'configure_chart_style',
    'create_empty_chart',
    'create_pie_chart',
    'create_bar_chart',
    'create_timeline_chart',
    'save_charts_to_png',
    'CHART_STYLE',
    # Maps
    'generate_heatmap',
    'open_map_in_browser',
    'save_map_copy',
    'get_last_generated_map',
    # Utils
    'ToolTip',
]
