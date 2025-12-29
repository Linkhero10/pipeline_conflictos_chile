"""
Pestaña Resultados - Filtrador FONDECYT
Extraído de app_gui.py original
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import pandas as pd
from datetime import datetime
from src.ui.utils import ToolTip

def crear_tab_resultados(parent, app):
    """Crea la interfaz de la pestaña de resultados"""
    
    # Frame principal con scroll
    container = tk.Frame(parent, bg=app.colors['bg_primary'])
    container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Título
    tk.Label(
        container,
        text="📊 Visualización de Resultados",
        font=("Segoe UI", 18, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(pady=(0, 20))
    
    # Barra de herramientas
    toolbar = tk.Frame(container, bg=app.colors['bg_primary'])
    toolbar.pack(fill=tk.X, pady=(0, 15))
    
    # Búsqueda
    search_frame = tk.Frame(toolbar, bg=app.colors['bg_primary'])
    search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    tk.Label(
        search_frame,
        text="🔍 Buscar:",
        font=("Segoe UI", 11, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(side=tk.LEFT, padx=(0, 10))
    
    app.search_var = tk.StringVar()
    app.search_var.trace('w', lambda *args: app._filtrar_resultados())
    
    search_entry = tk.Entry(
        search_frame,
        textvariable=app.search_var,
        font=("Segoe UI", 10),
        width=45,
        bg=app.colors['bg_secondary'],
        fg=app.colors['text_primary'],
        insertbackground=app.colors['text_primary'],
        relief=tk.FLAT,
        borderwidth=2
    )
    search_entry.pack(side=tk.LEFT, padx=(0, 20))
    
    # ===== FILTROS AVANZADOS =====
    filtros_frame = tk.Frame(toolbar, bg=app.colors['bg_primary'])
    filtros_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # Filtro por Estado
    tk.Label(
        filtros_frame,
        text="Estado:",
        font=("Segoe UI", 10, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(side=tk.LEFT, padx=(0, 5))
    
    app.filter_tipo = tk.StringVar(value="Todos")
    filter_combo = ttk.Combobox(
        filtros_frame,
        textvariable=app.filter_tipo,
        values=["Todos", "Incluidas", "Excluidas", "Revisión Manual", "Contenido Manual"],
        state='readonly',
        width=14
    )
    filter_combo.pack(side=tk.LEFT, padx=(0, 10))
    filter_combo.bind('<<ComboboxSelected>>', lambda e: app._filtrar_resultados())
    
    # Filtro por Región
    tk.Label(
        filtros_frame,
        text="Región:",
        font=("Segoe UI", 10, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(side=tk.LEFT, padx=(0, 5))
    
    app.filter_region = tk.StringVar(value="Todas")
    app.filter_region_combo = ttk.Combobox(
        filtros_frame,
        textvariable=app.filter_region,
        values=["Todas"],
        state='readonly',
        width=20
    )
    app.filter_region_combo.pack(side=tk.LEFT, padx=(0, 10))
    app.filter_region_combo.bind('<<ComboboxSelected>>', lambda e: app._filtrar_resultados())
    
    # Filtro por Tipo de Conflicto
    tk.Label(
        filtros_frame,
        text="Conflicto:",
        font=("Segoe UI", 10, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(side=tk.LEFT, padx=(0, 5))
    
    app.filter_conflicto = tk.StringVar(value="Todos")
    app.filter_conflicto_combo = ttk.Combobox(
        filtros_frame,
        textvariable=app.filter_conflicto,
        values=["Todos"],
        state='readonly',
        width=22
    )
    app.filter_conflicto_combo.pack(side=tk.LEFT, padx=(0, 10))
    app.filter_conflicto_combo.bind('<<ComboboxSelected>>', lambda e: app._filtrar_resultados())
    
    # ===== BOTONES DE ACCIÓN (Primera línea) =====
    btn_frame = tk.Frame(toolbar, bg=app.colors['bg_primary'])
    btn_frame.pack(side=tk.RIGHT)
    
    btn_cargar = tk.Button(
        btn_frame,
        text="📂 Cargar",
        command=app._cargar_resultados,
        bg=app.colors['info'],
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        relief=tk.FLAT,
        padx=15,
        pady=8
    )
    btn_cargar.pack(side=tk.LEFT, padx=3)
    ToolTip(btn_cargar, "Carga un archivo Excel de resultados previos.\nBusca archivos *_filtrado.xlsx")
    
    btn_exportar = tk.Button(
        btn_frame,
        text="💾 Exportar",
        command=app._exportar_excel,
        bg=app.colors['success'],
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        relief=tk.FLAT,
        padx=15,
        pady=8
    )
    btn_exportar.pack(side=tk.LEFT, padx=3)
    ToolTip(btn_exportar, "Exporta los resultados filtrados a un nuevo archivo Excel.\nRespeta el filtro activo (Todos/Incluidas/Excluidas)")
    
    btn_actualizar = tk.Button(
        btn_frame,
        text="🔄 Actualizar",
        command=app._actualizar_resultados,
        bg=app.colors['accent_violet'],
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        relief=tk.FLAT,
        padx=15,
        pady=8
    )
    btn_actualizar.pack(side=tk.LEFT, padx=3)
    ToolTip(btn_actualizar, "Recarga los resultados del archivo actual.\nÚtil después de procesar nuevas noticias")
    
    # ===== SEGUNDA LÍNEA: Reportes e IA =====
    reportes_frame = tk.Frame(container, bg=app.colors['bg_primary'])
    reportes_frame.pack(fill=tk.X, pady=(5, 10))
    
    tk.Label(
        reportes_frame,
        text="📊 Reportes:",
        font=("Segoe UI", 11, "bold"),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_primary']
    ).pack(side=tk.LEFT, padx=(0, 10))
    
    btn_generar_reporte = tk.Button(
        reportes_frame,
        text="📄 Generar Reporte Completo",
        command=app._generar_reporte_exhaustivo,
        bg="#FF6B35",  # Naranja
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        relief=tk.FLAT,
        padx=15,
        pady=8
    )
    btn_generar_reporte.pack(side=tk.LEFT, padx=3)
    ToolTip(btn_generar_reporte, "Genera reporte TXT + gráficos PNG + métricas JSON\nIncluye nube de palabras, evolución temporal, etc.")
    
    app.btn_analizar_ia = tk.Button(
        reportes_frame,
        text="🤖 Analizar con IA + Word/PDF",
        command=app._analizar_reporte_con_ia,
        bg="#9B59B6",  # Púrpura
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        relief=tk.FLAT,
        padx=15,
        pady=8,
        state=tk.DISABLED  # Deshabilitado hasta que se genere un reporte
    )
    app.btn_analizar_ia.pack(side=tk.LEFT, padx=3)
    ToolTip(app.btn_analizar_ia, "Analiza reporte + gráficos con IA\nGenera Word/PDF profesional con gráficos incluidos")
    
    # TreeView para mostrar resultados
    tree_frame = tk.Frame(container, bg=app.colors['bg_primary'])
    tree_frame.pack(fill=tk.BOTH, expand=True)
    
    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    
    # TreeView
    columns = ("ID", "Título", "Tipo Conflicto", "Región", "Fecha", "Estado")
    app.tree_resultados = ttk.Treeview(
        tree_frame,
        columns=columns,
        show='headings',
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set,
        height=20
    )
    
    vsb.config(command=app.tree_resultados.yview)
    hsb.config(command=app.tree_resultados.xview)
    
    # Configurar columnas
    app.tree_resultados.heading("ID", text="ID", command=lambda: app._ordenar_columna("ID"))
    app.tree_resultados.heading("Título", text="Título", command=lambda: app._ordenar_columna("Título"))
    app.tree_resultados.heading("Tipo Conflicto", text="Tipo Conflicto", command=lambda: app._ordenar_columna("Tipo Conflicto"))
    app.tree_resultados.heading("Región", text="Región", command=lambda: app._ordenar_columna("Región"))
    app.tree_resultados.heading("Fecha", text="Fecha", command=lambda: app._ordenar_columna("Fecha"))
    app.tree_resultados.heading("Estado", text="Estado", command=lambda: app._ordenar_columna("Estado"))
    
    app.tree_resultados.column("ID", width=60, anchor=tk.CENTER)
    app.tree_resultados.column("Título", width=400)
    app.tree_resultados.column("Tipo Conflicto", width=200)
    app.tree_resultados.column("Región", width=120)
    app.tree_resultados.column("Fecha", width=100, anchor=tk.CENTER)
    app.tree_resultados.column("Estado", width=100, anchor=tk.CENTER)
    
    app.tree_resultados.pack(fill=tk.BOTH, expand=True)
    
    # Doble clic para ver detalles
    app.tree_resultados.bind('<Double-1>', app._ver_detalles_noticia)
    
    # Label de información
    app.label_info_resultados = tk.Label(
        container,
        text="No hay resultados cargados. Procesa noticias o carga un archivo existente.",
        font=("Segoe UI", 11),
        bg=app.colors['bg_primary'],
        fg=app.colors['text_secondary']
    )
    app.label_info_resultados.pack(pady=15)

