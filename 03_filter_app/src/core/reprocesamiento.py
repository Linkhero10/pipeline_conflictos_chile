"""
MÓDULO DE RE-PROCESAMIENTO DE NOTICIAS
Sistema para recuperar contenido de noticias con problemas mediante cascada de scraping
"""

import pandas as pd
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger(__name__)

# ============================================================================
# FUNCIONES AUXILIARES PARA RE-PROCESAMIENTO
# ============================================================================

def detectar_contenido_problematico(noticia: dict, resultado_analisis: dict) -> Tuple[bool, str]:
    """
    Detecta si una noticia tiene contenido problemático que requiere re-scraping
    
    Args:
        noticia: Diccionario con datos de la noticia
        resultado_analisis: Resultado del análisis de IA
        
    Returns:
        (es_problematico, motivo): Tupla con booleano y motivo
    """
    # Criterio 1: Contenido muy corto
    contenido = noticia.get('contenido', '') or noticia.get('descripcion', '')
    if len(str(contenido).strip()) < 150:
        return True, "Contenido muy corto (< 150 caracteres)"
    
    # Criterio 2: Título duplicado en contenido
    titulo = noticia.get('titulo', '')
    if titulo and contenido:
        if str(contenido).strip() == str(titulo).strip():
            return True, "Contenido idéntico al título"
        if str(contenido).strip().startswith(str(titulo).strip()[:50]) and len(str(contenido)) < 300:
            return True, "Contenido es solo el título extendido"
    
    # Criterio 3: IA detectó contenido corrupto/ilegible
    if resultado_analisis.get('excluir'):
        explicacion = resultado_analisis.get('explicacion_exclusion', '').lower()
        if any(palabra in explicacion for palabra in ['corrupto', 'ilegible', 'no contiene información', 'no permite']):
            return True, "IA detectó contenido corrupto o ilegible"
    
    # Criterio 4: Motivo 8 (reportaje histórico) o Motivo 13 (error de procesamiento)
    # Nota: Motivo 11 es "Solo fiscalización" (exclusión válida), Motivo 13 es para errores técnicos
    motivo = resultado_analisis.get('motivo_exclusion', '')
    if 'Motivo 8' in motivo or 'Motivo 13' in motivo:
        return True, f"Motivo de exclusión problemático: {motivo}"
    
    return False, ""

def crear_fila_scraping_pendiente(noticia: dict, motivo: str) -> dict:
    """
    Crea una fila para la hoja Contenido_Manual
    
    Args:
        noticia: Diccionario con datos de la noticia
        motivo: Motivo por el cual se envía a scraping pendiente
        
    Returns:
        Diccionario con datos para la fila
    """
    return {
        'id_noticia': noticia.get('id_noticia', ''),
        'fecha': noticia.get('fecha', ''),
        'titulo': noticia.get('titulo', ''),
        'fuente': noticia.get('fuente', '') or noticia.get('Fuente', ''),  # ✅ AGREGADO
        'URL_Directa': noticia.get('URL_Directa', '') or noticia.get('url_decodificada', '') or noticia.get('link', ''),
        'motivo_pendiente': motivo,
        'contenido_noticia': '',  # Vacío, se llenará con scraping
        'metodo_scraping_exitoso': '',
        'intentos_scraping': 0,
        'ultimo_intento': '',
        'estado': 'Pendiente',
        'notas': ''
    }

def insertar_fila_ordenada(df: pd.DataFrame, nueva_fila: dict, columna_orden: str = 'id_noticia') -> pd.DataFrame:
    """
    Inserta una fila en el DataFrame en la posición correcta según columna de orden
    Desplaza filas existentes sin reemplazar
    
    Args:
        df: DataFrame donde insertar
        nueva_fila: Diccionario con datos de la nueva fila
        columna_orden: Columna por la cual ordenar (default: 'id_noticia')
        
    Returns:
        DataFrame con la fila insertada
    """
    # Crear DataFrame con la nueva fila
    nueva_fila_df = pd.DataFrame([nueva_fila])
    
    # Concatenar y ordenar
    df_resultado = pd.concat([df, nueva_fila_df], ignore_index=True)
    
    # Ordenar por la columna especificada
    if columna_orden in df_resultado.columns:
        df_resultado = df_resultado.sort_values(by=columna_orden).reset_index(drop=True)
    
    return df_resultado

def actualizar_noticia_en_todas_hojas(
    excel_path: str,
    id_noticia: int,
    resultado_analisis: dict,
    contenido_recuperado: str,
    metodo_scraping: str
) -> bool:
    """
    Actualiza una noticia en todas las hojas del Excel después de recuperar contenido
    
    Args:
        excel_path: Ruta al archivo Excel
        id_noticia: ID de la noticia a actualizar
        resultado_analisis: Resultado del análisis de IA con el contenido recuperado
        contenido_recuperado: Contenido scrapeado exitosamente
        metodo_scraping: Método que funcionó (ej: "Jina AI", "Selenium")
        
    Returns:
        True si se actualizó exitosamente, False si hubo error
    """
    try:
        logger.info(f"📝 Actualizando noticia {id_noticia} en todas las hojas...")
        print(f"\n📝 Actualizando noticia {id_noticia} en todas las hojas del Excel...")
        
        # Leer todas las hojas
        excel_data = pd.read_excel(excel_path, sheet_name=None)
        
        # Preparar datos de la noticia actualizada
        noticia_actualizada = {
            'id_noticia': id_noticia,
            'excluir': resultado_analisis.get('excluir', True),
            'motivo_exclusion': resultado_analisis.get('motivo_exclusion', ''),
            'explicacion_exclusion': resultado_analisis.get('explicacion_exclusion', ''),
            'tipo_conflicto': resultado_analisis.get('tipo_conflicto', ''),
            'explicacion_conflicto': resultado_analisis.get('explicacion_conflicto', ''),
            'tipo_accion': resultado_analisis.get('tipo_accion', ''),
            'explicacion_accion': resultado_analisis.get('explicacion_accion', ''),
            'actor_demandante': resultado_analisis.get('actor_demandante', ''),
            'explicacion_demandante': resultado_analisis.get('explicacion_demandante', ''),
            'actor_demandado': resultado_analisis.get('actor_demandado', ''),
            'explicacion_demandado': resultado_analisis.get('explicacion_demandado', ''),
            'resumen': resultado_analisis.get('resumen', ''),
            'region': resultado_analisis.get('region', ''),
            'provincia': resultado_analisis.get('provincia', ''),
            'comuna': resultado_analisis.get('comuna', ''),
            'localidad': resultado_analisis.get('localidad', ''),
            'sector_economico': resultado_analisis.get('sector_economico', ''),
            'notas': f"Contenido recuperado con {metodo_scraping}. {resultado_analisis.get('notas', '')}",
            'requiere_revision_manual': resultado_analisis.get('requiere_revision_manual', False)
        }
        
        # Actualizar en cada hoja relevante
        hojas_actualizadas = []
        
        # 1. Datos_completos - siempre actualizar
        if 'Datos_completos' in excel_data:
            df = excel_data['Datos_completos']
            mask = df['id_noticia'] == id_noticia
            if mask.any():
                # Actualizar fila existente
                for col, val in noticia_actualizada.items():
                    if col in df.columns:
                        df.loc[mask, col] = val
                hojas_actualizadas.append('Datos_completos')
            else:
                # Insertar nueva fila ordenadamente
                df = insertar_fila_ordenada(df, noticia_actualizada)
                hojas_actualizadas.append('Datos_completos (insertada)')
            excel_data['Datos_completos'] = df
        
        # 2. Datos_filtrados - solo si no se excluye
        if not resultado_analisis.get('excluir', True):
            if 'Datos_filtrados' in excel_data:
                df = excel_data['Datos_filtrados']
                mask = df['id_noticia'] == id_noticia
                if mask.any():
                    for col, val in noticia_actualizada.items():
                        if col in df.columns:
                            df.loc[mask, col] = val
                else:
                    df = insertar_fila_ordenada(df, noticia_actualizada)
                excel_data['Datos_filtrados'] = df
                hojas_actualizadas.append('Datos_filtrados')
        
        # 3. Datos_excluidos - solo si se excluye
        if resultado_analisis.get('excluir', True):
            if 'Datos_excluidos' in excel_data:
                df = excel_data['Datos_excluidos']
                mask = df['id_noticia'] == id_noticia
                if mask.any():
                    for col, val in noticia_actualizada.items():
                        if col in df.columns:
                            df.loc[mask, col] = val
                else:
                    df = insertar_fila_ordenada(df, noticia_actualizada)
                excel_data['Datos_excluidos'] = df
                hojas_actualizadas.append('Datos_excluidos')
        
        # 4. Revision_manual - solo si requiere revisión
        if resultado_analisis.get('requiere_revision_manual', False):
            if 'Revision_manual' in excel_data:
                df = excel_data['Revision_manual']
                mask = df['id_noticia'] == id_noticia
                if mask.any():
                    for col, val in noticia_actualizada.items():
                        if col in df.columns:
                            df.loc[mask, col] = val
                else:
                    df = insertar_fila_ordenada(df, noticia_actualizada)
                excel_data['Revision_manual'] = df
                hojas_actualizadas.append('Revision_manual')
        
        # 5. Actualizar Contenido_Manual - marcar como recuperado
        if 'Contenido_Manual' in excel_data:
            df = excel_data['Contenido_Manual']
            mask = df['id_noticia'] == id_noticia
            if mask.any():
                df.loc[mask, 'estado'] = 'Recuperado'
                df.loc[mask, 'metodo_scraping_exitoso'] = metodo_scraping
                # CRÍTICO: NO sobrescribir contenido_noticia si ya existe contenido manual
                # Solo actualizar si está vacío o es el placeholder
                contenido_actual = df.loc[mask, 'contenido_noticia'].iloc[0] if mask.any() else ''
                if not contenido_actual or contenido_actual in ['', 'nan', 'HUMANO DEBE INSERTAR NOTICIA'] or len(str(contenido_actual)) < 200:
                    # Solo actualizar si no hay contenido válido
                    df.loc[mask, 'contenido_noticia'] = contenido_recuperado[:500] + '...' if len(contenido_recuperado) > 500 else contenido_recuperado
                # Si ya hay contenido manual válido, NO sobrescribirlo
                df.loc[mask, 'ultimo_intento'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                excel_data['Contenido_Manual'] = df
                hojas_actualizadas.append('Contenido_Manual')
        
        # Guardar Excel actualizado
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='w') as writer:
            for sheet_name, df in excel_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"   ✅ Actualizado en: {', '.join(hojas_actualizadas)}")
        logger.info(f"✅ Noticia {id_noticia} actualizada en: {', '.join(hojas_actualizadas)}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error actualizando noticia {id_noticia}: {e}")
        print(f"   ❌ Error actualizando: {str(e)[:100]}")
        return False

def marcar_requiere_humano(excel_path: str, id_noticia: int, intentos: int = 0) -> bool:
    """
    Marca una noticia en Contenido_Manual como que requiere intervención humana
    
    Args:
        excel_path: Ruta al archivo Excel
        id_noticia: ID de la noticia
        intentos: Número de intentos realizados
        
    Returns:
        True si se marcó exitosamente
    """
    try:
        # Leer hoja Contenido_Manual
        df = pd.read_excel(excel_path, sheet_name='Contenido_Manual')
        
        # Actualizar fila
        mask = df['id_noticia'] == id_noticia
        if mask.any():
            df.loc[mask, 'estado'] = 'Requiere humano'
            df.loc[mask, 'contenido_noticia'] = 'HUMANO DEBE INSERTAR NOTICIA'
            df.loc[mask, 'intentos_scraping'] = intentos
            df.loc[mask, 'ultimo_intento'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df.loc[mask, 'notas'] = f'Todos los métodos de scraping fallaron ({intentos} intentos)'
            
            # Guardar
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name='Contenido_Manual', index=False)
            
            print(f"   ⚠️  Noticia {id_noticia} marcada como 'Requiere humano'")
            logger.warning(f"Noticia {id_noticia} requiere intervención humana")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error marcando noticia {id_noticia} como requiere humano: {e}")
        return False


def insertar_noticia_ordenada_por_id(
    excel_path: str,
    nombre_hoja: str,
    noticia: dict,
    callback_log=None,
    reemplazar_siempre=False
) -> int:
    """
    Inserta una noticia en una hoja ordenada por id_noticia
    Elimina duplicados automáticamente
    
    Args:
        excel_path: Ruta al archivo Excel
        nombre_hoja: Nombre de la hoja donde insertar
        noticia: Diccionario con datos de la noticia
        callback_log: Función callback para logs
        reemplazar_siempre: Si True, siempre reemplaza duplicados (para Datos_completos)
        
    Returns:
        Número de duplicados eliminados
    """
    try:
        id_noticia = noticia.get('id_noticia')
        duplicados_eliminados = 0
        
        # Leer hoja
        df = pd.read_excel(excel_path, sheet_name=nombre_hoja)
        
        # Buscar duplicados por ID
        mask_duplicados = df['id_noticia'] == id_noticia
        num_duplicados = mask_duplicados.sum()
        
        if num_duplicados > 0:
            if reemplazar_siempre or nombre_hoja == 'Datos_completos':
                # En Datos_completos siempre reemplazar
                msg = f"   🔄 Reemplazando noticia {id_noticia} en {nombre_hoja}"
                logger.info(msg)
                if callback_log:
                    callback_log(msg)
                
                # Eliminar duplicados
                df = df[~mask_duplicados]
                duplicados_eliminados = num_duplicados
            else:
                # En otras hojas, eliminar duplicados de hojas opuestas
                msg = f"   🗑️  Eliminando {num_duplicados} duplicado(s) de {id_noticia} en {nombre_hoja}"
                logger.info(msg)
                if callback_log:
                    callback_log(msg)
                
                df = df[~mask_duplicados]
                duplicados_eliminados = num_duplicados
        
        # Convertir noticia a DataFrame
        df_nueva = pd.DataFrame([noticia])
        
        # Concatenar
        df = pd.concat([df, df_nueva], ignore_index=True)
        
        # Ordenar por id_noticia
        df = df.sort_values('id_noticia').reset_index(drop=True)
        
        # Guardar
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)
        
        msg = f"   ✅ Noticia {id_noticia} insertada en {nombre_hoja} (ordenada por ID)"
        logger.info(msg)
        if callback_log:
            callback_log(msg)
        
        return duplicados_eliminados
        
    except Exception as e:
        logger.error(f"Error insertando noticia {id_noticia} en {nombre_hoja}: {e}")
        if callback_log:
            callback_log(f"   ❌ Error insertando en {nombre_hoja}: {e}")
        return 0


def procesar_decisiones_revision_manual(
    excel_path: str,
    callback_log=None,
    callback_progreso=None
) -> Dict[str, int]:
    """
    Procesa las decisiones del usuario en la hoja Revision_manual.
    
    El usuario puede escribir en la columna 'decision_usuario':
    - "INCLUIR: [explicación]" → Mueve a Datos_filtrados
    - "EXCLUIR: [explicación]" → Mueve a Datos_excluidos
    
    Args:
        excel_path: Ruta al archivo Excel
        callback_log: Función callback para logs
        callback_progreso: Función callback para progreso
        
    Returns:
        Dict con estadísticas: {incluidas, excluidas, pendientes, errores}
    """
    stats = {'incluidas': 0, 'excluidas': 0, 'pendientes': 0, 'errores': 0}
    
    try:
        # Leer todas las hojas necesarias
        df_revision = pd.read_excel(excel_path, sheet_name='Revision_manual')
        df_filtradas = pd.read_excel(excel_path, sheet_name='Datos_filtrados')
        df_excluidas = pd.read_excel(excel_path, sheet_name='Datos_excluidos')
        
        # Verificar que existe la columna decision_usuario
        if 'decision_usuario' not in df_revision.columns:
            df_revision['decision_usuario'] = ''
            if callback_log:
                callback_log("📝 Columna 'decision_usuario' creada en Revision_manual")
        
        total = len(df_revision)
        procesadas = []
        
        for idx, row in df_revision.iterrows():
            id_noticia = row['id_noticia']
            decision = str(row.get('decision_usuario', '')).strip().upper()
            
            if callback_progreso:
                callback_progreso(idx + 1, total, f"Procesando ID {id_noticia}...")
            
            # Saltar si no hay decisión
            if not decision or decision == 'NAN' or decision == '':
                stats['pendientes'] += 1
                continue
            
            try:
                if decision.startswith('INCLUIR'):
                    # Extraer explicación
                    explicacion = decision.replace('INCLUIR:', '').replace('INCLUIR', '').strip()
                    
                    # Preparar fila para Datos_filtrados
                    fila = row.to_dict()
                    fila['notas'] = f"[DECISION MANUAL] {explicacion}" if explicacion else "[DECISION MANUAL]"
                    
                    # Eliminar de Revision_manual
                    procesadas.append(id_noticia)
                    
                    # Agregar a Datos_filtrados
                    df_filtradas = pd.concat([df_filtradas, pd.DataFrame([fila])], ignore_index=True)
                    df_filtradas = df_filtradas.drop_duplicates(subset=['id_noticia'], keep='last')
                    
                    stats['incluidas'] += 1
                    if callback_log:
                        callback_log(f"✅ ID {id_noticia} → Datos_filtrados: {explicacion[:50]}..." if explicacion else f"✅ ID {id_noticia} → Datos_filtrados")
                    
                elif decision.startswith('EXCLUIR'):
                    # Extraer explicación
                    explicacion = decision.replace('EXCLUIR:', '').replace('EXCLUIR', '').strip()
                    
                    # Preparar fila para Datos_excluidos
                    fila = row.to_dict()
                    fila['motivo_exclusion'] = 'Decisión manual del usuario'
                    fila['explicacion_exclusion'] = explicacion if explicacion else 'Excluido manualmente'
                    fila['excluir'] = True
                    
                    # Eliminar de Revision_manual
                    procesadas.append(id_noticia)
                    
                    # Agregar a Datos_excluidos
                    df_excluidas = pd.concat([df_excluidas, pd.DataFrame([fila])], ignore_index=True)
                    df_excluidas = df_excluidas.drop_duplicates(subset=['id_noticia'], keep='last')
                    
                    stats['excluidas'] += 1
                    if callback_log:
                        callback_log(f"❌ ID {id_noticia} → Datos_excluidos: {explicacion[:50]}..." if explicacion else f"❌ ID {id_noticia} → Datos_excluidos")
                else:
                    # Decisión no reconocida
                    stats['pendientes'] += 1
                    if callback_log:
                        callback_log(f"⚠️ ID {id_noticia}: Decisión no reconocida '{decision[:30]}'. Use INCLUIR o EXCLUIR.")
                        
            except Exception as e:
                stats['errores'] += 1
                logger.error(f"Error procesando ID {id_noticia}: {e}")
                if callback_log:
                    callback_log(f"❌ Error procesando ID {id_noticia}: {e}")
        
        # Eliminar noticias procesadas de Revision_manual
        if procesadas:
            df_revision = df_revision[~df_revision['id_noticia'].isin(procesadas)]
        
        # Ordenar por id_noticia
        df_filtradas = df_filtradas.sort_values('id_noticia').reset_index(drop=True)
        df_excluidas = df_excluidas.sort_values('id_noticia').reset_index(drop=True)
        df_revision = df_revision.sort_values('id_noticia').reset_index(drop=True)
        
        # Guardar cambios
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_filtradas.to_excel(writer, sheet_name='Datos_filtrados', index=False)
            df_excluidas.to_excel(writer, sheet_name='Datos_excluidos', index=False)
            df_revision.to_excel(writer, sheet_name='Revision_manual', index=False)
        
        if callback_log:
            callback_log("")
            callback_log("=" * 50)
            callback_log(f"📊 RESUMEN:")
            callback_log(f"   ✅ Incluidas: {stats['incluidas']}")
            callback_log(f"   ❌ Excluidas: {stats['excluidas']}")
            callback_log(f"   ⏳ Pendientes: {stats['pendientes']}")
            callback_log(f"   ❗ Errores: {stats['errores']}")
            callback_log("=" * 50)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error procesando decisiones de Revision_manual: {e}")
        if callback_log:
            callback_log(f"❌ Error general: {e}")
        return stats


def eliminar_duplicados_por_id(
    excel_path: str,
    nombre_hoja: str,
    id_noticia: int,
    callback_log=None
) -> int:
    """
    Elimina duplicados de una noticia en una hoja específica
    
    Args:
        excel_path: Ruta al archivo Excel
        nombre_hoja: Nombre de la hoja
        id_noticia: ID de la noticia a limpiar
        callback_log: Función callback para logs
        
    Returns:
        Número de duplicados eliminados
    """
    try:
        # Leer hoja
        df = pd.read_excel(excel_path, sheet_name=nombre_hoja)
        
        # Contar duplicados
        mask_duplicados = df['id_noticia'] == id_noticia
        num_duplicados = mask_duplicados.sum()
        
        if num_duplicados > 0:
            # Eliminar todos los duplicados
            df = df[~mask_duplicados]
            
            # Guardar
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=nombre_hoja, index=False)
            
            msg = f"   🗑️  Eliminados {num_duplicados} duplicado(s) de noticia {id_noticia} en {nombre_hoja}"
            logger.info(msg)
            if callback_log:
                callback_log(msg)
            
            return num_duplicados
        
        return 0
        
    except Exception as e:
        logger.error(f"Error eliminando duplicados de {id_noticia} en {nombre_hoja}: {e}")
        if callback_log:
            callback_log(f"   ❌ Error eliminando duplicados en {nombre_hoja}: {e}")
        return 0
