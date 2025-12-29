"""
Processing controller for the filter application.

Manages the processing workflow: starting, stopping, progress updates,
and coordination between UI and backend processing.
"""

import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)


class ProcessingController:
    """
    Controls the processing workflow for news classification.
    
    Manages threading, progress tracking, and coordination between
    the UI and the backend FiltradorIA processor.
    """
    
    def __init__(
        self,
        filtrador_factory: Callable,
        progress_callback: Optional[Callable] = None,
        completion_callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None
    ) -> None:
        """
        Initialize the processing controller.
        
        Args:
            filtrador_factory: Factory function to create FiltradorIA instance.
            progress_callback: Function to call on progress updates.
            completion_callback: Function to call on completion.
            error_callback: Function to call on errors.
        """
        self.filtrador_factory = filtrador_factory
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.error_callback = error_callback
        
        self.filtrador = None
        self.processing = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # Timing statistics
        self.start_time: Optional[datetime] = None
        self.times_per_article: list = []
        
        # Real-time stats
        self.stats: Dict[str, int] = {
            'total': 0,
            'processed': 0,
            'included': 0,
            'excluded': 0,
            'errors': 0
        }
    
    def start_processing(
        self,
        excel_path: str,
        api_key: str,
        provider: str,
        sheet_name: str = 'Datos_enriquecidos',
        start_index: int = 0,
        end_index: int = 100,
        output_path: str = 'resultados_filtrado.xlsx',
        max_workers: int = 1
    ) -> bool:
        """
        Start the processing in a background thread.
        
        Args:
            excel_path: Path to input Excel file.
            api_key: API key for the AI provider.
            provider: AI provider name.
            sheet_name: Sheet name to process.
            start_index: Starting row index.
            end_index: Ending row index.
            output_path: Path for output file.
            max_workers: Number of parallel workers.
            
        Returns:
            True if processing started, False otherwise.
        """
        if self.processing:
            logger.warning("Processing already in progress")
            return False
        
        try:
            # Create filtrador instance
            self.filtrador = self.filtrador_factory(api_key, provider)
            self.processing = True
            self.start_time = datetime.now()
            self.times_per_article = []
            self.stats = {'total': 0, 'processed': 0, 'included': 0, 'excluded': 0, 'errors': 0}
            
            # Start processing thread
            self.processing_thread = threading.Thread(
                target=self._process_worker,
                args=(excel_path, sheet_name, start_index, end_index, output_path, max_workers),
                daemon=True
            )
            self.processing_thread.start()
            
            logger.info(f"Processing started: {excel_path} [{start_index}:{end_index}]")
            return True
            
        except Exception as e:
            logger.error(f"Error starting processing: {e}")
            self.processing = False
            if self.error_callback:
                self.error_callback(str(e))
            return False
    
    def stop_processing(self) -> None:
        """Stop the current processing."""
        if not self.processing:
            return
        
        self.processing = False
        
        if self.filtrador and hasattr(self.filtrador, 'procesador'):
            try:
                self.filtrador.procesador.detener = True
            except Exception:
                pass
        
        logger.info("Processing stopped by user")
    
    def _process_worker(
        self,
        excel_path: str,
        sheet_name: str,
        start_index: int,
        end_index: int,
        output_path: str,
        max_workers: int
    ) -> None:
        """Worker function for processing thread."""
        try:
            resultados = self.filtrador.procesar_excel(
                excel_path=excel_path,
                hoja=sheet_name,
                inicio=start_index,
                fin=end_index,
                output_path=output_path,
                callback=self._on_progress,
                max_workers=max_workers
            )
            
            self.processing = False
            
            if self.completion_callback:
                self.completion_callback(resultados, output_path)
                
        except Exception as e:
            self.processing = False
            logger.error(f"Processing error: {e}")
            if self.error_callback:
                self.error_callback(str(e))
    
    def _on_progress(self, current: int, total: int, title: str) -> None:
        """Handle progress updates from the processor."""
        self.stats['processed'] = current
        self.stats['total'] = total
        
        # Calculate timing
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if current > 0:
                avg_time = elapsed / current
                remaining = (total - current) * avg_time
                self.times_per_article.append(avg_time)
        
        if self.progress_callback:
            self.progress_callback(current, total, title)
    
    def get_elapsed_time(self) -> timedelta:
        """Get elapsed processing time."""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)
    
    def get_estimated_remaining(self) -> Optional[timedelta]:
        """Get estimated remaining time."""
        if not self.times_per_article or self.stats['processed'] == 0:
            return None
        
        avg_time = sum(self.times_per_article) / len(self.times_per_article)
        remaining_items = self.stats['total'] - self.stats['processed']
        remaining_seconds = remaining_items * avg_time
        
        return timedelta(seconds=remaining_seconds)
    
    def is_processing(self) -> bool:
        """Check if processing is in progress."""
        return self.processing


def format_time_delta(td: timedelta) -> str:
    """
    Format a timedelta for display.
    
    Args:
        td: Timedelta to format.
        
    Returns:
        Formatted string like "1h 23m 45s".
    """
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def validate_processing_config(
    excel_path: str,
    api_key: str,
    start_index: int,
    end_index: int
) -> tuple[bool, str]:
    """
    Validate processing configuration before starting.
    
    Args:
        excel_path: Path to Excel file.
        api_key: API key.
        start_index: Start index.
        end_index: End index.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    import os
    
    if not excel_path or not os.path.exists(excel_path):
        return False, "Archivo Excel no encontrado"
    
    if not api_key or len(api_key) < 10:
        return False, "API Key no válida"
    
    if start_index < 0:
        return False, "Índice de inicio debe ser >= 0"
    
    if end_index <= start_index:
        return False, "Índice final debe ser mayor que el inicial"
    
    return True, ""
