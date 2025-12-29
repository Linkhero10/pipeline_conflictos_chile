"""
FILTRADOR AUTOMÁTICO DE NOTICIAS CON IA - FONDECYT
Motor principal modularizado

Estructura:
- config.py: Configuración y constantes
- scraping.py: Métodos de web scraping
- analisis_ia.py: Análisis con IA
- procesamiento.py: Procesamiento de Excel
- estadisticas.py: Generación de estadísticas
- utils.py: Utilidades y decoradores
"""

import logging
from typing import Dict, Optional, Callable

from .config_loader import *
from .ai_classifier import AnalizadorIA
from .excel_processor import ProcesadorExcel
from .core_utils import setup_logging, verificar_dependencias, formatear_estadisticas

logger = logging.getLogger(__name__)


class FiltradorIA:
    """Clase principal del Filtrador de Noticias FONDECYT"""
    
    def __init__(self, api_key: str, provider: str = "google"):
        """
        Inicializa el filtrador con IA
        
        Args:
            api_key: API Key del provider
            provider: "google", "abacus" o "openrouter"
        """
        self.provider = provider
        
        # Inicializar componentes
        self.analizador = AnalizadorIA(api_key, provider)
        self.procesador = None  # Se crea en cada procesamiento
        
        # Verificar dependencias opcionales
        verificar_dependencias()
        
        logger.info(f"✅ FiltradorIA inicializado con provider: {provider}")
    
    def procesar_excel(
        self,
        excel_path: str,
        hoja: str = 'Datos_enriquecidos',
        inicio: Optional[int] = None,
        fin: Optional[int] = None,
        output_path: str = 'resultados_filtrado.xlsx',
        callback: Optional[Callable] = None,
        max_workers: int = 1,
        reemplazar_duplicadas: bool = False
    ) -> list:
        """
        Procesa archivo Excel con análisis de IA
        
        Args:
            excel_path: Ruta al Excel de entrada
            hoja: Nombre de la hoja a procesar (default: 'Datos_enriquecidos')
            inicio: Índice de inicio (0-based, None = desde el principio)
            fin: Índice de fin (0-based, None = hasta el final)
            output_path: Ruta del archivo de salida
            callback: Función para actualizar progreso (opcional)
            max_workers: Número de workers paralelos (1 = secuencial)
            reemplazar_duplicadas: Si True, reanaliza noticias ya procesadas
            
        Returns:
            Lista de resultados procesados
        """
        logger.info("="*80)
        logger.info("🚀 INICIANDO PROCESAMIENTO DE EXCEL")
        logger.info(f"   Archivo: {excel_path}")
        logger.info(f"   Hoja: {hoja}")
        logger.info(f"   Rango: {inicio or 0} - {fin or 'final'}")
        logger.info(f"   Salida: {output_path}")
        logger.info(f"   Workers: {max_workers}")
        logger.info(f"   Reemplazar: {reemplazar_duplicadas}")
        logger.info("="*80)
        
        # Crear nuevo procesador
        self.procesador = ProcesadorExcel(self.analizador)
        
        # Procesar
        resultados = self.procesador.procesar_excel(
            excel_path=excel_path,
            hoja=hoja,
            inicio=inicio,
            fin=fin,
            output_path=output_path,
            callback=callback,
            max_workers=max_workers,
            reemplazar_duplicadas=reemplazar_duplicadas
        )
        
        # Mostrar estadísticas
        print(formatear_estadisticas(self.procesador.stats))
        
        logger.info("✅ Procesamiento completado exitosamente")
        
        return resultados
    
    def analizar_noticia(self, noticia: dict) -> Dict:
        """
        Analiza una noticia individual
        
        Args:
            noticia: Diccionario con datos de la noticia
            
        Returns:
            Diccionario con clasificación
        """
        return self.analizador.analizar_noticia(noticia)
    
    @property
    def stats(self) -> Dict:
        """Property para acceso directo a estadísticas (compatibilidad con UI)"""
        if self.procesador:
            return self.procesador.stats
        return {'total': 0, 'incluidas': 0, 'excluidas': 0, 'errores': 0}
    
    @property
    def resultados(self) -> list:
        """Property para acceso directo a resultados (compatibilidad con UI)"""
        if self.procesador:
            return self.procesador.resultados
        return []
    
    def obtener_estadisticas_procesamiento(self) -> Dict:
        """Retorna estadísticas del procesamiento actual"""
        if self.procesador:
            return self.procesador.stats.copy()
        return {'total': 0, 'incluidas': 0, 'excluidas': 0, 'errores': 0}
    
    def analizar_y_clasificar_desde_scraping_pendiente(
        self,
        excel_path: str,
        callback_progreso=None,
        callback_log=None
    ) -> Dict[str, int]:
        """
        Analiza y clasifica noticias desde Contenido_Manual que ya tienen contenido
        Las inserta en las hojas correspondientes eliminando duplicados
        
        LÓGICA DE ESTADO:
        - Solo procesa noticias con columna 'estado' vacía (no analizadas)
        - Marca como 'EXITOSO' las noticias procesadas correctamente
        - Añade nota 'INCLUIDA' o 'EXCLUIDA' según resultado del análisis
        
        Args:
            excel_path: Ruta al archivo Excel
            callback_progreso: Función callback para actualizar progreso en UI
            callback_log: Función callback para enviar logs a UI
            
        Returns:
            Diccionario con estadísticas del procesamiento
        """
        import pandas as pd
        from .reprocesamiento import (
            insertar_noticia_ordenada_por_id,
            eliminar_duplicados_por_id
        )
        
        logger.info("="*80)
        logger.info("🔍 INICIANDO RE-ANÁLISIS Y CLASIFICACIÓN DESDE CONTENIDO_MANUAL")
        logger.info("="*80)
        
        if callback_log:
            callback_log("="*80)
            callback_log("🔍 RE-ANÁLISIS Y CLASIFICACIÓN DE NOTICIAS CON CONTENIDO MANUAL")
            callback_log("="*80)
        
        stats = {
            'total': 0,
            'incluidas': 0,
            'excluidas': 0,
            'errores': 0,
            'duplicados_eliminados': 0
        }
        
        try:
            # Leer Excel - Hoja Contenido_Manual
            df_pendiente = pd.read_excel(excel_path, sheet_name='Contenido_Manual')
            nombre_hoja = 'Contenido_Manual'
            
            msg = f"✅ Hoja {nombre_hoja} leída: {len(df_pendiente)} filas"
            logger.info(msg)
            if callback_log:
                callback_log(msg)
            
            # Filtrar solo noticias con contenido válido
            # Convertir a string primero para evitar errores
            df_pendiente['contenido_noticia'] = df_pendiente['contenido_noticia'].astype(str)
            
            # Asegurar que existe la columna 'estado'
            if 'estado' not in df_pendiente.columns:
                df_pendiente['estado'] = ''
            
            # Asegurar que existe la columna 'notas'
            if 'notas' not in df_pendiente.columns:
                df_pendiente['notas'] = ''
            
            # Filtrar solo noticias con contenido válido Y estado vacío (no procesadas)
            noticias_con_contenido = df_pendiente[
                (df_pendiente['contenido_noticia'].notna()) &
                (df_pendiente['contenido_noticia'] != '') &
                (df_pendiente['contenido_noticia'] != 'nan') &
                (df_pendiente['contenido_noticia'] != 'HUMANO DEBE INSERTAR NOTICIA') &
                (df_pendiente['contenido_noticia'].str.len() > 200) &
                ((df_pendiente['estado'].isna()) | (df_pendiente['estado'] == '') | (df_pendiente['estado'] != 'EXITOSO'))
            ].copy()
            
            stats['total'] = len(noticias_con_contenido)
            
            if stats['total'] == 0:
                msg = "\n⚠️  No hay noticias con contenido válido para analizar"
                msg += "\n💡 Recuerda: El contenido debe tener más de 200 caracteres"
                logger.info(msg)
                if callback_log:
                    callback_log(msg)
                return stats
            
            msg = f"\n📊 Total de noticias con contenido: {stats['total']}"
            logger.info(msg)
            if callback_log:
                callback_log(msg)
            
            # Procesar cada noticia
            for idx, row in noticias_con_contenido.iterrows():
                try:
                    id_noticia = row.get('id_noticia')
                    titulo = row.get('titulo', '')
                    fecha = row.get('fecha', '')
                    contenido = row.get('contenido_noticia', '')
                    
                    msg = f"\n{'='*80}"
                    msg += f"\n📰 Procesando noticia {idx+1}/{stats['total']}"
                    msg += f"\n   ID: {id_noticia}"
                    msg += f"\n   Título: {titulo[:60]}..."
                    msg += f"\n{'='*80}"
                    logger.info(msg)
                    if callback_log:
                        callback_log(msg)
                    
                    # Crear diccionario de noticia para análisis
                    noticia_para_analisis = {
                        'id_noticia': id_noticia,
                        'titulo': titulo,
                        'fecha': fecha,
                        'contenido_noticia': contenido
                    }
                    
                    # Analizar con IA
                    msg = "🤖 Analizando contenido con IA..."
                    logger.info(msg)
                    if callback_log:
                        callback_log(msg)
                    
                    resultado = self.analizador.analizar_noticia(noticia_para_analisis)
                    
                    # Agregar campos faltantes del row original
                    metodo = row.get('metodo_scraping_exitoso', '')
                    if not metodo or pd.isna(metodo) or metodo == '':
                        metodo = 'Manual'  # Marcar como insertado manualmente
                    
                    resultado.update({
                        'URL_Directa': row.get('URL_Directa', ''),
                        'url_decodificada': row.get('URL_Directa', ''),
                        'link': row.get('URL_Directa', ''),
                        'metodo_scraping_exitoso': metodo,
                        'intentos_scraping': row.get('intentos_scraping', 0) if not pd.isna(row.get('intentos_scraping')) else 0,
                        'ultimo_intento': row.get('ultimo_intento', '') if not pd.isna(row.get('ultimo_intento')) else '',
                    })
                    
                    # Insertar en hoja correspondiente
                    if not resultado.get('excluir', True):  # Si NO se excluye = incluir
                        msg = f"✅ Noticia INCLUIDA - Insertando en Datos_filtrados..."
                        logger.info(msg)
                        if callback_log:
                            callback_log(msg)
                        
                        # Eliminar de Datos_excluidos si existe
                        duplicados_excluidos = eliminar_duplicados_por_id(
                            excel_path,
                            'Datos_excluidos',
                            id_noticia,
                            callback_log=callback_log
                        )
                        
                        # Insertar en Datos_filtrados
                        duplicados = insertar_noticia_ordenada_por_id(
                            excel_path,
                            'Datos_filtrados',
                            resultado,
                            callback_log=callback_log
                        )
                        stats['incluidas'] += 1
                        stats['duplicados_eliminados'] += duplicados + duplicados_excluidos
                    else:
                        msg = f"❌ Noticia EXCLUIDA - Motivo: {resultado.get('motivo_exclusion', 'N/A')}"
                        logger.info(msg)
                        if callback_log:
                            callback_log(msg)
                        
                        msg = f"   Insertando en Datos_excluidos..."
                        logger.info(msg)
                        if callback_log:
                            callback_log(msg)
                        
                        # Eliminar de Datos_filtrados si existe
                        duplicados_filtrados = eliminar_duplicados_por_id(
                            excel_path,
                            'Datos_filtrados',
                            id_noticia,
                            callback_log=callback_log
                        )
                        
                        # Insertar en Datos_excluidos
                        duplicados = insertar_noticia_ordenada_por_id(
                            excel_path,
                            'Datos_excluidos',
                            resultado,
                            callback_log=callback_log
                        )
                        stats['excluidas'] += 1
                        stats['duplicados_eliminados'] += duplicados + duplicados_filtrados
                    
                    # Actualizar también en Datos_completos (siempre reemplazar)
                    insertar_noticia_ordenada_por_id(
                        excel_path,
                        'Datos_completos',
                        resultado,
                        callback_log=callback_log,
                        reemplazar_siempre=True
                    )
                    
                    # CRÍTICO: Marcar como EXITOSO en Contenido_Manual y añadir nota
                    try:
                        excel_data = pd.read_excel(excel_path, sheet_name=None)
                        
                        if nombre_hoja in excel_data:
                            df_revision = excel_data[nombre_hoja]
                            
                            # Asegurar que existen las columnas
                            if 'estado' not in df_revision.columns:
                                df_revision['estado'] = ''
                            if 'notas' not in df_revision.columns:
                                df_revision['notas'] = ''
                            
                            # Buscar la noticia por ID
                            mask = df_revision['id_noticia'] == id_noticia
                            if mask.any():
                                # Marcar como EXITOSO
                                df_revision.loc[mask, 'estado'] = 'EXITOSO'
                                
                                # Añadir nota según resultado
                                if not resultado.get('excluir', True):
                                    df_revision.loc[mask, 'notas'] = 'INCLUIDA'
                                else:
                                    df_revision.loc[mask, 'notas'] = 'EXCLUIDA'
                                
                                # Guardar cambios
                                excel_data[nombre_hoja] = df_revision
                                with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                                    for sheet_name, df_sheet in excel_data.items():
                                        df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)
                                
                                msg = f"   ✅ Marcada como EXITOSO en {nombre_hoja}"
                                logger.info(msg)
                                if callback_log:
                                    callback_log(msg)
                    except Exception as e:
                        logger.warning(f"No se pudo actualizar estado en {nombre_hoja}: {e}")
                    
                    # Actualizar progreso
                    progreso = int((idx + 1) / stats['total'] * 100)
                    if callback_progreso:
                        callback_progreso(progreso, f"Procesadas: {idx+1}/{stats['total']}")
                    
                except Exception as e:
                    logger.error(f"Error procesando noticia {id_noticia}: {e}")
                    if callback_log:
                        callback_log(f"❌ Error procesando noticia {id_noticia}: {e}")
                    stats['errores'] += 1
                    continue
            
            # Resumen final
            msg = f"\n{'='*80}"
            msg += f"\n📊 RESUMEN DE ANÁLISIS Y CLASIFICACIÓN"
            msg += f"\n{'='*80}"
            msg += f"\n✅ Noticias incluidas: {stats['incluidas']}"
            msg += f"\n❌ Noticias excluidas: {stats['excluidas']}"
            msg += f"\n⚠️  Errores: {stats['errores']}"
            msg += f"\n🗑️  Duplicados eliminados: {stats['duplicados_eliminados']}"
            msg += f"\n{'='*80}"
            logger.info(msg)
            if callback_log:
                callback_log(msg)
            
            if callback_progreso:
                callback_progreso(100, "Análisis completado")
            
            return stats
            
        except Exception as e:
            error_msg = f"❌ Error en análisis y clasificación: {e}"
            logger.error(error_msg)
            if callback_log:
                callback_log(error_msg)
            stats['errores'] += 1
            return stats
    
    def reanalizar_revision_manual(
        self,
        excel_path: str,
        callback_progreso=None,
        callback_log=None
    ) -> Dict[str, int]:
        """
        Re-analiza noticias de Revision_manual con prompt/código actualizado
        Las reclasifica y mueve a las hojas correspondientes
        
        Args:
            excel_path: Ruta al archivo Excel
            callback_progreso: Función callback para actualizar progreso en UI
            callback_log: Función callback para enviar logs a UI
            
        Returns:
            Diccionario con estadísticas del procesamiento
        """
        import pandas as pd
        from .reprocesamiento import (
            insertar_noticia_ordenada_por_id,
            eliminar_duplicados_por_id
        )
        
        logger.info("="*80)
        logger.info("🔍 RE-ANÁLISIS DE REVISION_MANUAL")
        logger.info("="*80)
        
        stats = {'total': 0, 'incluidas': 0, 'excluidas': 0, 'errores': 0, 'aun_requieren_revision': 0}
        
        try:
            # Leer hojas del Excel
            if callback_log:
                callback_log("📂 Leyendo archivo Excel...")
            
            df_revision = pd.read_excel(excel_path, sheet_name='Revision_manual')
            df_filtrados = pd.read_excel(excel_path, sheet_name='Datos_filtrados')
            df_excluidos = pd.read_excel(excel_path, sheet_name='Datos_excluidos')
            
            total_noticias = len(df_revision)
            stats['total'] = total_noticias
            
            if total_noticias == 0:
                if callback_log:
                    callback_log("ℹ️  No hay noticias en Revision_manual")
                return stats
            
            if callback_log:
                callback_log(f"📊 Total de noticias a re-analizar: {total_noticias}")
                callback_log("")
            
            # Re-analizar cada noticia
            noticias_reclasificadas = []
            
            for idx, row in df_revision.iterrows():
                try:
                    progreso = int((idx + 1) / total_noticias * 100)
                    if callback_progreso:
                        callback_progreso(progreso, f"Re-analizando {idx+1}/{total_noticias}")
                    
                    # Extraer datos de la noticia
                    noticia_dict = {
                        'titulo': row.get('titulo', ''),
                        'fecha': row.get('fecha', ''),
                        'noticia': row.get('noticia', ''),
                        'link_noticia': row.get('link_noticia', ''),
                        'region': row.get('region', ''),
                        'comuna': row.get('comuna', ''),
                        'localidad': row.get('localidad', '')
                    }
                    
                    # Re-analizar con IA
                    resultado = self.analizador.analizar_noticia(noticia_dict)
                    
                    # Verificar si aún requiere revisión
                    if resultado.get('requiere_revision_manual', False):
                        stats['aun_requieren_revision'] += 1
                        if callback_log:
                            callback_log(f"⚠️  Noticia {idx+1} aún requiere revisión: {noticia_dict['titulo'][:60]}...")
                        continue
                    
                    # Clasificar según resultado
                    if resultado.get('excluir', False):
                        # Excluida
                        stats['excluidas'] += 1
                        noticia_dict.update(resultado)
                        df_excluidos = insertar_noticia_ordenada_por_id(df_excluidos, noticia_dict)
                        noticias_reclasificadas.append(idx)
                        
                        if callback_log:
                            motivo = resultado.get('motivo_exclusion', 'Sin motivo')
                            callback_log(f"❌ Noticia {idx+1} EXCLUIDA: {motivo}")
                    
                    else:
                        # Incluida
                        stats['incluidas'] += 1
                        noticia_dict.update(resultado)
                        df_filtrados = insertar_noticia_ordenada_por_id(df_filtrados, noticia_dict)
                        noticias_reclasificadas.append(idx)
                        
                        if callback_log:
                            tipo = resultado.get('tipo_conflicto', 'Sin tipo')
                            callback_log(f"✅ Noticia {idx+1} INCLUIDA: {tipo}")
                
                except Exception as e:
                    stats['errores'] += 1
                    logger.error(f"Error re-analizando noticia {idx}: {e}")
                    if callback_log:
                        callback_log(f"❌ Error en noticia {idx+1}: {str(e)[:100]}")
            
            # Eliminar noticias reclasificadas de Revision_manual
            df_revision = df_revision.drop(noticias_reclasificadas)
            
            # Eliminar duplicados
            if callback_log:
                callback_log("\n🔄 Eliminando duplicados...")
            
            df_filtrados = eliminar_duplicados_por_id(df_filtrados)
            df_excluidos = eliminar_duplicados_por_id(df_excluidos)
            
            # Guardar cambios
            if callback_log:
                callback_log("\n💾 Guardando cambios en Excel...")
            
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_revision.to_excel(writer, sheet_name='Revision_manual', index=False)
                df_filtrados.to_excel(writer, sheet_name='Datos_filtrados', index=False)
                df_excluidos.to_excel(writer, sheet_name='Datos_excluidos', index=False)
            
            # Resumen final
            msg = f"""
✅ RE-ANÁLISIS COMPLETADO

📊 Estadísticas Finales:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Total re-analizadas: {stats['total']}
• Reclasificadas como incluidas: {stats['incluidas']}
• Reclasificadas como excluidas: {stats['excluidas']}
• Aún requieren revisión: {stats['aun_requieren_revision']}
• Errores: {stats['errores']}

💾 Cambios guardados en: {excel_path}
"""
            logger.info(msg)
            if callback_log:
                callback_log(msg)
            
            if callback_progreso:
                callback_progreso(100, "Re-análisis completado")
            
            return stats
            
        except Exception as e:
            error_msg = f"❌ Error en re-análisis: {e}"
            logger.error(error_msg)
            if callback_log:
                callback_log(error_msg)
            stats['errores'] += 1
            return stats


# Funciones auxiliares para importación directa
def crear_filtrador(api_key: str, provider: str = "google") -> FiltradorIA:
    """
    Función auxiliar para crear instancia del filtrador
    
    Args:
        api_key: API Key del provider
        provider: "google", "abacus" o "openrouter"
        
    Returns:
        Instancia de FiltradorIA
    """
    return FiltradorIA(api_key, provider)


# Configurar logging al importar el módulo
setup_logging()


# Exportar clases y funciones principales
__all__ = [
    'FiltradorIA',
    'crear_filtrador',
    'AnalizadorIA',
    'ProcesadorExcel',
    'TIPOS_CONFLICTO',
    'TIPOS_ACCION',
    'TIPOS_ACTOR_DEMANDANTE',
    'TIPOS_ACTOR_DEMANDADO',
    'REGIONES_CHILE',
    'TIPOS_SECTOR_ECONOMICO'
]
