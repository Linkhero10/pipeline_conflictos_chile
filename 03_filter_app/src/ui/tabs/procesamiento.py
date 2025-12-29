"""
Pestaña Procesamiento - Filtrador FONDECYT
Extraído de app_gui.py original
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import pandas as pd
import os
from datetime import datetime
from src.ui.utils import ToolTip
from src.ui.features_v3 import (
    validar_configuracion_exhaustiva,
    probar_api,
    guardar_configuracion,
    cargar_configuracion
)

def crear_tab_procesamiento(main_frame, app):
    """Crea la interfaz de la pestaña de procesamiento"""
    
    # ===== CONFIGURACIÓN =====
    config_frame = tk.LabelFrame(
        main_frame,
        text="⚙️ Configuración",
        font=("Segoe UI", 12, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    config_frame.pack(fill=tk.X, padx=20, pady=(10, 15))
    
    # Provider
    tk.Label(config_frame, text="🔌 Provider:", font=("Arial", 10, "bold")).grid(
        row=0, column=0, sticky=tk.W, pady=5
    )
    provider_combo = ttk.Combobox(
        config_frame,
        textvariable=app.provider,
        values=['abacus', 'google', 'openrouter'],
        state='readonly',
        width=47
    )
    provider_combo.grid(row=0, column=1, pady=5, padx=10)
    provider_combo.bind('<<ComboboxSelected>>', app._cambiar_provider)
    
    # Modelo
    tk.Label(config_frame, text="🤖 Modelo:", font=("Arial", 10, "bold")).grid(
        row=1, column=0, sticky=tk.W, pady=5
    )
    app.modelo_combo = ttk.Combobox(
        config_frame,
        textvariable=app.modelo,
        values=['google/gemini-3-flash-preview', 'gemini-2.5-flash', 'route-llm', 'deepseek-v3.1'],
        state='readonly',
        width=47
    )
    app.modelo_combo.grid(row=1, column=1, pady=5, padx=10)
    
    # API Key
    tk.Label(config_frame, text="🔑 API Key:", font=("Arial", 10, "bold")).grid(
        row=2, column=0, sticky=tk.W, pady=5
    )
    api_entry = tk.Entry(config_frame, textvariable=app.api_key, width=50, show="*")
    api_entry.grid(row=2, column=1, pady=5, padx=10)
    
    tk.Button(
        config_frame,
        text="👁️",
        command=lambda: api_entry.config(show="" if api_entry.cget("show") == "*" else "*")
    ).grid(row=2, column=2)
    
    # Archivo Excel
    tk.Label(config_frame, text="📁 Archivo Excel:", font=("Arial", 10, "bold")).grid(
        row=3, column=0, sticky=tk.W, pady=5
    )
    tk.Entry(config_frame, textvariable=app.archivo_excel, width=50, state='readonly').grid(
        row=3, column=1, pady=5, padx=10
    )
    tk.Button(
        config_frame,
        text="📂 Buscar",
        command=app.seleccionar_archivo,
        bg="#3498db",
        fg="white",
        font=("Arial", 9, "bold")
    ).grid(row=3, column=2)
    
    # Hoja a procesar con selector automático
    tk.Label(config_frame, text="📄 Hoja del Excel:", font=("Arial", 10, "bold")).grid(
        row=4, column=0, sticky=tk.W, pady=5
    )
    
    # Frame para hoja Excel con botón de selección
    hoja_frame = tk.Frame(config_frame)
    hoja_frame.grid(row=4, column=1, pady=5, padx=10, sticky=tk.W)
    
    app.hoja_excel = tk.StringVar(value="Datos_enriquecidos")
    hoja_entry = tk.Entry(hoja_frame, textvariable=app.hoja_excel, width=40)
    hoja_entry.pack(side=tk.LEFT, padx=(0, 5))
    
    def seleccionar_hoja():
        """Abre diálogo para seleccionar hoja del Excel"""
        archivo = app.archivo_excel.get()
        if not archivo or not os.path.exists(archivo):
            messagebox.showwarning("⚠️ Advertencia", "Primero selecciona un archivo Excel válido")
            return
        
        try:
            # Leer todas las hojas del Excel
            xls = pd.ExcelFile(archivo)
            hojas_disponibles = xls.sheet_names
            
            if not hojas_disponibles:
                messagebox.showinfo("ℹ️ Información", "El archivo no contiene hojas")
                return
            
            # Crear diálogo de selección
            dialog = tk.Toplevel(app.root)
            dialog.title("Seleccionar Hoja Excel")
            dialog.geometry("400x300")
            dialog.resizable(False, False)
            dialog.transient(app.root)
            dialog.grab_set()
            
            # Centrar diálogo
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - (300 // 2)
            dialog.geometry(f"400x300+{x}+{y}")
            
            # Título
            tk.Label(dialog, text="Selecciona la hoja a procesar:", 
                    font=("Arial", 12, "bold")).pack(pady=15)
            
            # Lista de hojas
            listbox = tk.Listbox(dialog, font=("Arial", 10), height=10)
            listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
            
            for hoja in hojas_disponibles:
                listbox.insert(tk.END, hoja)
            
            # Seleccionar hoja actual si existe
            hoja_actual = app.hoja_excel.get()
            if hoja_actual in hojas_disponibles:
                idx = hojas_disponibles.index(hoja_actual)
                listbox.selection_set(idx)
                listbox.see(idx)
            
            # Botones
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=10)
            
            def aceptar_seleccion():
                seleccion = listbox.curselection()
                if seleccion:
                    hoja_seleccionada = hojas_disponibles[seleccion[0]]
                    app.hoja_excel.set(hoja_seleccionada)
                    app.log(f"Hoja seleccionada: {hoja_seleccionada}", "SUCCESS")
                    dialog.destroy()
            
            tk.Button(btn_frame, text="✅ Aceptar", command=aceptar_seleccion,
                     bg="#27ae60", fg="white", font=("Arial", 10, "bold"),
                     width=12).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame, text="❌ Cancelar", command=dialog.destroy,
                     bg="#e74c3c", fg="white", font=("Arial", 10, "bold"),
                     width=12).pack(side=tk.LEFT, padx=5)
            
            # Doble clic para seleccionar rápidamente
            listbox.bind('<Double-Button-1>', lambda e: aceptar_seleccion())
            
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo leer el archivo Excel:\n{str(e)}")
    
    tk.Button(hoja_frame, text="📋 Seleccionar", command=seleccionar_hoja,
             bg="#3498db", fg="white", font=("Arial", 9, "bold"),
             width=12).pack(side=tk.LEFT)
    
    # Rango de procesamiento
    tk.Label(config_frame, text="📊 Rango:", font=("Arial", 10, "bold")).grid(
        row=4, column=0, sticky=tk.W, pady=5
    )
    rango_frame = tk.Frame(config_frame)
    rango_frame.grid(row=4, column=1, sticky=tk.W, pady=5, padx=10)
    
    tk.Spinbox(
        rango_frame,
        from_=0,
        to=20000,
        textvariable=app.indice_inicio,
        width=8,
        font=("Arial", 10)
    ).pack(side=tk.LEFT)
    
    tk.Label(rango_frame, text="Hasta:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
    
    tk.Spinbox(
        rango_frame,
        from_=1,
        to=20000,
        textvariable=app.indice_fin,
        width=8,
        font=("Arial", 10)
    ).pack(side=tk.LEFT)
    
    tk.Label(
        rango_frame,
        text="(0-based, fin=0 para todas)",
        font=("Arial", 8),
        fg="gray"
    ).pack(side=tk.LEFT, padx=10)
    
    # ===== CONTROL DE CONCURRENCIA =====
    concurrencia_frame = tk.Frame(config_frame, bg="#f8f9fa")
    concurrencia_frame.grid(row=5, column=0, columnspan=3, pady=10, sticky=tk.W+tk.E, padx=10)
    
    tk.Label(
        concurrencia_frame,
        text="🚀 Concurrencia (Workers):",
        font=("Arial", 10, "bold"),
        bg="#f8f9fa"
    ).pack(side=tk.LEFT, padx=5)
    
    # Variable para concurrencia
    if not hasattr(app, 'max_workers'):
        app.max_workers = tk.IntVar(value=5)  # Por defecto 5
    
    # Spinbox para concurrencia
    tk.Spinbox(
        concurrencia_frame,
        from_=1,
        to=10,
        textvariable=app.max_workers,
        width=8,
        font=("Arial", 10)
    ).pack(side=tk.LEFT)
    
    tk.Label(
        concurrencia_frame,
        text="(1=secuencial, 5=recomendado, 10=máximo)",
        font=("Arial", 8),
        fg="gray"
    ).pack(side=tk.LEFT, padx=10)
    
    # Tooltip explicativo
    info_label = tk.Label(
        concurrencia_frame,
        text="ℹ️",
        font=("Arial", 12, "bold"),
        fg="#3498db",
        bg="#f8f9fa",
        cursor="hand2"
    )
    info_label.pack(side=tk.LEFT, padx=5)
    ToolTip(info_label, "Concurrencia permite procesar múltiples noticias simultáneamente.\n" +
            "1 worker = procesamiento secuencial (más lento pero más seguro)\n" +
            "5 workers = balance óptimo velocidad/estabilidad (RECOMENDADO)\n" +
            "10 workers = máxima velocidad (puede causar rate limits)\n\n" +
            "⚡ Mayor concurrencia = procesamiento más rápido\n" +
            "⚠️ Demasiada concurrencia puede exceder límites de API")
    
    # ===== CONTROL DE NOTICIAS DUPLICADAS =====
    duplicadas_frame = tk.Frame(config_frame, bg="#f8f9fa")
    duplicadas_frame.grid(row=6, column=0, columnspan=3, pady=10, sticky=tk.W+tk.E, padx=10)
    
    # Variable para reemplazar duplicadas
    if not hasattr(app, 'reemplazar_duplicadas'):
        app.reemplazar_duplicadas = tk.BooleanVar(value=False)  # Por defecto NO reemplazar
    
    # Checkbox para reemplazar duplicadas
    duplicadas_check = tk.Checkbutton(
        duplicadas_frame,
        text="🔄 Reanalizar noticias ya procesadas (reemplazar)",
        variable=app.reemplazar_duplicadas,
        font=("Arial", 10, "bold"),
        bg="#f8f9fa",
        activebackground="#f8f9fa"
    )
    duplicadas_check.pack(side=tk.LEFT, padx=5)
    
    # Tooltip explicativo
    info_label_dup = tk.Label(
        duplicadas_frame,
        text="ℹ️",
        font=("Arial", 12, "bold"),
        fg="#3498db",
        bg="#f8f9fa",
        cursor="hand2"
    )
    info_label_dup.pack(side=tk.LEFT, padx=5)
    ToolTip(info_label_dup, "Control de noticias duplicadas:\n\n" +
            "✅ ACTIVADO (reemplazar):\n" +
            "   • Reanaliza noticias ya procesadas\n" +
            "   • Actualiza los resultados existentes\n" +
            "   • Útil para corregir análisis previos\n\n" +
            "❌ DESACTIVADO (omitir):\n" +
            "   • Salta noticias ya procesadas\n" +
            "   • Más rápido, no gasta API en duplicados\n" +
            "   • Modo recomendado para procesamiento normal")
    
    # ===== BOTONES ÚTILES (Features V3) =====
    utils_frame = tk.Frame(config_frame, bg="#f8f9fa")
    utils_frame.grid(row=7, column=0, columnspan=3, pady=(10, 0), sticky=tk.W+tk.E)
    
    # Botón Probar API
    def _probar_api_click():
        exitoso, mensaje = probar_api(app.provider.get(), app.modelo.get(), app.api_key.get())
        if exitoso:
            messagebox.showinfo("✅ Test API", mensaje)
        else:
            messagebox.showerror("❌ Test API", mensaje)
    
    tk.Button(
        utils_frame,
        text="🔌 Probar API",
        command=_probar_api_click,
        bg="#10b981",
        fg="white",
        font=("Arial", 9, "bold"),
        width=15
    ).pack(side=tk.LEFT, padx=5)
    
    # Botón Guardar Config
    def _guardar_config_click():
        exitoso, mensaje = guardar_configuracion(app)
        if exitoso:
            messagebox.showinfo("💾 Guardar", mensaje)
        else:
            messagebox.showerror("❌ Error", mensaje)
    
    tk.Button(
        utils_frame,
        text="💾 Guardar Config",
        command=_guardar_config_click,
        bg="#3b82f6",
        fg="white",
        font=("Arial", 9, "bold"),
        width=15
    ).pack(side=tk.LEFT, padx=5)
    
    # Botón Cargar Config
    def _cargar_config_click():
        exitoso, mensaje = cargar_configuracion(app)
        if exitoso:
            messagebox.showinfo("📂 Cargar", mensaje)
        else:
            messagebox.showwarning("⚠️ Cargar", mensaje)
    
    tk.Button(
        utils_frame,
        text="📂 Cargar Config",
        command=_cargar_config_click,
        bg="#8b5cf6",
        fg="white",
        font=("Arial", 9, "bold"),
        width=15
    ).pack(side=tk.LEFT, padx=5)
    
    # ===== BOTONES DE ACCIÓN =====
    btn_frame = tk.Frame(main_frame, bg='#1e1e2e')
    btn_frame.pack(fill=tk.X, padx=20, pady=10)
    
    app.btn_procesar = tk.Button(
        btn_frame,
        text="🚀 INICIAR ANÁLISIS",
        command=app.iniciar_procesamiento,
        bg="#27ae60",
        fg="white",
        font=("Segoe UI", 13, "bold"),
        height=2,
        cursor="hand2"
    )
    app.btn_procesar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    ToolTip(app.btn_procesar, "Inicia el análisis con IA de las noticias seleccionadas.\nProcesa el rango especificado y genera el archivo Excel filtrado.")
    
    app.btn_detener = tk.Button(
        btn_frame,
        text="⏸️ DETENER",
        command=app.detener_procesamiento,
        bg="#e74c3c",
        fg="white",
        font=("Segoe UI", 13, "bold"),
        height=2,
        cursor="hand2",
        state=tk.DISABLED
    )
    app.btn_detener.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
    ToolTip(app.btn_detener, "Detiene el procesamiento actual.\nLos datos procesados hasta el momento se guardarán.")
    
    # ===== INFORMACIÓN DEL ARCHIVO DE SALIDA =====
    output_frame = tk.LabelFrame(
        main_frame,
        text="📁 Archivo de Salida",
        font=("Segoe UI", 12, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    output_frame.pack(fill=tk.X, padx=20, pady=(10, 15))
    
    app.label_output = tk.Label(
        output_frame,
        text="Se creará: [nombre_archivo]_filtrado.xlsx",
        font=("Segoe UI", 10),
        bg="#e8f4f8",
        fg="#2c3e50",
        wraplength=1200,
        justify=tk.LEFT
    )
    app.label_output.pack(pady=5)
    
    tk.Label(
        output_frame,
        text="✅ 4 Hojas: Datos_completos | Datos_filtrados | Revision_manual | Estadisticas",
        font=("Segoe UI", 9, "italic"),
        bg="#e8f4f8",
        fg="#27ae60"
    ).pack()
    
    # ===== PANEL DE ESTADÍSTICAS EN TIEMPO REAL =====
    stats_frame = tk.LabelFrame(
        main_frame,
        text="📊 Estadísticas en Tiempo Real",
        font=("Segoe UI", 12, "bold"),
        padx=15,
        pady=10,
        bg="#f8f9fa"
    )
    stats_frame.pack(fill=tk.X, padx=20, pady=(10, 15))
    
    # Grid de estadísticas
    stats_grid = tk.Frame(stats_frame, bg="#f8f9fa")
    stats_grid.pack(fill=tk.X, pady=5)
    
    # Crear labels para estadísticas - Primera fila
    app.stat_labels = {}
    stats_config_row1 = [
        ('procesadas', '✅ Procesadas', '#27ae60'),
        ('incluidas', '✔️ Incluidas', '#2ecc71'),
        ('excluidas', '❌ Excluidas', '#e74c3c'),
        ('errores', '⚠️ Errores', '#f39c12')
    ]
    
    for i, (key, label, color) in enumerate(stats_config_row1):
        frame = tk.Frame(stats_grid, bg="#f8f9fa", relief=tk.RAISED, borderwidth=1)
        frame.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
        
        tk.Label(
            frame,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg="#f8f9fa",
            fg="#34495e"
        ).pack(pady=(8, 2))
        
        stat_label = tk.Label(
            frame,
            text="0",
            font=("Segoe UI", 22, "bold"),
            bg="#f8f9fa",
            fg=color
        )
        stat_label.pack(pady=(0, 8))
        app.stat_labels[key] = stat_label
    
    # Segunda fila - Métricas de rendimiento
    stats_config_row2 = [
        ('velocidad', '⚡ Velocidad', '#3498db'),
        ('tiempo_estimado', '⏱️ Tiempo Restante', '#9b59b6'),
        ('porcentaje_incluidas', '✅ % Incluidas', '#16a085'),
        ('hora_finalizacion', '🕐 Hora Estimada Fin', '#8e44ad')
    ]
    
    for i, (key, label, color) in enumerate(stats_config_row2):
        frame = tk.Frame(stats_grid, bg="#f8f9fa", relief=tk.RAISED, borderwidth=1)
        frame.grid(row=1, column=i, padx=8, pady=8, sticky="nsew")
        
        tk.Label(
            frame,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg="#f8f9fa",
            fg="#34495e"
        ).pack(pady=(8, 2))
        
        stat_label = tk.Label(
            frame,
            text="--",
            font=("Segoe UI", 18, "bold"),
            bg="#f8f9fa",
            fg=color
        )
        stat_label.pack(pady=(0, 8))
        app.stat_labels[key] = stat_label
    
    # Configurar grid para que se expanda uniformemente
    for i in range(4):
        stats_grid.columnconfigure(i, weight=1)
    
    # ===== PROGRESO =====
    progreso_frame = tk.LabelFrame(
        main_frame,
        text="📈 Progreso del Procesamiento",
        font=("Segoe UI", 12, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    progreso_frame.pack(fill=tk.X, padx=20, pady=(10, 15))
    
    app.progress_bar = ttk.Progressbar(
        progreso_frame,
        style='Modern.Horizontal.TProgressbar',
        mode='determinate',
        length=700
    )
    app.progress_bar.pack(pady=5)
    
    app.label_progreso = tk.Label(
        progreso_frame,
        text="Esperando inicio...",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        fg="#34495e"
    )
    app.label_progreso.pack(pady=5)
    
    # ===== LOGS DUALES (APP + CONSOLA) =====
    logs_container = tk.Frame(main_frame, bg="#f8f9fa")
    logs_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    # LOG DE LA APP (Izquierda)
    log_app_frame = tk.LabelFrame(
        logs_container,
        text="📝 Log de Actividad (App)",
        font=("Segoe UI", 11, "bold"),
        padx=10,
        pady=10,
        bg="#f8f9fa"
    )
    log_app_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
    app.log_text = scrolledtext.ScrolledText(
        log_app_frame,
        height=15,
        font=("Consolas", 9),
        bg="#2b2b2b",
        fg="#00ff00",
        wrap=tk.WORD,
        insertbackground="white"
    )
    app.log_text.pack(fill=tk.BOTH, expand=True)
    
    # Configurar tags para colores en el log
    app.log_text.tag_config('INFO', foreground='#89b4fa')
    app.log_text.tag_config('SUCCESS', foreground='#a6e3a1')
    app.log_text.tag_config('WARNING', foreground='#f9e2af')
    app.log_text.tag_config('ERROR', foreground='#f38ba8')
    
    # LOG DE CONSOLA/POWERSHELL (Derecha)
    log_console_frame = tk.LabelFrame(
        logs_container,
        text="💻 Log de Consola (PowerShell/Prints)",
        font=("Segoe UI", 11, "bold"),
        padx=10,
        pady=10,
        bg="#f8f9fa"
    )
    log_console_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    app.console_text = scrolledtext.ScrolledText(
        log_console_frame,
        height=15,
        font=("Consolas", 9),
        bg="#1e1e2e",
        fg="#cdd6f4",
        wrap=tk.WORD,
        insertbackground="white"
    )
    app.console_text.pack(fill=tk.BOTH, expand=True)
    
    # Configurar tags para colores en consola
    app.console_text.tag_config('DEBUG', foreground='#89dceb')
    app.console_text.tag_config('PRINT', foreground='#f5e0dc')
    app.console_text.tag_config('SUCCESS', foreground='#a6e3a1')
    app.console_text.tag_config('WARNING', foreground='#f9e2af')
    app.console_text.tag_config('ERROR', foreground='#f38ba8')
    app.console_text.tag_config('SEPARATOR', foreground='#fab387')

