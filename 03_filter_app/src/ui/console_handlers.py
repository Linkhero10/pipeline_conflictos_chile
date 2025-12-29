"""
Console and logging handlers for the filter application.

Contains classes for redirecting stdout and logging to Tkinter widgets.
"""

import logging
import sys
import tkinter as tk
from typing import Optional


class ConsoleRedirector:
    """Redirects stdout (prints) to a console widget in the interface."""
    
    def __init__(self, text_widget: tk.Text, tag: str = 'PRINT') -> None:
        """
        Initialize the console redirector.
        
        Args:
            text_widget: Tkinter Text widget to redirect output to.
            tag: Tag name for styling the output.
        """
        self.text_widget = text_widget
        self.tag = tag
        self.original_stdout = sys.stdout
        
    def write(self, message: str) -> None:
        """Write message to the console widget."""
        if message.strip():
            try:
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.insert(tk.END, message, (self.tag,))
                self.text_widget.see(tk.END)
                self.text_widget.config(state=tk.DISABLED)
                self.text_widget.update_idletasks()
            except tk.TclError:
                pass
        
    def flush(self) -> None:
        """Required flush method for stdout compatibility."""
        try:
            self.text_widget.update_idletasks()
        except tk.TclError:
            pass


class TextWidgetHandler(logging.Handler):
    """Logging handler that writes to a Tkinter text widget."""
    
    def __init__(self, text_widget: tk.Text) -> None:
        """
        Initialize the text widget handler.
        
        Args:
            text_widget: Tkinter Text widget to write logs to.
        """
        super().__init__()
        self.text_widget = text_widget
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the text widget."""
        try:
            msg = self.format(record)
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.update_idletasks()
        except tk.TclError:
            pass
