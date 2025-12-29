"""
Chart generation and visualization handlers for the filter application.

Contains functions for creating and updating matplotlib charts in the UI.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

# Configure matplotlib for Tkinter
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import seaborn as sns

logger = logging.getLogger(__name__)

# Dark theme configuration
CHART_STYLE = {
    'bg_color': '#1e293b',
    'text_color': '#f8fafc',
    'grid_color': '#334155',
    'grid_alpha': 0.3,
    'colors': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
               '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1']
}


def configure_chart_style() -> None:
    """Configure matplotlib style for dark theme."""
    plt.style.use('dark_background')
    plt.rcParams['figure.facecolor'] = CHART_STYLE['bg_color']
    plt.rcParams['axes.facecolor'] = CHART_STYLE['bg_color']
    plt.rcParams['text.color'] = CHART_STYLE['text_color']
    plt.rcParams['axes.labelcolor'] = CHART_STYLE['text_color']
    plt.rcParams['xtick.color'] = CHART_STYLE['text_color']
    plt.rcParams['ytick.color'] = CHART_STYLE['text_color']
    plt.rcParams['grid.color'] = CHART_STYLE['grid_color']
    plt.rcParams['grid.alpha'] = CHART_STYLE['grid_alpha']


def create_empty_chart(fig: Figure, ax: plt.Axes, message: str = "Sin datos") -> None:
    """
    Create an empty chart with a message.
    
    Args:
        fig: Matplotlib Figure object.
        ax: Matplotlib Axes object.
        message: Message to display.
    """
    ax.clear()
    ax.text(
        0.5, 0.5, message,
        ha='center', va='center',
        fontsize=14, color='#64748b',
        transform=ax.transAxes
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor(CHART_STYLE['bg_color'])
    fig.tight_layout()


def create_pie_chart(
    fig: Figure,
    ax: plt.Axes,
    data: Dict[str, int],
    title: str,
    max_items: int = 8
) -> None:
    """
    Create a pie chart from data.
    
    Args:
        fig: Matplotlib Figure object.
        ax: Matplotlib Axes object.
        data: Dictionary with labels and values.
        title: Chart title.
        max_items: Maximum number of items to show (rest grouped as 'Otros').
    """
    ax.clear()
    
    if not data or sum(data.values()) == 0:
        create_empty_chart(fig, ax, "Sin datos para mostrar")
        return
    
    # Sort and limit items
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    
    if len(sorted_data) > max_items:
        top_items = dict(sorted_data[:max_items-1])
        others_value = sum(v for k, v in sorted_data[max_items-1:])
        top_items['Otros'] = others_value
        sorted_data = list(top_items.items())
    
    labels = [item[0] for item in sorted_data]
    values = [item[1] for item in sorted_data]
    colors = CHART_STYLE['colors'][:len(labels)]
    
    # Create pie
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
        colors=colors,
        startangle=90,
        pctdistance=0.75
    )
    
    # Style
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(9)
    
    ax.set_title(title, fontsize=12, fontweight='bold', color=CHART_STYLE['text_color'])
    
    # Legend
    ax.legend(
        wedges, labels,
        loc='center left',
        bbox_to_anchor=(1, 0.5),
        fontsize=8
    )
    
    fig.tight_layout()


def create_bar_chart(
    fig: Figure,
    ax: plt.Axes,
    data: Dict[str, int],
    title: str,
    xlabel: str = '',
    ylabel: str = 'Cantidad',
    max_items: int = 10,
    horizontal: bool = False
) -> None:
    """
    Create a bar chart from data.
    
    Args:
        fig: Matplotlib Figure object.
        ax: Matplotlib Axes object.
        data: Dictionary with labels and values.
        title: Chart title.
        xlabel: X-axis label.
        ylabel: Y-axis label.
        max_items: Maximum number of bars to show.
        horizontal: If True, create horizontal bars.
    """
    ax.clear()
    
    if not data or sum(data.values()) == 0:
        create_empty_chart(fig, ax, "Sin datos para mostrar")
        return
    
    # Sort and limit
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    labels = [item[0][:30] for item in sorted_data]  # Truncate long labels
    values = [item[1] for item in sorted_data]
    
    colors = CHART_STYLE['colors'][:len(labels)]
    
    if horizontal:
        bars = ax.barh(labels, values, color=colors)
        ax.set_xlabel(ylabel)
        ax.invert_yaxis()
    else:
        bars = ax.bar(labels, values, color=colors)
        ax.set_ylabel(ylabel)
        plt.xticks(rotation=45, ha='right')
    
    ax.set_title(title, fontsize=12, fontweight='bold', color=CHART_STYLE['text_color'])
    ax.set_facecolor(CHART_STYLE['bg_color'])
    ax.grid(axis='y' if not horizontal else 'x', alpha=0.3)
    
    fig.tight_layout()


def create_timeline_chart(
    fig: Figure,
    ax: plt.Axes,
    dates: pd.Series,
    title: str = "Distribución Temporal"
) -> None:
    """
    Create a timeline/histogram chart from dates.
    
    Args:
        fig: Matplotlib Figure object.
        ax: Matplotlib Axes object.
        dates: Pandas Series with dates.
        title: Chart title.
    """
    ax.clear()
    
    if dates.empty or dates.isna().all():
        create_empty_chart(fig, ax, "Sin datos temporales")
        return
    
    # Convert to datetime if needed
    dates = pd.to_datetime(dates, errors='coerce')
    dates = dates.dropna()
    
    if dates.empty:
        create_empty_chart(fig, ax, "Sin fechas válidas")
        return
    
    # Group by month
    monthly = dates.dt.to_period('M').value_counts().sort_index()
    
    ax.bar(
        range(len(monthly)),
        monthly.values,
        color=CHART_STYLE['colors'][0],
        alpha=0.8
    )
    
    # X-axis labels
    ax.set_xticks(range(len(monthly)))
    ax.set_xticklabels(
        [str(p) for p in monthly.index],
        rotation=45,
        ha='right',
        fontsize=8
    )
    
    ax.set_title(title, fontsize=12, fontweight='bold', color=CHART_STYLE['text_color'])
    ax.set_ylabel('Cantidad')
    ax.set_facecolor(CHART_STYLE['bg_color'])
    ax.grid(axis='y', alpha=0.3)
    
    fig.tight_layout()


def save_charts_to_png(
    figures: List[Tuple[Figure, str]],
    output_dir: str
) -> List[str]:
    """
    Save multiple figures to PNG files.
    
    Args:
        figures: List of tuples (Figure, name).
        output_dir: Directory to save files.
        
    Returns:
        List of saved file paths.
    """
    saved_files = []
    
    for fig, name in figures:
        try:
            filename = f"{output_dir}/{name}.png"
            fig.savefig(
                filename,
                dpi=150,
                bbox_inches='tight',
                facecolor=CHART_STYLE['bg_color']
            )
            saved_files.append(filename)
            logger.info(f"Chart saved: {filename}")
        except Exception as e:
            logger.error(f"Error saving chart {name}: {e}")
    
    return saved_files
