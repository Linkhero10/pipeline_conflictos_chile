"""
Results manager for the filter application.

Manages loading, filtering, and exporting of processed results.
"""

import logging
import os
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
import pandas as pd
from tkinter import filedialog, messagebox

logger = logging.getLogger(__name__)


class ResultsManager:
    """
    Manages processed results: loading, filtering, and exporting.
    
    Provides a clean interface for working with classification results
    stored in Excel files.
    """
    
    def __init__(self) -> None:
        """Initialize the results manager."""
        self.df_all: Optional[pd.DataFrame] = None
        self.df_filtered: Optional[pd.DataFrame] = None
        self.current_file: Optional[str] = None
        self.available_sheets: List[str] = []
    
    def load_results(self, excel_path: str, sheet_name: str = 'Datos_completos') -> bool:
        """
        Load results from an Excel file.
        
        Args:
            excel_path: Path to the Excel file.
            sheet_name: Name of the sheet to load.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            if not os.path.exists(excel_path):
                logger.error(f"File not found: {excel_path}")
                return False
            
            # Get available sheets
            xl = pd.ExcelFile(excel_path)
            self.available_sheets = xl.sheet_names
            
            # Load the specified sheet
            if sheet_name not in self.available_sheets:
                # Try to find a suitable sheet
                for fallback in ['Datos_completos', 'Datos_filtrados', 'Datos']:
                    if fallback in self.available_sheets:
                        sheet_name = fallback
                        break
                else:
                    sheet_name = self.available_sheets[0]
            
            self.df_all = pd.read_excel(excel_path, sheet_name=sheet_name)
            self.df_filtered = self.df_all.copy()
            self.current_file = excel_path
            
            logger.info(f"Loaded {len(self.df_all)} rows from {excel_path} [{sheet_name}]")
            return True
            
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return False
    
    def filter_results(
        self,
        search_text: str = '',
        conflict_type: str = '',
        region: str = '',
        include_excluded: bool = True
    ) -> pd.DataFrame:
        """
        Filter results based on criteria.
        
        Args:
            search_text: Text to search in title/content.
            conflict_type: Filter by conflict type.
            region: Filter by region.
            include_excluded: Whether to include excluded articles.
            
        Returns:
            Filtered DataFrame.
        """
        if self.df_all is None:
            return pd.DataFrame()
        
        df = self.df_all.copy()
        
        # Text search
        if search_text:
            search_lower = search_text.lower()
            mask = df.apply(
                lambda row: search_lower in str(row.get('titulo', '')).lower() or
                           search_lower in str(row.get('noticia', '')).lower(),
                axis=1
            )
            df = df[mask]
        
        # Conflict type filter
        if conflict_type and conflict_type != 'Todos':
            if 'tipo_conflicto' in df.columns:
                df = df[df['tipo_conflicto'] == conflict_type]
        
        # Region filter
        if region and region != 'Todas':
            if 'region' in df.columns:
                df = df[df['region'] == region]
        
        # Exclude filter
        if not include_excluded and 'excluir' in df.columns:
            df = df[df['excluir'] == False]
        
        self.df_filtered = df
        return df
    
    def get_unique_values(self, column: str) -> List[str]:
        """
        Get unique values from a column.
        
        Args:
            column: Column name.
            
        Returns:
            List of unique values.
        """
        if self.df_all is None or column not in self.df_all.columns:
            return []
        
        values = self.df_all[column].dropna().unique().tolist()
        return sorted([str(v) for v in values])
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the loaded results.
        
        Returns:
            Dictionary with statistics.
        """
        if self.df_all is None:
            return {'total': 0}
        
        stats = {
            'total': len(self.df_all),
            'filtered': len(self.df_filtered) if self.df_filtered is not None else 0,
        }
        
        if 'excluir' in self.df_all.columns:
            stats['included'] = len(self.df_all[self.df_all['excluir'] == False])
            stats['excluded'] = len(self.df_all[self.df_all['excluir'] == True])
        
        if 'tipo_conflicto' in self.df_all.columns:
            stats['by_conflict_type'] = self.df_all['tipo_conflicto'].value_counts().to_dict()
        
        if 'region' in self.df_all.columns:
            stats['by_region'] = self.df_all['region'].value_counts().to_dict()
        
        return stats
    
    def export_filtered(self, output_path: Optional[str] = None) -> Optional[str]:
        """
        Export filtered results to Excel.
        
        Args:
            output_path: Path for output file. If None, prompts user.
            
        Returns:
            Path to exported file, or None if cancelled/failed.
        """
        if self.df_filtered is None or self.df_filtered.empty:
            messagebox.showwarning("Aviso", "No hay datos para exportar")
            return None
        
        if output_path is None:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                title="Exportar resultados filtrados"
            )
        
        if not output_path:
            return None
        
        try:
            self.df_filtered.to_excel(output_path, index=False)
            logger.info(f"Exported {len(self.df_filtered)} rows to {output_path}")
            messagebox.showinfo("Éxito", f"Exportado exitosamente:\n{output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting: {e}")
            messagebox.showerror("Error", f"Error exportando: {e}")
            return None
    
    def get_article_details(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific article.
        
        Args:
            index: DataFrame index of the article.
            
        Returns:
            Dictionary with article details, or None if not found.
        """
        if self.df_filtered is None:
            return None
        
        try:
            if index in self.df_filtered.index:
                return self.df_filtered.loc[index].to_dict()
            return None
        except Exception:
            return None


def get_column_display_mapping() -> Dict[str, str]:
    """
    Get mapping of internal column names to display names.
    
    Returns:
        Dictionary mapping column names to display names.
    """
    return {
        'id_noticia': 'ID',
        'titulo': 'Título',
        'fuente': 'Fuente',
        'fecha': 'Fecha',
        'tipo_conflicto': 'Tipo Conflicto',
        'tipo_accion': 'Tipo Acción',
        'actor_demandante': 'Actor Demandante',
        'actor_demandado': 'Actor Demandado',
        'region': 'Región',
        'comuna': 'Comuna',
        'excluir': 'Excluido',
        'motivo_exclusion': 'Motivo Exclusión',
        'enlace': 'Enlace'
    }


def format_article_for_display(article: Dict[str, Any]) -> str:
    """
    Format an article dictionary for display.
    
    Args:
        article: Article dictionary.
        
    Returns:
        Formatted string for display.
    """
    lines = []
    column_mapping = get_column_display_mapping()
    
    # Priority fields first
    priority_fields = ['titulo', 'tipo_conflicto', 'tipo_accion', 
                       'actor_demandante', 'actor_demandado', 'region', 'comuna']
    
    for field in priority_fields:
        if field in article and article[field]:
            display_name = column_mapping.get(field, field)
            lines.append(f"{display_name}: {article[field]}")
    
    # Add justification if present
    if 'justificacion_transicion' in article and article['justificacion_transicion']:
        lines.append(f"\nJustificación:\n{article['justificacion_transicion']}")
    
    # Add link if present
    if 'enlace' in article and article['enlace']:
        lines.append(f"\nEnlace: {article['enlace']}")
    
    return '\n'.join(lines)
