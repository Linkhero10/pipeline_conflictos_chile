"""
MÓDULO DE GESTIÓN DE BASE DE DATOS
Maneja la persistencia y gestión de datos del scraper temporal
"""

import pandas as pd
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gestor unificado de base de datos para conflictos ambientales"""
    
    def __init__(self, base_filename="conflictos_ambientales_chile"):
        self.base_filename = base_filename
        self.csv_file = f"{base_filename}.csv"
        self.json_file = f"{base_filename}.json"
        self.excel_file = f"{base_filename}.xlsx"
        
        # Archivos de copia
        self.csv_copy = f"Copia de {base_filename}.csv"
        self.json_copy = f"Copia de {base_filename}.json"
        self.excel_copy = f"Copia de {base_filename}.xlsx"
        
        # Control para guardar copias por formato
        self.save_csv_copy = True
        self.save_json_copy = True
        self.save_excel_copy = True
        
        # Columnas estándar
        self.standard_columns = [
            'titulo', 'url', 'fecha_publicacion', 'fuente', 'contenido',
            'region', 'comuna', 'tipo_conflicto', 'sector', 'actores',
            'fecha_scraping', 'metodo_extraccion', 'longitud_contenido'
        ]
        
        # Cargar datos existentes
        self.df = self.load_existing_data()
        
        # Cache de hashes para evitar duplicados
        self.existing_hashes = set()

        # Inicializar existing_hashes con datos existentes
        try:
            if 'content_hash' in self.df.columns:
                self.existing_hashes.update(set(self.df['content_hash'].dropna().astype(str)))
            else:
                # Fallback: derivar hash desde título + url/enlace si están disponibles
                import hashlib
                if 'titulo' in self.df.columns and ('url' in self.df.columns or 'enlace' in self.df.columns):
                    url_col = 'url' if 'url' in self.df.columns else 'enlace'
                    for _, row in self.df[['titulo', url_col]].dropna().iterrows():
                        h = hashlib.md5(f"{row['titulo']}{row[url_col]}".encode('utf-8', errors='ignore')).hexdigest()
                        self.existing_hashes.add(h)
        except Exception as e:
            logger.warning(f"No se pudo inicializar existing_hashes desde la base: {e}")
        
        # Lista unificada de datos para compatibilidad
        self.unified_data = []

    def _ensure_current_schema(self):
        """Limpia y estandariza el DataFrame para el segundo scraping.

        - Conserva solo columnas relevantes en este flujo.
        - Inserta 'id_noticia' como primera columna, secuencial desde 1.
        - Mapea 'url' -> 'enlace' si corresponde.
        - Elimina columnas no usadas por ahora (se agregarán en la segunda pasada).
        """
        try:
            df = self.df.copy() if self.df is not None else pd.DataFrame()

            # Asegurar columnas base presentes
            for col in ['titulo', 'descripcion', 'fuente', 'fecha_scraping',
                        'enlace', 'query_original', 'periodo_scraping',
                        'content_hash', 'fecha_agregado']:
                if col not in df.columns:
                    df[col] = pd.NA

            # Mapear url -> enlace si existe 'url'
            if 'url' in df.columns:
                if 'enlace' not in df.columns or df['enlace'].isna().all():
                    df['enlace'] = df['url']
                # Eliminar columna url para evitar duplicación
                try:
                    df = df.drop(columns=['url'])
                except Exception:
                    pass

            # Completar descripcion con titulo si falta
            if 'descripcion' in df.columns and 'titulo' in df.columns:
                df['descripcion'] = df['descripcion'].fillna(df['titulo'])

            # real_url y content_length fueron eliminadas del esquema

            # Columnas a conservar y su orden deseado (id_noticia primero)
            keep_cols = [
                'id_noticia', 'titulo', 'descripcion', 'fuente', 'fecha_scraping',
                'enlace', 'query_original', 'periodo_scraping',
                'content_hash', 'fecha_agregado'
            ]

            # Asegurar existencia de id_noticia y asignar secuencial ascendente desde 1
            df = df.reset_index(drop=True)
            df['id_noticia'] = range(1, len(df) + 1)

            # Reordenar y filtrar solo las columnas deseadas
            present_keep = [c for c in keep_cols if c in df.columns]
            df = df[present_keep]

            # Persistir en self.df
            self.df = df
        except Exception as e:
            logger.warning(f"No se pudo normalizar esquema actual: {e}")
        
    def load_existing_data(self):
        """Carga datos existentes desde Excel ('Datos') si existe; si no, desde CSV; si no, vacío."""
        try:
            # Preferir Excel principal si existe y tiene hoja 'Datos'
            if os.path.exists(self.excel_file):
                try:
                    xls = pd.ExcelFile(self.excel_file)
                    if 'Datos' in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name='Datos')
                        logger.info(f"Cargados {len(df)} registros existentes de hoja 'Datos' en {self.excel_file}")
                    else:
                        df = None
                except Exception as ex:
                    logger.warning(f"No se pudo leer Excel principal; se intentará CSV. Detalle: {ex}")
                    df = None
            else:
                df = None

            # Fallback a CSV si Excel no disponible
            if df is None:
                if os.path.exists(self.csv_file):
                    df = pd.read_csv(self.csv_file)
                    logger.info(f"Cargados {len(df)} registros existentes de {self.csv_file}")
                else:
                    logger.info("No se encontró Excel/CSV existente, creando nueva base de datos")
                    df = pd.DataFrame(columns=self.standard_columns)

            # Normalización mínima de columnas para dedupe y asignación de ids
            try:
                if 'url' not in df.columns and 'enlace' in df.columns:
                    df['url'] = df['enlace']
                if 'id_noticia' not in df.columns:
                    df['id_noticia'] = pd.NA
            except Exception as norm_ex:
                logger.warning(f"No se pudieron normalizar columnas: {norm_ex}")

            return df
        except Exception as e:
            logger.error(f"Error cargando datos existentes: {e}")
            # En caso de fallo, retornar DF vacío
            return pd.DataFrame(columns=self.standard_columns)
    
    def add_articles(self, articles_data):
        """
        Añade nuevos artículos a la base de datos
        
        Args:
            articles_data: Lista de diccionarios con datos de artículos
        """
        if not articles_data:
            return 0
            
        new_df = pd.DataFrame(articles_data)

        # Normalizar URL en dataset nuevo
        if 'url' not in new_df.columns and 'enlace' in new_df.columns:
            new_df['url'] = new_df['enlace']

        # Asegurar columna id_noticia en nuevo DF para asignación posterior
        if 'id_noticia' not in new_df.columns:
            new_df['id_noticia'] = pd.NA

        # De-duplicación interna del batch por url y/o content_hash
        try:
            if 'url' in new_df.columns:
                new_df = new_df.drop_duplicates(subset=['url'], keep='first')
            if 'content_hash' in new_df.columns:
                new_df = new_df.drop_duplicates(subset=['content_hash'], keep='first')
        except Exception as dd_ex:
            logger.warning(f"No se pudo eliminar duplicados internos en el batch: {dd_ex}")

        # De-duplicación contra existentes
        try:
            df_existing = self.df if self.df is not None else pd.DataFrame()
            # Unificar url en base existente si solo hay 'enlace'
            if 'url' not in df_existing.columns and 'enlace' in df_existing.columns:
                df_existing = df_existing.copy()
                df_existing['url'] = df_existing['enlace']

            if 'url' in new_df.columns and 'url' in df_existing.columns:
                existing_urls = set(df_existing['url'].dropna().astype(str))
                new_df = new_df[~new_df['url'].astype(str).isin(existing_urls)]

            if 'content_hash' in new_df.columns and 'content_hash' in df_existing.columns:
                existing_hashes = set(df_existing['content_hash'].dropna().astype(str))
                new_df = new_df[~new_df['content_hash'].astype(str).isin(existing_hashes)]
        except Exception as ex_ded:
            logger.warning(f"No se pudo de-duplicar contra existentes: {ex_ded}")

        if len(new_df) == 0:
            logger.info("No hay nuevos artículos únicos para añadir")
            return 0

        # Asignar id_noticia incremental solo a los nuevos que no lo traigan
        try:
            last_id = None
            if 'id_noticia' in self.df.columns:
                # Convertir a numérico para evitar tipos objeto
                existing_ids = pd.to_numeric(self.df['id_noticia'], errors='coerce')
                if existing_ids.notna().any():
                    last_id = int(existing_ids.max())
            if last_id is None:
                last_id = 0

            need_ids_mask = new_df['id_noticia'].isna()
            count_need_ids = int(need_ids_mask.sum())
            if count_need_ids > 0:
                new_ids = list(range(last_id + 1, last_id + 1 + count_need_ids))
                new_df.loc[need_ids_mask, 'id_noticia'] = new_ids
        except Exception as ex_ids:
            logger.warning(f"No se pudieron asignar ids incrementales: {ex_ids}")

        # Agregar a la base
        self.df = pd.concat([self.df, new_df], ignore_index=True)
        logger.info(f"Añadidos {len(new_df)} nuevos artículos a la base de datos")
        return len(new_df)
    
    def save_all_formats(self):
        """Guarda la base de datos en todos los formatos (originales y copias)"""
        try:
            # Normalizar esquema antes de guardar (siempre limpiar para segundo scraping)
            self._ensure_current_schema()

            # Guardar CSV (original y copia)
            self.df.to_csv(self.csv_file, index=False, encoding='utf-8')
            if self.save_csv_copy:
                self.df.to_csv(self.csv_copy, index=False, encoding='utf-8')
            logger.info(f"Base de datos guardada: {self.csv_file} ({len(self.df)} registros)")
            if self.save_csv_copy:
                logger.info(f"Copia guardada: {self.csv_copy}")
            
            # Guardar JSON (original y copia)
            json_data = self.df.to_dict('records')
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            if self.save_json_copy:
                with open(self.json_copy, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Base de datos JSON guardada: {self.json_file}")
            if self.save_json_copy:
                logger.info(f"Copia JSON guardada: {self.json_copy}")
            
            # Guardar Excel con análisis (original y copia)
            self.save_excel_with_analysis()
            if self.save_excel_copy:
                self._save_excel_copy()
            
            return True
            
        except Exception as e:
            logger.error(f"Error guardando base de datos: {e}")
            return False
    
    def save_excel_with_analysis(self):
        """Guarda Excel con hojas de análisis, preservando hojas existentes y creando 'Limpieza' si no existe."""
        try:
            # Asegurar que el esquema esté limpio también cuando se llama directamente
            self._ensure_current_schema()
            file_exists = os.path.exists(self.excel_file)
            mode = 'a' if file_exists else 'w'
            # if_sheet_exists solo es válido en modo 'a'. Para 'w' no debe pasarse.
            excelwriter_kwargs = {'engine': 'openpyxl'}
            if file_exists:
                excelwriter_kwargs.update({'mode': 'a', 'if_sheet_exists': 'replace'})
            else:
                excelwriter_kwargs.update({'mode': 'w'})

            with pd.ExcelWriter(self.excel_file, **excelwriter_kwargs) as writer:
                # Hoja principal
                self.df.to_excel(writer, sheet_name='Datos', index=False)

                # Análisis por fuente
                if 'fuente' in self.df.columns:
                    fuentes_analysis = self.df['fuente'].value_counts().head(20)
                    fuentes_analysis.to_excel(writer, sheet_name='Top_Fuentes')

                # Análisis por región
                if 'region' in self.df.columns:
                    regiones_analysis = self.df['region'].value_counts()
                    regiones_analysis.to_excel(writer, sheet_name='Por_Region')

                # Análisis temporal
                if 'fecha_publicacion' in self.df.columns:
                    df_temp = self.df.copy()
                    df_temp['fecha_publicacion'] = pd.to_datetime(df_temp['fecha_publicacion'], errors='coerce')
                    df_temp['año'] = df_temp['fecha_publicacion'].dt.year
                    temporal_analysis = df_temp['año'].value_counts().sort_index()
                    temporal_analysis.to_excel(writer, sheet_name='Temporal')

                # Crear hoja de limpieza si no existe
                try:
                    book = writer.book
                    if 'Limpieza' not in book.sheetnames:
                        self.df.to_excel(writer, sheet_name='Limpieza', index=False)
                        logger.info("Hoja 'Limpieza' creada a partir de 'Datos'")
                    else:
                        logger.info("Hoja 'Limpieza' ya existe; se preserva sin cambios")
                except Exception as e:
                    logger.warning(f"No se pudo verificar/crear hoja 'Limpieza': {e}")

            logger.info(f"Excel con análisis guardado: {self.excel_file}")

        except Exception as e:
            logger.error(f"Error guardando Excel: {e}")
    
    def _save_excel_copy(self):
        """Guarda copia del Excel con hojas de análisis"""
        try:
            with pd.ExcelWriter(self.excel_copy, engine='openpyxl') as writer:
                # Hoja principal
                self.df.to_excel(writer, sheet_name='Datos', index=False)
                
                # Análisis por fuente
                if 'fuente' in self.df.columns:
                    fuentes_analysis = self.df['fuente'].value_counts().head(20)
                    fuentes_analysis.to_excel(writer, sheet_name='Top_Fuentes')
                
                # Análisis por región
                if 'region' in self.df.columns:
                    regiones_analysis = self.df['region'].value_counts()
                    regiones_analysis.to_excel(writer, sheet_name='Por_Region')
                
                # Análisis temporal
                if 'fecha_publicacion' in self.df.columns:
                    df_temp = self.df.copy()
                    df_temp['fecha_publicacion'] = pd.to_datetime(df_temp['fecha_publicacion'], errors='coerce')
                    df_temp['año'] = df_temp['fecha_publicacion'].dt.year
                    temporal_analysis = df_temp['año'].value_counts().sort_index()
                    temporal_analysis.to_excel(writer, sheet_name='Temporal')
            
            logger.info(f"Copia Excel guardada: {self.excel_copy}")
            
        except Exception as e:
            logger.error(f"Error guardando copia Excel: {e}")
        
    def _sanitize_sheet_name(self, name: str) -> str:
        """Sanitiza el nombre de hoja para cumplir restricciones de Excel (<=31 chars y sin caracteres inválidos)."""
        invalid = set('[]:*?/\\')
        cleaned = ''.join(ch for ch in name if ch not in invalid)
        # Reemplazos comunes
        cleaned = cleaned.replace(' ', '_').replace('-', '_')
        # Limitar a 31 caracteres
        if len(cleaned) > 31:
            cleaned = cleaned[:31]
        return cleaned

    def add_run_sheet(self, period_name: str, config_name: str) -> bool:
        """Crea o reemplaza una hoja dedicada con los artículos del run especificado.
        No altera la hoja principal 'Datos'.

        Args:
            period_name: Nombre del período (ej: '1993-01-01_a_2024-12-31' o '2024_S1')
            config_name: Nombre de la configuración (ej: 'regional_chile')

        Returns:
            bool: True si se creó/actualizó la hoja, False si no había datos o en error
        """
        try:
            df = self.df
            if df is None or df.empty:
                return False

            subset = df.copy()
            if 'periodo_scraping' in subset.columns:
                subset = subset[subset['periodo_scraping'] == period_name]
            if 'configuracion' in subset.columns:
                subset = subset[subset['configuracion'] == config_name]

            if subset.empty:
                logger.info("No hay datos para crear hoja dedicada del run")
                return False

            sheet_name = self._sanitize_sheet_name(f"Run_{config_name}_{period_name}")
            mode = 'a' if os.path.exists(self.excel_file) else 'w'

            try:
                with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode=mode, if_sheet_exists='replace') as writer:
                    subset.to_excel(writer, sheet_name=sheet_name, index=False)
            except TypeError:
                # Pandas antiguo sin if_sheet_exists: reescribir archivo y volver a crear hojas básicas + hoja del run
                with pd.ExcelWriter(self.excel_file, engine='openpyxl') as writer:
                    # Hoja principal
                    self.df.to_excel(writer, sheet_name='Datos', index=False)
                    # Hojas de análisis mínimas
                    if 'fuente' in self.df.columns:
                        self.df['fuente'].value_counts().head(20).to_excel(writer, sheet_name='Top_Fuentes')
                    # Hoja del run
                    subset.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"Hoja de ejecución creada/actualizada: {sheet_name}")
            return True
        except Exception as e:
            logger.error(f"Error creando hoja de ejecución: {e}")
            return False

    def get_stats(self):
        """Obtiene estadísticas de la base de datos"""
        stats = {
            'total_articles': len(self.df),
            'unique_sources': len(self.df['fuente'].unique()) if 'fuente' in self.df.columns else 0,
            'unique_urls': len(self.df['url'].unique()) if 'url' in self.df.columns else 0,
            'date_range': None
        }
        
        if 'fecha_publicacion' in self.df.columns:
            try:
                dates = pd.to_datetime(self.df['fecha_publicacion'], errors='coerce').dropna()
                if len(dates) > 0:
                    stats['date_range'] = f"{dates.min().date()} a {dates.max().date()}"
            except:
                pass
        
        return stats
    
    def save_unified_database(self):
        """
        Guarda la base de datos unificada en todos los formatos
        Compatible con enhanced_temporal_scraper.py
        """
        try:
            # Convertir unified_data a DataFrame si hay datos nuevos
            if self.unified_data:
                new_df = pd.DataFrame(self.unified_data)
                self.df = pd.concat([self.df, new_df], ignore_index=True)
                self.unified_data = []  # Limpiar después de agregar
            
            # De-duplicar por content_hash si existe la columna
            try:
                if 'content_hash' in self.df.columns:
                    before = len(self.df)
                    self.df = self.df.drop_duplicates(subset=['content_hash'])
                    after = len(self.df)
                    if after < before:
                        logger.info(f"Eliminados {before - after} duplicados por content_hash antes de guardar")
            except Exception as e:
                logger.warning(f"No se pudo eliminar duplicados por content_hash: {e}")

            # Guardar en todos los formatos
            success = self.save_all_formats()
            
            if success:
                return {
                    'total_records': len(self.df),
                    'csv': self.csv_file,
                    'json': self.json_file, 
                    'excel': self.excel_file
                }
            else:
                return {'total_records': len(self.df)}
                
        except Exception as e:
            logger.error(f"Error guardando base de datos unificada: {e}")
            return {'total_records': len(self.df)}
    
    def filter_by_period(self, year=None, semester=None):
        """
        Filtra artículos por período temporal
        
        Args:
            year: Año específico
            semester: Semestre (1 o 2)
            
        Returns:
            DataFrame filtrado
        """
        if 'fecha_publicacion' not in self.df.columns:
            return self.df
            
        df_filtered = self.df.copy()
        df_filtered['fecha_publicacion'] = pd.to_datetime(df_filtered['fecha_publicacion'], errors='coerce')
        
        if year:
            df_filtered = df_filtered[df_filtered['fecha_publicacion'].dt.year == year]
            
        if semester:
            if semester == 1:
                # Enero a Junio
                df_filtered = df_filtered[df_filtered['fecha_publicacion'].dt.month <= 6]
            elif semester == 2:
                # Julio a Diciembre  
                df_filtered = df_filtered[df_filtered['fecha_publicacion'].dt.month > 6]
        
        return df_filtered

if __name__ == "__main__":
    # Test básico
    db = DatabaseManager()
    print(f"Base de datos inicializada: {len(db.df)} registros")
    print("Estadísticas:", db.get_stats())
