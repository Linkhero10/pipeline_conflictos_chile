#!/usr/bin/env python3
"""
FILTRADOR FONDECYT - Archivo Principal
Sistema de análisis de conflictos socioambientales en Chile usando IA
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

# Agregar la carpeta raíz del proyecto al path de Python
sys.path.insert(0, os.path.dirname(__file__))

try:
    from src.ui.app import FiltradorApp
except ImportError as e:
    print(f"Error al importar módulos: {e}")
    print("Asegúrate de estar en la carpeta correcta del proyecto")
    input("Presione Enter para salir...")
    sys.exit(1)

def main():
    """Función principal para iniciar la aplicación"""
    try:
        # Crear ventana principal
        root = tk.Tk()
        
        # Crear instancia de la aplicación
        app = FiltradorApp(root)
        
        # Iniciar el bucle principal de la interfaz
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\nAplicación interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        error_msg = f"Error fatal al iniciar la aplicación:\n{str(e)}"
        print(error_msg)
        
        # Mostrar error en diálogo si tkinter está disponible
        try:
            root = tk.Tk()
            root.withdraw()  # Ocultar ventana principal
            messagebox.showerror("Error Fatal", error_msg)
        except:
            pass
        
        input("Presione Enter para salir...")
        sys.exit(1)

if __name__ == "__main__":
    main()
