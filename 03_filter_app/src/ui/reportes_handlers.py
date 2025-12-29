"""
Handlers para los botones de reportes en la UI
Maneja la generación de reportes exhaustivos y análisis con IA
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import logging
import os

logger = logging.getLogger(__name__)


def generar_reporte_exhaustivo(app):
    """
    Handler para el botón 'Generar Reporte Completo'
    Genera reporte TXT + gráficos PNG + métricas JSON
    Usa el nuevo GeneradorReportes que incluye nube de palabras y visualizaciones
    """
    # Validar que hay un archivo cargado
    if not hasattr(app, 'archivo_actual') or not app.archivo_actual:
        messagebox.showerror(
            "Error",
            "❌ Debes cargar un archivo Excel primero.\n\n"
            "Ve a la pestaña 'Resultados' y usa el botón '📂 Cargar' "
            "para seleccionar un archivo *_filtrado.xlsx"
        )
        return
    
    if not os.path.exists(app.archivo_actual):
        messagebox.showerror(
            "Error",
            f"❌ El archivo no existe:\n{app.archivo_actual}"
        )
        return
    
    # Confirmar con el usuario
    confirmacion = messagebox.askyesno(
        "Generar Reporte Exhaustivo",
        f"""📄 GENERAR REPORTE ESTADÍSTICO EXHAUSTIVO

📂 Archivo: {os.path.basename(app.archivo_actual)}

Este proceso generará un REPORTE COMPLETO con:

✅ Nube de palabras por términos compuestos
✅ 9 gráficos profesionales (PNG)
✅ Informe ejecutivo TXT
✅ Métricas en formato JSON
✅ Análisis temporal, geográfico, de actores
✅ Heatmap de evolución temporal

Todos los archivos se guardarán en la carpeta 'reportes/'.

¿Deseas continuar?"""
    )
    
    if not confirmacion:
        return
    
    # Ejecutar en hilo separado
    def ejecutar():
        try:
            # Usar el nuevo GeneradorReportes con gráficos
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from generador_reportes import GeneradorReportes
            
            logger.info("="*100)
            logger.info("📄 Generando reporte completo con gráficos...")
            logger.info("="*100)
            
            # Crear generador
            generador = GeneradorReportes(app.archivo_actual)
            
            # Generar reporte completo (TXT + gráficos + métricas)
            archivos = generador.generar_reporte_completo()
            
            # Guardar referencias para el análisis IA
            app.ultimo_reporte_generado = archivos.get('informe', '')
            app.ultimos_graficos = generador.graficos_generados
            app.ultimas_metricas = generador.metricas
            app.carpeta_reportes = generador.output_dir
            
            reporte_path = app.ultimo_reporte_generado
            
            # Habilitar botón de análisis IA
            app.btn_analizar_ia.config(state=tk.NORMAL)
            
            # Contar gráficos generados
            num_graficos = len(generador.graficos_generados)
            
            # Mostrar mensaje de éxito
            messagebox.showinfo(
                "✅ Reporte Completo Generado",
                f"""📄 REPORTE COMPLETO GENERADO EXITOSAMENTE

📂 Carpeta: {generador.output_dir}

📊 Archivos generados:
   • Informe ejecutivo TXT
   • {num_graficos} gráficos PNG (nube de palabras, temporal, etc.)
   • Métricas JSON
   • Términos frecuentes Excel

💡 Ahora usa '🤖 Analizar con IA + Word/PDF' para:
   • Generar análisis académico con IA
   • Crear documento Word/PDF profesional
   • Incluir gráficos automáticamente"""
            )
            
            # Preguntar si quiere abrir el reporte
            if messagebox.askyesno("Abrir Reporte", "¿Deseas abrir el reporte ahora?"):
                os.startfile(reporte_path)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ Error generando reporte:\n\n{str(e)}\n\n{traceback.format_exc()}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
    
    thread = threading.Thread(target=ejecutar, daemon=True)
    thread.start()


def analizar_reporte_con_ia(app):
    """
    Handler para el botón 'Analizar con IA + Word/PDF'
    Analiza el reporte + gráficos con IA y genera documento Word/PDF profesional
    """
    # Validar que hay un reporte generado
    if not hasattr(app, 'ultimo_reporte_generado') or not app.ultimo_reporte_generado:
        messagebox.showerror(
            "Error",
            "❌ Debes generar un reporte primero.\n\n"
            "Usa el botón '📄 Generar Reporte' para crear un reporte exhaustivo."
        )
        return
    
    if not os.path.exists(app.ultimo_reporte_generado):
        messagebox.showerror(
            "Error",
            f"❌ El reporte no existe:\n{app.ultimo_reporte_generado}\n\n"
            "Genera un nuevo reporte usando el botón '📄 Generar Reporte'."
        )
        return
    
    # Obtener API key del .env (igual que los demás procesos)
    api_key = app.api_key.get()
    if not api_key:
        # Intentar cargar desde .env como fallback
        api_key = os.getenv('ABACUS_API_KEY', '')
        if not api_key:
            messagebox.showerror(
                "Error",
                "❌ No hay API key configurada.\n\n"
                "Configura ABACUS_API_KEY en el archivo .env"
            )
            return
    
    # Verificar si hay gráficos generados
    tiene_graficos = hasattr(app, 'ultimos_graficos') and app.ultimos_graficos
    num_graficos = len(app.ultimos_graficos) if tiene_graficos else 0
    
    # Confirmar con el usuario
    confirmacion = messagebox.askyesno(
        "Analizar con IA + Generar Word/PDF",
        f"""🤖 ANÁLISIS ACADÉMICO CON IA + WORD/PDF

📄 Reporte: {os.path.basename(app.ultimo_reporte_generado)}
📊 Gráficos disponibles: {num_graficos}
🌐 API: OpenRouter
🤖 Modelo: google/gemini-3-flash-preview
💰 Costo estimado: ~$0.01 USD

Este proceso:

✅ Analizará el reporte completo con IA
✅ Leerá las métricas y describirá los gráficos
✅ Generará análisis académico riguroso
✅ Creará documento WORD profesional
✅ Incluirá los gráficos automáticamente
✅ Opcionalmente generará PDF

⚠️  IMPORTANTE:
• El proceso puede tomar 2-3 minutos
• Requiere python-docx instalado
• El análisis debe ser validado por expertos

¿Deseas continuar?"""
    )
    
    if not confirmacion:
        return
    
    # Deshabilitar botón mientras se procesa
    app.btn_analizar_ia.config(state=tk.DISABLED, text="⏳ Analizando...")
    
    # Ejecutar en hilo separado
    def ejecutar():
        try:
            from src.reportes import AnalizadorReporteIA
            from src.reportes.generador_word_pdf import GeneradorReporteWord, HAS_DOCX
            
            logger.info("="*100)
            logger.info("🤖 Analizando reporte con IA...")
            logger.info("="*100)
            
            # Crear analizador con OpenRouter
            analizador = AnalizadorReporteIA(
                api_key=api_key,
                provider="google",
                use_openrouter=True
            )
            
            # Analizar reporte (genera TXT con análisis)
            analisis_path = analizador.analizar_reporte(app.ultimo_reporte_generado)
            
            # Leer el análisis generado
            with open(analisis_path, 'r', encoding='utf-8') as f:
                analisis_texto = f.read()
            
            # Generar Word/PDF si está disponible
            word_path = None
            pdf_path = None
            
            if HAS_DOCX:
                try:
                    logger.info("📄 Generando documento Word con gráficos...")
                    
                    # Obtener datos guardados
                    graficos = getattr(app, 'ultimos_graficos', [])
                    metricas = getattr(app, 'ultimas_metricas', {})
                    carpeta = getattr(app, 'carpeta_reportes', os.path.dirname(analisis_path))
                    
                    # Crear generador Word
                    generador_word = GeneradorReporteWord(carpeta)
                    
                    # Generar Word con gráficos
                    resultado = generador_word.generar_reporte(
                        analisis_ia=analisis_texto,
                        metricas=metricas,
                        graficos=graficos,
                        generar_pdf=True
                    )
                    
                    word_path = resultado.get('word')
                    pdf_path = resultado.get('pdf')
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error generando Word: {e}")
            
            # Construir mensaje de éxito
            archivos_generados = [f"• Análisis TXT: {os.path.basename(analisis_path)}"]
            if word_path:
                archivos_generados.append(f"• Documento Word: {os.path.basename(word_path)}")
            if pdf_path:
                archivos_generados.append(f"• Documento PDF: {os.path.basename(pdf_path)}")
            
            archivos_str = '\n'.join(archivos_generados)
            
            messagebox.showinfo(
                "✅ Análisis y Documentos Generados",
                f"""🤖 ANÁLISIS CON IA + WORD/PDF COMPLETADO

📂 Carpeta: {os.path.dirname(analisis_path)}

📄 Archivos generados:
{archivos_str}

El documento Word incluye:
• Análisis académico completo
• Gráficos integrados automáticamente
• Métricas y tablas profesionales
• Formato listo para presentar

⚠️  Validar con expertos antes de uso formal."""
            )
            
            # Preguntar qué archivo abrir
            archivo_abrir = word_path or analisis_path
            if messagebox.askyesno("Abrir Documento", f"¿Deseas abrir {os.path.basename(archivo_abrir)}?"):
                os.startfile(archivo_abrir)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ Error analizando con IA:\n\n{str(e)}\n\n{traceback.format_exc()}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
        finally:
            # Rehabilitar botón
            app.btn_analizar_ia.config(state=tk.NORMAL, text="🤖 Analizar con IA")
    
    thread = threading.Thread(target=ejecutar, daemon=True)
    thread.start()


# Funciones para añadir a la clase App
def añadir_metodos_reportes(app_class):
    """Añade los métodos de reportes a la clase App"""
    app_class._generar_reporte_exhaustivo = generar_reporte_exhaustivo
    app_class._analizar_reporte_con_ia = analizar_reporte_con_ia
