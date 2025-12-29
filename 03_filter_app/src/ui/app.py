"""
INTERFAZ GRÁFICA - FILTRADOR AUTOMÁTICO FONDECYT
App con GUI para filtrar noticias usando IA
Versión modularizada manteniendo funcionalidad original
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import os
import json
import pandas as pd
import sys
import webbrowser
import logging
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.core.pipeline_orchestrator import FiltradorIA

# Configurar logger
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
# CRÍTICO: Especificar ruta absoluta del .env para que funcione desde cualquier directorio
import os
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)

# Verificar que las variables se cargaron
_api_key_check = os.getenv('OPENROUTER_API_KEY')
if not _api_key_check:
    logger.warning("⚠️ OPENROUTER_API_KEY no encontrada en .env")
else:
    logger.info(f"✅ OPENROUTER API Key cargada: {_api_key_check[:20]}...")

# ===== CLASE PARA CAPTURAR STDOUT Y REDIRIGIR A CONSOLA =====
class ConsoleRedirector:
    """Redirige stdout (prints) al widget de consola en la interfaz"""
    def __init__(self, text_widget, tag='PRINT'):
        self.text_widget = text_widget
        self.tag = tag
        self.original_stdout = sys.stdout
        
    def write(self, message):
        """Escribe el mensaje en el widget de consola"""
        if message.strip():  # Solo si no es vacío
            try:
                self.text_widget.insert(tk.END, message, self.tag)
                self.text_widget.see(tk.END)
                self.text_widget.update_idletasks()
            except Exception as e:
                # Si falla la escritura en UI, no bloquear el proceso
                pass
        # También escribir en stdout original (para el log de PowerShell)
        try:
            self.original_stdout.write(message)
            self.original_stdout.flush()
        except Exception as e:
            # Si falla la escritura en stdout original, continuar
            pass
    
    def flush(self):
        """Método flush requerido por stdout"""
        try:
            self.original_stdout.flush()
        except Exception as e:
            # Si falla el flush, continuar
            pass

# ===== HANDLER DE LOGGING PARA LA CONSOLA DE LA APP =====
import logging

class TextWidgetHandler(logging.Handler):
    """Handler de logging que escribe en un widget de texto de Tkinter"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        
    def emit(self, record):
        """Emite un registro de log al widget de texto"""
        try:
            msg = self.format(record)
            self.text_widget.insert(tk.END, msg + '\n', 'LOG')
            self.text_widget.see(tk.END)
            self.text_widget.update_idletasks()
        except:
            pass  # Si falla, no bloquear

# Imports para gráficos
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import seaborn as sns
import numpy as np

from .utils import ToolTip
# Imports de tabs
from .tabs.procesamiento import crear_tab_procesamiento
from .tabs.resultados import crear_tab_resultados
from .tabs.graficos import crear_tab_graficos
from .tabs.perfiles import crear_tab_perfiles
from .tabs.reprocesamiento import crear_tab_reprocesamiento
# Imports de features V3
from .features_v3 import (
    configurar_logging,
    validar_configuracion_exhaustiva,
    cleanup_al_cerrar,
    cargar_configuracion
)

# Configurar estilo de gráficos
sns.set_style("darkgrid")
plt.rcParams['figure.facecolor'] = '#0f172a'
plt.rcParams['axes.facecolor'] = '#1e293b'
plt.rcParams['text.color'] = '#f8fafc'
plt.rcParams['axes.labelcolor'] = '#f8fafc'
plt.rcParams['xtick.color'] = '#f8fafc'
plt.rcParams['ytick.color'] = '#f8fafc'
plt.rcParams['grid.color'] = '#334155'
plt.rcParams['grid.alpha'] = 0.3

class FiltradorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Filtrador IA - FONDECYT | Análisis de Conflictos Socioambientales")
        self.root.geometry("1500x950")
        self.root.configure(bg='#1e1e2e')
        
        # Hacer la ventana redimensionable
        self.root.resizable(True, True)
        
        # ===== FEATURE V3: Configurar logging con rotación =====
        self.logger = configurar_logging()
        self.logger.info("Aplicación iniciada")
        
        # ===== FEATURE V3: Configurar cleanup al cerrar =====
        self.root.protocol("WM_DELETE_WINDOW", lambda: cleanup_al_cerrar(self))
        
        # Variables de tiempo
        self.tiempo_inicio = None
        self.tiempo_por_noticia = []
        
        # Variables para resultados
        self.df_resultados = None
        self.df_filtrado = None
        self.search_var = None
        self.filter_tipo = None
        self.tree_resultados = None
        self.label_info_resultados = None
        self.archivo_actual = None  # Para guardar el archivo Excel actual
        
        # Variables para reportes
        self.ultimo_reporte_generado = None  # Ruta del último reporte generado
        self.btn_analizar_ia = None  # Referencia al botón de análisis IA
        
        # Variables para perfiles
        self.listbox_perfiles = None
        
        # Configurar estilos modernos
        self._configurar_estilos()
        
        # Variables
        self.archivo_excel = tk.StringVar()
        # Cargar API key desde .env (seguro) - Priorizar OpenRouter
        default_api_key = os.getenv('OPENROUTER_API_KEY', '') or os.getenv('ABACUS_API_KEY', '')
        self.api_key = tk.StringVar(value=default_api_key)
        self.provider = tk.StringVar(value=os.getenv('PROVIDER', 'openrouter'))
        self.modelo = tk.StringVar(value=os.getenv('MODELO', 'google/gemini-3-flash-preview'))
        self.indice_inicio = tk.IntVar(value=0)
        self.indice_fin = tk.IntVar(value=100)
        self.hoja_excel = tk.StringVar(value="Datos_enriquecidos")
        self.sector_economico = tk.StringVar()
        self.procesando = False
        self.filtrador = None
        
        # Estadísticas en tiempo real
        self.stats_realtime = {
            'total': 0,
            'procesadas': 0,
            'incluidas': 0,
            'excluidas': 0,
            'errores': 0
        }
        
        self.crear_interfaz()
        
        # ===== FEATURE V3: Cargar configuración guardada automáticamente =====
        exitoso, mensaje = cargar_configuracion(self)
        if exitoso:
            self.logger.info(f"Configuración cargada: {mensaje}")
        else:
            self.logger.info("No hay configuración previa guardada")
    
    def _configurar_estilos(self):
        """Configura los estilos de ttk"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colores del tema moderno
        self.colors = {
            'bg_primary': '#0f172a',
            'bg_secondary': '#1e293b',
            'bg_card': '#334155',
            'accent_violet': '#8b5cf6',
            'accent_purple': '#a855f7',
            'text_primary': '#f8fafc',
            'text_secondary': '#94a3b8',
            'success': '#10b981',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'info': '#3b82f6',
            'border': '#475569'
        }
        
        # Estilo para progressbar
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['accent_violet'],
                       troughcolor=self.colors['bg_card'],
                       borderwidth=0,
                       thickness=25)
    
    def crear_interfaz(self):
        """Crea todos los elementos de la interfaz con scroll"""
        
        # ===== HEADER MODERNO =====
        header_frame = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=110)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)
        
        # Contenedor centrado
        header_content = tk.Frame(header_frame, bg=self.colors['bg_secondary'])
        header_content.pack(expand=True)
        
        # Frame para icono y títulos
        title_frame = tk.Frame(header_content, bg=self.colors['bg_secondary'])
        title_frame.pack()
        
        # Icono grande
        tk.Label(
            title_frame,
            text="✨",
            font=("Segoe UI", 36),
            bg=self.colors['bg_secondary'],
            fg=self.colors['accent_violet']
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        # Títulos
        titles_container = tk.Frame(title_frame, bg=self.colors['bg_secondary'])
        titles_container.pack(side=tk.LEFT)
        
        tk.Label(
            titles_container,
            text="Filtrador Automático con IA",
            font=("Segoe UI", 26, "bold"),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        ).pack(anchor=tk.W)
        
        tk.Label(
            titles_container,
            text="FONDECYT 1231353 - Análisis Inteligente de Conflictos Socioambientales",
            font=("Segoe UI", 11),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary']
        ).pack(anchor=tk.W, pady=(3, 0))
        
        # ===== SISTEMA DE PESTAÑAS =====
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # Pestaña 1: Procesamiento
        tab_procesamiento = tk.Frame(notebook, bg='#1e1e2e')
        notebook.add(tab_procesamiento, text="  🚀 Procesamiento  ")
        
        # Pestaña 2: Resultados
        tab_resultados = tk.Frame(notebook, bg='#1e1e2e')
        notebook.add(tab_resultados, text="  📊 Resultados  ")
        
        # Pestaña 3: Gráficos
        tab_graficos = tk.Frame(notebook, bg='#0f172a')
        notebook.add(tab_graficos, text="  📈 Gráficos  ")
        
        # Pestaña 4: Perfiles
        tab_perfiles = tk.Frame(notebook, bg='#1e1e2e')
        notebook.add(tab_perfiles, text="  ⚙️ Perfiles  ")
        
        # Pestaña 5: Mapas
        tab_mapas = tk.Frame(notebook, bg='#1e1e2e')
        notebook.add(tab_mapas, text="  🗺️ Mapas  ")
        
        # Pestaña 6: Re-procesamiento
        tab_reprocesamiento = tk.Frame(notebook, bg='#1e1e2e')
        notebook.add(tab_reprocesamiento, text="  🔄 Re-procesamiento  ")
        
        # Configurar scroll para re-procesamiento
        canvas_reprocesar = tk.Canvas(tab_reprocesamiento, bg='#1e1e2e', highlightthickness=0)
        scrollbar_reprocesar = ttk.Scrollbar(tab_reprocesamiento, orient="vertical", command=canvas_reprocesar.yview)
        main_frame_reprocesar = tk.Frame(canvas_reprocesar, bg='#1e1e2e')
        
        canvas_window_reprocesar = canvas_reprocesar.create_window((0, 0), window=main_frame_reprocesar, anchor="nw")
        
        # Función para actualizar scroll region
        def on_frame_configure_reprocesar(event=None):
            canvas_reprocesar.configure(scrollregion=canvas_reprocesar.bbox("all"))
        
        main_frame_reprocesar.bind("<Configure>", on_frame_configure_reprocesar)
        
        # Función para ajustar ancho del frame al canvas
        def on_canvas_configure_reprocesar(event):
            canvas_reprocesar.itemconfig(canvas_window_reprocesar, width=event.width)
        
        canvas_reprocesar.bind("<Configure>", on_canvas_configure_reprocesar)
        canvas_reprocesar.configure(yscrollcommand=scrollbar_reprocesar.set)
        
        canvas_reprocesar.pack(side="left", fill="both", expand=True)
        scrollbar_reprocesar.pack(side="right", fill="y")
        
        def on_mousewheel_reprocesar(event):
            canvas_reprocesar.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_reprocesar(event):
            canvas_reprocesar.bind_all("<MouseWheel>", on_mousewheel_reprocesar)
        
        def unbind_mousewheel_reprocesar(event):
            canvas_reprocesar.unbind_all("<MouseWheel>")
        
        canvas_reprocesar.bind("<Enter>", bind_mousewheel_reprocesar)
        canvas_reprocesar.bind("<Leave>", unbind_mousewheel_reprocesar)
        
        # Configurar scroll para procesamiento
        canvas = tk.Canvas(tab_procesamiento, bg='#1e1e2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_procesamiento, orient="vertical", command=canvas.yview)
        main_frame = tk.Frame(canvas, bg='#1e1e2e')
        
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Función para actualizar scroll region
        def on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        main_frame.bind("<Configure>", on_frame_configure)
        
        # Función para ajustar ancho del frame al canvas
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_mousewheel_procesamiento(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_procesamiento(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel_procesamiento)
        
        def unbind_mousewheel_procesamiento(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel_procesamiento)
        canvas.bind("<Leave>", unbind_mousewheel_procesamiento)
        
        # Crear interfaces de cada pestaña usando las funciones importadas
        crear_tab_procesamiento(main_frame, self)
        crear_tab_resultados(tab_resultados, self)
        crear_tab_graficos(tab_graficos, self)
        crear_tab_perfiles(tab_perfiles, self)
        crear_tab_mapas(tab_mapas, self)
        crear_tab_reprocesamiento(main_frame_reprocesar, self)
        
        # ===== ACTIVAR REDIRECCIÓN DE CONSOLA =====
        # Redirigir stdout (prints) al panel de consola
        if hasattr(self, 'console_text'):
            self.console_redirector = ConsoleRedirector(self.console_text, 'PRINT')
            sys.stdout = self.console_redirector
            
            # NUEVO: Agregar handler de logging para capturar todos los logs
            text_handler = TextWidgetHandler(self.console_text)
            # Formato igual al de PowerShell
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            text_handler.setFormatter(formatter)
            
            # Agregar el handler al logger raíz (captura TODOS los logs)
            root_logger = logging.getLogger()
            root_logger.addHandler(text_handler)
            
            print("=" * 80)
            print("💻 CONSOLA DE DEBUG ACTIVADA")
            print("=" * 80)
            print("✅ Todos los prints Y logs del código ahora aparecerán aquí")
            print("📝 Log de la app (izquierda) + Consola/Prints/Logs (derecha)")
            print("=" * 80)
        
        # ===== FOOTER =====
        footer_frame = tk.Frame(self.root, bg="#ecf0f1", height=40)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        footer_frame.pack_propagate(False)
        
        tk.Label(
            footer_frame,
            text="FONDECYT 1231353 | Desarrollado con ❤️ para investigación académica",
            bg="#ecf0f1",
            font=("Segoe UI", 9),
            fg="#7f8c8d"
        ).pack(pady=10)

    def _inicializar_graficos_vacios(self):
        """Inicializa los gráficos con mensaje de 'Sin datos'"""
        for ax in [self.ax_pie, self.ax_tipos, self.ax_regiones, self.ax_acciones, self.ax_motivos, self.ax_actores, self.ax_temporal]:
            ax.clear()
            ax.text(0.5, 0.5, 'Sin datos\nProcesa noticias para ver gráficos', 
                   ha='center', va='center', fontsize=12, color='#94a3b8',
                   transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)
        
        self.canvas_graficos.draw()
    

    def _actualizar_graficos(self):
        """Actualiza todos los gráficos con los datos actuales"""
        # Obtener datos actuales
        base, ext = os.path.splitext(self.archivo_excel.get())
        output_path = f"{base}_filtrado.xlsx"
        
        if not os.path.exists(output_path):
            # NO mostrar popup durante procesamiento - solo retornar silenciosamente
            return
        
        try:
            # Cargar datos
            df = pd.read_excel(output_path, sheet_name='Datos_completos')
            
            if len(df) == 0:
                # NO mostrar popup durante procesamiento - solo retornar silenciosamente
                return
            
            # Limpiar todos los axes
            for ax in [self.ax_pie, self.ax_tipos, self.ax_regiones, self.ax_acciones, self.ax_motivos, self.ax_actores, self.ax_temporal]:
                ax.clear()
            
            # 1. GRÁFICO CIRCULAR: Incluidas vs Excluidas vs Revisión Manual (ACTUALIZADO)
            incluidas = len(df[df['motivo_exclusion'].isna()])
            excluidas = len(df[df['motivo_exclusion'].notna()])
            revision = len(df[df['requiere_revision_manual'] == True])
            
            colors_pie = ['#10b981', '#ef4444', '#f59e0b']  # Verde, Rojo, Naranja
            explode = (0.05, 0, 0.05)  # Separar incluidas y revisión
            
            # Crear función personalizada para mostrar porcentaje y cantidad
            def autopct_format(pct, allvals):
                absolute = int(pct/100.*sum(allvals))
                return f'{pct:.1f}%\n(n={absolute:,})'
            
            wedges, texts, autotexts = self.ax_pie.pie(
                [incluidas, excluidas, revision],
                labels=['Incluidas\n(Relevantes)', 'Excluidas', 'Requieren\nRevisión'],
                autopct=lambda pct: autopct_format(pct, [incluidas, excluidas, revision]),
                colors=colors_pie,
                explode=explode,
                startangle=90,
                textprops={'color': '#f8fafc', 'fontsize': 9, 'weight': 'bold'}
            )
            
            # Ajustar tamaño de fuente de los porcentajes y cantidades dentro del gráfico
            for autotext in autotexts:
                autotext.set_color('#f8fafc')
                autotext.set_fontsize(8)
                autotext.set_weight('bold')
            
            self.ax_pie.set_title(f'Distribución de Noticias Procesadas\n(Total: {len(df):,})', 
                                 color='#f8fafc', fontsize=12, weight='bold', pad=15)
            
            # 2. TIPOS DE CONFLICTO (Top 10)
            tipos = df[df['tipo_conflicto'].notna()]['tipo_conflicto'].value_counts().head(10)
            
            if len(tipos) > 0:
                bars = self.ax_tipos.barh(range(len(tipos)), tipos.values, color='#3b82f6')
                self.ax_tipos.set_yticks(range(len(tipos)))
                self.ax_tipos.set_yticklabels([t[:30] + '...' if len(t) > 30 else t for t in tipos.index], 
                                             fontsize=8)
                self.ax_tipos.set_xlabel('Cantidad', color='#f8fafc', fontsize=9)
                self.ax_tipos.set_title('Top 10 Tipos de Conflicto', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                self.ax_tipos.invert_yaxis()
                
                # Agregar valores en las barras
                for i, (bar, value) in enumerate(zip(bars, tipos.values)):
                    self.ax_tipos.text(value, i, f' {value}', va='center', color='#f8fafc', fontsize=8)
            else:
                self.ax_tipos.text(0.5, 0.5, 'Sin datos de tipos de conflicto', 
                                  ha='center', va='center', color='#94a3b8', transform=self.ax_tipos.transAxes)
            
            # 3. DISTRIBUCIÓN POR REGIÓN (Top 10)
            regiones = df[df['region'].notna()]['region'].value_counts().head(10)
            
            if len(regiones) > 0:
                bars = self.ax_regiones.barh(range(len(regiones)), regiones.values, color='#8b5cf6')
                self.ax_regiones.set_yticks(range(len(regiones)))
                self.ax_regiones.set_yticklabels([r[:25] + '...' if len(r) > 25 else r for r in regiones.index], 
                                                fontsize=8)
                self.ax_regiones.set_xlabel('Cantidad', color='#f8fafc', fontsize=9)
                self.ax_regiones.set_title('Top 10 Regiones', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                self.ax_regiones.invert_yaxis()
                
                # Agregar valores
                for i, (bar, value) in enumerate(zip(bars, regiones.values)):
                    self.ax_regiones.text(value, i, f' {value}', va='center', color='#f8fafc', fontsize=8)
            else:
                self.ax_regiones.text(0.5, 0.5, 'Sin datos de regiones', 
                                     ha='center', va='center', color='#94a3b8', transform=self.ax_regiones.transAxes)
            
            # 4. TIPOS DE ACCIÓN CONTENCIOSA (Top 10)
            acciones = df[df['tipo_accion'].notna()]['tipo_accion'].value_counts().head(10)
            
            if len(acciones) > 0:
                bars = self.ax_acciones.bar(range(len(acciones)), acciones.values, color='#f59e0b')
                self.ax_acciones.set_xticks(range(len(acciones)))
                self.ax_acciones.set_xticklabels([a[:15] + '...' if len(a) > 15 else a for a in acciones.index], 
                                                rotation=45, ha='right', fontsize=8)
                self.ax_acciones.set_ylabel('Cantidad', color='#f8fafc', fontsize=9)
                self.ax_acciones.set_title('Top 10 Tipos de Acción', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                
                # Agregar valores encima de las barras
                for bar, value in zip(bars, acciones.values):
                    height = bar.get_height()
                    self.ax_acciones.text(bar.get_x() + bar.get_width()/2., height,
                                         f'{int(value)}', ha='center', va='bottom', color='#f8fafc', fontsize=8)
            else:
                self.ax_acciones.text(0.5, 0.5, 'Sin datos de tipos de acción', 
                                     ha='center', va='center', color='#94a3b8', transform=self.ax_acciones.transAxes)
            
            # 5. MOTIVOS DE EXCLUSIÓN (Top 5) - NUEVO
            motivos = df[df['motivo_exclusion'].notna()]['motivo_exclusion'].value_counts().head(5)
            
            if len(motivos) > 0:
                bars = self.ax_motivos.barh(range(len(motivos)), motivos.values, color='#ef4444')
                self.ax_motivos.set_yticks(range(len(motivos)))
                self.ax_motivos.set_yticklabels([m[:25] + '...' if len(m) > 25 else m for m in motivos.index], 
                                               fontsize=8)
                self.ax_motivos.set_xlabel('Cantidad', color='#f8fafc', fontsize=9)
                self.ax_motivos.set_title('Top 5 Motivos de Exclusión', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                self.ax_motivos.invert_yaxis()
                
                # Agregar valores
                for i, (bar, value) in enumerate(zip(bars, motivos.values)):
                    self.ax_motivos.text(value, i, f' {value}', va='center', color='#f8fafc', fontsize=8)
            else:
                self.ax_motivos.text(0.5, 0.5, 'Sin motivos de exclusión', 
                                    ha='center', va='center', color='#94a3b8', transform=self.ax_motivos.transAxes)
            
            # 6. TOP ACTORES (Top 10) - NUEVO
            actores_demandantes = df[df['actor_demandante'].notna()]['actor_demandante'].value_counts().head(5)
            actores_demandados = df[df['actor_demandado'].notna()]['actor_demandado'].value_counts().head(5)
            
            # Combinar y tomar top 10
            todos_actores = pd.concat([actores_demandantes, actores_demandados]).groupby(level=0).sum().nlargest(10)
            
            if len(todos_actores) > 0:
                bars = self.ax_actores.barh(range(len(todos_actores)), todos_actores.values, color='#06b6d4')
                self.ax_actores.set_yticks(range(len(todos_actores)))
                self.ax_actores.set_yticklabels([a[:25] + '...' if len(a) > 25 else a for a in todos_actores.index], 
                                               fontsize=8)
                self.ax_actores.set_xlabel('Menciones', color='#f8fafc', fontsize=9)
                self.ax_actores.set_title('Top 10 Actores Involucrados', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                self.ax_actores.invert_yaxis()
                
                # Agregar valores
                for i, (bar, value) in enumerate(zip(bars, todos_actores.values)):
                    self.ax_actores.text(value, i, f' {int(value)}', va='center', color='#f8fafc', fontsize=8)
            else:
                self.ax_actores.text(0.5, 0.5, 'Sin datos de actores', 
                                    ha='center', va='center', color='#94a3b8', transform=self.ax_actores.transAxes)
            
            # 7. LÍNEA TEMPORAL DE CONFLICTOS POR AÑO (ACTUALIZADO)
            if 'fecha' in df.columns and df['fecha'].notna().sum() > 0:
                # Convertir fechas y filtrar solo incluidas
                df_incluidas = df[df['motivo_exclusion'].isna()].copy()
                df_incluidas['fecha'] = pd.to_datetime(df_incluidas['fecha'], errors='coerce')
                df_incluidas = df_incluidas[df_incluidas['fecha'].notna()]
                
                if len(df_incluidas) > 0:
                    # Agrupar por AÑO (no por mes)
                    df_incluidas['año'] = df_incluidas['fecha'].dt.year
                    conflictos_año = df_incluidas.groupby('año').size()
                    
                    # Graficar
                    años = conflictos_año.index.tolist()
                    valores = conflictos_año.values
                    
                    self.ax_temporal.plot(años, valores, color='#10b981', linewidth=2.5, marker='o', markersize=8, markerfacecolor='#ef4444')
                    self.ax_temporal.fill_between(años, valores, alpha=0.3, color='#10b981')
                    
                    # Añadir línea de tendencia polinomial
                    if len(años) >= 3:
                        z = np.polyfit(años, valores, 2)
                        p = np.poly1d(z)
                        self.ax_temporal.plot(años, p(años), "--", alpha=0.8, color='#ef4444', linewidth=2, label='Tendencia')
                        self.ax_temporal.legend(loc='upper left', fontsize=8, facecolor='#1e293b', edgecolor='#334155')
                    
                    self.ax_temporal.set_xlabel('Año', color='#f8fafc', fontsize=9)
                    self.ax_temporal.set_ylabel('Conflictos', color='#f8fafc', fontsize=9)
                    self.ax_temporal.set_title('Evolución Temporal de Conflictos por Año (Solo Incluidas)', color='#f8fafc', fontsize=11, weight='bold', pad=10)
                    self.ax_temporal.grid(True, alpha=0.3, color='#334155')
                    
                    # Configurar etiquetas de años
                    self.ax_temporal.set_xticks(años)
                    self.ax_temporal.set_xticklabels([int(a) for a in años], rotation=45, ha='right', fontsize=8)
                else:
                    self.ax_temporal.text(0.5, 0.5, 'Sin fechas válidas en noticias incluidas', 
                                         ha='center', va='center', color='#94a3b8', transform=self.ax_temporal.transAxes)
            else:
                self.ax_temporal.text(0.5, 0.5, 'Sin datos de fechas\nProcesa noticias con fechas válidas', 
                                     ha='center', va='center', color='#94a3b8', transform=self.ax_temporal.transAxes)
            
            # 8. ACTUALIZAR ESTADÍSTICAS EN LABELS (debajo de los gráficos)
            total = len(df)
            tasa_inc = (incluidas / total * 100) if total > 0 else 0
            tasa_exc = (excluidas / total * 100) if total > 0 else 0
            revision = len(df[df['requiere_revision_manual'] == True])
            
            # Actualizar labels de estadísticas
            self.label_stats_total.config(text=f"Total Procesadas: {total:,}")
            self.label_stats_incluidas.config(text=f"✅ Incluidas: {incluidas:,} ({tasa_inc:.1f}%)")
            self.label_stats_excluidas.config(text=f"❌ Excluidas: {excluidas:,} ({tasa_exc:.1f}%)")
            self.label_stats_revision.config(text=f"⚠️  Requieren Revisión: {revision:,}")
            self.label_stats_tipos.config(text=f"Tipos Conflicto: {len(tipos)}")
            self.label_stats_regiones.config(text=f"Regiones: {len(regiones)}")
            self.label_stats_acciones.config(text=f"Tipos Acción: {len(acciones)}")
            
            # Redibujar canvas
            self.canvas_graficos.draw()
            
            self.log("✅ Gráficos actualizados exitosamente", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar gráficos:\n{str(e)}")
            self.log(f"❌ Error actualizando gráficos: {e}", "ERROR")
    

    def _guardar_graficos_png(self):
        """Guarda los gráficos actuales como imagen PNG"""
        try:
            # Pedir ubicación y nombre
            filename = filedialog.asksaveasfilename(
                title="Guardar gráficos",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                initialfile=f"graficos_analisis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            
            if filename:
                # Guardar figura
                self.fig_graficos.savefig(filename, dpi=300, facecolor='#0f172a', edgecolor='none', bbox_inches='tight')
                messagebox.showinfo("Éxito", f"Gráficos guardados en:\n{filename}")
                self.log(f"💾 Gráficos guardados: {os.path.basename(filename)}", "SUCCESS")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar gráficos:\n{str(e)}")
            self.log(f"❌ Error guardando gráficos: {e}", "ERROR")
    

    def _cambiar_provider(self, event=None):
        """Actualiza modelos disponibles según el provider"""
        provider = self.provider.get()
        
        if provider == 'abacus':
            # Modelos disponibles en Abacus.ai (actualizados diciembre 2024)
            # PRIORIZANDO GEMINI 3 (más nuevo y preciso)
            modelos = [
                'gemini-3-flash-preview',  # ⭐ RECOMENDADO: Más nuevo + preciso
                'gemini-2.5-flash',  # Alternativa: Lee links + rápido + económico
                'gemini-2.0-flash-001',  # Lee links + muy rápido
                'route-llm',  # Enruta automáticamente al mejor modelo
                'gpt-5',  # Más avanzado de OpenAI
                'gpt-5-mini',  # Balance velocidad/calidad
                'gpt-5-nano',  # Más rápido y económico
                'gpt-4o-2024-11-20',  # Multimodal avanzado
                'gpt-4o-mini',  # Eficiente y económico
                'claude-sonnet-4-20250514',  # Excelente razonamiento
                'claude-3-7-sonnet-20250219',  # Razonamiento híbrido
                'deepseek-ai/DeepSeek-V3.1-Terminus',  # Económico y efectivo
                'o3',  # Razonamiento profundo
                'o3-mini'  # Razonamiento rápido
            ]
            # Cargar desde .env si existe
            abacus_key = os.getenv('ABACUS_API_KEY', '')
            if abacus_key:
                self.api_key.set(abacus_key)
        elif provider == 'google':
            modelos = ['gemini-2.5-flash']
            google_key = os.getenv('GOOGLE_API_KEY', '')
            if google_key:
                self.api_key.set(google_key)
        else:  # openrouter
            modelos = [
                'google/gemini-3-flash-preview',  # ⭐ RECOMENDADO: Más nuevo + preciso
                'google/gemini-2.5-flash-preview-05-20',
                'anthropic/claude-opus-4',  # Premium para Golden Dataset
                'anthropic/claude-sonnet-4',
                'deepseek/deepseek-v3.1',
                'openai/gpt-4-turbo'
            ]
            openrouter_key = os.getenv('OPENROUTER_API_KEY', '')
            if openrouter_key:
                self.api_key.set(openrouter_key)
        
        self.modelo_combo['values'] = modelos
        self.modelo.set(modelos[0])
    

    def log(self, mensaje, tipo="INFO"):
        """Agrega mensaje al log con colores"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefijo = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️"
        }.get(tipo, "•")
        
        self.log_text.insert(tk.END, f"[{timestamp}] {prefijo} {mensaje}\n", tipo)
        self.log_text.see(tk.END)
        self.root.update()
    

    def detener_procesamiento(self):
        """Detiene el procesamiento en curso"""
        if self.procesando:
            if messagebox.askyesno("Confirmar", "¿Deseas detener el procesamiento?\n\nEl progreso se guardará automáticamente."):
                self.procesando = False
                self.log("⏸️ Deteniendo procesamiento... (guardando progreso)", "WARNING")
    

    def seleccionar_archivo(self):
        """Abre diálogo para seleccionar archivo Excel"""
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if filename:
            self.archivo_excel.set(filename)
            self.log(f"Archivo seleccionado: {os.path.basename(filename)}", "SUCCESS")
    

    def validar_configuracion(self):
        """Valida que la configuración sea correcta usando validación exhaustiva"""
        # ===== FEATURE V3: Validación exhaustiva =====
        es_valido, mensaje = validar_configuracion_exhaustiva(self)
        
        if not es_valido:
            messagebox.showerror("❌ Error de Configuración", mensaje)
            self.logger.error(f"Validación fallida: {mensaje}")
            return False
        
        self.logger.info("✅ Configuración validada correctamente")
        return True
    

    def actualizar_progreso(self, actual, total, titulo):
        """Actualiza barra de progreso y estadísticas en tiempo real"""
        porcentaje = (actual / total) * 100
        self.progress_bar['value'] = porcentaje
        self.label_progreso.config(
            text=f"Procesando {actual}/{total} ({porcentaje:.1f}%) - {titulo}"
        )
        
        # Calcular velocidad y tiempo estimado
        if self.tiempo_inicio:
            tiempo_transcurrido = (datetime.now() - self.tiempo_inicio).total_seconds()
            if actual > 0:
                velocidad = actual / (tiempo_transcurrido / 60)  # noticias por minuto
                tiempo_por_noticia = tiempo_transcurrido / actual
                noticias_restantes = total - actual
                tiempo_restante_seg = noticias_restantes * tiempo_por_noticia
                
                # Formatear tiempo restante
                if tiempo_restante_seg < 60:
                    tiempo_str = f"{int(tiempo_restante_seg)}s"
                elif tiempo_restante_seg < 3600:
                    tiempo_str = f"{int(tiempo_restante_seg/60)}m {int(tiempo_restante_seg%60)}s"
                else:
                    horas = int(tiempo_restante_seg / 3600)
                    minutos = int((tiempo_restante_seg % 3600) / 60)
                    tiempo_str = f"{horas}h {minutos}m"
                
                # Calcular hora estimada de finalización
                hora_fin = datetime.now() + timedelta(seconds=tiempo_restante_seg)
                hora_fin_str = hora_fin.strftime("%H:%M")
                
                self.stat_labels['velocidad'].config(text=f"{velocidad:.1f}/min")
                self.stat_labels['tiempo_estimado'].config(text=tiempo_str)
                self.stat_labels['hora_finalizacion'].config(text=hora_fin_str)
        
        # Actualizar estadísticas en tiempo real si el filtrador está disponible
        if self.filtrador and hasattr(self.filtrador, 'stats'):
            stats = self.filtrador.stats
            incluidas = stats.get('incluidas', 0)
            excluidas = stats.get('excluidas', 0)
            errores = stats.get('errores', 0)
            
            # Usar 'actual' como total procesadas (más confiable que stats['total'])
            self.stat_labels['procesadas'].config(text=str(actual))
            self.stat_labels['incluidas'].config(text=str(incluidas))
            self.stat_labels['excluidas'].config(text=str(excluidas))
            self.stat_labels['errores'].config(text=str(errores))
            
            # Calcular porcentaje de incluidas
            if actual > 0:
                porc_inc = (incluidas / actual) * 100
                self.stat_labels['porcentaje_incluidas'].config(text=f"{porc_inc:.1f}%")
            
            # ===== ACTUALIZAR GRÁFICOS CADA 10 NOTICIAS =====
            if actual % 10 == 0:
                try:
                    self._actualizar_graficos()
                except Exception as e:
                    # No bloquear el procesamiento si falla la actualización de gráficos
                    self.log(f"⚠️ Error actualizando gráficos: {e}", "WARNING")
        
        self.root.update()
    

    def iniciar_procesamiento(self):
        """Inicia el procesamiento en un thread separado"""
        if not self.validar_configuracion():
            return
        
        if self.procesando:
            messagebox.showwarning("Advertencia", "Ya hay un procesamiento en curso")
            return
        
        # Confirmar y validar rango
        inicio = self.indice_inicio.get()
        fin = self.indice_fin.get()
        cantidad = fin - inicio if fin > 0 else "todas"
        
        # ===== VALIDACIÓN: Verificar si ya hay noticias procesadas en este rango =====
        base, ext = os.path.splitext(self.archivo_excel.get())
        output_path = f"{base}_filtrado.xlsx"
        
        if os.path.exists(output_path):
            try:
                import pandas as pd
                df_existing = pd.read_excel(output_path, sheet_name='Datos_completos')
                ids_procesados = set(df_existing['id_noticia'].tolist())
                
                # Contar cuántas del rango ya están procesadas
                overlap = len([i for i in range(inicio, fin if fin > 0 else inicio+1000) if i in ids_procesados])
                
                if overlap > 0:
                    respuesta = messagebox.askyesno(
                        "⚠️ Advertencia - Noticias ya procesadas",
                        f"⚠️ ALERTA DE COSTOS:\n\n"
                        f"• {overlap} noticias ya fueron procesadas\n"
                        f"• Reprocesarlas gastará dinero innecesariamente\n"
                        f"• Costo estimado desperdiciado: ${overlap * 0.001:.2f} USD\n\n"
                        f"💡 RECOMENDACIÓN:\n"
                        f"• Ajusta el rango para evitar duplicados\n"
                        f"• O continúa desde donde quedaste\n\n"
                        f"¿Continuar de todos modos?"
                    )
                    if not respuesta:
                        return
            except Exception as e:
                self.log(f"No se pudo verificar archivo existente: {e}", "WARNING")
        
        mensaje = f"¿Iniciar análisis desde índice {inicio} hasta {fin if fin > 0 else 'el final'}?\n({cantidad} noticias)"
        if not messagebox.askyesno("Confirmar", mensaje):
            return
        
        # Deshabilitar botón iniciar, habilitar detener
        self.btn_procesar.config(state=tk.DISABLED, bg="#95a5a6")
        self.btn_detener.config(state=tk.NORMAL)
        self.procesando = True
        
        # Inicializar tiempo
        self.tiempo_inicio = datetime.now()
        self.tiempo_por_noticia = []
        
        # Actualizar label de archivo de salida
        base, ext = os.path.splitext(self.archivo_excel.get())
        output_path = f"{base}_filtrado.xlsx"
        self.label_output.config(
            text=f"📁 Se guardará en: {os.path.basename(output_path)}\n"
                 f"✅ 4 Hojas: Datos_completos | Datos_filtrados | Revision_manual | Estadisticas"
        )
        
        # Limpiar log y resetear estadísticas visuales
        self.log_text.delete(1.0, tk.END)
        for key in self.stat_labels:
            self.stat_labels[key].config(text="0")
        
        self.log("="*70, "INFO")
        self.log("🚀 INICIANDO PROCESAMIENTO", "SUCCESS")
        self.log("="*70, "INFO")
        
        # Verificar si existe archivo de salida
        base, ext = os.path.splitext(self.archivo_excel.get())
        output_path = f"{base}_filtrado.xlsx"
        if os.path.exists(output_path):
            self.log(f"📂 Archivo existente detectado: {os.path.basename(output_path)}", "WARNING")
            self.log("   Se cargarán resultados previos y se agregarán los nuevos", "INFO")
        else:
            self.log("📝 Creando nuevo archivo de resultados", "INFO")
        
        # Ejecutar en thread
        thread = threading.Thread(target=self.procesar)
        thread.daemon = True
        thread.start()
    

    def procesar(self):
        """Proceso principal de análisis"""
        try:
            # Crear filtrador
            provider = self.provider.get()
            modelo = self.modelo.get()
            self.log(f"Inicializando IA ({provider} - {modelo})...", "INFO")
            self.filtrador = FiltradorIA(api_key=self.api_key.get(), provider=provider)
            
            # Cambiar modelo si es diferente al default
            if hasattr(self.filtrador, 'model_name') and self.filtrador.model_name:
                self.filtrador.model_name = modelo
            
            # Procesar Excel
            self.log(f"Leyendo archivo: {os.path.basename(self.archivo_excel.get())}", "INFO")
            
            inicio = self.indice_inicio.get()
            fin = self.indice_fin.get() if self.indice_fin.get() > 0 else None
            
            # Usar nombre fijo para el archivo de salida
            base, ext = os.path.splitext(self.archivo_excel.get())
            output_path = f"{base}_filtrado.xlsx"
            
            # Obtener concurrencia configurada
            max_workers = self.max_workers.get() if hasattr(self, 'max_workers') else 5
            self.log(f"🚀 Concurrencia configurada: {max_workers} workers", "INFO")
            
            # Obtener configuración de duplicadas
            reemplazar_duplicadas = self.reemplazar_duplicadas.get() if hasattr(self, 'reemplazar_duplicadas') else False
            
            resultados = self.filtrador.procesar_excel(
                excel_path=self.archivo_excel.get(),
                hoja=self.hoja_excel.get(),
                inicio=inicio,
                fin=fin,
                output_path=output_path,
                callback=self.actualizar_progreso,
                max_workers=max_workers,
                reemplazar_duplicadas=reemplazar_duplicadas
            )
            
            # Mostrar estadísticas
            stats = self.filtrador.stats
            
            # Calcular noticias que requieren revisión
            import pandas as pd
            df_temp = pd.DataFrame(self.filtrador.resultados)
            revision_count = len(df_temp[df_temp['requiere_revision_manual'] == True])
            
            self.log("", "INFO")
            self.log("="*60, "INFO")
            self.log("ANÁLISIS COMPLETADO", "SUCCESS")
            self.log("="*60, "INFO")
            
            # Calcular total real de resultados procesados
            total_real = len(resultados) if resultados else 0
            incluidas = stats.get('incluidas', 0)
            excluidas = stats.get('excluidas', 0)
            
            self.log(f"Total analizadas: {total_real}", "INFO")
            
            # Calcular porcentajes con protección contra división por cero
            if total_real > 0:
                porc_inc = (incluidas / total_real * 100)
                porc_exc = (excluidas / total_real * 100)
            else:
                porc_inc = 0
                porc_exc = 0
            
            self.log(f"✅ Incluidas: {incluidas} ({porc_inc:.1f}%)", "SUCCESS")
            self.log(f"❌ Excluidas: {excluidas} ({porc_exc:.1f}%)", "INFO")
            self.log(f"⚠️  Requieren revisión: {revision_count}", "WARNING")
            self.log("", "INFO")
            self.log("📊 HOJAS CREADAS EN EL EXCEL:", "INFO")
            self.log("  1️⃣ Datos_completos - Todas las noticias", "INFO")
            self.log(f"  2️⃣ Datos_filtrados - {stats['incluidas']} noticias válidas", "SUCCESS")
            self.log(f"  3️⃣ Datos_excluidos - {stats['excluidas']} noticias excluidas", "INFO")
            self.log(f"  4️⃣ Revision_manual - {revision_count} noticias a revisar", "WARNING")
            self.log("  5️⃣ Estadisticas + 7 hojas de análisis riguroso", "INFO")
            self.log("", "INFO")
            self.log(f"📄 Archivo generado: {os.path.basename(output_path)}", "SUCCESS")
            self.log("="*60, "INFO")
            
            # Mensaje final
            messagebox.showinfo(
                "¡Completado!",
                f"Análisis completado exitosamente\n\n"
                f"📊 RESULTADOS:\n"
                f"Total: {total_real}\n"
                f"Incluidas: {stats['incluidas']}\n"
                f"Excluidas: {stats['excluidas']}\n"
                f"Requieren revisión: {revision_count}\n\n"
                f"📁 HOJAS CREADAS (12 HOJAS):\n"
                f"• Datos_completos (todas)\n"
                f"• Datos_filtrados ({stats['incluidas']} válidas)\n"
                f"• Datos_excluidos ({stats['excluidas']} excluidas)\n"
                f"• Revision_manual ({revision_count} a revisar)\n"
                f"• Estadisticas (8 hojas de análisis riguroso)\n\n"
                f"📄 Archivo: {os.path.basename(output_path)}"
            )
            
            # Abrir carpeta
            if messagebox.askyesno("Abrir carpeta", "¿Deseas abrir la carpeta con el resultado?"):
                os.startfile(os.path.dirname(output_path))
            
        except Exception as e:
            self.log(f"ERROR: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Error durante el procesamiento:\n\n{str(e)}")
        
        finally:
            # Rehabilitar botones
            self.btn_procesar.config(state=tk.NORMAL, bg="#27ae60")
            self.btn_detener.config(state=tk.DISABLED)
            self.procesando = False
            self.tiempo_inicio = None
            self.progress_bar['value'] = 0
            self.label_progreso.config(text="Esperando...")
            
            # Actualizar resultados si se procesó
            if hasattr(self, 'tree_resultados'):
                self._actualizar_resultados()
    
    # ========================================================================
    # MÉTODOS PARA PESTAÑA DE RESULTADOS
    # ========================================================================
    

    def _cargar_resultados(self):
        """Carga resultados desde un archivo Excel"""
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo de resultados",
            filetypes=[("Excel files", "*_filtrado.xlsx"), ("All files", "*.*")]
        )
        if filename:
            try:
                # Cargar Datos_completos para vista general
                self.df_resultados = pd.read_excel(filename, sheet_name='Datos_completos')
                
                # Cargar Datos_filtrados para mapas (solo conflictos incluidos)
                try:
                    self.df_filtrados = pd.read_excel(filename, sheet_name='Datos_filtrados')
                except:
                    self.df_filtrados = self.df_resultados.copy()
                
                self.archivo_actual = filename  # ✅ GUARDAR ARCHIVO ACTUAL PARA REPORTES
                
                # Intentar cargar también Contenido_Manual si existe
                try:
                    self.df_contenido_manual = pd.read_excel(filename, sheet_name='Contenido_Manual')
                except:
                    # Si no existe la hoja, intentar con nombre antiguo
                    try:
                        self.df_contenido_manual = pd.read_excel(filename, sheet_name='Scraping_Pendiente')
                    except:
                        self.df_contenido_manual = None
                
                # Actualizar combos de filtros con valores únicos
                self._actualizar_filtros_combos()
                
                self._actualizar_vista_resultados()
                messagebox.showinfo("Éxito", f"Resultados cargados: {len(self.df_resultados)} noticias")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar resultados:\n{str(e)}")
    
    def _actualizar_filtros_combos(self):
        """Actualiza los valores de los combos de filtros basado en los datos cargados"""
        if self.df_resultados is None:
            return
        
        # Actualizar combo de regiones
        if hasattr(self, 'filter_region_combo'):
            regiones = ["Todas"]
            if 'region' in self.df_resultados.columns:
                regiones_unicas = self.df_resultados['region'].dropna().unique().tolist()
                regiones_unicas.sort()
                regiones.extend(regiones_unicas)
            self.filter_region_combo['values'] = regiones
            self.filter_region.set("Todas")
        
        # Actualizar combo de tipos de conflicto
        if hasattr(self, 'filter_conflicto_combo'):
            conflictos = ["Todos"]
            if 'tipo_conflicto' in self.df_resultados.columns:
                conflictos_unicos = self.df_resultados['tipo_conflicto'].dropna().unique().tolist()
                conflictos_unicos.sort()
                conflictos.extend(conflictos_unicos)
            self.filter_conflicto_combo['values'] = conflictos
            self.filter_conflicto.set("Todos")
    

    def _actualizar_resultados(self):
        """Actualiza la vista de resultados con el archivo actual"""
        base, ext = os.path.splitext(self.archivo_excel.get())
        output_path = f"{base}_filtrado.xlsx"
        
        if os.path.exists(output_path):
            try:
                self.df_resultados = pd.read_excel(output_path, sheet_name='Datos_completos')
                # También cargar df_filtrados para mapas
                try:
                    self.df_filtrados = pd.read_excel(output_path, sheet_name='Datos_filtrados')
                except:
                    self.df_filtrados = self.df_resultados.copy()
                self._actualizar_vista_resultados()
            except Exception as e:
                self.log(f"Error al actualizar resultados: {e}", "ERROR")
    

    def _actualizar_vista_resultados(self):
        """Actualiza el TreeView con los resultados"""
        if self.df_resultados is None:
            return
        
        # Limpiar TreeView
        for item in self.tree_resultados.get_children():
            self.tree_resultados.delete(item)
        
        # Aplicar filtros
        filtro = self.filter_tipo.get()
        
        # Si es Contenido Manual, usar ese DataFrame
        if filtro == "Contenido Manual":
            if hasattr(self, 'df_contenido_manual') and self.df_contenido_manual is not None:
                df_mostrar = self.df_contenido_manual.copy()
            else:
                # No hay datos de Contenido Manual
                messagebox.showinfo("Info", "No hay noticias en Contenido Manual en este archivo")
                return
        else:
            df_mostrar = self.df_resultados.copy()
            
            # Filtros normales por estado
            if filtro == "Incluidas":
                df_mostrar = df_mostrar[df_mostrar['motivo_exclusion'].isna()]
            elif filtro == "Excluidas":
                df_mostrar = df_mostrar[df_mostrar['motivo_exclusion'].notna()]
            elif filtro == "Revisión Manual":
                df_mostrar = df_mostrar[df_mostrar['requiere_revision_manual'] == True]
        
        # Filtro por región (si existe el filtro)
        if hasattr(self, 'filter_region'):
            region_filtro = self.filter_region.get()
            if region_filtro and region_filtro != "Todas":
                df_mostrar = df_mostrar[df_mostrar['region'] == region_filtro]
        
        # Filtro por tipo de conflicto (si existe el filtro)
        if hasattr(self, 'filter_conflicto'):
            conflicto_filtro = self.filter_conflicto.get()
            if conflicto_filtro and conflicto_filtro != "Todos":
                df_mostrar = df_mostrar[df_mostrar['tipo_conflicto'] == conflicto_filtro]
        
        # Filtro por búsqueda (ahora busca en más campos)
        search_text = self.search_var.get().lower()
        if search_text:
            mask = df_mostrar['titulo'].str.lower().str.contains(search_text, na=False)
            if 'resumen' in df_mostrar.columns:
                mask = mask | df_mostrar['resumen'].str.lower().str.contains(search_text, na=False)
            if 'palabras_clave' in df_mostrar.columns:
                mask = mask | df_mostrar['palabras_clave'].str.lower().str.contains(search_text, na=False)
            if 'noticia' in df_mostrar.columns:
                mask = mask | df_mostrar['noticia'].str.lower().str.contains(search_text, na=False)
            df_mostrar = df_mostrar[mask]
        
        # Calcular tasa de inclusión
        total = len(self.df_resultados)
        incluidas = len(self.df_resultados[self.df_resultados['motivo_exclusion'].isna()])
        tasa = (incluidas / total * 100) if total > 0 else 0
        
        # Insertar datos
        for idx, row in df_mostrar.iterrows():
            estado = "✅ Incluida" if pd.isna(row.get('motivo_exclusion')) else "❌ Excluida"
            if row.get('requiere_revision_manual'):
                estado = "⚠️ Revisar"
            
            # Obtener fecha (puede estar en diferentes columnas)
            fecha = row.get('fecha_publicacion', row.get('fecha', ''))
            if pd.notna(fecha):
                # Si es datetime, formatear
                try:
                    if isinstance(fecha, str):
                        fecha_str = fecha[:10]  # YYYY-MM-DD
                    else:
                        fecha_str = fecha.strftime('%Y-%m-%d')
                except:
                    fecha_str = str(fecha)[:10]
            else:
                fecha_str = 'N/A'
            
            self.tree_resultados.insert('', 'end', values=(
                row.get('id_noticia', ''),
                row.get('titulo', '')[:80],
                row.get('tipo_conflicto', '')[:40] if pd.notna(row.get('tipo_conflicto')) else '',
                row.get('region', ''),
                fecha_str,
                estado
            ))
        
        # Actualizar label de información
        self.label_info_resultados.config(
            text=f"Mostrando {len(df_mostrar)} de {total} noticias | "
                 f"Incluidas: {incluidas} ({tasa:.1f}%) | "
                 f"Excluidas: {total - incluidas}"
        )
    

    def _filtrar_resultados(self):
        """Aplica filtros a los resultados"""
        self._actualizar_vista_resultados()
    

    def _ordenar_columna(self, col):
        """Ordena el TreeView por columna"""
        # Implementación básica - se puede mejorar
        self._actualizar_vista_resultados()
    

    def _ver_detalles_noticia(self, event):
        """Muestra detalles completos de una noticia"""
        selection = self.tree_resultados.selection()
        if not selection:
            return
        
        item = self.tree_resultados.item(selection[0])
        id_noticia = item['values'][0]
        
        # Buscar la noticia en el DataFrame
        noticia = self.df_resultados[self.df_resultados['id_noticia'] == id_noticia].iloc[0]
        
        # Crear ventana de detalles
        detalle_window = tk.Toplevel(self.root)
        detalle_window.title(f"Detalles - Noticia #{id_noticia}")
        detalle_window.geometry("800x600")
        detalle_window.configure(bg='#f8f9fa')
        
        # Frame con scroll
        container = tk.Frame(detalle_window, bg='#f8f9fa')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título
        tk.Label(
            container,
            text=noticia.get('titulo', ''),
            font=("Segoe UI", 14, "bold"),
            bg='#f8f9fa',
            fg='#2c3e50',
            wraplength=750,
            justify=tk.LEFT
        ).pack(pady=(0, 15))
        
        # Texto con detalles
        text_widget = scrolledtext.ScrolledText(
            container,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            height=25
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Insertar información
        detalles = f"""
══════════════════════════════════════════════════════════════
📰 NOTICIA #{noticia.get('id_noticia', 'N/A')}
══════════════════════════════════════════════════════════════

📅 Fecha: {noticia.get('fecha', 'N/A')}
📰 Fuente: {noticia.get('fuente', 'N/A')}
🔗 Link: {noticia.get('link_noticia', 'N/A')}

──────────────────────────────────────────────────────────────
📝 RESUMEN
──────────────────────────────────────────────────────────────
{noticia.get('resumen', 'N/A')}

🏷️ Palabras Clave: {noticia.get('palabras_clave', 'N/A')}
😤 Tono Emocional: {noticia.get('tono_emocional', 'N/A')}

──────────────────────────────────────────────────────────────
🔍 CLASIFICACIÓN
──────────────────────────────────────────────────────────────
• Tipo de Conflicto: {noticia.get('tipo_conflicto', 'N/A')}
  └─ {noticia.get('explicacion_conflicto', '')}

• Tipo de Acción: {noticia.get('tipo_accion', 'N/A')}
  └─ {noticia.get('explicacion_accion', '')}

• Escala del Conflicto: {noticia.get('escala_conflicto', 'N/A')}
• Vínculo Transición: {noticia.get('vinculo_transicion', 'N/A')}

──────────────────────────────────────────────────────────────
👥 ACTORES
──────────────────────────────────────────────────────────────
• Demandante: {noticia.get('actor_demandante', 'N/A')}
  └─ {noticia.get('explicacion_demandante', '')}

• Demandado: {noticia.get('actor_demandado', 'N/A')}
  └─ {noticia.get('explicacion_demandado', '')}

──────────────────────────────────────────────────────────────
📍 UBICACIÓN
──────────────────────────────────────────────────────────────
• Región: {noticia.get('region', 'N/A')}
• Provincia: {noticia.get('provincia', 'N/A')}
• Comuna: {noticia.get('comuna', 'N/A')}
• Localidad: {noticia.get('localidad', 'N/A')}

──────────────────────────────────────────────────────────────
🏭 SECTOR Y PROYECTO
──────────────────────────────────────────────────────────────
• Sector Económico: {noticia.get('sector_economico', 'N/A')}
• Proyecto Específico: {noticia.get('proyecto_especifico', 'N/A')}

──────────────────────────────────────────────────────────────
⚡ RELACIÓN CON TRANSICIÓN ENERGÉTICA
──────────────────────────────────────────────────────────────
{noticia.get('justificacion_transicion', 'N/A')}

──────────────────────────────────────────────────────────────
📋 ESTADO Y NOTAS
──────────────────────────────────────────────────────────────
• Motivo Exclusión: {noticia.get('motivo_exclusion', 'Incluida ✅')}
• Explicación: {noticia.get('explicacion_exclusion', 'N/A')}
• Requiere Revisión: {'Sí ⚠️' if noticia.get('requiere_revision_manual') else 'No ✅'}
• Notas: {noticia.get('notas', 'N/A')}

──────────────────────────────────────────────────────────────
📊 MÉTRICAS DE IA
──────────────────────────────────────────────────────────────
• Modelo: {noticia.get('modelo_usado', 'N/A')}
• Tokens Input: {noticia.get('tokens_input', 0):,}
• Tokens Output: {noticia.get('tokens_output', 0):,}
• Tokens Totales: {noticia.get('tokens_totales', 0):,}
• Latencia: {noticia.get('latencia_ms', 0):.0f} ms
• Costo Estimado: ${noticia.get('costo_estimado_usd', 0):.6f} USD
"""
        
        text_widget.insert('1.0', detalles)
        text_widget.config(state=tk.DISABLED)
        
        # Botón cerrar
        tk.Button(
            container,
            text="Cerrar",
            command=detalle_window.destroy,
            bg="#95a5a6",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        ).pack(pady=(10, 0))
    

    def _exportar_excel(self):
        """Exporta resultados filtrados a Excel"""
        if self.df_resultados is None:
            messagebox.showwarning("Advertencia", "No hay resultados para exportar")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Guardar como Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Determinar qué exportar según el filtro
                filtro = self.filter_tipo.get()
                if filtro == "Incluidas":
                    df_export = self.df_resultados[self.df_resultados['motivo_exclusion'].isna()]
                elif filtro == "Excluidas":
                    df_export = self.df_resultados[self.df_resultados['motivo_exclusion'].notna()]
                elif filtro == "Revisión Manual":
                    df_export = self.df_resultados[self.df_resultados['requiere_revision_manual'] == True]
                else:
                    df_export = self.df_resultados
                
                df_export.to_excel(filename, index=False, engine='openpyxl')
                messagebox.showinfo("Éxito", f"Exportado: {len(df_export)} noticias a Excel")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar:\n{str(e)}")
    
    # ========================================================================
    # MÉTODOS PARA PESTAÑA DE PERFILES
    # ========================================================================
    

    def _actualizar_lista_perfiles(self):
        """Actualiza la lista de perfiles guardados"""
        self.listbox_perfiles.delete(0, tk.END)
        
        perfiles_dir = "perfiles"
        if not os.path.exists(perfiles_dir):
            os.makedirs(perfiles_dir)
        
        for archivo in os.listdir(perfiles_dir):
            if archivo.endswith('.json'):
                nombre = archivo.replace('.json', '')
                self.listbox_perfiles.insert(tk.END, nombre)
    

    def _guardar_perfil(self):
        """Guarda la configuración actual como perfil"""
        nombre = tk.simpledialog.askstring("Guardar Perfil", "Nombre del perfil:")
        if not nombre:
            return
        
        perfil = {
            "nombre": nombre,
            "provider": self.provider.get(),
            "modelo": self.modelo.get(),
            "api_key": self.api_key.get(),
            "hoja_excel": self.hoja_excel.get(),
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        perfiles_dir = "perfiles"
        if not os.path.exists(perfiles_dir):
            os.makedirs(perfiles_dir)
        
        filepath = os.path.join(perfiles_dir, f"{nombre}.json")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(perfil, f, indent=2, ensure_ascii=False)
            
            self._actualizar_lista_perfiles()
            self._mostrar_config_actual()
            messagebox.showinfo("Éxito", f"Perfil '{nombre}' guardado correctamente")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar perfil:\n{str(e)}")
    

    def _cargar_perfil(self):
        """Carga un perfil seleccionado"""
        selection = self.listbox_perfiles.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona un perfil")
            return
        
        nombre = self.listbox_perfiles.get(selection[0])
        filepath = os.path.join("perfiles", f"{nombre}.json")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                perfil = json.load(f)
            
            # Aplicar configuración
            self.provider.set(perfil.get('provider', 'abacus'))
            self.modelo.set(perfil.get('modelo', 'google/gemini-3-flash-preview'))
            self.api_key.set(perfil.get('api_key', ''))
            self.hoja_excel.set(perfil.get('hoja_excel', 'Datos_enriquecidos'))
            
            self._mostrar_config_actual()
            messagebox.showinfo("Éxito", f"Perfil '{nombre}' cargado correctamente")
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar perfil:\n{str(e)}")
    

    def _eliminar_perfil(self):
        """Elimina un perfil seleccionado"""
        selection = self.listbox_perfiles.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona un perfil")
            return
        
        nombre = self.listbox_perfiles.get(selection[0])
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar perfil '{nombre}'?"):
            filepath = os.path.join("perfiles", f"{nombre}.json")
            try:
                os.remove(filepath)
                self._actualizar_lista_perfiles()
                messagebox.showinfo("Éxito", f"Perfil '{nombre}' eliminado")
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar:\n{str(e)}")
    

    def _mostrar_config_actual(self):
        """Muestra la configuración actual en el label"""
        config_text = f"""
Provider: {self.provider.get()}
Modelo: {self.modelo.get()}
Hoja Excel: {self.hoja_excel.get()}
API Key: {'*' * 20}
"""
        self.label_config_actual.config(text=config_text.strip())
    
    # ========================================================================
    # MÉTODOS PARA REPORTES EXHAUSTIVOS Y ANÁLISIS CON IA
    # ========================================================================
    
    def _generar_reporte_exhaustivo(self):
        """Genera un reporte exhaustivo TXT con todas las estadísticas"""
        generar_reporte_exhaustivo(self)
    
    def _analizar_reporte_con_ia(self):
        """Analiza el reporte generado con IA para generar insights académicos"""
        analizar_reporte_con_ia(self)
    
    # ========================================================================
    # FUNCIONES DE MAPAS INTERACTIVOS
    # ========================================================================
    
    def _generar_mapa_calor(self):
        """Genera mapa de calor interactivo con conflictos"""
        if not hasattr(self, 'df_filtrados') or self.df_filtrados is None:
            messagebox.showwarning(
                "Sin datos",
                "Debes cargar un archivo Excel en la pestaña 'Resultados' primero"
            )
            return
        
        try:
            # Actualizar preview
            self.preview_mapa.config(state=tk.NORMAL)
            self.preview_mapa.delete(1.0, tk.END)
            self.preview_mapa.insert(tk.END, "🗺️ Generando mapa de calor...\n\n")
            self.preview_mapa.config(state=tk.DISABLED)
            self.preview_mapa.update()
            
            # Importar dinámicamente desde Fase 4 (04_interactive_map)
            # Ruta relativa: src/ui/app.py -> src/ui -> src -> 03 -> pipeline -> 04
            try:
                import sys
                import os
                
                # Calcular ruta a la carpeta de Fase 4
                # __file__ = .../03_filter_app/src/ui/app.py
                current_dir = os.path.dirname(os.path.abspath(__file__)) # src/ui
                src_dir = os.path.dirname(current_dir) # src
                app_dir = os.path.dirname(src_dir) # 03_filter_app
                pipeline_dir = os.path.dirname(app_dir) # pipeline_conflictos_chile
                map_dir = os.path.join(pipeline_dir, '04_interactive_map')
                
                if map_dir not in sys.path:
                    sys.path.append(map_dir)
                
                from map_engine import GeneradorMapas
                logger.info("✅ GeneradorMapas importado exitosamente desde Fase 4")
                
            except ImportError as e:
                logger.error(f"❌ No se pudo importar GeneradorMapas desde {map_dir}: {e}")
                messagebox.showerror("Error de Configuración", f"No se encontró el módulo de mapas en la Fase 4.\n\nError: {e}")
                self.preview_mapa.config(state=tk.NORMAL)
                self.preview_mapa.insert(tk.END, f"\n❌ Error crítico: Falta módulo de mapas\n")
                self.preview_mapa.config(state=tk.DISABLED)
                return

            # Crear generador de mapas UNIFICADO
            generador = GeneradorMapas()
            
            # Usar SOLO Datos_filtrados (conflictos incluidos)
            df_mapa = self.df_filtrados.copy()
            
            # Filtrar solo noticias con ubicación válida
            df_mapa = df_mapa.dropna(subset=['region'])
            
            if len(df_mapa) == 0:
                messagebox.showwarning(
                    "Sin datos geográficos",
                    "No hay noticias filtradas con información de ubicación (región/comuna)"
                )
                return
            
            # Generar MAPA UNIFICADO con panel lateral y selector de nivel
            output_path = os.path.join(os.getcwd(), 'mapa_conflictos_interactivo.html')
            
            self.preview_mapa.config(state=tk.NORMAL)
            self.preview_mapa.insert(tk.END, f"📍 Generando mapa unificado...\n")
            self.preview_mapa.insert(tk.END, f"📊 Total noticias: {len(df_mapa)}\n")
            self.preview_mapa.insert(tk.END, f"🎯 Incluye: Regiones, Provincias y Comunas\n")
            self.preview_mapa.config(state=tk.DISABLED)
            
            # Generar el mapa unificado con panel lateral
            mapa = generador.generar_mapa_unificado_con_panel(df_mapa, output_path)
            
            # Guardar ruta del último mapa
            self.ultimo_mapa_path = output_path
            
            # Actualizar estadísticas
            regiones_unicas = df_mapa['region'].nunique()
            comunas_unicas = df_mapa['comuna'].dropna().nunique() if 'comuna' in df_mapa.columns else 0
            
            stats_text = f"""Mapa interactivo generado exitosamente:
• Total conflictos: {len(df_mapa)}
• Regiones: {regiones_unicas}
• Comunas: {comunas_unicas}
• Archivo: {output_path}

✅ Funcionalidades incluidas:
  - Panel lateral con información detallada
  - Selector de nivel (Regiones/Provincias/Comunas)
  - Desplegable de territorios
  - Click en mapa actualiza el panel
  - Ordenado por fecha (más reciente primero)
  
Usa los controles en la esquina superior derecha
"""
            
            self.label_stats_mapa.config(text=stats_text)
            
            # Actualizar preview
            self.preview_mapa.config(state=tk.NORMAL)
            self.preview_mapa.insert(tk.END, "\n✅ Mapa generado exitosamente\n")
            self.preview_mapa.insert(tk.END, f"💾 Guardado en: {output_path}\n\n")
            self.preview_mapa.insert(tk.END, "🌐 Abriendo en navegador...\n")
            self.preview_mapa.config(state=tk.DISABLED)
            
            # Abrir en navegador (convertir ruta a URI correcta)
            file_uri = Path(output_path).absolute().as_uri()
            webbrowser.open(file_uri)
            
            messagebox.showinfo(
                "Éxito",
                f"Mapa generado y abierto en navegador\n\nArchivo: {output_path}"
            )
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error al generar mapa: {e}\n{error_traceback}")
            
            self.preview_mapa.config(state=tk.NORMAL)
            self.preview_mapa.insert(tk.END, f"\n❌ Error: {str(e)}\n")
            self.preview_mapa.insert(tk.END, f"\n📋 Traceback:\n{error_traceback}\n")
            self.preview_mapa.config(state=tk.DISABLED)
            
            messagebox.showerror(
                "Error",
                f"Error al generar mapa:\n{str(e)}"
            )
    
    def _integrar_funcionalidades_avanzadas(self, output_path: str, df: pd.DataFrame):
        """
        Integra funcionalidades avanzadas al mapa HTML ya generado
        de forma más compacta y profesional
        """
        try:
            # Leer HTML generado
            with open(output_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Importar módulos necesarios
            from src.core.mapa_animacion_temporal import AnimacionTemporal
            from src.core.mapa_comparacion_periodos import ComparadorPeriodos
            from src.core.mapa_exportar_visualizaciones import ExportadorVisualizaciones
            
            # Añadir solo las funcionalidades más importantes y compactas
            # 1. Animación Temporal (compacta)
            animacion = AnimacionTemporal(df)
            html_animacion = animacion.generar_html_animacion()
            html_content = html_content.replace('</body>', f'{html_animacion}\n</body>')
            
            # 2. Comparación de Períodos (compacta)
            comparador = ComparadorPeriodos(df)
            html_comparacion = comparador.generar_html_comparacion()
            html_content = html_content.replace('</body>', f'{html_comparacion}\n</body>')
            
            # 3. Exportar Visualizaciones
            exportador = ExportadorVisualizaciones()
            html_exportar = exportador.generar_html_exportador()
            html_content = html_content.replace('</body>', f'{html_exportar}\n</body>')
            
            # Guardar HTML modificado
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info("✅ Funcionalidades avanzadas integradas")
            
        except Exception as e:
            logger.warning(f"No se pudieron integrar todas las funcionalidades: {e}")
    
    def _abrir_ultimo_mapa(self):
        """Abre el último mapa generado en el navegador"""
        if not hasattr(self, 'ultimo_mapa_path') or not os.path.exists(self.ultimo_mapa_path):
            messagebox.showwarning(
                "Sin mapa",
                "No hay ningún mapa generado. Genera uno primero."
            )
            return
        
        # Convertir ruta a URI correcta
        file_uri = Path(self.ultimo_mapa_path).absolute().as_uri()
        webbrowser.open(file_uri)
        messagebox.showinfo("Mapa abierto", "Mapa abierto en navegador")
    
    def _guardar_mapa_como(self):
        """Guarda el mapa actual con un nombre personalizado"""
        if not hasattr(self, 'ultimo_mapa_path') or not os.path.exists(self.ultimo_mapa_path):
            messagebox.showwarning(
                "Sin mapa",
                "No hay ningún mapa generado. Genera uno primero."
            )
            return
        
        filename = filedialog.asksaveasfilename(
            title="Guardar mapa como",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                import shutil
                shutil.copy(self.ultimo_mapa_path, filename)
                messagebox.showinfo(
                    "Éxito",
                    f"Mapa guardado en:\n{filename}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Error al guardar mapa:\n{str(e)}"
                )

# ============================================================================
# MAIN
# ============================================================================
