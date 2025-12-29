"""
Map generation handlers for the filter application.

Contains functions for generating interactive maps using Folium.
"""

import logging
import os
import webbrowser
from typing import Dict, Optional, Any
from pathlib import Path
import pandas as pd
from tkinter import messagebox, filedialog

logger = logging.getLogger(__name__)


def get_map_output_directory() -> Path:
    """Get or create the maps output directory."""
    maps_dir = Path(__file__).parent.parent.parent / 'mapas_generados'
    maps_dir.mkdir(exist_ok=True)
    return maps_dir


def generate_heatmap(
    df: pd.DataFrame,
    output_path: Optional[str] = None,
    title: str = "Mapa de Conflictos Socioambientales"
) -> Optional[str]:
    """
    Generate an interactive heatmap from conflict data.
    
    Args:
        df: DataFrame with conflict data (must have 'region' or 'comuna' column).
        output_path: Optional custom output path.
        title: Map title.
        
    Returns:
        Path to generated HTML file, or None if failed.
    """
    try:
        # Try to import GeneradorMapas from Phase 4
        import sys
        
        # Calculate path to Phase 4
        current_dir = Path(__file__).parent
        src_dir = current_dir.parent
        app_dir = src_dir.parent
        pipeline_dir = app_dir.parent
        map_dir = pipeline_dir / '04_interactive_map'
        
        if str(map_dir) not in sys.path:
            sys.path.append(str(map_dir))
        
        from map_engine import GeneradorMapas
        logger.info("GeneradorMapas imported successfully from Phase 4")
        
    except ImportError as e:
        logger.error(f"Could not import GeneradorMapas: {e}")
        messagebox.showerror(
            "Error", 
            "No se pudo cargar el módulo de mapas.\n"
            "Asegúrese de que la carpeta 04_interactive_map esté presente."
        )
        return None
    
    try:
        # Default output path
        if output_path is None:
            maps_dir = get_map_output_directory()
            output_path = str(maps_dir / 'mapa_conflictos_interactivo.html')
        
        # Create map generator
        generador = GeneradorMapas()
        
        # Generate unified map with panel
        mapa = generador.generar_mapa_unificado_con_panel(
            df=df,
            output_path=output_path
        )
        
        logger.info(f"Map generated successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating map: {e}")
        messagebox.showerror("Error", f"Error generando mapa: {e}")
        return None


def open_map_in_browser(map_path: str) -> bool:
    """
    Open a map HTML file in the default browser.
    
    Args:
        map_path: Path to the HTML map file.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        if not os.path.exists(map_path):
            logger.error(f"Map file not found: {map_path}")
            messagebox.showerror("Error", f"Archivo no encontrado: {map_path}")
            return False
        
        webbrowser.open(f'file://{os.path.abspath(map_path)}')
        logger.info(f"Map opened in browser: {map_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error opening map: {e}")
        messagebox.showerror("Error", f"Error abriendo mapa: {e}")
        return False


def save_map_copy(source_path: str, destination_path: Optional[str] = None) -> Optional[str]:
    """
    Save a copy of the map with a custom name.
    
    Args:
        source_path: Path to the source map file.
        destination_path: Optional destination path. If None, prompts user.
        
    Returns:
        Path to the saved copy, or None if cancelled/failed.
    """
    try:
        if not os.path.exists(source_path):
            messagebox.showerror("Error", "No hay mapa para guardar.")
            return None
        
        if destination_path is None:
            destination_path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html")],
                title="Guardar mapa como..."
            )
        
        if not destination_path:
            return None
        
        import shutil
        shutil.copy2(source_path, destination_path)
        
        logger.info(f"Map saved to: {destination_path}")
        messagebox.showinfo("Éxito", f"Mapa guardado en:\n{destination_path}")
        return destination_path
        
    except Exception as e:
        logger.error(f"Error saving map: {e}")
        messagebox.showerror("Error", f"Error guardando mapa: {e}")
        return None


def get_last_generated_map() -> Optional[str]:
    """
    Get the path to the last generated map.
    
    Returns:
        Path to the last map, or None if no maps exist.
    """
    maps_dir = get_map_output_directory()
    default_map = maps_dir / 'mapa_conflictos_interactivo.html'
    
    if default_map.exists():
        return str(default_map)
    
    # Look for any HTML file in maps directory
    html_files = list(maps_dir.glob('*.html'))
    if html_files:
        # Return most recently modified
        return str(max(html_files, key=lambda p: p.stat().st_mtime))
    
    return None
