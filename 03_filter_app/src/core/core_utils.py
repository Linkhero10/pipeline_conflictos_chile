"""
utils.py - Utilidades, decoradores y funciones auxiliares
"""

import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


# NOTA: retry_on_error eliminado - se usa tenacity en filtrador_analisis.py

def setup_logging(log_dir='logs'):
    """Configura el sistema de logging"""
    import os
    from datetime import datetime
    
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                f'{log_dir}/filtrado_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


# NOTA: validar_archivo_excel eliminado - validación se hace en ProcesadorExcel

def formatear_estadisticas(stats: dict) -> str:
    """
    Formatea diccionario de estadísticas para impresión
    
    Args:
        stats: Diccionario con estadísticas
        
    Returns:
        String formateado para imprimir
    """
    output = "\n" + "="*80 + "\n"
    output += "📊 RESUMEN DE PROCESAMIENTO\n"
    output += "="*80 + "\n"
    
    total = stats.get('total', 0)
    incluidas = stats.get('incluidas', 0)
    excluidas = stats.get('excluidas', 0)
    errores = stats.get('errores', 0)
    
    output += f"✅ Noticias incluidas: {incluidas}/{total}\n"
    output += f"❌ Noticias excluidas: {excluidas}/{total}\n"
    output += f"⚠️  Errores: {errores}\n"
    
    if total > 0:
        tasa_inclusion = (incluidas / total) * 100
        output += f"📈 Tasa de inclusión: {tasa_inclusion:.1f}%\n"
    
    output += "="*80 + "\n"
    
    return output


# NOTA: limpiar_archivos_temporales eliminado - no se usa

def verificar_dependencias():
    """Verifica que las dependencias opcionales estén instaladas"""
    dependencias = {
        'trafilatura': False,
        'newspaper': False,
        'googlenewsdecoder': False,
        'selenium': False
    }
    
    try:
        import trafilatura
        dependencias['trafilatura'] = True
    except ImportError:
        pass
    
    try:
        from newspaper import Article
        dependencias['newspaper'] = True
    except ImportError:
        pass
    
    try:
        from googlenewsdecoder import gnewsdecoder
        dependencias['googlenewsdecoder'] = True
    except ImportError:
        pass
    
    try:
        from selenium import webdriver
        dependencias['selenium'] = True
    except ImportError:
        pass
    
    logger.info("📦 Estado de dependencias opcionales:")
    for dep, instalado in dependencias.items():
        estado = "✅ Instalado" if instalado else "⚠️  No instalado"
        logger.info(f"   {dep}: {estado}")
    
    return dependencias


# NOTA: crear_backup_seguro eliminado - backup se maneja en ProcesadorExcel
