"""
Módulo de Base de Datos SQLite para el Filtrador de Conflictos
==============================================================

Este módulo proporciona almacenamiento robusto en SQLite que funciona
EN PARALELO con Excel. Ventajas:

- Transacciones ACID (no se corrompe si falla el proceso)
- Consultas SQL rápidas para análisis
- Escala bien con 25,000+ noticias
- Backup automático
- Exportación a Excel cuando lo necesites

Uso:
    from src.core.database import DatabaseManager
    
    db = DatabaseManager("mi_proyecto.db")
    db.insertar_noticia(resultado)
    db.exportar_a_excel("salida.xlsx")
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestor de base de datos SQLite para noticias de conflictos.
    Funciona en paralelo con Excel - ambos se actualizan.
    """
    
    def __init__(self, db_path: str = None):
        """
        Inicializa la base de datos.
        
        Args:
            db_path: Ruta al archivo .db. Si es None, usa ruta por defecto.
        """
        if db_path is None:
            # Usar misma carpeta que el Excel por defecto
            db_path = "conflictos_transicion_energetica.db"
        
        self.db_path = Path(db_path)
        self.conn = None
        self._inicializar_db()
    
    def _inicializar_db(self):
        """Crea las tablas si no existen."""
        # check_same_thread=False permite usar la conexión desde múltiples threads
        # Esto es necesario para el procesamiento paralelo con ThreadPoolExecutor
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
        
        # Habilitar foreign keys y optimizaciones
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging para mejor concurrencia
        
        cursor = self.conn.cursor()
        
        # Tabla principal de noticias
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS noticias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_noticia TEXT UNIQUE,
                fecha TEXT,
                titulo TEXT,
                fuente TEXT,
                link_noticia TEXT,
                noticia TEXT,
                
                -- Clasificación
                excluir INTEGER DEFAULT 0,
                motivo_exclusion TEXT,
                explicacion_exclusion TEXT,
                
                tipo_conflicto TEXT,
                explicacion_conflicto TEXT,
                tipo_accion TEXT,
                explicacion_accion TEXT,
                
                actor_demandante TEXT,
                explicacion_demandante TEXT,
                actor_demandado TEXT,
                explicacion_demandado TEXT,
                
                -- Ubicación
                region TEXT,
                provincia TEXT,
                comuna TEXT,
                localidad TEXT,
                
                -- Detalles
                sector_economico TEXT,
                justificacion_transicion TEXT,
                resumen TEXT,
                notas TEXT,
                
                -- Control
                requiere_revision_manual INTEGER DEFAULT 0,
                decision_usuario TEXT,
                fecha_decision TEXT,
                
                -- Metadatos
                procesado_por TEXT DEFAULT 'IA',
                fecha_procesamiento TEXT,
                version_modelo TEXT,
                
                -- Timestamps
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de estadísticas de procesamiento
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estadisticas_procesamiento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                total_noticias INTEGER,
                incluidas INTEGER,
                excluidas INTEGER,
                revision_manual INTEGER,
                tiempo_total_segundos REAL,
                tokens_utilizados INTEGER,
                costo_estimado REAL,
                modelo_utilizado TEXT
            )
        """)
        
        # Tabla de auditoría (para tracking de cambios)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_noticia TEXT,
                accion TEXT,
                valor_anterior TEXT,
                valor_nuevo TEXT,
                usuario TEXT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para búsquedas rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_excluir ON noticias(excluir)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_revision ON noticias(requiere_revision_manual)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tipo_conflicto ON noticias(tipo_conflicto)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_region ON noticias(region)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fecha ON noticias(fecha)")
        
        self.conn.commit()
        logger.info(f"✅ Base de datos SQLite inicializada: {self.db_path}")
    
    def insertar_noticia(self, resultado: Dict[str, Any], noticia_original: Dict[str, Any] = None) -> bool:
        """
        Inserta o actualiza una noticia en la base de datos.
        
        Args:
            resultado: Diccionario con el resultado del análisis de IA
            noticia_original: Diccionario con datos originales de la noticia
            
        Returns:
            True si se insertó/actualizó correctamente
        """
        try:
            cursor = self.conn.cursor()
            
            # Combinar datos originales con resultado
            datos = {}
            if noticia_original:
                datos['id_noticia'] = noticia_original.get('id_noticia') or noticia_original.get('ID')
                datos['fecha'] = noticia_original.get('Fecha_Extraida_ISO') or noticia_original.get('fecha')
                datos['titulo'] = noticia_original.get('titulo')
                datos['fuente'] = noticia_original.get('medio') or noticia_original.get('fuente')
                datos['link_noticia'] = noticia_original.get('link')
            
            # Agregar campos del resultado
            datos.update({
                'noticia': resultado.get('noticia'),
                'excluir': 1 if resultado.get('excluir') else 0,
                'motivo_exclusion': resultado.get('motivo_exclusion'),
                'explicacion_exclusion': resultado.get('explicacion_exclusion'),
                'tipo_conflicto': resultado.get('tipo_conflicto'),
                'explicacion_conflicto': resultado.get('explicacion_conflicto'),
                'tipo_accion': resultado.get('tipo_accion'),
                'explicacion_accion': resultado.get('explicacion_accion'),
                'actor_demandante': resultado.get('actor_demandante'),
                'explicacion_demandante': resultado.get('explicacion_demandante'),
                'actor_demandado': resultado.get('actor_demandado'),
                'explicacion_demandado': resultado.get('explicacion_demandado'),
                'region': resultado.get('region'),
                'provincia': resultado.get('provincia'),
                'comuna': resultado.get('comuna'),
                'localidad': resultado.get('localidad'),
                'sector_economico': resultado.get('sector_economico'),
                'justificacion_transicion': resultado.get('justificacion_transicion'),
                'resumen': resultado.get('resumen'),
                'notas': resultado.get('notas'),
                'requiere_revision_manual': 1 if resultado.get('requiere_revision_manual') else 0,
                'fecha_procesamiento': datetime.now().isoformat()
            })
            
            # Usar INSERT OR REPLACE para actualizar si ya existe
            columnas = ', '.join(datos.keys())
            placeholders = ', '.join(['?' for _ in datos])
            
            cursor.execute(f"""
                INSERT OR REPLACE INTO noticias ({columnas})
                VALUES ({placeholders})
            """, list(datos.values()))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error insertando noticia: {e}")
            self.conn.rollback()
            return False
    
    def insertar_batch(self, resultados: List[Dict[str, Any]]) -> int:
        """
        Inserta múltiples noticias en una transacción (más eficiente).
        
        Args:
            resultados: Lista de diccionarios con resultados
            
        Returns:
            Número de noticias insertadas correctamente
        """
        insertados = 0
        try:
            for resultado in resultados:
                if self.insertar_noticia(resultado):
                    insertados += 1
            return insertados
        except Exception as e:
            logger.error(f"Error en batch insert: {e}")
            return insertados
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la base de datos."""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total de noticias
        cursor.execute("SELECT COUNT(*) FROM noticias")
        stats['total'] = cursor.fetchone()[0]
        
        # Incluidas (no excluidas y no en revisión)
        cursor.execute("""
            SELECT COUNT(*) FROM noticias 
            WHERE excluir = 0 AND requiere_revision_manual = 0
        """)
        stats['incluidas'] = cursor.fetchone()[0]
        
        # Excluidas
        cursor.execute("SELECT COUNT(*) FROM noticias WHERE excluir = 1")
        stats['excluidas'] = cursor.fetchone()[0]
        
        # Revisión manual
        cursor.execute("SELECT COUNT(*) FROM noticias WHERE requiere_revision_manual = 1")
        stats['revision_manual'] = cursor.fetchone()[0]
        
        # Por tipo de conflicto
        cursor.execute("""
            SELECT tipo_conflicto, COUNT(*) as cantidad
            FROM noticias
            WHERE excluir = 0 AND tipo_conflicto IS NOT NULL
            GROUP BY tipo_conflicto
            ORDER BY cantidad DESC
        """)
        stats['por_tipo_conflicto'] = dict(cursor.fetchall())
        
        # Por región
        cursor.execute("""
            SELECT region, COUNT(*) as cantidad
            FROM noticias
            WHERE excluir = 0 AND region IS NOT NULL
            GROUP BY region
            ORDER BY cantidad DESC
        """)
        stats['por_region'] = dict(cursor.fetchall())
        
        # Por motivo de exclusión
        cursor.execute("""
            SELECT motivo_exclusion, COUNT(*) as cantidad
            FROM noticias
            WHERE excluir = 1 AND motivo_exclusion IS NOT NULL
            GROUP BY motivo_exclusion
            ORDER BY cantidad DESC
        """)
        stats['por_motivo_exclusion'] = dict(cursor.fetchall())
        
        return stats
    
    def exportar_a_excel(self, excel_path: str) -> bool:
        """
        Exporta la base de datos a Excel con múltiples hojas.
        
        Args:
            excel_path: Ruta del archivo Excel de salida
            
        Returns:
            True si se exportó correctamente
        """
        try:
            # Leer todas las noticias
            df_completos = pd.read_sql_query("SELECT * FROM noticias", self.conn)
            
            # Filtrar por categoría
            df_filtrados = df_completos[
                (df_completos['excluir'] == 0) & 
                (df_completos['requiere_revision_manual'] == 0)
            ].copy()
            
            df_excluidos = df_completos[df_completos['excluir'] == 1].copy()
            
            df_revision = df_completos[df_completos['requiere_revision_manual'] == 1].copy()
            
            # Crear estadísticas
            stats = self.obtener_estadisticas()
            df_stats = pd.DataFrame([
                {'Métrica': k, 'Valor': str(v)} 
                for k, v in stats.items() 
                if not isinstance(v, dict)
            ])
            
            # Escribir Excel
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df_completos.to_excel(writer, sheet_name='Datos_completos', index=False)
                df_filtrados.to_excel(writer, sheet_name='Datos_filtrados', index=False)
                df_excluidos.to_excel(writer, sheet_name='Datos_excluidos', index=False)
                df_revision.to_excel(writer, sheet_name='Revision_manual', index=False)
                df_stats.to_excel(writer, sheet_name='Estadisticas', index=False)
            
            logger.info(f"✅ Exportado a Excel: {excel_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exportando a Excel: {e}")
            return False
    
    def buscar(self, 
               tipo_conflicto: str = None,
               region: str = None,
               excluir: bool = None,
               revision_manual: bool = None,
               texto: str = None,
               limit: int = 100) -> List[Dict]:
        """
        Busca noticias con filtros.
        
        Args:
            tipo_conflicto: Filtrar por tipo de conflicto
            region: Filtrar por región
            excluir: Filtrar por estado de exclusión
            revision_manual: Filtrar por revisión manual
            texto: Buscar en título o contenido
            limit: Máximo de resultados
            
        Returns:
            Lista de noticias que coinciden
        """
        query = "SELECT * FROM noticias WHERE 1=1"
        params = []
        
        if tipo_conflicto:
            query += " AND tipo_conflicto = ?"
            params.append(tipo_conflicto)
        
        if region:
            query += " AND region = ?"
            params.append(region)
        
        if excluir is not None:
            query += " AND excluir = ?"
            params.append(1 if excluir else 0)
        
        if revision_manual is not None:
            query += " AND requiere_revision_manual = ?"
            params.append(1 if revision_manual else 0)
        
        if texto:
            query += " AND (titulo LIKE ? OR noticia LIKE ?)"
            params.extend([f'%{texto}%', f'%{texto}%'])
        
        query += f" LIMIT {limit}"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def actualizar_decision(self, id_noticia: str, decision: str, notas: str = None) -> bool:
        """
        Actualiza la decisión del usuario para una noticia en revisión manual.
        
        Args:
            id_noticia: ID de la noticia
            decision: 'INCLUIR' o 'EXCLUIR'
            notas: Notas adicionales
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            cursor = self.conn.cursor()
            
            # Guardar valor anterior para auditoría
            cursor.execute(
                "SELECT decision_usuario FROM noticias WHERE id_noticia = ?",
                (id_noticia,)
            )
            anterior = cursor.fetchone()
            valor_anterior = anterior[0] if anterior else None
            
            # Actualizar
            if decision.upper().startswith('INCLUIR'):
                cursor.execute("""
                    UPDATE noticias 
                    SET decision_usuario = ?,
                        excluir = 0,
                        requiere_revision_manual = 0,
                        fecha_decision = ?,
                        notas = COALESCE(notas || ' | ', '') || ?
                    WHERE id_noticia = ?
                """, (decision, datetime.now().isoformat(), notas or '', id_noticia))
            
            elif decision.upper().startswith('EXCLUIR'):
                cursor.execute("""
                    UPDATE noticias 
                    SET decision_usuario = ?,
                        excluir = 1,
                        requiere_revision_manual = 0,
                        fecha_decision = ?,
                        notas = COALESCE(notas || ' | ', '') || ?
                    WHERE id_noticia = ?
                """, (decision, datetime.now().isoformat(), notas or '', id_noticia))
            
            # Registrar en auditoría
            cursor.execute("""
                INSERT INTO auditoria (id_noticia, accion, valor_anterior, valor_nuevo, usuario)
                VALUES (?, 'decision_usuario', ?, ?, 'usuario')
            """, (id_noticia, valor_anterior, decision))
            
            self.conn.commit()
            logger.info(f"✅ Decisión actualizada para {id_noticia}: {decision}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando decisión: {e}")
            self.conn.rollback()
            return False
    
    def obtener_muestra_auditoria(self, n: int = 50, tipo: str = 'excluidas') -> pd.DataFrame:
        """
        Obtiene una muestra aleatoria para auditoría manual.
        
        Args:
            n: Número de noticias a muestrear
            tipo: 'excluidas', 'incluidas', o 'todas'
            
        Returns:
            DataFrame con la muestra
        """
        if tipo == 'excluidas':
            query = f"SELECT * FROM noticias WHERE excluir = 1 ORDER BY RANDOM() LIMIT {n}"
        elif tipo == 'incluidas':
            query = f"SELECT * FROM noticias WHERE excluir = 0 ORDER BY RANDOM() LIMIT {n}"
        else:
            query = f"SELECT * FROM noticias ORDER BY RANDOM() LIMIT {n}"
        
        return pd.read_sql_query(query, self.conn)
    
    def cerrar(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            logger.info("🔒 Conexión a base de datos cerrada")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cerrar()
    
    def __del__(self):
        self.cerrar()


# Función de conveniencia para uso rápido
def crear_db(ruta: str = None) -> DatabaseManager:
    """Crea y retorna una instancia de DatabaseManager."""
    return DatabaseManager(ruta)
