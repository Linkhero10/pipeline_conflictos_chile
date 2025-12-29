"""
UI styles and theme configuration for the filter application.

Centralizes all styling, colors, and theme constants.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any


# ============================================================================
# THEME COLORS
# ============================================================================

COLORS = {
    # Background colors
    'bg_primary': '#1e1e2e',
    'bg_secondary': '#2d2d44',
    'bg_tertiary': '#252538',
    'bg_card': '#1e293b',
    
    # Text colors
    'text_primary': '#f8fafc',
    'text_secondary': '#94a3b8',
    'text_muted': '#64748b',
    
    # Accent colors
    'accent_blue': '#3b82f6',
    'accent_green': '#10b981',
    'accent_yellow': '#f59e0b',
    'accent_red': '#ef4444',
    'accent_purple': '#8b5cf6',
    'accent_cyan': '#06b6d4',
    
    # Status colors
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'info': '#3b82f6',
    
    # Border colors
    'border': '#334155',
    'border_light': '#475569',
}


# ============================================================================
# FONT CONFIGURATION
# ============================================================================

FONTS = {
    'default': ('Segoe UI', 10),
    'heading': ('Segoe UI', 12, 'bold'),
    'subheading': ('Segoe UI', 11, 'bold'),
    'small': ('Segoe UI', 9),
    'monospace': ('Consolas', 10),
    'title': ('Segoe UI', 14, 'bold'),
}


# ============================================================================
# STYLE CONFIGURATION
# ============================================================================

def configure_styles(root: tk.Tk) -> ttk.Style:
    """
    Configure ttk styles for the application.
    
    Args:
        root: Tkinter root window.
        
    Returns:
        Configured ttk.Style object.
    """
    style = ttk.Style()
    
    # Try to use a modern theme as base
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass
    
    # Frame styles
    style.configure(
        'TFrame',
        background=COLORS['bg_primary']
    )
    
    style.configure(
        'Card.TFrame',
        background=COLORS['bg_card']
    )
    
    # Label styles
    style.configure(
        'TLabel',
        background=COLORS['bg_primary'],
        foreground=COLORS['text_primary'],
        font=FONTS['default']
    )
    
    style.configure(
        'Heading.TLabel',
        background=COLORS['bg_primary'],
        foreground=COLORS['text_primary'],
        font=FONTS['heading']
    )
    
    style.configure(
        'Status.TLabel',
        background=COLORS['bg_secondary'],
        foreground=COLORS['text_secondary'],
        font=FONTS['small']
    )
    
    # Button styles
    style.configure(
        'TButton',
        background=COLORS['accent_blue'],
        foreground='white',
        font=FONTS['default'],
        padding=(10, 5)
    )
    
    style.map(
        'TButton',
        background=[('active', COLORS['accent_purple']), ('pressed', COLORS['accent_cyan'])]
    )
    
    style.configure(
        'Success.TButton',
        background=COLORS['success']
    )
    
    style.configure(
        'Danger.TButton',
        background=COLORS['error']
    )
    
    # Entry styles
    style.configure(
        'TEntry',
        fieldbackground=COLORS['bg_secondary'],
        foreground=COLORS['text_primary'],
        insertcolor=COLORS['text_primary']
    )
    
    # Combobox styles
    style.configure(
        'TCombobox',
        fieldbackground=COLORS['bg_secondary'],
        foreground=COLORS['text_primary'],
        selectbackground=COLORS['accent_blue']
    )
    
    # Notebook (tabs) styles
    style.configure(
        'TNotebook',
        background=COLORS['bg_primary'],
        borderwidth=0
    )
    
    style.configure(
        'TNotebook.Tab',
        background=COLORS['bg_secondary'],
        foreground=COLORS['text_secondary'],
        padding=(15, 8),
        font=FONTS['default']
    )
    
    style.map(
        'TNotebook.Tab',
        background=[('selected', COLORS['accent_blue'])],
        foreground=[('selected', 'white')]
    )
    
    # Treeview styles
    style.configure(
        'Treeview',
        background=COLORS['bg_secondary'],
        foreground=COLORS['text_primary'],
        fieldbackground=COLORS['bg_secondary'],
        font=FONTS['default'],
        rowheight=25
    )
    
    style.configure(
        'Treeview.Heading',
        background=COLORS['bg_tertiary'],
        foreground=COLORS['text_primary'],
        font=FONTS['subheading']
    )
    
    style.map(
        'Treeview',
        background=[('selected', COLORS['accent_blue'])],
        foreground=[('selected', 'white')]
    )
    
    # Progressbar styles
    style.configure(
        'TProgressbar',
        background=COLORS['accent_blue'],
        troughcolor=COLORS['bg_secondary'],
        borderwidth=0,
        thickness=10
    )
    
    style.configure(
        'Success.TProgressbar',
        background=COLORS['success']
    )
    
    # Scrollbar styles
    style.configure(
        'TScrollbar',
        background=COLORS['bg_secondary'],
        troughcolor=COLORS['bg_primary'],
        arrowcolor=COLORS['text_secondary']
    )
    
    # LabelFrame styles
    style.configure(
        'TLabelframe',
        background=COLORS['bg_primary'],
        foreground=COLORS['text_primary']
    )
    
    style.configure(
        'TLabelframe.Label',
        background=COLORS['bg_primary'],
        foreground=COLORS['accent_blue'],
        font=FONTS['subheading']
    )
    
    return style


def get_tag_colors() -> Dict[str, Dict[str, str]]:
    """
    Get tag colors for text widget formatting.
    
    Returns:
        Dictionary of tag names to color configurations.
    """
    return {
        'INFO': {'foreground': COLORS['info']},
        'SUCCESS': {'foreground': COLORS['success']},
        'WARNING': {'foreground': COLORS['warning']},
        'ERROR': {'foreground': COLORS['error']},
        'DEBUG': {'foreground': COLORS['text_muted']},
        'PRINT': {'foreground': COLORS['text_secondary']},
        'HEADER': {'foreground': COLORS['accent_purple'], 'font': FONTS['heading']},
    }


def apply_text_widget_style(text_widget: tk.Text) -> None:
    """
    Apply dark theme styling to a text widget.
    
    Args:
        text_widget: Tkinter Text widget to style.
    """
    text_widget.configure(
        bg=COLORS['bg_secondary'],
        fg=COLORS['text_primary'],
        insertbackground=COLORS['text_primary'],
        selectbackground=COLORS['accent_blue'],
        selectforeground='white',
        font=FONTS['monospace'],
        relief='flat',
        borderwidth=0,
        padx=10,
        pady=10
    )
    
    # Configure tags
    for tag_name, config in get_tag_colors().items():
        text_widget.tag_configure(tag_name, **config)


def create_styled_button(
    parent: tk.Widget,
    text: str,
    command: callable,
    style_type: str = 'primary'
) -> ttk.Button:
    """
    Create a styled button.
    
    Args:
        parent: Parent widget.
        text: Button text.
        command: Button command.
        style_type: 'primary', 'success', 'danger', or 'secondary'.
        
    Returns:
        Configured ttk.Button.
    """
    style_map = {
        'primary': 'TButton',
        'success': 'Success.TButton',
        'danger': 'Danger.TButton',
        'secondary': 'TButton'
    }
    
    return ttk.Button(
        parent,
        text=text,
        command=command,
        style=style_map.get(style_type, 'TButton')
    )
