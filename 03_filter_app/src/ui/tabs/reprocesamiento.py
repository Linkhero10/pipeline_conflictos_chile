"""
PESTAÑA DE RE-PROCESAMIENTO
Interfaz para procesar noticias en Contenido_Manual con cascada completa de scraping
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import os
import logging

logger = logging.getLogger(__name__)

def crear_tab_reprocesamiento(parent, app):
    """Crea la interfaz de re-procesamiento"""
    
    # Frame principal (parent ya es el frame dentro del canvas con scroll)
    main_frame = parent
    
    # ===== TÍTULO =====
    title_frame = tk.Frame(main_frame, bg='#2c3e50', height=80)
    title_frame.pack(fill=tk.X)
    title_frame.pack_propagate(False)
    
    tk.Label(
        title_frame,
        text="🔄 RE-PROCESAMIENTO DE NOTICIAS",
        font=("Segoe UI", 18, "bold"),
        bg='#2c3e50',
        fg='white'
    ).pack(pady=20)
    
    # ===== INFORMACIÓN =====
    info_frame = tk.LabelFrame(
        main_frame,
        text="ℹ️  ¿Qué hace este módulo?",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    info_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
    
    info_text = """Este módulo re-analiza y clasifica noticias de dos hojas:

📋 CONTENIDO_MANUAL:
• Noticias SIN contenido (requieren scraping o pegado manual)
• Flujo: Pegar contenido → Re-analizar → Clasificar

🔍 REVISION_MANUAL:
• Noticias CON contenido pero que IA marcó para validación humana
• Flujo: Ajustar prompt/código → Re-analizar → Reclasificar automáticamente

FLUJO RECOMENDADO:
1. Seleccionar hoja a procesar (Contenido_Manual o Revision_manual)
2. Para Contenido_Manual: Pegar contenido en columna 'contenido_noticia'
3. Para Revision_manual: Ajustar prompt/código según análisis de errores
4. Presionar "RE-ANALIZAR Y CLASIFICAR"
5. Sistema analiza con IA y clasifica automáticamente"""
    
    tk.Label(
        info_frame,
        text=info_text,
        font=("Segoe UI", 9),
        bg="#f8f9fa",
        fg="#2c3e50",
        justify=tk.LEFT
    ).pack()
    
    # ===== SELECCIÓN DE ARCHIVO =====
    file_frame = tk.LabelFrame(
        main_frame,
        text="📁 Archivo Excel Filtrado",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    file_frame.pack(fill=tk.X, padx=20, pady=10)
    
    app.excel_reprocesar = tk.StringVar()
    
    entry_frame = tk.Frame(file_frame, bg="#f8f9fa")
    entry_frame.pack(fill=tk.X)
    
    tk.Entry(
        entry_frame,
        textvariable=app.excel_reprocesar,
        font=("Segoe UI", 10),
        width=70
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    tk.Button(
        entry_frame,
        text="📂 Seleccionar",
        command=lambda: seleccionar_excel_reprocesar(app),
        bg="#3498db",
        fg="white",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2"
    ).pack(side=tk.LEFT)
    
    # ===== SELECCIÓN DE HOJA =====
    hoja_frame = tk.LabelFrame(
        main_frame,
        text="📋 Hoja a Procesar",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    hoja_frame.pack(fill=tk.X, padx=20, pady=10)
    
    app.hoja_reprocesar = tk.StringVar(value="Contenido_Manual")
    
    radio_frame = tk.Frame(hoja_frame, bg="#f8f9fa")
    radio_frame.pack(fill=tk.X)
    
    tk.Radiobutton(
        radio_frame,
        text="📋 Contenido_Manual (noticias sin contenido)",
        variable=app.hoja_reprocesar,
        value="Contenido_Manual",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        command=lambda: actualizar_stats_reprocesar(app)
    ).pack(anchor=tk.W, pady=5)
    
    tk.Radiobutton(
        radio_frame,
        text="🔍 Revision_manual (noticias que requieren revisión)",
        variable=app.hoja_reprocesar,
        value="Revision_manual",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        command=lambda: actualizar_stats_reprocesar(app)
    ).pack(anchor=tk.W, pady=5)
    
    # ===== ESTADÍSTICAS PREVIAS =====
    stats_frame = tk.LabelFrame(
        main_frame,
        text="📊 Estadísticas de Contenido_Manual",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    stats_frame.pack(fill=tk.X, padx=20, pady=10)
    
    app.label_stats_reprocesar = tk.Label(
        stats_frame,
        text="Selecciona un archivo para ver estadísticas...",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        fg="#7f8c8d",
        justify=tk.LEFT
    )
    app.label_stats_reprocesar.pack()
    
    # ===== BOTÓN PRINCIPAL =====
    btn_frame = tk.Frame(main_frame, bg='#1e1e2e')
    btn_frame.pack(fill=tk.X, padx=20, pady=20)
    
    # Botón único para re-analizar y clasificar noticias con contenido manual
    app.btn_analizar_clasificar = tk.Button(
        btn_frame,
        text="🔍 RE-ANALIZAR Y CLASIFICAR (Noticias con contenido manual)",
        command=lambda: iniciar_analisis_clasificacion(app),
        bg="#3498db",
        fg="white",
        font=("Segoe UI", 13, "bold"),
        height=2,
        cursor="hand2"
    )
    app.btn_analizar_clasificar.pack(fill=tk.X, pady=(0, 10))
    
    # Botón para procesar decisiones manuales de Revision_manual
    app.btn_procesar_decisiones = tk.Button(
        btn_frame,
        text="📋 PROCESAR DECISIONES (Revision_manual → Filtrado/Excluido)",
        command=lambda: procesar_decisiones_manuales(app),
        bg="#9b59b6",
        fg="white",
        font=("Segoe UI", 12, "bold"),
        height=2,
        cursor="hand2"
    )
    app.btn_procesar_decisiones.pack(fill=tk.X)
    
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
    app.stat_labels_reprocesar = {}
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
        app.stat_labels_reprocesar[key] = stat_label
    
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
        app.stat_labels_reprocesar[key] = stat_label
    
    # Configurar grid para que se expanda uniformemente
    for i in range(4):
        stats_grid.columnconfigure(i, weight=1)
    
    # ===== PROGRESO =====
    progreso_frame = tk.LabelFrame(
        main_frame,
        text="📈 Progreso del Re-procesamiento",
        font=("Segoe UI", 11, "bold"),
        padx=20,
        pady=15,
        bg="#f8f9fa"
    )
    progreso_frame.pack(fill=tk.X, padx=20, pady=10)
    
    app.progress_bar_reprocesar = ttk.Progressbar(
        progreso_frame,
        style='Modern.Horizontal.TProgressbar',
        mode='determinate',
        length=700
    )
    app.progress_bar_reprocesar.pack(pady=5)
    
    app.label_progreso_reprocesar = tk.Label(
        progreso_frame,
        text="Esperando inicio...",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        fg="#34495e"
    )
    app.label_progreso_reprocesar.pack(pady=5)
    
    # ===== LOGS DUALES (APP + CONSOLA) =====
    logs_container = tk.Frame(main_frame, bg="#f8f9fa")
    logs_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    # LOG DE LA APP (Izquierda)
    log_app_frame = tk.LabelFrame(
        logs_container,
        text="📝 Log de Re-procesamiento (App)",
        font=("Segoe UI", 11, "bold"),
        padx=10,
        pady=10,
        bg="#f8f9fa"
    )
    log_app_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    
    app.log_reprocesar = scrolledtext.ScrolledText(
        log_app_frame,
        height=15,
        font=("Consolas", 9),
        bg="#2b2b2b",
        fg="#00ff00",
        wrap=tk.WORD,
        insertbackground="white"
    )
    app.log_reprocesar.pack(fill=tk.BOTH, expand=True)
    
    # Configurar tags para colores en log de app
    app.log_reprocesar.tag_config('INFO', foreground='#89b4fa')
    app.log_reprocesar.tag_config('SUCCESS', foreground='#a6e3a1')
    app.log_reprocesar.tag_config('WARNING', foreground='#f9e2af')
    app.log_reprocesar.tag_config('ERROR', foreground='#f38ba8')
    
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
    
    app.console_reprocesar = scrolledtext.ScrolledText(
        log_console_frame,
        height=15,
        font=("Consolas", 9),
        bg="#1e1e2e",
        fg="#cdd6f4",
        wrap=tk.WORD,
        insertbackground="white"
    )
    app.console_reprocesar.pack(fill=tk.BOTH, expand=True)
    
    # Configurar tags para colores en consola
    app.console_reprocesar.tag_config('DEBUG', foreground='#89dceb')
    app.console_reprocesar.tag_config('PRINT', foreground='#f5e0dc')
    app.console_reprocesar.tag_config('SUCCESS', foreground='#a6e3a1')
    app.console_reprocesar.tag_config('WARNING', foreground='#f9e2af')
    app.console_reprocesar.tag_config('ERROR', foreground='#f38ba8')
    app.console_reprocesar.tag_config('SEPARATOR', foreground='#fab387')

def seleccionar_excel_reprocesar(app):
    """Selecciona archivo Excel filtrado"""
    archivo = filedialog.askopenfilename(
        title="Seleccionar Excel Filtrado",
        filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
        initialdir=os.path.dirname(app.archivo_excel.get()) if app.archivo_excel.get() else None
    )
    if archivo:
        app.excel_reprocesar.set(archivo)
        # Actualizar estadísticas
        actualizar_stats_reprocesar(app, archivo)

def actualizar_stats_reprocesar(app, excel_path=None):
    """Actualiza las estadísticas de la hoja seleccionada"""
    try:
        import pandas as pd
        
        # Usar el archivo actual si no se proporciona uno
        if excel_path is None:
            excel_path = app.excel_reprocesar.get()
        
        if not excel_path or not os.path.exists(excel_path):
            app.label_stats_reprocesar.config(
                text="Selecciona un archivo para ver estadísticas...",
                fg="#7f8c8d"
            )
            return
        
        # Obtener hoja seleccionada
        hoja = app.hoja_reprocesar.get()
        
        # Leer hoja correspondiente
        df = pd.read_excel(excel_path, sheet_name=hoja)
        
        total = len(df)
        
        if hoja == 'Contenido_Manual':
            pendientes = len(df[df['estado'] == 'Pendiente'])
            recuperadas = len(df[df['estado'] == 'Recuperado'])
            requieren_humano = len(df[df['estado'] == 'Requiere humano'])
            
            stats_text = f"""📊 Estadísticas de Contenido_Manual:

• Total de noticias: {total}
• Pendientes de procesar: {pendientes}
• Ya recuperadas: {recuperadas}
• Requieren intervención humana: {requieren_humano}

{f'✅ Listo para procesar {pendientes} noticias' if pendientes > 0 else 'ℹ️  No hay noticias pendientes'}"""
        
        else:  # Revision_manual
            # Contar noticias que requieren revisión
            stats_text = f"""📊 Estadísticas de Revision_manual:

• Total de noticias: {total}
• Todas requieren re-análisis con IA

✅ Listo para re-analizar {total} noticias
💡 Ajusta el prompt/código antes de procesar"""
        
        app.label_stats_reprocesar.config(text=stats_text, fg="#2c3e50")
        
    except Exception as e:
        app.label_stats_reprocesar.config(
            text=f"⚠️  No se pudo leer la hoja {app.hoja_reprocesar.get()}:\n{str(e)[:100]}",
            fg="#e74c3c"
        )

def iniciar_reprocesamiento(app):
    """Inicia el re-procesamiento en hilo separado"""
    
    excel_path = app.excel_reprocesar.get()
    
    if not excel_path:
        messagebox.showerror("Error", "❌ Debes seleccionar un archivo Excel")
        return
    
    if not os.path.exists(excel_path):
        messagebox.showerror("Error", f"❌ El archivo no existe:\n{excel_path}")
        return
    
    # Confirmar
    respuesta = messagebox.askyesno(
        "Confirmar Re-procesamiento",
        "🔄 ¿Iniciar re-procesamiento de noticias pendientes?\n\n" +
        "Este proceso:\n" +
        "• Aplicará cascada completa de 6 métodos de scraping\n" +
        "• Validará contenido con IA entre cada método\n" +
        "• Actualizará todas las hojas del Excel\n" +
        "• Puede tomar varios minutos\n\n" +
        "¿Continuar?"
    )
    
    if not respuesta:
        return
    
    # Deshabilitar botón
    app.btn_reprocesar.config(state=tk.DISABLED, text="⏳ Procesando...")
    
    # Limpiar log
    app.log_reprocesar.delete(1.0, tk.END)
    app.progress_bar_reprocesar['value'] = 0
    app.label_progreso_reprocesar.config(text="Iniciando...")
    
    # Callbacks
    def callback_progreso(progreso, mensaje):
        app.progress_bar_reprocesar['value'] = progreso
        app.label_progreso_reprocesar.config(text=mensaje)
        app.root.update_idletasks()
    
    def callback_log(mensaje):
        app.log_reprocesar.insert(tk.END, mensaje + "\n")
        app.log_reprocesar.see(tk.END)
        app.root.update_idletasks()
    
    # Ejecutar en hilo
    def ejecutar():
        try:
            from src.core.filtrador import FiltradorIA
            
            callback_log("="*80)
            callback_log("🔄 INICIANDO RE-PROCESAMIENTO")
            callback_log("="*80)
            
            # Crear filtrador
            api_key = app.api_key.get()
            provider = app.provider.get()
            reanalizar = app.reanalizar_reprocesar.get()
            
            if not api_key:
                raise Exception("No hay API key configurada")
            
            callback_log(f"\n🤖 Inicializando FiltradorIA...")
            callback_log(f"   Provider: {provider}")
            callback_log(f"   Modelo: {app.modelo.get()}")
            callback_log(f"   Reanalizar ya procesadas: {'✅ SÍ' if reanalizar else '❌ NO'}")
            
            filtrador = FiltradorIA(api_key=api_key, provider=provider)
            
            # Procesar
            callback_log(f"\n📂 Procesando: {os.path.basename(excel_path)}")
            callback_log("")
            
            stats = filtrador.procesar_scraping_pendiente(
                excel_path,
                callback_progreso=callback_progreso,
                callback_log=callback_log,
                reanalizar=reanalizar
            )
            
            # Mostrar resumen
            tasa_exito = (stats['recuperadas']/stats['total']*100) if stats['total'] > 0 else 0
            
            resumen = f"""
✅ RE-PROCESAMIENTO COMPLETADO

📊 Estadísticas Finales:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Total procesadas: {stats['procesadas']}
• Recuperadas exitosamente: {stats['recuperadas']}
• Requieren intervención humana: {stats['requieren_humano']}
• Errores: {stats['errores']}

📈 Tasa de éxito: {tasa_exito:.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{f'✅ {stats["recuperadas"]} noticias fueron recuperadas y actualizadas en todas las hojas del Excel' if stats['recuperadas'] > 0 else ''}
{f'⚠️  {stats["requieren_humano"]} noticias requieren que insertes el contenido manualmente' if stats['requieren_humano'] > 0 else ''}

💡 Tip: Si hay noticias que requieren humano:
   1. Abre el Excel
   2. Ve a la hoja "Contenido_Manual"
   3. Busca las filas con "HUMANO DEBE INSERTAR"
   4. Copia el contenido de la noticia en la columna "contenido_noticia"
   5. Ejecuta el re-procesamiento de nuevo
"""
            
            callback_log("\n" + resumen)
            messagebox.showinfo("✅ Completado", resumen)
            
            # Actualizar estadísticas
            actualizar_stats_reprocesar(app, excel_path)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ Error en re-procesamiento:\n\n{str(e)}\n\n{traceback.format_exc()}"
            callback_log(f"\n{error_msg}")
            logger.error(f"Error en re-procesamiento: {e}", exc_info=True)
            messagebox.showerror("Error", f"❌ Error en re-procesamiento:\n\n{str(e)}")
        finally:
            app.btn_reprocesar.config(state=tk.NORMAL, text="🚀 INICIAR RE-PROCESAMIENTO")
            callback_progreso(0, "Esperando inicio...")
    
    thread = threading.Thread(target=ejecutar, daemon=True)
    thread.start()


def iniciar_analisis_clasificacion(app):
    """
    Analiza y clasifica noticias desde Contenido_Manual o Revision_manual
    Las inserta en las hojas correspondientes (incluidas/excluidas) eliminando duplicados
    """
    import threading
    from tkinter import messagebox
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Validar que hay archivo seleccionado
    excel_path = app.excel_reprocesar.get()
    if not excel_path or not os.path.exists(excel_path):
        messagebox.showerror(
            "Error",
            "❌ Debes seleccionar un archivo Excel válido primero"
        )
        return
    
    # Obtener hoja seleccionada
    hoja = app.hoja_reprocesar.get()
    
    # Mensaje de confirmación según la hoja
    if hoja == 'Contenido_Manual':
        mensaje_confirmacion = f"""🔍 RE-ANALIZAR Y CLASIFICAR - CONTENIDO_MANUAL

📂 Archivo: {os.path.basename(excel_path)}
📋 Hoja: {hoja}

Este proceso:
✅ Analizará noticias que tengan contenido
✅ Solo procesará noticias con estado vacío (no analizadas)
✅ Las clasificará como incluidas o excluidas
✅ Marcará como 'EXITOSO' las noticias procesadas
✅ Las insertará en las hojas correspondientes

⚠️  IMPORTANTE:
• Solo se procesarán noticias con contenido válido (>200 chars)
• Noticias con estado 'EXITOSO' serán omitidas
• Se añadirá nota de 'INCLUIDA' o 'EXCLUIDA' según resultado

¿Deseas continuar?"""
    else:  # Revision_manual
        mensaje_confirmacion = f"""🔍 RE-ANALIZAR Y RECLASIFICAR - REVISION_MANUAL

📂 Archivo: {os.path.basename(excel_path)}
📋 Hoja: {hoja}

Este proceso:
✅ Re-analizará TODAS las noticias de Revision_manual
✅ Aplicará el prompt y código actualizados
✅ Las reclasificará automáticamente
✅ Las moverá a Datos_filtrados o Datos_excluidos
✅ Eliminará de Revision_manual las que ya no requieren revisión

⚠️  IMPORTANTE:
• Asegúrate de haber ajustado el prompt/código antes de procesar
• Todas las noticias serán re-analizadas desde cero
• Las que sigan requiriendo revisión permanecerán en la hoja

¿Deseas continuar?"""
    
    # Confirmar con el usuario
    confirmacion = messagebox.askyesno(
        "Confirmar Análisis",
        mensaje_confirmacion
    )
    
    if not confirmacion:
        return
    
    # Deshabilitar botón
    app.btn_analizar_clasificar.config(state=tk.DISABLED, text="⏳ Analizando...")
    
    # Limpiar log
    app.log_reprocesar.delete(1.0, tk.END)
    app.progress_bar_reprocesar['value'] = 0
    app.label_progreso_reprocesar.config(text="Iniciando análisis...")
    
    # Callbacks
    def callback_progreso(progreso, mensaje):
        app.progress_bar_reprocesar['value'] = progreso
        app.label_progreso_reprocesar.config(text=mensaje)
        app.root.update_idletasks()
    
    def callback_log(mensaje):
        app.log_reprocesar.insert(tk.END, mensaje + "\n")
        app.log_reprocesar.see(tk.END)
        app.root.update_idletasks()
    
    # Ejecutar en hilo
    def ejecutar():
        try:
            from src.core.filtrador import FiltradorIA
            
            callback_log("="*80)
            callback_log("🔍 INICIANDO ANÁLISIS Y CLASIFICACIÓN")
            callback_log("="*80)
            
            # Crear filtrador
            api_key = app.api_key.get()
            provider = app.provider.get()
            
            if not api_key:
                raise Exception("No hay API key configurada")
            
            callback_log(f"\n🤖 Inicializando FiltradorIA...")
            callback_log(f"   Provider: {provider}")
            callback_log(f"   Modelo: {app.modelo.get()}")
            
            filtrador = FiltradorIA(api_key=api_key, provider=provider)
            
            # Analizar y clasificar según la hoja seleccionada
            callback_log(f"\n📂 Procesando: {os.path.basename(excel_path)}")
            callback_log(f"📋 Hoja: {hoja}")
            callback_log("")
            
            if hoja == 'Contenido_Manual':
                stats = filtrador.analizar_y_clasificar_desde_scraping_pendiente(
                    excel_path,
                    callback_progreso=callback_progreso,
                    callback_log=callback_log
                )
            else:  # Revision_manual
                stats = filtrador.reanalizar_revision_manual(
                    excel_path,
                    callback_progreso=callback_progreso,
                    callback_log=callback_log
                )
            
            # Mostrar resumen
            tasa_exito = (stats['incluidas']/stats['total']*100) if stats['total'] > 0 else 0
            
            resumen = f"""
✅ ANÁLISIS Y CLASIFICACIÓN COMPLETADO

📊 Estadísticas Finales:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Total analizadas: {stats['total']}
• Incluidas: {stats['incluidas']}
• Excluidas: {stats['excluidas']}
• Errores: {stats['errores']}
• Duplicados eliminados: {stats.get('duplicados_eliminados', 0)}

📈 Tasa de inclusión: {tasa_exito:.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Noticias insertadas y ordenadas por ID
✅ Duplicados eliminados automáticamente
"""
            
            callback_log("\n" + resumen)
            messagebox.showinfo("✅ Completado", resumen)
            
            # Actualizar estadísticas
            actualizar_stats_reprocesar(app, excel_path)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ Error en análisis:\n\n{str(e)}\n\n{traceback.format_exc()}"
            callback_log(f"\n{error_msg}")
            logger.error(f"Error en análisis: {e}", exc_info=True)
            messagebox.showerror("Error", f"❌ Error en análisis:\n\n{str(e)}")
        finally:
            app.btn_analizar_clasificar.config(state=tk.NORMAL, text="🔍 RE-ANALIZAR Y CLASIFICAR (Noticias con contenido manual)")
            callback_progreso(0, "Esperando inicio...")
    
    thread = threading.Thread(target=ejecutar, daemon=True)
    thread.start()


def procesar_decisiones_manuales(app):
    """
    Procesa las decisiones del usuario en la hoja Revision_manual.
    El usuario escribe "INCLUIR: razón" o "EXCLUIR: razón" en la columna 'decision_usuario'
    """
    import threading
    from tkinter import messagebox
    import os
    
    # Validar que hay archivo seleccionado
    excel_path = app.excel_reprocesar.get()
    if not excel_path or not os.path.exists(excel_path):
        messagebox.showerror(
            "Error",
            "❌ Debes seleccionar un archivo Excel válido primero"
        )
        return
    
    # Mensaje de confirmación
    mensaje = f"""📋 PROCESAR DECISIONES MANUALES

📂 Archivo: {os.path.basename(excel_path)}

Este proceso lee la columna 'decision_usuario' en Revision_manual y:

✅ Si dice "INCLUIR: razón" → Mueve a Datos_filtrados
❌ Si dice "EXCLUIR: razón" → Mueve a Datos_excluidos

⚠️ INSTRUCCIONES:
1. Abre el Excel y ve a la hoja "Revision_manual"
2. En la columna "decision_usuario", escribe:
   • "INCLUIR: Es un conflicto real porque..."
   • "EXCLUIR: Es solo un anuncio sin oposición"
3. Guarda el Excel
4. Presiona Aceptar para procesar

¿Deseas continuar?"""
    
    if not messagebox.askyesno("Confirmar", mensaje):
        return
    
    # Callbacks
    def callback_log(msg):
        if hasattr(app, 'log_text_reprocesar'):
            app.log_text_reprocesar.insert(tk.END, msg + "\n")
            app.log_text_reprocesar.see(tk.END)
            app.log_text_reprocesar.update()
    
    def callback_progreso(actual, total, msg=""):
        if hasattr(app, 'progress_reprocesar'):
            if total > 0:
                app.progress_reprocesar['value'] = (actual / total) * 100
            app.progress_reprocesar.update()
    
    def ejecutar():
        try:
            app.btn_procesar_decisiones.config(state=tk.DISABLED, text="⏳ Procesando...")
            
            callback_log("")
            callback_log("=" * 50)
            callback_log("📋 PROCESANDO DECISIONES MANUALES")
            callback_log("=" * 50)
            callback_log("")
            
            # Importar función de procesamiento
            from src.core.reprocesamiento import procesar_decisiones_revision_manual
            
            # Ejecutar
            stats = procesar_decisiones_revision_manual(
                excel_path,
                callback_log=callback_log,
                callback_progreso=callback_progreso
            )
            
            # Mostrar resumen
            resumen = f"""✅ DECISIONES PROCESADAS

📊 Resultados:
• Incluidas: {stats['incluidas']}
• Excluidas: {stats['excluidas']}
• Pendientes: {stats['pendientes']}
• Errores: {stats['errores']}

Las noticias han sido movidas a sus hojas correspondientes."""
            
            messagebox.showinfo("✅ Completado", resumen)
            
            # Actualizar estadísticas
            actualizar_stats_reprocesar(app, excel_path)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ Error procesando decisiones:\n\n{str(e)}\n\n{traceback.format_exc()}"
            callback_log(f"\n{error_msg}")
            messagebox.showerror("Error", f"❌ Error:\n\n{str(e)}")
        finally:
            app.btn_procesar_decisiones.config(state=tk.NORMAL, text="📋 PROCESAR DECISIONES (Revision_manual → Filtrado/Excluido)")
    
    thread = threading.Thread(target=ejecutar, daemon=True)
    thread.start()
