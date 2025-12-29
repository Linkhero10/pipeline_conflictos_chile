"""
Utilidades para la interfaz gráfica
"""

import tkinter as tk

class ToolTip:
    """Clase para crear tooltips (ayudas emergentes) en los widgets"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip,
            text=self.text,
            background="#1e293b",
            foreground="#f8fafc",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=10,
            pady=5
        )
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
