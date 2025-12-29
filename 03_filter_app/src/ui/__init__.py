"""
UI module for the Filter Application.

This module provides a modular, well-organized user interface with:

Components:
- app.py: Main application window (FiltradorApp)
- console_handlers.py: Console/logging redirection
- chart_handlers.py: Chart generation with matplotlib
- profile_handlers.py: User profile management
- map_handlers.py: Interactive map generation with Folium
- processing_controller.py: Background processing control
- results_manager.py: Results loading/filtering/export
- ui_styles.py: Centralized theme and styling

Tabs:
- tabs/procesamiento.py: Processing configuration tab
- tabs/resultados.py: Results viewer tab
- tabs/graficos.py: Charts and statistics tab
- tabs/perfiles.py: Profile management tab
- tabs/reprocesamiento.py: Reprocessing tab
"""

# Console handlers
from .console_handlers import (
    ConsoleRedirector,
    TextWidgetHandler
)

# Profile management
from .profile_handlers import (
    list_profiles,
    save_profile,
    load_profile,
    delete_profile,
    get_profile_config,
    get_profiles_directory
)

# Chart generation
from .chart_handlers import (
    configure_chart_style,
    create_empty_chart,
    create_pie_chart,
    create_bar_chart,
    create_timeline_chart,
    save_charts_to_png,
    CHART_STYLE
)

# Map generation
from .map_handlers import (
    generate_heatmap,
    open_map_in_browser,
    save_map_copy,
    get_last_generated_map,
    get_map_output_directory
)

# Processing control
from .processing_controller import (
    ProcessingController,
    format_time_delta,
    validate_processing_config
)

# Results management
from .results_manager import (
    ResultsManager,
    get_column_display_mapping,
    format_article_for_display
)

# UI styling
from .ui_styles import (
    configure_styles,
    apply_text_widget_style,
    create_styled_button,
    get_tag_colors,
    COLORS,
    FONTS
)

# Utilities
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
    'get_profiles_directory',
    
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
    'get_map_output_directory',
    
    # Processing
    'ProcessingController',
    'format_time_delta',
    'validate_processing_config',
    
    # Results
    'ResultsManager',
    'get_column_display_mapping',
    'format_article_for_display',
    
    # Styles
    'configure_styles',
    'apply_text_widget_style',
    'create_styled_button',
    'get_tag_colors',
    'COLORS',
    'FONTS',
    
    # Utils
    'ToolTip',
]
