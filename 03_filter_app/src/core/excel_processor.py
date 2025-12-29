"""
procesamiento.py - Módulo de procesamiento de archivos Excel
"""

import logging
import os
import shutil
import time
from datetime import datetime
from typing import Dict, Optional, Callable
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .ai_classifier import AnalizadorIA
from .stats_generator import EstadisticasManager
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class ProcesadorExcel:
    """Gestiona el procesamiento de archivos Excel"""
    
    def __init__(self, analizador: AnalizadorIA):
        self.analizador = analizador
        self.resultados = []
        self.resultados_dict = {}
        self.noticias_pendientes = []
        self.stats = {'total': 0, 'incluidas': 0, 'excluidas': 0, 'errores': 0}
        self.output_path_actual = None
        self.cuota_excedida = False
        self.db: DatabaseManager = None  # Base de datos SQLite (opcional, funciona en paralelo con Excel)
    
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
    ):
        """
        Procesa archivo Excel con guardado incremental
        
        Args:
            excel_path: Ruta al Excel de entrada
            hoja: Nombre de la hoja a procesar
            inicio: Índice de inicio (0-based)
            fin: Índice de fin (0-based)
            output_path: Ruta del archivo de salida
            callback: Función para actualizar progreso
            max_workers: Número de workers paralelos (1 = secuencial)
            reemplazar_duplicadas: Si True, reanaliza noticias procesadas
        """
        # Leer Excel
        try:
            df_input = pd.read_excel(excel_path, sheet_name=hoja)
        except Exception as e:
            raise Exception(f"Error leyendo Excel (hoja '{hoja}'): {e}")
        
        total_noticias = len(df_input)
        inicio = inicio if inicio is not None else 0
        fin = fin if fin is not None else total_noticias
        
        # Validar rango
        if inicio < 0 or inicio >= total_noticias:
            raise ValueError(f"Índice de inicio inválido: {inicio}")
        if fin <= inicio or fin > total_noticias:
            raise ValueError(f"Índice de fin inválido: {fin}")
        
        self.output_path_actual = output_path
        
        # =====================================================================
        # INICIALIZAR BASE DE DATOS SQLITE (funciona en paralelo con Excel)
        # =====================================================================
        db_path = output_path.replace('.xlsx', '.db')
        try:
            self.db = DatabaseManager(db_path)
            print(f"🗄️  Base de datos SQLite: {db_path}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar SQLite: {e}")
            self.db = None
        
        # Cargar resultados existentes
        self._cargar_resultados_existentes(output_path, df_input)
        
        # Extraer subset
        df_subset = df_input.iloc[inicio:fin]
        noticias_a_procesar = len(df_subset)
        
        print(f"📊 Procesando noticias {inicio+1} a {fin} de {total_noticias}")
        print(f"   Total a procesar: {noticias_a_procesar}")
        
        # Procesamiento paralelo o secuencial
        if max_workers > 1:
            logger.info(f"🚀 Procesamiento paralelo: {max_workers} workers")
            self._procesar_paralelo(
                df_subset, inicio, total_noticias, 
                output_path, callback, max_workers, reemplazar_duplicadas
            )
        else:
            self._procesar_secuencial(
                df_subset, inicio, total_noticias, 
                output_path, callback, reemplazar_duplicadas
            )
        
        # Guardar resultados finales
        self._guardar_incremental(output_path)
        print("✅ Procesamiento completado")
        
        return self.resultados
    
    def _cargar_resultados_existentes(self, output_path: str, df_input: pd.DataFrame):
        """Carga resultados existentes si el archivo existe"""
        if os.path.exists(output_path):
            try:
                try:
                    df_existing = pd.read_excel(output_path, sheet_name='Datos_completos')
                except:
                    df_existing = pd.read_excel(output_path, sheet_name='Datos_Completos')
                
                # Rellenar fechas faltantes
                if 'fecha' not in df_existing.columns:
                    df_existing['fecha'] = pd.NA
                
                fechas_dict = {}
                for idx, row in df_input.iterrows():
                    id_not = row.get('id_noticia', idx + 1)
                    fecha = (
                        row.get('Fecha_Extraida_ISO', '') or 
                        row.get('fecha_scraping', '') or 
                        row.get('fecha', '') or ''
                    )
                    if fecha and fecha != '':
                        fechas_dict[id_not] = fecha
                
                mask = df_existing['fecha'].isna() | (df_existing['fecha'] == '')
                if mask.any():
                    df_existing.loc[mask, 'fecha'] = df_existing.loc[mask, 'id_noticia'].map(fechas_dict)
                
                self.resultados = df_existing.to_dict('records')
                
                self.resultados_dict = {}
                for idx, r in enumerate(self.resultados):
                    id_not = r.get('id_noticia')
                    if id_not:
                        self.resultados_dict[id_not] = idx
                
                logger.info(f"📂 Cargados {len(self.resultados)} resultados existentes")
                
            except Exception as e:
                logger.warning(f"No se pudieron cargar resultados: {e}")
                self.resultados = []
                self.resultados_dict = {}
        else:
            self.resultados = []
            self.resultados_dict = {}
    
    def _procesar_secuencial(
        self, 
        df_subset: pd.DataFrame, 
        inicio: int, 
        total_noticias: int,
        output_path: str, 
        callback: Optional[Callable],
        reemplazar_duplicadas: bool
    ):
        """Procesamiento secuencial (1 noticia a la vez)"""
        for idx_local, (idx_global, row) in enumerate(df_subset.iterrows()):
            noticia = row.to_dict()
            noticia_num = inicio + idx_local + 1
            id_noticia_actual = noticia.get('id_noticia', noticia_num)
            
            # Saltar o reemplazar duplicadas
            if id_noticia_actual in self.resultados_dict:
                if not reemplazar_duplicadas:
                    print(f"⏭️  [{noticia_num}/{total_noticias}] Saltando (ya procesada)")
                    if callback:
                        callback(idx_local + 1, len(df_subset), "⏭️ Saltando")
                    continue
                else:
                    print(f"🔄 [{noticia_num}/{total_noticias}] Reanalizando")
            
            if callback:
                callback(idx_local + 1, len(df_subset), noticia.get('titulo', '')[:50])
            
            print(f"[{noticia_num}/{total_noticias}] Procesando: {noticia.get('titulo', '')[:60]}...")
            
            # Analizar
            try:
                resultado = self.analizador.analizar_noticia(noticia)
                llamada_api = True
            except Exception as e:
                print(f"⚠️  Error: {e}")
                resultado = {
                    'excluir': True,
                    'motivo_exclusion': 'Motivo 13: Error de procesamiento',
                    'explicacion_exclusion': 'Error de procesamiento - Requiere revisión manual',
                    'requiere_revision_manual': True
                }
                llamada_api = False
            
            # Verificar si es contenido insuficiente
            motivo = resultado.get('motivo_exclusion') or ''
            explicacion = resultado.get('explicacion_exclusion') or ''
            if 'Sin contenido' in motivo or 'Requiere scraping' in explicacion:
                # Agregar a Contenido_Manual
                from .reprocesamiento import crear_fila_scraping_pendiente
                fila = crear_fila_scraping_pendiente(noticia, motivo)
                self.noticias_pendientes.append(fila)
            
            self._agregar_resultado(noticia, resultado, id_noticia_actual, reemplazar_duplicadas)
            
            # Guardar cada 100
            if (idx_local + 1) % 100 == 0:
                self._guardar_incremental(output_path)
                print(f"💾 Guardado incremental: {len(self.resultados)} noticias")
            
            # Pausar si llamó API
            if llamada_api:
                time.sleep(0.3)
    
    def _procesar_paralelo(
        self,
        df_subset: pd.DataFrame,
        inicio: int,
        total_noticias: int,
        output_path: str,
        callback: Optional[Callable],
        max_workers: int,
        reemplazar_duplicadas: bool
    ):
        """Procesamiento paralelo con ThreadPoolExecutor"""
        noticias_pendientes = []
        
        # Filtrar noticias
        for idx_local, (idx_global, row) in enumerate(df_subset.iterrows()):
            noticia = row.to_dict()
            noticia_num = inicio + idx_local + 1
            id_noticia_actual = noticia.get('id_noticia', noticia_num)
            
            if id_noticia_actual not in self.resultados_dict:
                noticias_pendientes.append((idx_local, noticia_num, noticia, id_noticia_actual))
            elif reemplazar_duplicadas:
                print(f"🔄 [{noticia_num}/{total_noticias}] Marcada para reanálisis")
                noticias_pendientes.append((idx_local, noticia_num, noticia, id_noticia_actual))
            else:
                print(f"⏭️  [{noticia_num}/{total_noticias}] Saltando")
        
        if not noticias_pendientes:
            print("✅ Todas las noticias ya fueron procesadas")
            return
        
        print(f"🚀 Procesando {len(noticias_pendientes)} noticias con {max_workers} workers")
        
        lock = threading.Lock()
        procesadas = 0
        
        def procesar_thread(idx_local, noticia_num, noticia, id_noticia_actual):
            nonlocal procesadas
            
            try:
                resultado = self.analizador.analizar_noticia(noticia)
                
                with lock:
                    # Verificar si es contenido insuficiente
                    motivo = resultado.get('motivo_exclusion') or ''
                    explicacion = resultado.get('explicacion_exclusion') or ''
                    if 'Sin contenido' in motivo or 'Requiere scraping' in explicacion:
                        # Agregar a Contenido_Manual
                        from .reprocesamiento import crear_fila_scraping_pendiente
                        fila = crear_fila_scraping_pendiente(noticia, motivo)
                        self.noticias_pendientes.append(fila)
                    
                    self._agregar_resultado(noticia, resultado, id_noticia_actual, reemplazar_duplicadas)
                    procesadas += 1
                    
                    if callback:
                        callback(procesadas, len(noticias_pendientes), noticia.get('titulo', '')[:50])
                    
                    if procesadas % 100 == 0:
                        self._guardar_incremental(output_path)
                
                return True
                
            except Exception as e:
                print(f"⚠️  Error en noticia {noticia_num}: {e}")
                
                resultado = {
                    'excluir': True,
                    'motivo_exclusion': 'Motivo 13: Error de procesamiento',
                    'explicacion_exclusion': 'Error de procesamiento - Requiere revisión manual',
                    'requiere_revision_manual': True
                }
                
                with lock:
                    self._agregar_resultado(noticia, resultado, id_noticia_actual)
                    procesadas += 1
                
                return False
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futuros = {
                executor.submit(procesar_thread, idx_local, noticia_num, noticia, id_noticia_actual): (idx_local, noticia_num)
                for idx_local, noticia_num, noticia, id_noticia_actual in noticias_pendientes
            }
            
            for futuro in as_completed(futuros):
                try:
                    futuro.result(timeout=60)
                except Exception as e:
                    idx_local, noticia_num = futuros[futuro]
                    logger.error(f"❌ Error crítico en noticia {noticia_num}: {e}")
        
        print(f"✅ Procesamiento paralelo completado: {procesadas} noticias")
    
    def _agregar_resultado(
        self, 
        noticia: dict, 
        resultado: dict, 
        id_noticia_actual: int,
        reemplazar: bool = False
    ):
        """Agrega o reemplaza un resultado"""
        fecha_noticia = (
            noticia.get('Fecha_Extraida_ISO', '') or 
            noticia.get('fecha_scraping', '') or 
            noticia.get('fecha', '') or ''
        )
        
        # Extraer contenido completo de la noticia original
        # PRIORIDAD: contenido_noticia (manual) > Contenido_Completo (scraping) > otros
        contenido_completo = (
            noticia.get('contenido_noticia', '') or  # ✅ NUEVO: Contenido pegado manualmente en reanálisis
            noticia.get('Contenido_Completo', '') or 
            noticia.get('contenido_extraido', '') or 
            noticia.get('contenido', '') or
            resultado.get('noticia', '')  # Fallback al contenido procesado por IA
        )
        
        # Extraer URL directa de la noticia
        url_directa = (
            noticia.get('URL_Directa', '') or 
            noticia.get('url_decodificada', '') or 
            noticia.get('link', '') or 
            noticia.get('url', '')
        )
        
        # Extraer fuente de la noticia original
        fuente = (
            noticia.get('fuente', '') or
            noticia.get('Fuente', '') or
            noticia.get('source', '') or
            ''
        )
        
        registro = {
            'id_noticia': id_noticia_actual,
            'fecha': fecha_noticia,
            'titulo': noticia.get('titulo', ''),
            'fuente': fuente,
            'noticia': contenido_completo,
            'resumen': resultado.get('resumen', ''),
            'palabras_clave': resultado.get('palabras_clave', ''),
            'tono_emocional': resultado.get('tono_emocional', ''),
            'excluir': resultado.get('excluir', True),
            'motivo_exclusion': resultado.get('motivo_exclusion', ''),
            'explicacion_exclusion': resultado.get('explicacion_exclusion', ''),
            'tipo_conflicto': resultado.get('tipo_conflicto', ''),
            'explicacion_conflicto': resultado.get('explicacion_conflicto', ''),
            'tipo_accion': resultado.get('tipo_accion', ''),
            'explicacion_accion': resultado.get('explicacion_accion', ''),
            'actor_demandante': resultado.get('actor_demandante', ''),
            'explicacion_demandante': resultado.get('explicacion_demandante', ''),
            'actor_demandado': resultado.get('actor_demandado', ''),
            'explicacion_demandado': resultado.get('explicacion_demandado', ''),
            'region': resultado.get('region', ''),
            'provincia': resultado.get('provincia', ''),
            'comuna': resultado.get('comuna', ''),
            'localidad': resultado.get('localidad', ''),
            'sector_economico': resultado.get('sector_economico', ''),
            'proyecto_especifico': resultado.get('proyecto_especifico', ''),
            'escala_conflicto': resultado.get('escala_conflicto', ''),
            'vinculo_transicion': resultado.get('vinculo_transicion', ''),
            'justificacion_transicion': resultado.get('justificacion_transicion', ''),
            'notas': resultado.get('notas', ''),
            'requiere_revision_manual': resultado.get('requiere_revision_manual', False),
            'link_noticia': url_directa,
            # ✅ MÉTRICAS DE IA - Columnas nuevas
            'tokens_input': resultado.get('tokens_input', 0),
            'tokens_output': resultado.get('tokens_output', 0),
            'tokens_totales': resultado.get('tokens_totales', 0),
            'latencia_ms': resultado.get('latencia_ms', 0),
            'modelo_usado': resultado.get('modelo_usado', ''),
            'costo_estimado_usd': resultado.get('costo_estimado', 0),
        }
        
        # Agregar o reemplazar
        if reemplazar and id_noticia_actual in self.resultados_dict:
            idx_existente = self.resultados_dict[id_noticia_actual]
            self.resultados[idx_existente] = registro
        else:
            self.resultados.append(registro)
            self.resultados_dict[id_noticia_actual] = len(self.resultados) - 1
        
        # =====================================================================
        # GUARDAR EN SQLITE (en paralelo con Excel)
        # =====================================================================
        if self.db:
            try:
                self.db.insertar_noticia(registro, noticia)
            except Exception as e:
                logger.warning(f"⚠️ Error guardando en SQLite: {e}")
        
        # Actualizar stats
        if resultado.get('excluir', True):
            self.stats['excluidas'] += 1
        else:
            self.stats['incluidas'] += 1
    
    def _guardar_incremental(self, output_path: str):
        """Guarda resultados incrementalmente AÑADIENDO a los existentes"""
        if not self.resultados:
            return
        
        try:
            # CRÍTICO: Cargar datos existentes y COMBINAR con nuevos
            df_nuevos = pd.DataFrame(self.resultados)
            
            if os.path.exists(output_path):
                try:
                    # Cargar datos existentes
                    df_existing = pd.read_excel(output_path, sheet_name='Datos_completos')
                    logger.info(f"📊 Datos existentes: {len(df_existing)} registros")
                    logger.info(f"📊 Datos nuevos: {len(df_nuevos)} registros")
                    
                    # COMBINAR: Mantener existentes + añadir nuevos
                    # Usar id_noticia como clave única
                    df_combined = pd.concat([df_existing, df_nuevos], ignore_index=True)
                    
                    # Eliminar duplicados manteniendo el último (más reciente)
                    df_combined = df_combined.drop_duplicates(subset=['id_noticia'], keep='last')
                    
                    df = df_combined.sort_values('id_noticia').reset_index(drop=True)
                    logger.info(f"✅ Total combinado: {len(df)} registros")
                    
                    # Backup de seguridad (un solo archivo que se actualiza)
                    backup = output_path.replace('.xlsx', '_backup.xlsx')
                    shutil.copy2(output_path, backup)
                    logger.info(f"💾 Backup actualizado: {backup}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo cargar archivo existente: {e}")
                    df = df_nuevos.sort_values('id_noticia').reset_index(drop=True)
            else:
                df = df_nuevos.sort_values('id_noticia').reset_index(drop=True)
            
            # Asegurar que existe la columna 'excluir'
            if 'excluir' not in df.columns:
                logger.warning("Columna 'excluir' no encontrada, usando 'motivo_exclusion'")
                df['excluir'] = df['motivo_exclusion'].notna()
            
            # CRÍTICO: Cargar hojas existentes y combinar con nuevas
            df_filtradas_existentes = pd.DataFrame()
            df_excluidas_existentes = pd.DataFrame()
            df_revision_existentes = pd.DataFrame()
            df_contenido_manual_existente = pd.DataFrame()
            
            if os.path.exists(output_path):
                try:
                    # Intentar cargar hojas existentes
                    try:
                        df_filtradas_existentes = pd.read_excel(output_path, sheet_name='Datos_filtrados')
                        logger.info(f"📊 Datos_filtrados existentes: {len(df_filtradas_existentes)} registros")
                    except:
                        pass
                    
                    try:
                        df_excluidas_existentes = pd.read_excel(output_path, sheet_name='Datos_excluidos')
                        logger.info(f"📊 Datos_excluidos existentes: {len(df_excluidas_existentes)} registros")
                    except:
                        pass
                    
                    try:
                        df_revision_existentes = pd.read_excel(output_path, sheet_name='Revision_manual')
                        logger.info(f"📊 Revision_manual existentes: {len(df_revision_existentes)} registros")
                    except:
                        pass
                    
                    try:
                        df_contenido_manual_existente = pd.read_excel(output_path, sheet_name='Contenido_Manual')
                        logger.info(f"📊 Contenido_Manual existente: {len(df_contenido_manual_existente)} registros")
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"⚠️ Error cargando hojas existentes: {e}")
            
            # Separar noticias NUEVAS usando el campo 'excluir'
            df_filtradas_nuevas = df[df['excluir'] == False].copy()
            df_excluidas_nuevas = df[df['excluir'] == True].copy()
            df_revision_nuevas = df[df.get('requiere_revision_manual', False) == True].copy()
            
            # COMBINAR hojas existentes con nuevas (sin duplicados)
            if len(df_filtradas_existentes) > 0:
                df_filtradas = pd.concat([df_filtradas_existentes, df_filtradas_nuevas], ignore_index=True)
                df_filtradas = df_filtradas.drop_duplicates(subset=['id_noticia'], keep='last')
            else:
                df_filtradas = df_filtradas_nuevas
            
            if len(df_excluidas_existentes) > 0:
                df_excluidas = pd.concat([df_excluidas_existentes, df_excluidas_nuevas], ignore_index=True)
                df_excluidas = df_excluidas.drop_duplicates(subset=['id_noticia'], keep='last')
            else:
                df_excluidas = df_excluidas_nuevas
            
            if len(df_revision_existentes) > 0:
                # PRESERVAR decisiones del usuario en registros existentes
                cols_decision = ['decision_usuario', 'motivo_decision_usuario', 'fecha_revision']
                decisiones_existentes = {}
                for col in cols_decision:
                    if col in df_revision_existentes.columns:
                        for _, row in df_revision_existentes.iterrows():
                            if pd.notna(row.get(col)) and str(row.get(col)).strip():
                                key = row.get('id_noticia')
                                if key not in decisiones_existentes:
                                    decisiones_existentes[key] = {}
                                decisiones_existentes[key][col] = row[col]
                
                df_revision = pd.concat([df_revision_existentes, df_revision_nuevas], ignore_index=True)
                df_revision = df_revision.drop_duplicates(subset=['id_noticia'], keep='last')
                
                # Restaurar decisiones del usuario
                for col in cols_decision:
                    if col not in df_revision.columns:
                        df_revision[col] = ''
                    for id_noticia, decisiones in decisiones_existentes.items():
                        if col in decisiones:
                            mask = df_revision['id_noticia'] == id_noticia
                            df_revision.loc[mask, col] = decisiones[col]
            else:
                df_revision = df_revision_nuevas
            
            logger.info(f"✅ Datos_filtrados combinados: {len(df_filtradas)} registros")
            logger.info(f"✅ Datos_excluidos combinados: {len(df_excluidas)} registros")
            logger.info(f"✅ Revision_manual combinados: {len(df_revision)} registros")
            
            # Backup
            if os.path.exists(output_path):
                backup_path = output_path.replace('.xlsx', '_backup.xlsx')
                shutil.copy2(output_path, backup_path)
            
            # Guardar
            temp_path = output_path.replace('.xlsx', '_temp.xlsx')
            
            with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                # Columnas para el Excel - ORDENADAS SEGÚN PREFERENCIA DEL USUARIO
                columnas = [
                    # === IDENTIFICACIÓN ===
                    'id_noticia', 'fecha', 'fuente',
                    
                    # === CONTENIDO (noticia primero, luego titulo) ===
                    'noticia', 'titulo', 'resumen', 'palabras_clave', 'tono_emocional',
                    
                    # === EXCLUSIÓN (justo después de palabras clave) ===
                    'motivo_exclusion', 'explicacion_exclusion',
                    
                    # === CLASIFICACIÓN (si es conflicto) ===
                    'tipo_conflicto', 'explicacion_conflicto',
                    'tipo_accion', 'explicacion_accion',
                    
                    # === ACTORES ===
                    'actor_demandante', 'explicacion_demandante',
                    'actor_demandado', 'explicacion_demandado',
                    
                    # === UBICACIÓN GEOGRÁFICA ===
                    'region', 'provincia', 'comuna', 'localidad',
                    
                    # === CONTEXTO DEL CONFLICTO ===
                    'sector_economico', 'proyecto_especifico', 'escala_conflicto',
                    'vinculo_transicion', 'justificacion_transicion',
                    
                    # === CONTROL Y REVISIÓN ===
                    'requiere_revision_manual', 'notas',
                    
                    # === LINK AL FINAL ===
                    'link_noticia'
                ]
                
                # Filtrar columnas que existen en el DataFrame (evitar KeyError)
                columnas_existentes = [c for c in columnas if c in df.columns]
                
                df[columnas_existentes].to_excel(writer, sheet_name='Datos_completos', index=False)
                
                if len(df_filtradas) > 0:
                    cols_filtradas = [c for c in columnas if c in df_filtradas.columns]
                    df_filtradas[cols_filtradas].to_excel(writer, sheet_name='Datos_filtrados', index=False)
                
                if len(df_excluidas) > 0:
                    cols_excluidas = [c for c in columnas if c in df_excluidas.columns]
                    df_excluidas[cols_excluidas].to_excel(writer, sheet_name='Datos_excluidos', index=False)
                
                if len(df_revision) > 0:
                    cols_revision = [c for c in columnas if c in df_revision.columns]
                    # =========================================================
                    # COLUMNAS DE DECISIÓN DEL USUARIO (para revisión manual)
                    # =========================================================
                    df_revision_export = df_revision[cols_revision].copy()
                    # Agregar columnas de decisión si no existen
                    if 'decision_usuario' not in df_revision_export.columns:
                        df_revision_export['decision_usuario'] = ''  # INCLUIR / EXCLUIR / PENDIENTE
                    if 'motivo_decision_usuario' not in df_revision_export.columns:
                        df_revision_export['motivo_decision_usuario'] = ''  # Razón del usuario
                    if 'fecha_revision' not in df_revision_export.columns:
                        df_revision_export['fecha_revision'] = ''  # Fecha de revisión
                    df_revision_export.to_excel(writer, sheet_name='Revision_manual', index=False)
                
                # Contenido_Manual (combinar existentes con nuevas)
                df_contenido_manual_nuevas = pd.DataFrame(self.noticias_pendientes) if len(self.noticias_pendientes) > 0 else pd.DataFrame()
                
                if len(df_contenido_manual_existente) > 0 or len(df_contenido_manual_nuevas) > 0:
                    if len(df_contenido_manual_existente) > 0 and len(df_contenido_manual_nuevas) > 0:
                        df_contenido_manual = pd.concat([df_contenido_manual_existente, df_contenido_manual_nuevas], ignore_index=True)
                        df_contenido_manual = df_contenido_manual.drop_duplicates(subset=['id_noticia'], keep='last')
                    elif len(df_contenido_manual_existente) > 0:
                        df_contenido_manual = df_contenido_manual_existente
                    else:
                        df_contenido_manual = df_contenido_manual_nuevas
                    
                    df_contenido_manual.to_excel(writer, sheet_name='Contenido_Manual', index=False)
                    logger.info(f"✅ Contenido_Manual combinado: {len(df_contenido_manual)} registros")
                
                # Estadísticas
                stats_mgr = EstadisticasManager()
                stats_mgr.generar_estadisticas(writer, df, df_filtradas, df_excluidas, df_revision)
            
            # Reemplazar archivo
            shutil.move(temp_path, output_path)
            
        except Exception as e:
            logger.error(f"Error guardando: {e}")
            temp_path = output_path.replace('.xlsx', '_temp.xlsx')
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
