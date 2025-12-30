"""
Generador de Mapas Interactivos - Filtrador FONDECYT
Crea mapas de calor con conflictos socioambientales
"""

import pandas as pd
import folium
from folium import plugins
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

def _sanitizar_valor(valor):
    """
    Convierte valores no hashables (dict, list) a string para evitar errores.
    Esto es necesario porque algunas celdas del Excel pueden contener estructuras complejas.
    """
    # Primero verificar tipos no hashables (dict, list) antes de pd.isna()
    # porque pd.isna() puede fallar con estos tipos
    if isinstance(valor, dict):
        return str(valor)
    if isinstance(valor, list):
        return str(valor)
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        # Si pd.isna() falla, convertir a string
        return str(valor)
    return valor

def _sanitizar_columna(serie: pd.Series) -> pd.Series:
    """Aplica sanitización a toda una columna de pandas"""
    return serie.apply(_sanitizar_valor)

class GeneradorMapas:
    """Genera mapas interactivos de conflictos socioambientales"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent / 'data' / 'geojson'
        self.regiones_geojson = self.base_path / 'regiones.geojson'
        self.provincias_geojson = self.base_path / 'provincias.geojson'  # ✅ NUEVO
        self.comunas_geojson = self.base_path / 'comunas.geojson'
        
        # Coordenadas centrales de Chile
        self.chile_center = [-33.4489, -70.6693]  # Santiago
        self.chile_zoom = 4
    
    @staticmethod
    def normalizar_nombre_geografico(nombre: str, nivel: str = None) -> str:
        """
        Normaliza nombres de regiones, provincias y comunas eliminando prefijos comunes
        y normalizando tildes/acentos para matching consistente.
        Incluye diccionario de variaciones para regiones problemáticas.
        
        Args:
            nombre: Nombre geográfico a normalizar
            nivel: 'regiones', 'provincias', 'comunas' o None (auto-detectar)
        
        Ejemplos:
            "Comuna de San Pedro de Atacama" -> "san pedro de atacama"
            "Provincia de El Loa" -> "el loa"
            "Región de Valparaíso" -> "valparaiso"
            "Libertador Bernardo O'Higgins" -> "libertador general bernardo ohiggins"
            "Biobío" -> "biobio"
            "Aysén" -> "aysen del general carlos ibanez del campo"
        """
        if not isinstance(nombre, str):
            return nombre
        
        # Eliminar espacios extras
        nombre = nombre.strip()
        
        # Prefijos a eliminar (case insensitive)
        prefijos = [
            'Comuna de ',
            'comuna de ',
            'COMUNA DE ',
            'Provincia de ',
            'provincia de ',
            'PROVINCIA DE ',
            'Región de ',
            'Region de ',
            'región de ',
            'region de ',
            'REGIÓN DE ',
            'REGION DE ',
            'Región ',
            'Region ',
            'región ',
            'region ',
            'REGIÓN ',
            'REGION '
        ]
        
        # Eliminar prefijos
        for prefijo in prefijos:
            if nombre.startswith(prefijo):
                nombre = nombre[len(prefijo):]
                break
        
        # Normalizar tildes/acentos y convertir a minúsculas para matching consistente
        import unicodedata
        nombre = nombre.strip()
        
        # Intentar corregir problemas de encoding UTF-8 mal interpretado
        try:
            if 'Ã' in nombre or 'Â' in nombre or 'Ñ' in nombre:
                nombre = nombre.encode('latin-1').decode('utf-8')
        except:
            pass
        
        nombre = unicodedata.normalize('NFD', nombre)
        nombre = ''.join(char for char in nombre if unicodedata.category(char) != 'Mn')
        nombre = nombre.lower()
        
        # Normalizar apóstrofes (diferentes tipos de comillas)
        nombre = nombre.replace(''', '\'').replace(''', '\'').replace('`', '\'')
        
        # Eliminar prefijos comunes (orden importante: más específicos primero)
        prefijos_a_eliminar = [
            'region de los ',
            'region de las ',
            'region de la ',
            'region del ',
            'region de ',
            'provincia de los ',
            'provincia de las ',
            'provincia de la ',
            'provincia del ',
            'provincia de ',
            'del ',  # Casos como "del Libertador", "del Biobío"
            'de la ',
            'de los ',
            'de las ',
            'de '
        ]
        
        for prefijo in prefijos_a_eliminar:
            if nombre.startswith(prefijo):
                nombre = nombre[len(prefijo):]
                break
        
        # ✅ DICCIONARIO DE VARIACIONES DE REGIONES
        # Mapea todas las variaciones posibles al nombre canónico
        variaciones_regiones = {
            # O'Higgins - múltiples variaciones
            'libertador general bernardo ohiggins': 'libertador general bernardo ohiggins',
            'libertador bernardo ohiggins': 'libertador general bernardo ohiggins',
            'libertador gral. bernardo ohiggins': 'libertador general bernardo ohiggins',
            'libertador general bernardo o\'higgins': 'libertador general bernardo ohiggins',
            'libertador bernardo o\'higgins': 'libertador general bernardo ohiggins',
            'del libertador general bernardo ohiggins': 'libertador general bernardo ohiggins',
            'del libertador bernardo ohiggins': 'libertador general bernardo ohiggins',
            'ohiggins': 'libertador general bernardo ohiggins',
            'o\'higgins': 'libertador general bernardo ohiggins',
            'vi region': 'libertador general bernardo ohiggins',
            'sexta region': 'libertador general bernardo ohiggins',
            
            # Biobío - con y sin tilde, junto o separado
            'biobio': 'biobio',
            'bio bio': 'biobio',
            'bio-bio': 'biobio',
            'bío bío': 'biobio',
            'viii region': 'biobio',
            'octava region': 'biobio',
            
            # Aysén - nombre completo y variaciones
            'aysen': 'aysen del gral.ibanez del campo',
            'aysen del gral. carlos ibanez del campo': 'aysen del gral.ibanez del campo',
            'aysen del general carlos ibanez del campo': 'aysen del gral.ibanez del campo',
            'aysen del gral.ibanez del campo': 'aysen del gral.ibanez del campo',
            'aysen del general carlos ibañez del campo': 'aysen del gral.ibanez del campo',
            'xi region': 'aysen del gral.ibanez del campo',
            'undecima region': 'aysen del gral.ibanez del campo',
            
            # Magallanes - nombre completo y variaciones
            # IMPORTANTE: El GeoJSON usa "Antártica" sin "de la"
            'magallanes': 'magallanes y antartica chilena',
            'magallanes y antartica chilena': 'magallanes y antartica chilena',
            'magallanes y la antartica': 'magallanes y antartica chilena',
            'magallanes y la antartica chilena': 'magallanes y antartica chilena',  # ✅ NUEVO
            'magallanes y de la antartica chilena': 'magallanes y antartica chilena',
            'xii region': 'magallanes y antartica chilena',
            'duodecima region': 'magallanes y antartica chilena',
            
            # Otras regiones con variaciones comunes
            'arica y parinacota': 'arica y parinacota',
            'arica parinacota': 'arica y parinacota',
            'xv region': 'arica y parinacota',
            
            'tarapaca': 'tarapaca',
            'i region': 'tarapaca',
            'primera region': 'tarapaca',
            
            'antofagasta': 'antofagasta',
            'ii region': 'antofagasta',
            'segunda region': 'antofagasta',
            
            'atacama': 'atacama',
            'iii region': 'atacama',
            'tercera region': 'atacama',
            
            'coquimbo': 'coquimbo',
            'iv region': 'coquimbo',
            'cuarta region': 'coquimbo',
            
            'valparaiso': 'valparaiso',
            'v region': 'valparaiso',
            'quinta region': 'valparaiso',
            
            'metropolitana': 'metropolitana de santiago',
            'metropolitana santiago': 'metropolitana de santiago',
            'metropolitana de santiago': 'metropolitana de santiago',
            'region metropolitana': 'metropolitana de santiago',
            'region metropolitana de santiago': 'metropolitana de santiago',
            'rm': 'metropolitana de santiago',
            'santiago': 'metropolitana de santiago',
            
            'maule': 'maule',
            'vii region': 'maule',
            'septima region': 'maule',
            
            'nuble': 'nuble',
            'ñuble': 'nuble',
            'araucania': 'la araucania',
            'la araucania': 'la araucania',
            'la araaucania': 'la araucania',  # ✅ NUEVO: Error de tipeo común
            'ix region': 'la araucania',
            'novena region': 'la araucania',
            
            'los rios': 'los rios',
            'xiv region': 'los rios',
            
            'los lagos': 'los lagos',
            'x region': 'los lagos',
            'decima region': 'los lagos',
        }
        
        # Aplicar mapeo de variaciones SOLO para regiones
        # Para provincias y comunas, NO aplicar el diccionario (evita que "santiago" → "metropolitana de santiago")
        if nivel == 'regiones' or nivel is None:
            if nombre in variaciones_regiones:
                return variaciones_regiones[nombre]
        
        return nombre
    
    def _corregir_encoding_nombre(self, texto: str) -> str:
        """
        Corrige problemas de encoding en nombres geográficos.
        Maneja casos como: CopiapÃ³ -> Copiapó, ValparaÃ­so -> Valparaíso
        """
        if not isinstance(texto, str):
            return texto
        
        # Primero intentar decodificación Latin-1 -> UTF-8 (método más robusto)
        if '\xc3' in texto or 'Ã' in texto or 'Â' in texto:
            try:
                resultado = texto.encode('latin-1').decode('utf-8')
                return resultado
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
        
        # Si eso no funciona, usar reemplazos manuales
        # Estos son los patrones más comunes de UTF-8 mal interpretado
        reemplazos = [
            ('\xc3\xa1', 'á'), ('\xc3\xa9', 'é'), ('\xc3\xad', 'í'), 
            ('\xc3\xb3', 'ó'), ('\xc3\xba', 'ú'), ('\xc3\xb1', 'ñ'),
            ('\xc3\x81', 'Á'), ('\xc3\x89', 'É'), ('\xc3\x8d', 'Í'),
            ('\xc3\x93', 'Ó'), ('\xc3\x9a', 'Ú'), ('\xc3\x91', 'Ñ'),
            ('\xc3\xbc', 'ü'), ('\xc3\x9c', 'Ü'),
        ]
        
        resultado = texto
        for mal, bien in reemplazos:
            resultado = resultado.replace(mal, bien)
        
        return resultado
        
    def cargar_geojson(self, nivel: str = 'regiones') -> dict:
        """Carga archivo GeoJSON según nivel territorial con corrección de encoding"""
        try:
            if nivel == 'regiones':
                path = self.regiones_geojson
            elif nivel == 'provincias':
                path = self.provincias_geojson
            elif nivel == 'comunas':
                path = self.comunas_geojson
            else:
                raise ValueError(f"Nivel '{nivel}' no válido. Use 'regiones', 'provincias' o 'comunas'")
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Corregir encoding corrupto en nombres (CopiapÃ³ → Copiapó)
            if 'features' in data:
                for feature in data['features']:
                    if 'properties' in feature:
                        for key, value in feature['properties'].items():
                            if isinstance(value, str):
                                feature['properties'][key] = self._corregir_encoding_nombre(value)
            
            return data
        except Exception as e:
            logger.error(f"Error cargando GeoJSON {nivel}: {e}")
            return None
    
    def procesar_datos_excel(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Procesa DataFrame y agrupa conflictos por región/comuna
        
        Returns:
            Dict con estadísticas por ubicación
        """
        stats = {}
        
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_normalizado = df.copy()
        for col in df_normalizado.columns:
            df_normalizado[col] = _sanitizar_columna(df_normalizado[col])
        
        # NORMALIZAR nombres de región y comuna antes de procesar
        if 'region' in df_normalizado.columns:
            df_normalizado['region'] = df_normalizado['region'].apply(lambda x: self.normalizar_nombre_geografico(x, nivel='regiones'))
        if 'comuna' in df_normalizado.columns:
            df_normalizado['comuna'] = df_normalizado['comuna'].apply(lambda x: self.normalizar_nombre_geografico(x, nivel='comunas'))
        
        # Agrupar por región
        for region in df_normalizado['region'].dropna().unique():
            df_region = df_normalizado[df_normalizado['region'] == region]
            
            # ORDENAR por fecha (más reciente primero)
            if 'fecha' in df_region.columns:
                df_region = df_region.sort_values('fecha', ascending=False)
            
            # Preparar lista de noticias con TODA la información
            noticias_list = []
            for _, row in df_region.iterrows():
                noticias_list.append({
                    'titulo': row.get('titulo', 'Sin título'),
                    'url': row.get('link_noticia', row.get('url', '#')),
                    'fecha': str(row.get('fecha', 'Sin fecha'))[:10],
                    'fecha_raw': row.get('fecha'),
                    'resumen': row.get('resumen', ''),
                    'tipo_conflicto': row.get('tipo_conflicto', ''),
                    'tipo_accion': row.get('tipo_accion', ''),
                    'explicacion_conflicto': row.get('explicacion_conflicto', ''),
                    'explicacion_accion': row.get('explicacion_accion', ''),
                    'actor_demandante': row.get('actor_demandante', ''),
                    'actor_demandado': row.get('actor_demandado', ''),
                    'explicacion_demandante': row.get('explicacion_demandante', ''),
                    'explicacion_demandado': row.get('explicacion_demandado', ''),
                    'region': row.get('region', ''),
                    'provincia': row.get('provincia', ''),
                    'comuna': row.get('comuna', ''),
                    'localidad': row.get('localidad', ''),
                    'sector_economico': row.get('sector_economico', '')
                })
            
            stats[region] = {
                'total_conflictos': len(df_region),
                'tipos_conflicto': df_region['tipo_conflicto'].value_counts().to_dict() if 'tipo_conflicto' in df_region.columns else {},
                'sectores': df_region['sector_economico'].value_counts().to_dict() if 'sector_economico' in df_region.columns else {},
                'actores_demandantes': df_region['actor_demandante'].value_counts().to_dict() if 'actor_demandante' in df_region.columns else {},
                'noticias': noticias_list
            }
        
        return stats
    
    def calcular_intensidad_color(self, cantidad: int, max_cantidad: int = None) -> str:
        """
        Calcula color según intensidad de conflictos usando UMBRALES FIJOS
        
        Umbrales basados en análisis de datos:
        - Antofagasta: 408 conflictos (máximo regional)
        - Valparaíso: 431 conflictos (máximo regional)
        
        Returns:
            Color en formato hex
        """
        if cantidad == 0:
            return '#FFFFFF'  # Blanco (sin conflictos)
        
        # UMBRALES FIJOS (no porcentajes dinámicos)
        # Estos umbrales son significativos en términos absolutos
        if cantidad >= 100:
            return '#F03B20'  # Rojo - Alta concentración (100+)
        elif cantidad >= 50:
            return '#FEB24C'  # Naranja - Media-Alta (50-99)
        elif cantidad >= 20:
            return '#FFEDA0'  # Amarillo - Media (20-49)
        else:
            return '#FFFFCC'  # Amarillo claro - Baja (1-19)
    
    
    # =========================================================================
    # NOTA: Codigo legacy eliminado (funciones no utilizadas):
    # - crear_popup_html() [lineas 401-486] - Reemplazada por panel lateral
    # - crear_popup_html_detallado() [lineas 488-626] - Reemplazada por panel lateral  
    # - generar_mapa_regiones() [lineas 628-706] - Reemplazada por generar_mapa_unificado_con_panel()
    # - generar_mapa_comunal() [lineas 708-825] - Reemplazada por generar_mapa_unificado_con_panel()
    # - generar_mapa_provincial() [lineas 827-958] - Reemplazada por generar_mapa_unificado_con_panel()
    # =========================================================================
    
    def _preparar_datos_temporales(self, df: pd.DataFrame) -> Dict:
        """Prepara datos para la línea de tiempo con todos los niveles geográficos"""
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_temp = df.copy()
        for col in df_temp.columns:
            df_temp[col] = _sanitizar_columna(df_temp[col])
        
        logger.info(f"Preparando datos temporales. Columnas disponibles: {list(df_temp.columns)}")
        
        if 'año' not in df_temp.columns and 'fecha' in df_temp.columns:
            df_temp['fecha_dt'] = pd.to_datetime(df_temp['fecha'], errors='coerce')
            df_temp['año'] = df_temp['fecha_dt'].dt.year
            logger.info(f"Columna 'año' creada desde 'fecha'. Años únicos: {sorted(df_temp['año'].dropna().unique())}")
        elif 'año' in df_temp.columns:
            logger.info(f"Columna 'año' ya existe. Años únicos: {sorted(df_temp['año'].dropna().unique())}")
        else:
            logger.warning("No se encontró columna 'fecha' ni 'año'. No se puede crear línea de tiempo.")
            return {'años': [], 'datos': {}, 'año_min': 2000, 'año_max': 2025, 'sin_fecha': {}}
        
        # Contar noticias sin fecha
        df_sin_fecha = df_temp[df_temp['año'].isna()]
        noticias_sin_fecha_count = len(df_sin_fecha)
        logger.info(f"Noticias SIN fecha detectadas: {noticias_sin_fecha_count}")
        
        # Preparar datos de noticias sin fecha
        datos_sin_fecha = self._preparar_datos_sin_fecha(df_sin_fecha)
        
        # Obtener rango de años
        años = sorted(df_temp['año'].dropna().unique())
        if len(años) == 0:
            logger.warning("No hay años válidos en los datos")
            return {'años': [], 'datos': {}, 'año_min': 2000, 'año_max': 2025, 'sin_fecha': datos_sin_fecha}
        
        año_min = int(años[0])
        año_max = int(años[-1])
        
        # Preparar datos por año con TODOS los niveles
        datos_por_año = {}
        for año in range(año_min, año_max + 1):
            df_año = df_temp[df_temp['año'] == año]
            
            # Estadísticas por región
            stats_regiones = {}
            if 'region' in df_año.columns:
                for region in df_año['region'].dropna().unique():
                    region_norm = self.normalizar_nombre_geografico(region, nivel='regiones')
                    count = len(df_año[df_año['region'] == region])
                    stats_regiones[region_norm] = count
            
            # Estadísticas por provincia
            stats_provincias = {}
            if 'provincia' in df_año.columns:
                for provincia in df_año['provincia'].dropna().unique():
                    prov_norm = self.normalizar_nombre_geografico(provincia, nivel='provincias')
                    count = len(df_año[df_año['provincia'] == provincia])
                    stats_provincias[prov_norm] = count
            
            # Estadísticas por comuna
            stats_comunas = {}
            if 'comuna' in df_año.columns:
                for comuna in df_año['comuna'].dropna().unique():
                    comuna_norm = self.normalizar_nombre_geografico(comuna, nivel='comunas')
                    count = len(df_año[df_año['comuna'] == comuna])
                    stats_comunas[comuna_norm] = count
            
            # Preparar noticias del año para cada territorio
            noticias_año = {}
            for nivel in ['region', 'provincia', 'comuna']:
                if nivel in df_año.columns:
                    for territorio in df_año[nivel].dropna().unique():
                        territorio_norm = self.normalizar_nombre_geografico(
                            territorio, 
                            nivel='regiones' if nivel == 'region' else 'provincias' if nivel == 'provincia' else 'comunas'
                        )
                        
                        # Obtener noticias de este territorio en este año
                        noticias_territorio = df_año[df_año[nivel] == territorio]
                        
                        if territorio_norm not in noticias_año:
                            noticias_año[territorio_norm] = []
                        
                        for _, row in noticias_territorio.iterrows():
                            noticia = {
                                'titulo': row.get('titulo', 'Sin título'),
                                'fecha': str(row.get('fecha', '')),
                                'url': row.get('url', ''),
                                'descripcion': row.get('descripcion', '')
                            }
                            noticias_año[territorio_norm].append(noticia)
            
            datos_por_año[año] = {
                'total': len(df_año),
                'por_region': stats_regiones,
                'por_provincia': stats_provincias,
                'por_comuna': stats_comunas,
                'noticias': noticias_año
            }
        
        logger.info(f"Datos temporales preparados: {año_min}-{año_max} ({len(datos_por_año)} años)")
        logger.info(f"Noticias sin fecha: {datos_sin_fecha.get('total', 0)}")
        
        return {
            'año_min': año_min,
            'año_max': año_max,
            'años': list(range(año_min, año_max + 1)),
            'datos': datos_por_año,
            'sin_fecha': datos_sin_fecha
        }
    
    def _preparar_datos_sin_fecha(self, df_sin_fecha: pd.DataFrame) -> Dict:
        """Prepara datos de noticias que no tienen fecha para incluirlas opcionalmente"""
        if len(df_sin_fecha) == 0:
            return {'total': 0, 'por_region': {}, 'por_provincia': {}, 'por_comuna': {}, 'noticias': {}}
        
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_sin_fecha = df_sin_fecha.copy()
        for col in df_sin_fecha.columns:
            df_sin_fecha[col] = _sanitizar_columna(df_sin_fecha[col])
        
        # Estadísticas por región
        stats_regiones = {}
        if 'region' in df_sin_fecha.columns:
            for region in df_sin_fecha['region'].dropna().unique():
                region_norm = self.normalizar_nombre_geografico(region, nivel='regiones')
                count = len(df_sin_fecha[df_sin_fecha['region'] == region])
                stats_regiones[region_norm] = count
        
        # Estadísticas por provincia
        stats_provincias = {}
        if 'provincia' in df_sin_fecha.columns:
            for provincia in df_sin_fecha['provincia'].dropna().unique():
                prov_norm = self.normalizar_nombre_geografico(provincia, nivel='provincias')
                count = len(df_sin_fecha[df_sin_fecha['provincia'] == provincia])
                stats_provincias[prov_norm] = count
        
        # Estadísticas por comuna
        stats_comunas = {}
        if 'comuna' in df_sin_fecha.columns:
            for comuna in df_sin_fecha['comuna'].dropna().unique():
                comuna_norm = self.normalizar_nombre_geografico(comuna, nivel='comunas')
                count = len(df_sin_fecha[df_sin_fecha['comuna'] == comuna])
                stats_comunas[comuna_norm] = count
        
        # Preparar noticias sin fecha para cada territorio
        noticias_sin_fecha = {}
        for nivel in ['region', 'provincia', 'comuna']:
            if nivel in df_sin_fecha.columns:
                for territorio in df_sin_fecha[nivel].dropna().unique():
                    territorio_norm = self.normalizar_nombre_geografico(
                        territorio, 
                        nivel='regiones' if nivel == 'region' else 'provincias' if nivel == 'provincia' else 'comunas'
                    )
                    
                    noticias_territorio = df_sin_fecha[df_sin_fecha[nivel] == territorio]
                    
                    if territorio_norm not in noticias_sin_fecha:
                        noticias_sin_fecha[territorio_norm] = []
                    
                    for _, row in noticias_territorio.iterrows():
                        noticia = {
                            'titulo': row.get('titulo', 'Sin título'),
                            'fecha': 'Sin fecha',
                            'url': row.get('url', ''),
                            'descripcion': row.get('descripcion', '')
                        }
                        noticias_sin_fecha[territorio_norm].append(noticia)
        
        return {
            'total': len(df_sin_fecha),
            'por_region': stats_regiones,
            'por_provincia': stats_provincias,
            'por_comuna': stats_comunas,
            'noticias': noticias_sin_fecha
        }
    
    def generar_mapa_unificado_con_panel(self, df: pd.DataFrame, output_path: str = None) -> folium.Map:
        """
        Genera un mapa unificado con:
        - Panel lateral izquierdo con información detallada
        - Selector de nivel geográfico (Regiones/Provincias/Comunas)
        - Click en territorio actualiza el panel (NO popup)
        - Desplegable de territorios arriba del panel
        """
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df = df.copy()
        for col in df.columns:
            df[col] = _sanitizar_columna(df[col])
        
        # Preparar datos para los 3 niveles
        stats_regiones = self._preparar_estadisticas_regiones(df)
        stats_provincias = self._preparar_estadisticas_provincias(df)
        stats_comunas = self._preparar_estadisticas_comunas(df)
        
        # Preparar datos temporales para la línea de tiempo
        datos_temporales = self._preparar_datos_temporales(df)
        
        # Preparar valores únicos para los filtros categóricos
        filtros_categoricos = {
            'tipos_conflicto': sorted([x for x in df['tipo_conflicto'].dropna().unique() if x and str(x).strip()]),
            'tipos_accion': sorted([x for x in df['tipo_accion'].dropna().unique() if x and str(x).strip()]),
            'actores_demandante': sorted([x for x in df['actor_demandante'].dropna().unique() if x and str(x).strip()]),
            'actores_demandado': sorted([x for x in df['actor_demandado'].dropna().unique() if x and str(x).strip()]),
            'sectores': sorted([x for x in df['sector_economico'].dropna().unique() if x and str(x).strip()])
        }
        logger.info(f"🎛️ Filtros categóricos preparados: {len(filtros_categoricos['tipos_conflicto'])} tipos conflicto, {len(filtros_categoricos['tipos_accion'])} tipos acción")
        
        # Crear mapa base (sin tiles por defecto, los añadimos manualmente)
        mapa = folium.Map(
            location=self.chile_center,
            zoom_start=self.chile_zoom,
            tiles=None  # No añadir tiles por defecto
        )
        
        # Añadir múltiples capas de tiles para que el usuario elija
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='🗺️ Calles',
            control=True
        ).add_to(mapa)
        
        folium.TileLayer(
            tiles='CartoDB positron',
            name='⬜ Minimalista',
            control=True
        ).add_to(mapa)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri World Imagery',
            name='🛰️ Satélite',
            control=True
        ).add_to(mapa)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri World Topo',
            name='🏔️ Relieve',
            control=True
        ).add_to(mapa)
        
        folium.TileLayer(
            tiles='CartoDB dark_matter',
            name='🌙 Modo Oscuro',
            control=True
        ).add_to(mapa)
        
        # Convertir estadísticas a JSON para JavaScript
        import json
        stats_json = json.dumps({
            'regiones': stats_regiones,
            'provincias': stats_provincias,
            'comunas': stats_comunas
        }, ensure_ascii=False, default=str)
        
        # Convertir datos temporales a JSON
        temporal_json = json.dumps(datos_temporales, ensure_ascii=False, default=str)
        
        # Convertir filtros categóricos a JSON
        filtros_json = json.dumps(filtros_categoricos, ensure_ascii=False, default=str)
        
        # Extraer valores para usar en el f-string (evitar problemas con {{}})
        sin_fecha_total = datos_temporales.get('sin_fecha', {}).get('total', 0)
        año_max_display = datos_temporales.get('año_max', 2025)
        
        # Obtener el ID del mapa ANTES de crear el HTML
        id_mapa = mapa.get_name()
        
        # HTML del panel lateral + controles + JavaScript
        panel_html = f"""
        <style>
            #sidebar {{
                position: fixed;
                top: 0;
                left: 0;
                width: 400px;
                height: 100%;
                background: white;
                z-index: 9999;
                padding: 15px;
                box-shadow: 2px 0 10px rgba(0,0,0,0.2);
                overflow-y: auto;
                font-family: Arial, sans-serif;
                transition: transform 0.3s ease;
            }}
            
            #sidebar.collapsed {{
                transform: translateX(-400px);
            }}
            
            #toggle-sidebar {{
                position: fixed;
                top: 10px;
                left: 410px;
                z-index: 10000;
                background: white;
                border: none;
                border-radius: 0 8px 8px 0;
                padding: 10px 12px;
                cursor: pointer;
                box-shadow: 2px 0 10px rgba(0,0,0,0.2);
                font-size: 18px;
                transition: left 0.3s ease;
            }}
            
            #toggle-sidebar:hover {{
                background: #f0f0f0;
            }}
            
            #sidebar.collapsed + #toggle-sidebar,
            #toggle-sidebar.sidebar-collapsed {{
                left: 10px;
                border-radius: 8px;
            }}
            
            #controls {{
                position: fixed;
                top: 10px;
                right: 10px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 9998;
                max-height: 90vh;
                overflow-y: auto;
                width: 240px;
            }}
            
            #filtros-categoricos {{
                margin-top: 15px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            }}
            
            #filtros-categoricos h4 {{
                margin: 0 0 10px 0;
                color: #2c3e50;
                font-size: 13px;
            }}
            
            .filtro-grupo {{
                margin-bottom: 12px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
            }}
            
            .filtro-grupo-header {{
                background: #f5f5f5;
                padding: 8px 10px;
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 12px;
                font-weight: bold;
                color: #2c3e50;
            }}
            
            .filtro-grupo-header:hover {{
                background: #e8e8e8;
            }}
            
            .filtro-grupo-header .toggle-icon {{
                transition: transform 0.2s;
            }}
            
            .filtro-grupo.expanded .toggle-icon {{
                transform: rotate(180deg);
            }}
            
            .filtro-grupo-content {{
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease;
            }}
            
            .filtro-grupo.expanded .filtro-grupo-content {{
                max-height: 200px;
                overflow-y: auto;
            }}
            
            .filtro-checkbox-list {{
                padding: 5px 10px;
            }}
            
            .filtro-checkbox-item {{
                display: flex;
                align-items: flex-start;
                padding: 4px 0;
                font-size: 11px;
                color: #555;
            }}
            
            .filtro-checkbox-item input[type="checkbox"] {{
                margin-right: 6px;
                margin-top: 2px;
                cursor: pointer;
            }}
            
            .filtro-checkbox-item label {{
                cursor: pointer;
                line-height: 1.3;
            }}
            
            .filtro-count {{
                background: #3498db;
                color: white;
                border-radius: 10px;
                padding: 2px 6px;
                font-size: 10px;
                margin-left: 5px;
            }}
            
            .filtro-count.empty {{
                background: #bdc3c7;
            }}
            
            .btn-filtros {{
                display: flex;
                gap: 5px;
                margin-top: 10px;
            }}
            
            .btn-filtro {{
                flex: 1;
                padding: 6px 10px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 11px;
                transition: background 0.2s;
            }}
            
            .btn-aplicar {{
                background: #3498db;
                color: white;
            }}
            
            .btn-aplicar:hover {{
                background: #2980b9;
            }}
            
            .btn-limpiar {{
                background: #ecf0f1;
                color: #7f8c8d;
            }}
            
            .btn-limpiar:hover {{
                background: #bdc3c7;
            }}
            
            .filtro-activo {{
                background: #e8f4f8 !important;
                border-color: #3498db !important;
            }}
            
            #filtros-resumen {{
                margin-top: 10px;
                padding: 8px;
                background: #f8f9fa;
                border-radius: 4px;
                font-size: 11px;
                color: #7f8c8d;
                display: none;
            }}
            
            #filtros-resumen.activo {{
                display: block;
            }}
            
            .control-group {{
                margin-bottom: 10px;
            }}
            
            .control-label {{
                font-weight: bold;
                margin-bottom: 5px;
                display: block;
                color: #2c3e50;
            }}
            
            select {{
                width: 200px;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            
            /* Estilos para búsqueda por término */
            #search-container {{
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 1px solid #eee;
            }}
            
            #search-input {{
                width: 100%;
                padding: 10px 35px 10px 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                box-sizing: border-box;
                transition: border-color 0.2s, box-shadow 0.2s;
            }}
            
            #search-input:focus {{
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
                outline: none;
            }}
            
            #search-input::placeholder {{
                color: #aaa;
            }}
            
            .search-wrapper {{
                position: relative;
            }}
            
            #search-clear {{
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                color: #aaa;
                cursor: pointer;
                font-size: 16px;
                padding: 5px;
                display: none;
            }}
            
            #search-clear:hover {{
                color: #e74c3c;
            }}
            
            #search-results-count {{
                margin-top: 8px;
                font-size: 12px;
                color: #7f8c8d;
            }}
            
            #search-results-count.has-results {{
                color: #27ae60;
            }}
            
            .highlight {{
                background-color: #fff3cd;
                padding: 1px 2px;
                border-radius: 2px;
            }}
            
            .noticia-card {{
                margin: 15px 0;
                padding: 12px;
                background: #f8f9fa;
                border-left: 4px solid #3498db;
                border-radius: 4px;
            }}
            
            .noticia-title {{
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 8px;
            }}
            
            .noticia-date {{
                font-size: 11px;
                color: #7f8c8d;
                margin-bottom: 8px;
            }}
            
            .noticia-section {{
                margin: 8px 0;
                font-size: 12px;
            }}
            
            .section-title {{
                font-weight: bold;
                color: #34495e;
            }}
            
            .section-content {{
                color: #555;
                margin-top: 3px;
            }}
            
            .ubicacion {{
                background: #e8f4f8;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 11px;
                color: #2980b9;
            }}
            
            /* ⏱️ LÍNEA DE TIEMPO - DISEÑO SIMPLE Y COMPACTO */
            #timeline-panel {{
                position: fixed;
                bottom: 10px;
                right: 20px;
                width: 500px;
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid #ddd;
                border-radius: 6px;
                z-index: 9997;
                padding: 10px 15px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            
            #timeline-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }}
            
            #timeline-info {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 12px;
                color: #555;
            }}
            
            #año-display {{
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }}
            
            #conflictos-count {{
                font-size: 11px;
                color: #7f8c8d;
            }}
            
            #timeline-controls {{
                display: flex;
                gap: 5px;
                align-items: center;
            }}
            
            .timeline-btn {{
                background: #3498db;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                cursor: pointer;
                font-size: 11px;
                transition: background 0.2s;
            }}
            
            .timeline-btn:hover {{
                background: #2980b9;
            }}
            
            .timeline-btn.active {{
                background: #27ae60;
            }}
            
            #modo-toggle {{
                padding: 4px 10px;
                background: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                cursor: pointer;
                color: #2c3e50;
                font-size: 11px;
                transition: all 0.2s;
            }}
            
            #modo-toggle.acumulado {{
                background: #3498db;
                border-color: #2980b9;
                color: white;
            }}
            
            #timeline-slider-container {{
                position: relative;
                width: 100%;
                height: 25px;
            }}
            
            #timeline-slider {{
                width: 100%;
                height: 4px;
                -webkit-appearance: none;
                appearance: none;
                background: #ddd;
                border-radius: 2px;
                outline: none;
                cursor: pointer;
            }}
            
            #timeline-slider::-webkit-slider-thumb {{
                -webkit-appearance: none;
                appearance: none;
                width: 14px;
                height: 14px;
                background: #3498db;
                border: 2px solid white;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }}
            
            #timeline-slider::-webkit-slider-thumb:hover {{
                background: #2980b9;
            }}
            
            #timeline-slider::-moz-range-thumb {{
                width: 14px;
                height: 14px;
                background: #3498db;
                border: 2px solid white;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }}
            
            #timeline-markers {{
                position: absolute;
                top: 12px;
                left: 0;
                right: 0;
                height: 15px;
                display: flex;
                justify-content: space-between;
                pointer-events: none;
            }}
            
            .year-marker {{
                font-size: 9px;
                color: #95a5a6;
                text-align: center;
            }}
            
            #timeline-tooltip {{
                position: absolute;
                bottom: 30px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 11px;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.2s;
                white-space: nowrap;
            }}
            
            #timeline-tooltip.show {{
                opacity: 1;
            }}
            
            /* Tooltip dinámico del mapa */
            #map-tooltip {{
                position: fixed;
                background: rgba(0, 0, 0, 0.85);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 13px;
                pointer-events: none;
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.2s;
                white-space: nowrap;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            }}
            
            #map-tooltip.show {{
                opacity: 1;
            }}
        </style>
        
        <!-- PANEL DE LÍNEA DE TIEMPO -->
        <div id="timeline-panel">
            <div id="timeline-header">
                <div id="timeline-info">
                    <span id="año-display">{año_max_display}</span>
                    <span id="conflictos-count">0 conflictos</span>
                    <span id="sin-fecha-count" style="color: #e67e22; font-size: 11px; margin-left: 8px;" title="Noticias sin fecha detectada">({sin_fecha_total} sin fecha)</span>
                </div>
                <div id="timeline-controls">
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px; color: #7f8c8d; cursor: pointer;" title="Incluir noticias que no tienen fecha en el conteo">
                        <input type="checkbox" id="incluir-sin-fecha" onchange="toggleIncluirSinFecha()">
                        <span>+Sin fecha</span>
                    </label>
                    <button id="btn-play-timeline" class="timeline-btn">Play</button>
                    <button id="btn-stop-timeline" class="timeline-btn active" style="display: none;">Stop</button>
                    <button id="modo-toggle" class="acumulado" title="Cambiar entre año único y acumulado">Acumulado</button>
                    <button id="btn-total" class="timeline-btn" title="Mostrar todos los conflictos sin filtro temporal">Total</button>
                </div>
            </div>
            
            <div id="timeline-slider-container">
                <div id="timeline-tooltip">{datos_temporales.get('año_max', 2025)}</div>
                <input type="range" id="timeline-slider" 
                    min="{datos_temporales.get('año_min', 2000)}" 
                    max="{datos_temporales.get('año_max', 2025)}" 
                    value="{datos_temporales.get('año_max', 2025)}"
                    step="1">
                <div id="timeline-markers"></div>
            </div>
        </div>
        
        <div id="controls">
            <div class="control-group">
                <label class="control-label" for="nivelSelector">Nivel Geográfico:</label>
                <select id="nivelSelector" name="nivelSelector" aria-label="Seleccionar nivel geográfico" title="Seleccionar nivel geográfico (regiones, provincias o comunas)" onchange="cambiarNivel()">
                    <option value="regiones">Regiones</option>
                    <option value="provincias">Provincias</option>
                    <option value="comunas">Comunas</option>
                </select>
            </div>
            
            <div class="control-group">
                <label class="control-label" for="territorioSelector">Territorio:</label>
                <select id="territorioSelector" name="territorioSelector" aria-label="Seleccionar territorio" title="Seleccionar un territorio específico para ver sus conflictos" onchange="mostrarTerritorio()">
                    <option value="">Todos</option>
                </select>
            </div>
            
            <!-- BÚSQUEDA POR TÉRMINO -->
            <div id="search-container">
                <label class="control-label" for="search-input">🔍 Buscar:</label>
                <div class="search-wrapper">
                    <input type="text" id="search-input" 
                           placeholder="Ej: litio, protesta, SQM..." 
                           oninput="buscarTermino(this.value)"
                           title="Buscar en título, resumen, actores, tipo de conflicto y acción">
                    <button id="search-clear" onclick="limpiarBusqueda()" title="Limpiar búsqueda">✕</button>
                </div>
                <div id="search-results-count"></div>
            </div>
            
            <!-- FILTROS CATEGÓRICOS -->
            <div id="filtros-categoricos">
                <h4>🎛️ Filtros de Clasificación</h4>
                
                <!-- Sector Económico -->
                <div class="filtro-grupo" id="grupo-sector">
                    <div class="filtro-grupo-header" onclick="toggleGrupoFiltro('sector')">
                        <span>Sector Económico <span class="filtro-count empty" id="count-sector">0</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="filtro-grupo-content">
                        <div class="filtro-checkbox-list" id="checkboxes-sector"></div>
                    </div>
                </div>
                
                <!-- Tipo de Conflicto -->
                <div class="filtro-grupo" id="grupo-tipo_conflicto">
                    <div class="filtro-grupo-header" onclick="toggleGrupoFiltro('tipo_conflicto')">
                        <span>Tipo de Conflicto <span class="filtro-count empty" id="count-tipo_conflicto">0</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="filtro-grupo-content">
                        <div class="filtro-checkbox-list" id="checkboxes-tipo_conflicto"></div>
                    </div>
                </div>
                
                <!-- Tipo de Acción -->
                <div class="filtro-grupo" id="grupo-tipo_accion">
                    <div class="filtro-grupo-header" onclick="toggleGrupoFiltro('tipo_accion')">
                        <span>Tipo de Acción <span class="filtro-count empty" id="count-tipo_accion">0</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="filtro-grupo-content">
                        <div class="filtro-checkbox-list" id="checkboxes-tipo_accion"></div>
                    </div>
                </div>
                
                <!-- Actor Demandante -->
                <div class="filtro-grupo" id="grupo-actor_demandante">
                    <div class="filtro-grupo-header" onclick="toggleGrupoFiltro('actor_demandante')">
                        <span>Actor Demandante <span class="filtro-count empty" id="count-actor_demandante">0</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="filtro-grupo-content">
                        <div class="filtro-checkbox-list" id="checkboxes-actor_demandante"></div>
                    </div>
                </div>
                
                <!-- Actor Demandado -->
                <div class="filtro-grupo" id="grupo-actor_demandado">
                    <div class="filtro-grupo-header" onclick="toggleGrupoFiltro('actor_demandado')">
                        <span>Actor Demandado <span class="filtro-count empty" id="count-actor_demandado">0</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="filtro-grupo-content">
                        <div class="filtro-checkbox-list" id="checkboxes-actor_demandado"></div>
                    </div>
                </div>
                
                <div class="btn-filtros">
                    <button class="btn-filtro btn-aplicar" onclick="aplicarFiltrosCategoricos()">Aplicar</button>
                    <button class="btn-filtro btn-limpiar" onclick="limpiarFiltrosCategoricos()">Limpiar</button>
                </div>
                
                <div id="filtros-resumen"></div>
            </div>
        </div>
        
        <div id="sidebar">
            <h3 style="color: #2c3e50; margin-top: 0;">Información de Conflictos</h3>
            <p style="color: #7f8c8d;">Selecciona un territorio en el mapa o usa el selector arriba</p>
            <div id="contenido"></div>
        </div>
        
        <!-- Botón para ocultar/mostrar sidebar -->
        <button id="toggle-sidebar" onclick="toggleSidebar()" title="Ocultar/Mostrar panel">◀</button>
        
        <!-- Tooltip dinámico del mapa -->
        <div id="map-tooltip"></div>
        
        <script>
            // Datos de estadísticas
            const statsData = {stats_json};
            const datosTemporales = {temporal_json};
            const filtrosCategoricos = {filtros_json};
            let nivelActual = 'regiones';
            
            // ⏱️ VARIABLES DE LÍNEA DE TIEMPO
            let añoActual = datosTemporales.año_max || 2025;
            let modoAcumulado = true; // Iniciar en modo acumulado
            let animacionActiva = false;
            let intervaloAnimacion = null;
            let filtroTemporalActivo = false; // Trackea si se ha movido el slider
            let incluirSinFecha = false; // Incluir noticias sin fecha en el filtrado
            
            // 🎛️ VARIABLES DE FILTROS CATEGÓRICOS (ahora son arrays para múltiples selecciones)
            let filtrosActivos = {{
                sector: [],
                tipo_conflicto: [],
                tipo_accion: [],
                actor_demandante: [],
                actor_demandado: []
            }};
            let filtroCategoricoActivo = false;
            let sidebarVisible = true;
            
            // 🔍 VARIABLES DE BÚSQUEDA POR TÉRMINO
            let terminoBusqueda = '';
            
            // Mapeo de categorías a campos de datos
            const mapeoFiltros = {{
                'sector': 'sectores',
                'tipo_conflicto': 'tipos_conflicto',
                'tipo_accion': 'tipos_accion',
                'actor_demandante': 'actores_demandante',
                'actor_demandado': 'actores_demandado'
            }};
            
            const mapeoNoticia = {{
                'sector': 'sector_economico',
                'tipo_conflicto': 'tipo_conflicto',
                'tipo_accion': 'tipo_accion',
                'actor_demandante': 'actor_demandante',
                'actor_demandado': 'actor_demandado'
            }};
            
            // 📌 FUNCIÓN TOGGLE SIDEBAR
            function toggleSidebar() {{
                const sidebar = document.getElementById('sidebar');
                const toggleBtn = document.getElementById('toggle-sidebar');
                
                if (sidebarVisible) {{
                    sidebar.classList.add('collapsed');
                    toggleBtn.classList.add('sidebar-collapsed');
                    toggleBtn.innerHTML = '▶';
                    toggleBtn.title = 'Mostrar panel';
                }} else {{
                    sidebar.classList.remove('collapsed');
                    toggleBtn.classList.remove('sidebar-collapsed');
                    toggleBtn.innerHTML = '◀';
                    toggleBtn.title = 'Ocultar panel';
                }}
                sidebarVisible = !sidebarVisible;
            }}
            
            // Función para toggle de incluir sin fecha
            function toggleIncluirSinFecha() {{
                incluirSinFecha = document.getElementById('incluir-sin-fecha').checked;
                console.log('Incluir sin fecha:', incluirSinFecha);
                // Re-aplicar el filtro actual
                if (filtroTemporalActivo) {{
                    filtrarMapaPorAño(añoActual, modoAcumulado);
                }}
            }}
            
            // 🎛️ FUNCIONES DE FILTROS CATEGÓRICOS
            
            // Toggle para expandir/colapsar grupo de filtros
            function toggleGrupoFiltro(categoria) {{
                const grupo = document.getElementById('grupo-' + categoria);
                grupo.classList.toggle('expanded');
            }}
            
            // Poblar los checkboxes de filtros con las opciones disponibles
            function poblarFiltrosCategoricos() {{
                const categorias = ['sector', 'tipo_conflicto', 'tipo_accion', 'actor_demandante', 'actor_demandado'];
                
                categorias.forEach(categoria => {{
                    const container = document.getElementById('checkboxes-' + categoria);
                    const opciones = filtrosCategoricos[mapeoFiltros[categoria]] || [];
                    
                    if (container && opciones.length > 0) {{
                        opciones.forEach((opcion, index) => {{
                            const item = document.createElement('div');
                            item.className = 'filtro-checkbox-item';
                            
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.id = `cb-${{categoria}}-${{index}}`;
                            checkbox.value = opcion;
                            checkbox.dataset.categoria = categoria;
                            checkbox.onchange = () => actualizarConteoFiltro(categoria);
                            
                            const label = document.createElement('label');
                            label.htmlFor = checkbox.id;
                            label.textContent = opcion;
                            
                            item.appendChild(checkbox);
                            item.appendChild(label);
                            container.appendChild(item);
                        }});
                    }}
                }});
                console.log('🎛️ Filtros categóricos poblados con checkboxes');
            }}
            
            // Actualizar el conteo de filtros seleccionados en cada categoría
            function actualizarConteoFiltro(categoria) {{
                const checkboxes = document.querySelectorAll(`input[data-categoria="${{categoria}}"]:checked`);
                const countSpan = document.getElementById('count-' + categoria);
                const count = checkboxes.length;
                
                countSpan.textContent = count;
                if (count > 0) {{
                    countSpan.classList.remove('empty');
                }} else {{
                    countSpan.classList.add('empty');
                }}
            }}
            
            // Obtener los valores seleccionados de una categoría
            function obtenerValoresSeleccionados(categoria) {{
                const checkboxes = document.querySelectorAll(`input[data-categoria="${{categoria}}"]:checked`);
                return Array.from(checkboxes).map(cb => cb.value);
            }}
            
            // Aplicar todos los filtros categóricos
            function aplicarFiltrosCategoricos() {{
                filtrosActivos.sector = obtenerValoresSeleccionados('sector');
                filtrosActivos.tipo_conflicto = obtenerValoresSeleccionados('tipo_conflicto');
                filtrosActivos.tipo_accion = obtenerValoresSeleccionados('tipo_accion');
                filtrosActivos.actor_demandante = obtenerValoresSeleccionados('actor_demandante');
                filtrosActivos.actor_demandado = obtenerValoresSeleccionados('actor_demandado');
                
                // Verificar si hay algún filtro activo
                filtroCategoricoActivo = Object.values(filtrosActivos).some(arr => arr.length > 0);
                
                console.log('🎛️ Aplicando filtros:', filtrosActivos);
                
                // Si hay filtro temporal activo, re-aplicarlo con los filtros categóricos
                if (filtroTemporalActivo) {{
                    filtrarMapaPorAño(añoActual, modoAcumulado);
                }} else {{
                    // Filtrar solo por categorías
                    filtrarDatosPorCategorias();
                }}
                
                // Mostrar resumen de filtros
                mostrarResumenFiltros();
            }}
            
            // Limpiar todos los filtros categóricos
            function limpiarFiltrosCategoricos() {{
                // Desmarcar todos los checkboxes
                document.querySelectorAll('#filtros-categoricos input[type="checkbox"]').forEach(cb => {{
                    cb.checked = false;
                }});
                
                // Resetear conteos
                ['sector', 'tipo_conflicto', 'tipo_accion', 'actor_demandante', 'actor_demandado'].forEach(cat => {{
                    const countSpan = document.getElementById('count-' + cat);
                    countSpan.textContent = '0';
                    countSpan.classList.add('empty');
                }});
                
                filtrosActivos = {{
                    sector: [],
                    tipo_conflicto: [],
                    tipo_accion: [],
                    actor_demandante: [],
                    actor_demandado: []
                }};
                filtroCategoricoActivo = false;
                
                console.log('🎛️ Filtros limpiados');
                
                // Si hay filtro temporal, re-aplicarlo sin filtros categóricos
                if (filtroTemporalActivo) {{
                    filtrarMapaPorAño(añoActual, modoAcumulado);
                }} else {{
                    // Restaurar datos originales
                    restaurarDatosOriginales();
                }}
                
                // Ocultar resumen
                document.getElementById('filtros-resumen').classList.remove('activo');
            }}
            
            // 🔍 FUNCIÓN DE BÚSQUEDA POR TÉRMINO
            function buscarTermino(valor) {{
                terminoBusqueda = valor.toLowerCase().trim();
                
                // Mostrar/ocultar botón de limpiar
                const clearBtn = document.getElementById('search-clear');
                clearBtn.style.display = terminoBusqueda ? 'block' : 'none';
                
                console.log('🔍 Buscando:', terminoBusqueda);
                
                // Aplicar filtro (combinado con otros filtros activos)
                if (filtroTemporalActivo) {{
                    filtrarMapaPorAño(añoActual, modoAcumulado);
                }} else {{
                    filtrarDatosPorCategorias();
                }}
                
                // Actualizar contador de resultados
                actualizarContadorBusqueda();
            }}
            
            // Limpiar búsqueda
            function limpiarBusqueda() {{
                terminoBusqueda = '';
                document.getElementById('search-input').value = '';
                document.getElementById('search-clear').style.display = 'none';
                document.getElementById('search-results-count').textContent = '';
                document.getElementById('search-results-count').classList.remove('has-results');
                
                console.log('🔍 Búsqueda limpiada');
                
                // Reaplicar otros filtros
                if (filtroTemporalActivo) {{
                    filtrarMapaPorAño(añoActual, modoAcumulado);
                }} else if (filtroCategoricoActivo) {{
                    filtrarDatosPorCategorias();
                }} else {{
                    restaurarDatosOriginales();
                }}
            }}
            
            // Verificar si una noticia contiene el término buscado
            function noticiaContieneTermino(noticia) {{
                if (!terminoBusqueda) return true;
                
                // Campos donde buscar
                const camposBusqueda = [
                    noticia.titulo || '',
                    noticia.resumen || '',
                    noticia.descripcion || '',
                    noticia.tipo_conflicto || '',
                    noticia.tipo_accion || '',
                    noticia.actor_demandante || '',
                    noticia.actor_demandante_especifico || '',
                    noticia.actor_demandado || '',
                    noticia.actor_demandado_especifico || '',
                    noticia.sector_economico || '',
                    noticia.proyecto_especifico || '',
                    noticia.palabras_clave || ''
                ];
                
                // Concatenar y buscar
                const textoCompleto = camposBusqueda.join(' ').toLowerCase();
                return textoCompleto.includes(terminoBusqueda);
            }}
            
            // Actualizar contador de resultados de búsqueda
            function actualizarContadorBusqueda() {{
                if (!terminoBusqueda) {{
                    document.getElementById('search-results-count').textContent = '';
                    document.getElementById('search-results-count').classList.remove('has-results');
                    return;
                }}
                
                // Contar noticias que coinciden
                let total = 0;
                for (const nivel of ['regiones', 'provincias', 'comunas']) {{
                    for (const territorio in statsData[nivel]) {{
                        total += statsData[nivel][territorio].total_conflictos || 0;
                    }}
                }}
                
                const countEl = document.getElementById('search-results-count');
                if (total > 0) {{
                    countEl.textContent = `✓ ${{total}} resultado${{total !== 1 ? 's' : ''}} encontrado${{total !== 1 ? 's' : ''}}`;
                    countEl.classList.add('has-results');
                }} else {{
                    countEl.textContent = 'Sin resultados para "' + terminoBusqueda + '"';
                    countEl.classList.remove('has-results');
                }}
            }}
            
            // Función para verificar si una noticia pasa los filtros categóricos Y de búsqueda
            function noticiaPassaFiltros(noticia) {{
                // 1. Primero verificar búsqueda por término
                if (terminoBusqueda && !noticiaContieneTermino(noticia)) {{
                    return false;
                }}
                
                // 2. Si no hay filtros categóricos activos, pasa
                if (!filtroCategoricoActivo) return true;
                
                // 3. Verificar cada categoría (OR dentro de categoría, AND entre categorías)
                for (const [categoria, valores] of Object.entries(filtrosActivos)) {{
                    if (valores.length > 0) {{
                        const campoNoticia = mapeoNoticia[categoria];
                        const valorNoticia = noticia[campoNoticia];
                        // La noticia debe tener al menos uno de los valores seleccionados
                        if (!valores.includes(valorNoticia)) {{
                            return false;
                        }}
                    }}
                }}
                return true;
            }}
            
            // Filtrar los datos según los filtros categóricos activos
            function filtrarDatosPorCategorias() {{
                // Crear copia filtrada de statsData
                for (const nivel of ['regiones', 'provincias', 'comunas']) {{
                    for (const territorio in statsDataOriginal[nivel]) {{
                        const datosOriginales = statsDataOriginal[nivel][territorio];
                        const noticiasOriginales = datosOriginales.noticias || [];
                        
                        // Filtrar noticias según criterios
                        const noticiasFiltradas = noticiasOriginales.filter(noticia => noticiaPassaFiltros(noticia));
                        
                        // Actualizar statsData con datos filtrados
                        statsData[nivel][territorio] = {{
                            total_conflictos: noticiasFiltradas.length,
                            noticias: noticiasFiltradas
                        }};
                    }}
                }}
                
                // Actualizar el mapa con los nuevos datos
                actualizarMapaConFiltros();
            }}
            
            // Restaurar los datos originales (sin filtros)
            function restaurarDatosOriginales() {{
                for (const nivel of ['regiones', 'provincias', 'comunas']) {{
                    for (const territorio in statsDataOriginal[nivel]) {{
                        statsData[nivel][territorio] = JSON.parse(JSON.stringify(statsDataOriginal[nivel][territorio]));
                    }}
                }}
                actualizarMapaConFiltros();
            }}
            
            // Actualizar el mapa después de aplicar/limpiar filtros
            function actualizarMapaConFiltros() {{
                // Calcular datos por territorio para actualizar colores
                let datosRegiones = {{}};
                let datosProvincias = {{}};
                let datosComunas = {{}};
                
                // Extraer totales de statsData filtrado
                for (const region in statsData.regiones) {{
                    datosRegiones[region] = statsData.regiones[region].total_conflictos || 0;
                }}
                for (const provincia in statsData.provincias) {{
                    datosProvincias[provincia] = statsData.provincias[provincia].total_conflictos || 0;
                }}
                for (const comuna in statsData.comunas) {{
                    datosComunas[comuna] = statsData.comunas[comuna].total_conflictos || 0;
                }}
                
                // ACTUALIZAR VISUALMENTE LAS CAPAS DEL MAPA (colores)
                if (typeof actualizarCapasVisualmente === 'function') {{
                    actualizarCapasVisualmente(datosRegiones, datosProvincias, datosComunas);
                }}
                
                // Actualizar selector de territorios
                actualizarSelectorTerritorio();
                
                // Si hay un territorio seleccionado, actualizar su info
                const territorioSeleccionado = document.getElementById('territorioSelector').value;
                if (territorioSeleccionado) {{
                    mostrarInfoTerritorio(territorioSeleccionado, nivelActual);
                }}
                
                // Actualizar conteo en el panel
                let totalFiltrado = 0;
                for (const territorio in statsData[nivelActual]) {{
                    totalFiltrado += statsData[nivelActual][territorio].total_conflictos;
                }}
                console.log(`📊 Total conflictos con filtros: ${{totalFiltrado}}`);
            }}
            
            // Mostrar resumen de filtros aplicados
            function mostrarResumenFiltros() {{
                const resumenDiv = document.getElementById('filtros-resumen');
                const filtrosAplicados = [];
                
                if (filtrosActivos.sector.length > 0) {{
                    filtrosAplicados.push(`<strong>Sector:</strong> ${{filtrosActivos.sector.length}} selec.`);
                }}
                if (filtrosActivos.tipo_conflicto.length > 0) {{
                    filtrosAplicados.push(`<strong>Conflicto:</strong> ${{filtrosActivos.tipo_conflicto.length}} selec.`);
                }}
                if (filtrosActivos.tipo_accion.length > 0) {{
                    filtrosAplicados.push(`<strong>Acción:</strong> ${{filtrosActivos.tipo_accion.length}} selec.`);
                }}
                if (filtrosActivos.actor_demandante.length > 0) {{
                    filtrosAplicados.push(`<strong>Demandante:</strong> ${{filtrosActivos.actor_demandante.length}} selec.`);
                }}
                if (filtrosActivos.actor_demandado.length > 0) {{
                    filtrosAplicados.push(`<strong>Demandado:</strong> ${{filtrosActivos.actor_demandado.length}} selec.`);
                }}
                
                if (filtrosAplicados.length > 0) {{
                    // Calcular total filtrado
                    let total = 0;
                    for (const territorio in statsData[nivelActual]) {{
                        total += statsData[nivelActual][territorio].total_conflictos || 0;
                    }}
                    resumenDiv.innerHTML = `${{filtrosAplicados.join(' | ')}}<br><strong>Total: ${{total}} conflictos</strong>`;
                    resumenDiv.classList.add('activo');
                }} else {{
                    resumenDiv.classList.remove('activo');
                }}
            }}
            
            // Inicializar cuando el DOM esté listo
            setTimeout(function() {{
                actualizarSelectorTerritorio();
                poblarFiltrosCategoricos();
                console.log('Sistema inicializado con', Object.keys(statsData).length, 'niveles');
                console.log('🎛️ Filtros disponibles:', filtrosCategoricos);
            }}, 500);
            
            function cambiarNivel() {{
                nivelActual = document.getElementById('nivelSelector').value;
                console.log('Cambiando a nivel:', nivelActual);
                
                // IMPORTANTE: Cambiar la capa del mapa
                if (typeof cambiarCapaMapa === 'function') {{
                    cambiarCapaMapa(nivelActual);
                }}
                
                actualizarSelectorTerritorio();
                
                // Limpiar panel
                document.getElementById('contenido').innerHTML = '<p style="color: #7f8c8d;">Selecciona un territorio del desplegable o haz click en el mapa</p>';
            }}
            
            function actualizarSelectorTerritorio() {{
                const selector = document.getElementById('territorioSelector');
                selector.innerHTML = '<option value="">Selecciona un territorio...</option>';
                
                const territorios = Object.keys(statsData[nivelActual] || {{}});
                console.log('Territorios disponibles:', territorios.length);
                
                territorios.sort().forEach(territorio => {{
                    const option = document.createElement('option');
                    option.value = territorio;
                    option.textContent = territorio;
                    selector.appendChild(option);
                }});
            }}
            
            function mostrarTerritorio() {{
                const territorio = document.getElementById('territorioSelector').value;
                console.log('Mostrando territorio:', territorio, 'nivel:', nivelActual);
                if (territorio) {{
                    mostrarInfoTerritorio(territorio, nivelActual);
                }} else {{
                    document.getElementById('contenido').innerHTML = '<p style="color: #7f8c8d;">Selecciona un territorio del desplegable</p>';
                }}
            }}
            
            function mostrarInfoTerritorio(nombre, nivel) {{
                const stats = statsData[nivel][nombre];
                if (!stats) return;
                
                // Obtener total histórico del backup original
                const statsOriginal = statsDataOriginal[nivel][nombre];
                const totalHistorico = statsOriginal ? statsOriginal.total_conflictos : stats.total_conflictos;
                const totalPeriodo = stats.total_conflictos;
                
                // Construir texto del período
                let textoPeriodo = '';
                if (filtroTemporalActivo) {{
                    if (modoAcumulado) {{
                        textoPeriodo = `${{datosTemporales.año_min}}-${{añoActual}}`;
                    }} else {{
                        textoPeriodo = añoActual.toString();
                    }}
                }}
                
                let html = `
                    <h3 style="color: #2c3e50; margin-top: 0;">${{nombre}}</h3>
                    <p style="font-size: 16px; color: #e74c3c; font-weight: bold; margin-bottom: 5px;">
                        Total conflictos: ${{totalHistorico}}
                    </p>
                `;
                
                // Agregar "Total período" solo si hay filtro temporal activo
                if (filtroTemporalActivo) {{
                    html += `
                        <p style="font-size: 16px; color: #3498db; font-weight: bold; margin-top: 5px; margin-bottom: 5px;">
                            Total período (${{textoPeriodo}}): ${{totalPeriodo}}
                        </p>
                    `;
                }}
                
                html += `
                    <hr style="margin: 15px 0;">
                    <h4 style="color: #34495e;">Noticias Detalladas:</h4>
                `;
                
                const noticias = stats.noticias || [];
                noticias.forEach((noticia, i) => {{
                    // Construir ubicación completa
                    const ubicacion = [
                        noticia.region,
                        noticia.provincia,
                        noticia.comuna,
                        noticia.localidad
                    ].filter(u => u && u !== 'nan' && u !== 'None').join(' → ');
                    
                    html += `
                        <div class="noticia-card">
                            <div class="noticia-title">${{i + 1}}. ${{noticia.titulo || 'Sin título'}}</div>
                            <div class="noticia-date">📅 ${{noticia.fecha || 'Sin fecha'}}</div>
                            
                            <div class="noticia-section">
                                <div class="section-title">Resumen IA:</div>
                                <div class="section-content">${{noticia.resumen || 'Sin resumen'}}</div>
                            </div>
                    `;
                    
                    if (noticia.tipo_conflicto) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">🔴 Tipo de Conflicto:</div>
                                <div class="section-content">${{noticia.tipo_conflicto}}</div>
                                ${{noticia.explicacion_conflicto ? `<div class="section-content" style="font-size: 11px; color: #7f8c8d;">${{noticia.explicacion_conflicto}}</div>` : ''}}
                            </div>
                        `;
                    }}
                    
                    if (noticia.tipo_accion) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">⚡ Tipo de Acción:</div>
                                <div class="section-content">${{noticia.tipo_accion}}</div>
                                ${{noticia.explicacion_accion ? `<div class="section-content" style="font-size: 11px; color: #7f8c8d;">${{noticia.explicacion_accion}}</div>` : ''}}
                            </div>
                        `;
                    }}
                    
                    if (noticia.actor_demandante) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">👥 Actor Demandante:</div>
                                <div class="section-content">${{noticia.actor_demandante}}</div>
                                ${{noticia.explicacion_demandante ? `<div class="section-content" style="font-size: 11px; color: #7f8c8d;">${{noticia.explicacion_demandante}}</div>` : ''}}
                            </div>
                        `;
                    }}
                    
                    if (noticia.actor_demandado) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">🏢 Actor Demandado:</div>
                                <div class="section-content">${{noticia.actor_demandado}}</div>
                                ${{noticia.explicacion_demandado ? `<div class="section-content" style="font-size: 11px; color: #7f8c8d;">${{noticia.explicacion_demandado}}</div>` : ''}}
                            </div>
                        `;
                    }}
                    
                    if (ubicacion) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">📍 Ubicación:</div>
                                <div class="ubicacion">${{ubicacion}}</div>
                            </div>
                        `;
                    }}
                    
                    if (noticia.sector_economico) {{
                        html += `
                            <div class="noticia-section">
                                <div class="section-title">🏭 Sector:</div>
                                <div class="section-content">${{noticia.sector_economico}}</div>
                            </div>
                        `;
                    }}
                    
                    if (noticia.url && noticia.url !== '#') {{
                        html += `
                            <div class="noticia-section">
                                <a href="${{noticia.url}}" target="_blank" style="color: #3498db; text-decoration: none; font-size: 12px;">
                                    🔗 Ver noticia completa
                                </a>
                            </div>
                        `;
                    }}
                    
                    html += `</div>`;
                }});
                
                document.getElementById('contenido').innerHTML = html;
            }}
            
            // ⏱️ FUNCIONES DE LÍNEA DE TIEMPO
            console.log('Datos temporales recibidos:', datosTemporales);
            console.log('Stats data original:', Object.keys(statsData));
            let statsDataOriginal = JSON.parse(JSON.stringify(statsData)); // Backup de datos originales
            
            function generarMarcadoresAño() {{
                const markers = document.getElementById('timeline-markers');
                markers.innerHTML = '';
                
                const rangoAños = datosTemporales.año_max - datosTemporales.año_min;
                const intervalo = rangoAños <= 10 ? 1 : rangoAños <= 25 ? 5 : 10;
                
                for (let año = datosTemporales.año_min; año <= datosTemporales.año_max; año += intervalo) {{
                    const marker = document.createElement('div');
                    marker.className = 'year-marker';
                    marker.textContent = año;
                    markers.appendChild(marker);
                }}
                
                // Añadir último año si no está
                if ((datosTemporales.año_max - datosTemporales.año_min) % intervalo !== 0) {{
                    const marker = document.createElement('div');
                    marker.className = 'year-marker';
                    marker.textContent = datosTemporales.año_max;
                    markers.appendChild(marker);
                }}
            }}
            
            function actualizarAño(año) {{
                añoActual = parseInt(año);
                document.getElementById('año-display').textContent = añoActual;
                document.getElementById('timeline-slider').value = añoActual;
                
                // Calcular conflictos del año
                let total = 0;
                if (modoAcumulado) {{
                    // Sumar todos los años hasta el actual
                    for (let y = datosTemporales.año_min; y <= añoActual; y++) {{
                        if (datosTemporales.datos[y]) {{
                            total += datosTemporales.datos[y].total || 0;
                        }}
                    }}
                }} else {{
                    // Solo el año actual
                    const datosAño = datosTemporales.datos[añoActual];
                    total = datosAño ? (datosAño.total || 0) : 0;
                }}
                
                document.getElementById('conflictos-count').textContent = 
                    total + ' conflicto' + (total !== 1 ? 's' : '');
                
                // Filtrar datos del mapa
                filtrarMapaPorAño(añoActual, modoAcumulado);
            }}
            
            function filtrarMapaPorAño(año, acumulado) {{
                console.log('Filtrando mapa para año:', año, 'Modo:', acumulado ? 'Acumulado' : 'Año único', 'Incluir sin fecha:', incluirSinFecha);
                filtroTemporalActivo = true;
                
                // Obtener datos acumulados por nivel geográfico
                let datosRegiones = {{}};
                let datosProvincias = {{}};
                let datosComunas = {{}};
                let noticiasAcumuladas = {{}};
                
                if (acumulado) {{
                    // Acumular datos desde año_min hasta año actual
                    for (let y = datosTemporales.año_min; y <= año; y++) {{
                        const datosAño = datosTemporales.datos[y];
                        if (!datosAño) continue;
                        
                        // Regiones
                        if (datosAño.por_region) {{
                            Object.keys(datosAño.por_region).forEach(region => {{
                                datosRegiones[region] = (datosRegiones[region] || 0) + datosAño.por_region[region];
                            }});
                        }}
                        
                        // Provincias
                        if (datosAño.por_provincia) {{
                            Object.keys(datosAño.por_provincia).forEach(prov => {{
                                datosProvincias[prov] = (datosProvincias[prov] || 0) + datosAño.por_provincia[prov];
                            }});
                        }}
                        
                        // Comunas
                        if (datosAño.por_comuna) {{
                            Object.keys(datosAño.por_comuna).forEach(comuna => {{
                                datosComunas[comuna] = (datosComunas[comuna] || 0) + datosAño.por_comuna[comuna];
                            }});
                        }}
                        
                        // Acumular noticias
                        if (datosAño.noticias) {{
                            Object.keys(datosAño.noticias).forEach(territorio => {{
                                if (!noticiasAcumuladas[territorio]) {{
                                    noticiasAcumuladas[territorio] = [];
                                }}
                                noticiasAcumuladas[territorio] = noticiasAcumuladas[territorio].concat(datosAño.noticias[territorio]);
                            }});
                        }}
                    }}
                }} else {{
                    // Solo datos del año específico
                    const datosAño = datosTemporales.datos[año];
                    if (datosAño) {{
                        datosRegiones = JSON.parse(JSON.stringify(datosAño.por_region || {{}}));
                        datosProvincias = JSON.parse(JSON.stringify(datosAño.por_provincia || {{}}));
                        datosComunas = JSON.parse(JSON.stringify(datosAño.por_comuna || {{}}));
                        noticiasAcumuladas = JSON.parse(JSON.stringify(datosAño.noticias || {{}}));
                    }}
                }}
                
                // 📌 INCLUIR NOTICIAS SIN FECHA si el checkbox está activado
                if (incluirSinFecha && datosTemporales.sin_fecha) {{
                    const sinFecha = datosTemporales.sin_fecha;
                    console.log('Agregando noticias sin fecha:', sinFecha.total);
                    
                    // Agregar regiones sin fecha
                    if (sinFecha.por_region) {{
                        Object.keys(sinFecha.por_region).forEach(region => {{
                            datosRegiones[region] = (datosRegiones[region] || 0) + sinFecha.por_region[region];
                        }});
                    }}
                    
                    // Agregar provincias sin fecha
                    if (sinFecha.por_provincia) {{
                        Object.keys(sinFecha.por_provincia).forEach(prov => {{
                            datosProvincias[prov] = (datosProvincias[prov] || 0) + sinFecha.por_provincia[prov];
                        }});
                    }}
                    
                    // Agregar comunas sin fecha
                    if (sinFecha.por_comuna) {{
                        Object.keys(sinFecha.por_comuna).forEach(comuna => {{
                            datosComunas[comuna] = (datosComunas[comuna] || 0) + sinFecha.por_comuna[comuna];
                        }});
                    }}
                    
                    // Agregar noticias sin fecha
                    if (sinFecha.noticias) {{
                        Object.keys(sinFecha.noticias).forEach(territorio => {{
                            if (!noticiasAcumuladas[territorio]) {{
                                noticiasAcumuladas[territorio] = [];
                            }}
                            noticiasAcumuladas[territorio] = noticiasAcumuladas[territorio].concat(sinFecha.noticias[territorio]);
                        }});
                    }}
                }}
                
                // Actualizar statsData con los datos filtrados
                Object.keys(statsData).forEach(key => delete statsData[key]);
                
                statsData.regiones = {{}};
                statsData.provincias = {{}};
                statsData.comunas = {{}};
                
                // Filtrar regiones MANTENIENDO TODA LA INFO ORIGINAL + APLICANDO FILTROS CATEGÓRICOS
                Object.keys(statsDataOriginal.regiones || {{}}).forEach(region => {{
                    // Copiar TODO el objeto original
                    statsData.regiones[region] = JSON.parse(JSON.stringify(statsDataOriginal.regiones[region]));
                    
                    // Filtrar las noticias por año Y por categorías
                    if (statsDataOriginal.regiones[region].noticias) {{
                        const noticiasOriginales = statsDataOriginal.regiones[region].noticias;
                        const titulosFiltrados = noticiasAcumuladas[region] ? new Set(noticiasAcumuladas[region].map(n => n.titulo)) : new Set();
                        
                        // Aplicar filtro temporal + filtro categórico
                        statsData.regiones[region].noticias = noticiasOriginales.filter(n => {{
                            const passaTemporal = titulosFiltrados.has(n.titulo);
                            const passaCategorico = noticiaPassaFiltros(n);
                            return passaTemporal && passaCategorico;
                        }});
                        statsData.regiones[region].total_conflictos = statsData.regiones[region].noticias.length;
                    }}
                    
                    // Actualizar conteo en datosRegiones para la visualización
                    datosRegiones[region] = statsData.regiones[region].total_conflictos;
                }});
                
                // Filtrar provincias MANTENIENDO TODA LA INFO ORIGINAL + APLICANDO FILTROS CATEGÓRICOS
                Object.keys(statsDataOriginal.provincias || {{}}).forEach(prov => {{
                    // Copiar TODO el objeto original
                    statsData.provincias[prov] = JSON.parse(JSON.stringify(statsDataOriginal.provincias[prov]));
                    
                    // Filtrar las noticias por año Y por categorías
                    if (statsDataOriginal.provincias[prov].noticias) {{
                        const noticiasOriginales = statsDataOriginal.provincias[prov].noticias;
                        const titulosFiltrados = noticiasAcumuladas[prov] ? new Set(noticiasAcumuladas[prov].map(n => n.titulo)) : new Set();
                        
                        // Aplicar filtro temporal + filtro categórico
                        statsData.provincias[prov].noticias = noticiasOriginales.filter(n => {{
                            const passaTemporal = titulosFiltrados.has(n.titulo);
                            const passaCategorico = noticiaPassaFiltros(n);
                            return passaTemporal && passaCategorico;
                        }});
                        statsData.provincias[prov].total_conflictos = statsData.provincias[prov].noticias.length;
                    }}
                    
                    // Actualizar conteo en datosProvincias para la visualización
                    datosProvincias[prov] = statsData.provincias[prov].total_conflictos;
                }});
                
                // Filtrar comunas MANTENIENDO TODA LA INFO ORIGINAL + APLICANDO FILTROS CATEGÓRICOS
                Object.keys(statsDataOriginal.comunas || {{}}).forEach(comuna => {{
                    // Copiar TODO el objeto original
                    statsData.comunas[comuna] = JSON.parse(JSON.stringify(statsDataOriginal.comunas[comuna]));
                    
                    // Filtrar las noticias por año Y por categorías
                    if (statsDataOriginal.comunas[comuna].noticias) {{
                        const noticiasOriginales = statsDataOriginal.comunas[comuna].noticias;
                        const titulosFiltrados = noticiasAcumuladas[comuna] ? new Set(noticiasAcumuladas[comuna].map(n => n.titulo)) : new Set();
                        
                        // Aplicar filtro temporal + filtro categórico
                        statsData.comunas[comuna].noticias = noticiasOriginales.filter(n => {{
                            const passaTemporal = titulosFiltrados.has(n.titulo);
                            const passaCategorico = noticiaPassaFiltros(n);
                            return passaTemporal && passaCategorico;
                        }});
                        statsData.comunas[comuna].total_conflictos = statsData.comunas[comuna].noticias.length;
                    }}
                    
                    // Actualizar conteo en datosComunas para la visualización
                    datosComunas[comuna] = statsData.comunas[comuna].total_conflictos;
                }});
                
                // ACTUALIZAR VISUALMENTE LAS CAPAS DEL MAPA
                actualizarCapasVisualmente(datosRegiones, datosProvincias, datosComunas);
                
                // Actualizar selector de territorios
                actualizarSelectorTerritorio();
                
                // REFRESCAR EL PANEL LATERAL si hay un territorio seleccionado
                const territorioActual = document.getElementById('territorio-selector').value;
                if (territorioActual && territorioActual !== '') {{
                    // Obtener el nivel actual
                    const nivelActual = nivelGeografico;
                    const datosNivel = nivelActual === 'regiones' ? statsData.regiones : 
                                      nivelActual === 'provincias' ? statsData.provincias : 
                                      statsData.comunas;
                    
                    // Si el territorio actual tiene datos filtrados, actualizar panel
                    if (datosNivel[territorioActual]) {{
                        console.log('🔄 Refrescando panel para:', territorioActual);
                        window.actualizarPanel(territorioActual, nivelActual);
                    }} else {{
                        // El territorio no tiene datos en este año
                        document.getElementById('contenido').innerHTML = 
                            '<p style="color: #7f8c8d; text-align: center; padding: 20px;">Este territorio no tiene conflictos en el año/período seleccionado</p>';
                    }}
                }} else {{
                    // No hay territorio seleccionado
                    const totalDatos = Object.keys(datosRegiones).length + Object.keys(datosProvincias).length + Object.keys(datosComunas).length;
                    if (totalDatos === 0) {{
                        document.getElementById('contenido').innerHTML = 
                            '<p style="color: #7f8c8d; text-align: center; padding: 20px;">No hay conflictos registrados en ' + año + '</p>';
                    }} else {{
                        document.getElementById('contenido').innerHTML = 
                            '<p style="color: #7f8c8d;">Selecciona un territorio en el mapa o usa el selector arriba</p>';
                    }}
                }}
                
                console.log('Mapa filtrado - Regiones:', Object.keys(datosRegiones).length, 
                           'Provincias:', Object.keys(datosProvincias).length,
                           'Comunas:', Object.keys(datosComunas).length);
            }}
            
            // Función para calcular color según umbrales fijos
            function calcularColorPorUmbral(cantidad) {{
                if (cantidad >= 100) return '#F03B20';      // Rojo - Alta (100+)
                if (cantidad >= 50) return '#FEB24C';       // Naranja - Media-Alta (50-99)
                if (cantidad >= 20) return '#FFEDA0';       // Amarillo - Media (20-49)
                if (cantidad > 0) return '#FFFFCC';         // Amarillo claro - Baja (1-19)
                return '#FFFFFF';                            // Blanco - Sin conflictos
            }}
            
            function actualizarCapasVisualmente(datosRegiones, datosProvincias, datosComunas) {{
                console.log('🔄 Actualizando capas visualmente con:', {{
                    regiones: Object.keys(datosRegiones).length,
                    provincias: Object.keys(datosProvincias).length,
                    comunas: Object.keys(datosComunas).length
                }});
                
                let capasVisibles = 0;
                let capasOcultas = 0;
                
                // Función para procesar una capa
                function procesarCapa(capa, datos) {{
                    if (!capa || !capa.eachLayer) return;
                    
                    capa.eachLayer(function(layer) {{
                        if (layer.eachLayer) {{
                            // Es un grupo, iterar recursivamente
                            layer.eachLayer(function(sublayer) {{
                                if (sublayer.feature && sublayer.feature.properties) {{
                                    const nombreNormalizado = sublayer.feature.properties.nombre_normalizado;
                                    const nombreOriginal = sublayer.feature.properties.nombre_original || nombreNormalizado;
                                    const cantidad = datos[nombreNormalizado] || 0;
                                    
                                    if (cantidad > 0) {{
                                        // MOSTRAR con color recalculado
                                        const nuevoColor = calcularColorPorUmbral(cantidad);
                                        sublayer.setStyle({{
                                            fillColor: nuevoColor,
                                            fillOpacity: 0.7,
                                            opacity: 1
                                        }});
                                        if (sublayer._path) {{
                                            sublayer._path.style.display = '';
                                        }}
                                        
                                        // ACTUALIZAR TOOLTIP con formato combinado
                                        if (sublayer.unbindTooltip) {{
                                            sublayer.unbindTooltip();
                                        }}
                                        // Obtener total histórico
                                        const nivel = sublayer.feature.properties.nivel;
                                        const statsOriginal = statsDataOriginal[nivel] && statsDataOriginal[nivel][nombreNormalizado];
                                        const totalHistorico = statsOriginal ? statsOriginal.total_conflictos : cantidad;
                                        // Formato: "Nombre: Total (Período) conflictos"
                                        sublayer.bindTooltip(`${{nombreOriginal}}: ${{totalHistorico}} (${{cantidad}}) conflictos`);
                                        
                                        capasVisibles++;
                                    }} else {{
                                        // OCULTAR
                                        sublayer.setStyle({{
                                            fillOpacity: 0,
                                            opacity: 0
                                        }});
                                        if (sublayer._path) {{
                                            sublayer._path.style.display = 'none';
                                        }}
                                        capasOcultas++;
                                    }}
                                }}
                            }});
                        }} else if (layer.feature && layer.feature.properties) {{
                            const nombreNormalizado = layer.feature.properties.nombre_normalizado;
                            const nombreOriginal = layer.feature.properties.nombre_original || nombreNormalizado;
                            const cantidad = datos[nombreNormalizado] || 0;
                            
                            if (cantidad > 0) {{
                                // MOSTRAR con color recalculado
                                const nuevoColor = calcularColorPorUmbral(cantidad);
                                layer.setStyle({{
                                    fillColor: nuevoColor,
                                    fillOpacity: 0.7,
                                    opacity: 1
                                }});
                                if (layer._path) {{
                                    layer._path.style.display = '';
                                }}
                                
                                // ACTUALIZAR TOOLTIP con formato combinado
                                if (layer.unbindTooltip) {{
                                    layer.unbindTooltip();
                                }}
                                // Obtener total histórico
                                const nivel = layer.feature.properties.nivel;
                                const statsOriginal = statsDataOriginal[nivel] && statsDataOriginal[nivel][nombreNormalizado];
                                const totalHistorico = statsOriginal ? statsOriginal.total_conflictos : cantidad;
                                // Formato: "Nombre: Total (Período) conflictos"
                                layer.bindTooltip(`${{nombreOriginal}}: ${{totalHistorico}} (${{cantidad}}) conflictos`);
                                
                                capasVisibles++;
                            }} else {{
                                // OCULTAR
                                layer.setStyle({{
                                    fillOpacity: 0,
                                    opacity: 0
                                }});
                                if (layer._path) {{
                                    layer._path.style.display = 'none';
                                }}
                                capasOcultas++;
                            }}
                        }}
                    }});
                }}
                
                // Procesar las 3 capas usando las referencias globales
                if (typeof capaRegiones !== 'undefined') {{
                    procesarCapa(capaRegiones, datosRegiones);
                }}
                if (typeof capaProvincias !== 'undefined') {{
                    procesarCapa(capaProvincias, datosProvincias);
                }}
                if (typeof capaComunas !== 'undefined') {{
                    procesarCapa(capaComunas, datosComunas);
                }}
                
                console.log('✅ Actualización visual completa - Visibles:', capasVisibles, '| Ocultas:', capasOcultas);
            }}
            
            function toggleModo() {{
                modoAcumulado = !modoAcumulado;
                const btn = document.getElementById('modo-toggle');
                
                if (modoAcumulado) {{
                    btn.textContent = 'Acumulado';
                    btn.classList.add('acumulado');
                    btn.title = 'Modo acumulado: muestra todos los conflictos hasta el año seleccionado';
                }} else {{
                    btn.textContent = 'Año';
                    btn.classList.remove('acumulado');
                    btn.title = 'Modo año único: muestra solo conflictos del año seleccionado';
                }}
                
                actualizarAño(añoActual);
            }}
            
            function iniciarAnimacion() {{
                if (animacionActiva) return;
                
                animacionActiva = true;
                document.getElementById('btn-play-timeline').style.display = 'none';
                document.getElementById('btn-stop-timeline').style.display = 'inline-block';
                
                intervaloAnimacion = setInterval(function() {{
                    if (añoActual >= datosTemporales.año_max) {{
                        detenerAnimacion();
                        return;
                    }}
                    añoActual++;
                    actualizarAño(añoActual);
                }}, 1500); // 1.5 segundos por año para que se vea bien
            }}
            
            function detenerAnimacion() {{
                animacionActiva = false;
                if (intervaloAnimacion) {{
                    clearInterval(intervaloAnimacion);
                    intervaloAnimacion = null;
                }}
                document.getElementById('btn-play-timeline').style.display = 'inline-block';
                document.getElementById('btn-stop-timeline').style.display = 'none';
            }}
            
            function mostrarTodosLosConflictos() {{
                console.log('📊 Mostrando TODOS los conflictos (sin filtro temporal)');
                
                // Desactivar filtro temporal
                filtroTemporalActivo = false;
                
                // Restaurar datos originales
                statsData = JSON.parse(JSON.stringify(statsDataOriginal));
                
                // Actualizar display
                document.getElementById('año-display').textContent = 'TOTAL';
                
                // Contar total de conflictos
                let totalConflictos = 0;
                Object.keys(statsData.regiones).forEach(region => {{
                    totalConflictos += statsData.regiones[region].total_conflictos || 0;
                }});
                document.getElementById('conflictos-count').textContent = totalConflictos + ' conflictos';
                
                // Actualizar capas visualmente
                actualizarCapasVisualmente();
                
                console.log('✅ Mostrando todos los conflictos:', totalConflictos);
            }}
            
            // Event listeners para la línea de tiempo
            const slider = document.getElementById('timeline-slider');
            const tooltip = document.getElementById('timeline-tooltip');
            
            slider.addEventListener('input', function(e) {{
                detenerAnimacion();
                const año = e.target.value;
                tooltip.textContent = año;
                tooltip.classList.add('show');
                filtroTemporalActivo = true; // Activar flag de filtro temporal
                actualizarAño(año);
            }});
            
            slider.addEventListener('mouseenter', function() {{
                tooltip.classList.add('show');
            }});
            
            slider.addEventListener('mouseleave', function() {{
                tooltip.classList.remove('show');
            }});
            
            slider.addEventListener('mousemove', function(e) {{
                const rect = slider.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                const año = Math.round(datosTemporales.año_min + percent * (datosTemporales.año_max - datosTemporales.año_min));
                tooltip.textContent = año;
                
                // Posicionar tooltip
                const tooltipX = e.clientX - rect.left;
                tooltip.style.left = tooltipX + 'px';
            }});
            
            document.getElementById('btn-play-timeline').addEventListener('click', iniciarAnimacion);
            document.getElementById('btn-stop-timeline').addEventListener('click', detenerAnimacion);
            document.getElementById('modo-toggle').addEventListener('click', toggleModo);
            document.getElementById('btn-total').addEventListener('click', mostrarTodosLosConflictos);
            
            // Inicializar línea de tiempo en ÚLTIMO AÑO con MODO ACUMULADO
            setTimeout(function() {{
                generarMarcadoresAño();
                // Iniciar en el último año disponible con modo acumulado
                añoActual = datosTemporales.año_max;
                modoAcumulado = true;
                document.getElementById('modo-toggle').classList.add('acumulado');
                actualizarAño(datosTemporales.año_max);
                console.log('Línea de tiempo inicializada en año', datosTemporales.año_max, 'modo acumulado');
            }}, 700);
        </script>
        """
        
        mapa.get_root().html.add_child(folium.Element(panel_html))
        
        # Añadir las 3 capas (regiones, provincias, comunas)
        capa_regiones = self._crear_capa_regiones(stats_regiones)
        capa_provincias = self._crear_capa_provincias(stats_provincias)
        capa_comunas = self._crear_capa_comunas(stats_comunas)
        
        # Añadir capas al mapa (solo regiones visible por defecto)
        capa_regiones.add_to(mapa)
        capa_provincias.add_to(mapa)
        capa_comunas.add_to(mapa)
        
        # Obtener el ID único del mapa de Folium
        id_mapa = mapa.get_name()
        
        # Script para manejar cambio de capas y clicks
        self._agregar_script_interactividad(mapa, id_mapa)
        
        # Añadir leyenda con UMBRALES FIJOS
        leyenda_html = """
        <div style="position: fixed; 
                    bottom: 50px; left: 420px; width: 220px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
            <p style="margin: 0 0 10px 0; font-weight: bold;">Intensidad de Conflictos</p>
            <p style="margin: 5px 0;"><span style="background-color: #F03B20; padding: 5px 10px;">█</span> Alta (100+)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FEB24C; padding: 5px 10px;">█</span> Media-Alta (50-99)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FFEDA0; padding: 5px 10px;">█</span> Media (20-49)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FFFFCC; padding: 5px 10px;">█</span> Baja (1-19)</p>
        </div>
        """
        mapa.get_root().html.add_child(folium.Element(leyenda_html))
        
        # Guardar si se especifica ruta
        if output_path:
            mapa.save(output_path)
            logger.info(f"Mapa unificado guardado en: {output_path}")
        
        return mapa
    
    def _crear_capa_regiones(self, stats: Dict) -> folium.FeatureGroup:
        """Crea capa de regiones con FeatureGroup y eventos de click"""
        capa = folium.FeatureGroup(name='regiones_layer')
        
        if not os.path.exists(self.regiones_geojson):
            logger.warning(f"No se encontró GeoJSON de regiones: {self.regiones_geojson}")
            return capa
        
        with open(self.regiones_geojson, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        max_conflictos = max([s['total_conflictos'] for s in stats.values()]) if stats else 1
        
        for feature in geojson_data['features']:
            region_nombre_geojson = feature['properties'].get('Region', '')
            
            # Corregir encoding antes de normalizar
            region_nombre_corregido = region_nombre_geojson
            try:
                if 'Ã' in region_nombre_geojson or 'Â' in region_nombre_geojson:
                    region_nombre_corregido = region_nombre_geojson.encode('latin-1').decode('utf-8')
            except:
                pass
            
            region_nombre_normalizado = self.normalizar_nombre_geografico(region_nombre_geojson, nivel='regiones')
            
            # Debug: Log para regiones problemáticas
            if 'metropolitana' in region_nombre_geojson.lower() or 'ohiggins' in region_nombre_geojson.lower():
                logger.info(f"🔍 DEBUG Región GeoJSON: '{region_nombre_geojson}' → Normalizado: '{region_nombre_normalizado}'")
                logger.info(f"   ¿Existe en stats? {region_nombre_normalizado in stats}")
                if stats:
                    logger.info(f"   Stats disponibles: {list(stats.keys())[:5]}")
            
            if region_nombre_normalizado in stats:
                cantidad = stats[region_nombre_normalizado]['total_conflictos']
                color = self.calcular_intensidad_color(cantidad, max_conflictos)
                
                # Agregar el nombre normalizado y original a las propiedades
                feature['properties']['nombre_normalizado'] = region_nombre_normalizado
                feature['properties']['nombre_original'] = region_nombre_geojson
                feature['properties']['nivel'] = 'regiones'
                
                # Crear GeoJson con evento onclick (SIN tooltip)
                geojson = folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': '#2c3e50',
                        'weight': 1,
                        'fillOpacity': 0.7
                    },
                    tooltip=None  # Deshabilitar tooltip de Folium
                )
                
                # Añadir evento de click mediante JavaScript
                geojson.add_child(folium.Element(f"""
                    <script>
                    (function() {{
                        var layer = arguments[0];
                        layer.on('click', function(e) {{
                            console.log('🖱️ Click en región:', '{region_nombre_normalizado}');
                            if (typeof window.actualizarPanel === 'function') {{
                                window.actualizarPanel('{region_nombre_normalizado}', 'regiones');
                            }} else {{
                                console.error('❌ window.actualizarPanel no está definida');
                            }}
                            e.originalEvent.stopPropagation();
                        }});
                    }})(this._layers[Object.keys(this._layers)[0]]);
                    </script>
                """))
                
                geojson.add_to(capa)
        
        return capa
    
    def _crear_capa_provincias(self, stats: Dict) -> folium.FeatureGroup:
        """Crea capa de provincias con FeatureGroup y eventos de click"""
        capa = folium.FeatureGroup(name='provincias_layer')
        
        if not os.path.exists(self.provincias_geojson):
            logger.warning(f"No se encontró GeoJSON de provincias: {self.provincias_geojson}")
            return capa
        
        with open(self.provincias_geojson, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        max_conflictos = max([s['total_conflictos'] for s in stats.values()]) if stats else 1
        
        for feature in geojson_data['features']:
            # El GeoJSON de provincias usa 'NOM_PROV' como clave
            provincia_nombre_geojson = feature['properties'].get('NOM_PROV', feature['properties'].get('provincia', feature['properties'].get('Provincia', '')))
            
            # Corregir encoding antes de normalizar
            provincia_nombre_corregido = provincia_nombre_geojson
            try:
                if 'Ã' in provincia_nombre_geojson or 'Â' in provincia_nombre_geojson:
                    provincia_nombre_corregido = provincia_nombre_geojson.encode('latin-1').decode('utf-8')
            except:
                pass
            
            provincia_nombre_normalizado = self.normalizar_nombre_geografico(provincia_nombre_geojson, nivel='provincias')
            
            if provincia_nombre_normalizado in stats:
                cantidad = stats[provincia_nombre_normalizado]['total_conflictos']
                color = self.calcular_intensidad_color(cantidad, max_conflictos)
                
                # Agregar el nombre normalizado y original a las propiedades
                feature['properties']['nombre_normalizado'] = provincia_nombre_normalizado
                feature['properties']['nombre_original'] = provincia_nombre_geojson
                feature['properties']['nivel'] = 'provincias'
                
                geojson = folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': 'gray',
                        'weight': 0.5,
                        'fillOpacity': 0.7
                    },
                    tooltip=None  # Deshabilitar tooltip de Folium
                )
                
                # Añadir evento de click
                geojson.add_child(folium.Element(f"""
                    <script>
                    (function() {{
                        var layer = arguments[0];
                        layer.on('click', function(e) {{
                            console.log('🖱️ Click en provincia:', '{provincia_nombre_normalizado}');
                            if (typeof window.actualizarPanel === 'function') {{
                                console.log('🔍 Función actualizarPanel existe');
                                window.actualizarPanel('{provincia_nombre_normalizado}', 'provincias');
                            }} else {{
                                console.error('❌ window.actualizarPanel no está definida');
                            }}
                            e.originalEvent.stopPropagation();
                        }});
                    }})(this._layers[Object.keys(this._layers)[0]]);
                    </script>
                """))
                
                geojson.add_to(capa)
        
        return capa
    
    def _crear_capa_comunas(self, stats: Dict) -> folium.FeatureGroup:
        """Crea capa de comunas con FeatureGroup"""
        capa = folium.FeatureGroup(name='comunas_layer')
        
        if not os.path.exists(self.comunas_geojson):
            logger.warning(f"No se encontró GeoJSON de comunas: {self.comunas_geojson}")
            return capa
        
        with open(self.comunas_geojson, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        max_conflictos = max([s['total_conflictos'] for s in stats.values()]) if stats else 1
        
        for feature in geojson_data['features']:
            comuna_nombre_geojson = feature['properties'].get('NOM_COMUNA', feature['properties'].get('Comuna', ''))
            
            # Corregir encoding antes de normalizar
            comuna_nombre_corregido = comuna_nombre_geojson
            try:
                if 'Ã' in comuna_nombre_geojson or 'Â' in comuna_nombre_geojson:
                    comuna_nombre_corregido = comuna_nombre_geojson.encode('latin-1').decode('utf-8')
            except:
                pass
            
            comuna_nombre_normalizado = self.normalizar_nombre_geografico(comuna_nombre_geojson, nivel='comunas')
            
            if comuna_nombre_normalizado in stats:
                cantidad = stats[comuna_nombre_normalizado]['total_conflictos']
                color = self.calcular_intensidad_color(cantidad, max_conflictos)
                
                # Agregar el nombre normalizado y original a las propiedades
                feature['properties']['nombre_normalizado'] = comuna_nombre_normalizado
                feature['properties']['nombre_original'] = comuna_nombre_geojson
                feature['properties']['nivel'] = 'comunas'
                
                geojson = folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 0.3,
                        'fillOpacity': 0.7
                    },
                    tooltip=None  # Deshabilitar tooltip de Folium
                )
                
                # Añadir evento de click
                geojson.add_child(folium.Element(f"""
                    <script>
                    (function() {{
                        var layer = arguments[0];
                        layer.on('click', function(e) {{
                            console.log('🖱️ Click en comuna:', '{comuna_nombre_normalizado}');
                            if (typeof window.actualizarPanel === 'function') {{
                                window.actualizarPanel('{comuna_nombre_normalizado}', 'comunas');
                            }} else {{
                                console.error('❌ window.actualizarPanel no está definida');
                            }}
                            e.originalEvent.stopPropagation();
                        }});
                    }})(this._layers[Object.keys(this._layers)[0]]);
                    </script>
                """))
                
                geojson.add_to(capa)
        
        return capa
    
    def _agregar_script_interactividad(self, mapa: folium.Map, id_mapa: str):
        """Añade script para manejar cambio de capas buscándolas por iteración en el mapa"""
        script = f"""
        <script>
            // Variables globales para las capas (deben estar en scope global)
            var capasGlobales = {{
                'regiones': null,
                'provincias': null,
                'comunas': null
            }};
            
            // Referencia al mapa usando el ID específico de Folium
            var mapaRef = null;
            
            // Función para actualizar el panel lateral cuando se hace click en el mapa
            window.actualizarPanel = function(nombreTerritorio, nivel) {{
                console.log('📍 Click en mapa:', nombreTerritorio, 'nivel:', nivel);
                
                // Actualizar el selector de nivel si es diferente
                const nivelSelector = document.getElementById('nivelSelector');
                if (nivelSelector && nivelSelector.value !== nivel) {{
                    nivelSelector.value = nivel;
                    cambiarNivel();  // Esto actualizará el selector de territorio
                }}
                
                // Actualizar el selector de territorio
                const territorioSelector = document.getElementById('territorioSelector');
                if (territorioSelector) {{
                    territorioSelector.value = nombreTerritorio;
                }}
                
                // Mostrar la información del territorio
                if (typeof mostrarInfoTerritorio === 'function') {{
                    mostrarInfoTerritorio(nombreTerritorio, nivel);
                }} else {{
                    console.error('❌ Función mostrarInfoTerritorio no está definida');
                }}
            }};
            
            // Función para cambiar la capa visible (debe estar en scope global)
            function cambiarCapaMapa(nivel) {{
                console.log('🔄 Cambiando a nivel:', nivel);
                console.log('   Capas disponibles:', {{
                    regiones: !!capasGlobales.regiones,
                    provincias: !!capasGlobales.provincias,
                    comunas: !!capasGlobales.comunas
                }});
                
                // Verificar que el mapa existe
                if (!mapaRef) {{
                    console.error('❌ ERROR: mapaRef no está definido');
                    return;
                }}
                
                // Guardar posición actual
                var centro = mapaRef.getCenter();
                var zoom = mapaRef.getZoom();
                
                // Ocultar todas las capas
                console.log('   🔒 Ocultando todas las capas...');
                if (capasGlobales.regiones) {{
                    mapaRef.removeLayer(capasGlobales.regiones);
                    console.log('      - Regiones ocultadas');
                }}
                if (capasGlobales.provincias) {{
                    mapaRef.removeLayer(capasGlobales.provincias);
                    console.log('      - Provincias ocultadas');
                }}
                if (capasGlobales.comunas) {{
                    mapaRef.removeLayer(capasGlobales.comunas);
                    console.log('      - Comunas ocultadas');
                }}
                
                // Mostrar la capa seleccionada
                console.log('   👁️  Mostrando capa:', nivel);
                if (nivel === 'regiones' && capasGlobales.regiones) {{
                    mapaRef.addLayer(capasGlobales.regiones);
                    console.log('   ✅ Regiones mostradas');
                }} else if (nivel === 'provincias' && capasGlobales.provincias) {{
                    mapaRef.addLayer(capasGlobales.provincias);
                    console.log('   ✅ Provincias mostradas');
                }} else if (nivel === 'comunas' && capasGlobales.comunas) {{
                    mapaRef.addLayer(capasGlobales.comunas);
                    console.log('   ✅ Comunas mostradas');
                }} else {{
                    console.error('   ❌ No se pudo mostrar la capa:', nivel);
                }}
                
                // Restaurar posición
                setTimeout(function() {{
                    mapaRef.setView(centro, zoom);
                    console.log('   ✅ Posición restaurada');
                }}, 100);
            }}
            
            // Esperar a que el DOM y el mapa estén completamente cargados
            window.addEventListener('load', function() {{
                // Esperar un poco más para asegurar que Folium haya inicializado todo
                setTimeout(function() {{
                    console.log('🔍 Inicializando sistema de capas...');
                    
                    // Obtener referencia al mapa usando el ID específico de Folium
                    mapaRef = {id_mapa};
                    
                    // Verificar que el mapa existe
                    if (!mapaRef) {{
                        console.error('❌ ERROR: No se pudo obtener referencia al mapa');
                        return;
                    }}
                    
                    console.log('✅ Mapa encontrado, inicializando capas...');
                    console.log('🔍 Buscando capas en el mapa...');
                    
                    // Buscar las capas iterando sobre todas las capas del mapa
                    // Los FeatureGroup contienen las capas GeoJSON como hijos
                    var layerGroups = [];
                    
                    mapaRef.eachLayer(function(layer) {{
                        // Verificar si la capa es un LayerGroup (FeatureGroup)
                        if (layer instanceof L.LayerGroup) {{
                            // Contar cuántas subcapas tiene
                            var numSubcapas = 0;
                            layer.eachLayer(function() {{ numSubcapas++; }});
                            
                            console.log('📦 LayerGroup encontrado con', numSubcapas, 'subcapas');
                            
                            // Guardar el LayerGroup con su número de subcapas
                            layerGroups.push({{
                                layer: layer,
                                count: numSubcapas
                            }});
                        }}
                    }});
                    
                    // Ordenar por número de subcapas (de menor a mayor)
                    layerGroups.sort(function(a, b) {{ return a.count - b.count; }});
                    
                    console.log('🔍 LayerGroups ordenados por tamaño:', layerGroups.map(function(lg) {{ return lg.count; }}));
                    
                    // Filtrar solo los grupos con más de 5 subcapas (ignorar grupos pequeños/vacíos)
                    var gruposRelevantes = layerGroups.filter(function(lg) {{ return lg.count > 5; }});
                    
                    console.log('🔍 Grupos relevantes (>5 subcapas):', gruposRelevantes.map(function(lg) {{ return lg.count; }}));
                    
                    // Asignar las 3 capas más grandes como comunas, provincias y regiones
                    // Esperamos: provincias (~10-29), regiones (~16), comunas (~67-72)
                    if (gruposRelevantes.length >= 3) {{
                        // El más grande = comunas
                        capasGlobales.comunas = gruposRelevantes[gruposRelevantes.length - 1].layer;
                        console.log('✅ Capa comunas asignada (', gruposRelevantes[gruposRelevantes.length - 1].count, 'subcapas)');
                        
                        // El mediano = provincias (INTERCAMBIADO)
                        capasGlobales.provincias = gruposRelevantes[gruposRelevantes.length - 2].layer;
                        console.log('✅ Capa provincias asignada (', gruposRelevantes[gruposRelevantes.length - 2].count, 'subcapas)');
                        
                        // El más pequeño de los 3 = regiones (INTERCAMBIADO)
                        capasGlobales.regiones = gruposRelevantes[gruposRelevantes.length - 3].layer;
                        console.log('✅ Capa regiones asignada (', gruposRelevantes[gruposRelevantes.length - 3].count, 'subcapas)');
                    }} else if (gruposRelevantes.length === 2) {{
                        // Solo hay 2 grupos, asignar el más grande como comunas y el más pequeño como regiones
                        capasGlobales.comunas = gruposRelevantes[1].layer;
                        console.log('✅ Capa comunas asignada (', gruposRelevantes[1].count, 'subcapas)');
                        
                        capasGlobales.regiones = gruposRelevantes[0].layer;
                        console.log('✅ Capa regiones asignada (', gruposRelevantes[0].count, 'subcapas)');
                        
                        console.warn('⚠️ Solo se encontraron 2 grupos relevantes, provincias no disponible');
                    }} else {{
                        console.error('❌ No se encontraron suficientes grupos relevantes');
                    }}
                    
                    // Verificar que se asignaron las 3 capas
                    var capasAsignadas = 0;
                    if (capasGlobales.regiones) capasAsignadas++;
                    if (capasGlobales.provincias) capasAsignadas++;
                    if (capasGlobales.comunas) capasAsignadas++;
                    
                    if (capasAsignadas !== 3) {{
                        console.error('❌ Se esperaban 3 capas pero se asignaron:', capasAsignadas);
                    }}
                    
                    // ✅ CREAR REFERENCIAS GLOBALES PARA LA LÍNEA DE TIEMPO
                    window.capaRegiones = capasGlobales.regiones;
                    window.capaProvincias = capasGlobales.provincias;
                    window.capaComunas = capasGlobales.comunas;
                    console.log('✅ Referencias globales creadas para línea de tiempo');
                    
                    // ✅ INICIALIZAR TOOLTIPS DINÁMICOS CON EVENTOS
                    function inicializarTooltips() {{
                        console.log('🏷️ Inicializando tooltips dinámicos...');
                        
                        const mapTooltip = document.getElementById('map-tooltip');
                        
                        function agregarTooltips(capa, nivel) {{
                            if (!capa || !capa.eachLayer) return;
                            
                            capa.eachLayer(function(layer) {{
                                if (layer.eachLayer) {{
                                    layer.eachLayer(function(sublayer) {{
                                        if (sublayer.feature && sublayer.feature.properties) {{
                                            const nombreOriginal = sublayer.feature.properties.nombre_original;
                                            const nombreNormalizado = sublayer.feature.properties.nombre_normalizado;
                                            
                                            // Evento mouseover
                                            sublayer.on('mouseover', function(e) {{
                                                const stats = statsData[nivel][nombreNormalizado];
                                                const statsOriginal = statsDataOriginal[nivel][nombreNormalizado];
                                                if (stats && nombreOriginal) {{
                                                    const totalHistorico = statsOriginal ? statsOriginal.total_conflictos : stats.total_conflictos;
                                                    const totalPeriodo = stats.total_conflictos || 0;
                                                    
                                                    // Formato: "Nombre: Total (Período) conflictos"
                                                    mapTooltip.textContent = `${{nombreOriginal}}: ${{totalHistorico}} (${{totalPeriodo}}) conflictos`;
                                                    mapTooltip.classList.add('show');
                                                }}
                                            }});
                                            
                                            // Evento mousemove
                                            sublayer.on('mousemove', function(e) {{
                                                mapTooltip.style.left = (e.originalEvent.clientX + 15) + 'px';
                                                mapTooltip.style.top = (e.originalEvent.clientY + 15) + 'px';
                                            }});
                                            
                                            // Evento mouseout
                                            sublayer.on('mouseout', function() {{
                                                mapTooltip.classList.remove('show');
                                            }});
                                        }}
                                    }});
                                }} else if (layer.feature && layer.feature.properties) {{
                                    const nombreOriginal = layer.feature.properties.nombre_original;
                                    const nombreNormalizado = layer.feature.properties.nombre_normalizado;
                                    
                                    // Evento mouseover
                                    layer.on('mouseover', function(e) {{
                                        const stats = statsData[nivel][nombreNormalizado];
                                        const statsOriginal = statsDataOriginal[nivel][nombreNormalizado];
                                        if (stats && nombreOriginal) {{
                                            const totalHistorico = statsOriginal ? statsOriginal.total_conflictos : stats.total_conflictos;
                                            const totalPeriodo = stats.total_conflictos || 0;
                                            
                                            // Formato: "Nombre: Total (Período) conflictos"
                                            mapTooltip.textContent = `${{nombreOriginal}}: ${{totalHistorico}} (${{totalPeriodo}}) conflictos`;
                                            mapTooltip.classList.add('show');
                                        }}
                                    }});
                                    
                                    // Evento mousemove
                                    layer.on('mousemove', function(e) {{
                                        mapTooltip.style.left = (e.originalEvent.clientX + 15) + 'px';
                                        mapTooltip.style.top = (e.originalEvent.clientY + 15) + 'px';
                                    }});
                                    
                                    // Evento mouseout
                                    layer.on('mouseout', function() {{
                                        mapTooltip.classList.remove('show');
                                    }});
                                }}
                            }});
                        }}
                        
                        agregarTooltips(window.capaRegiones, 'regiones');
                        agregarTooltips(window.capaProvincias, 'provincias');
                        agregarTooltips(window.capaComunas, 'comunas');
                        console.log('✅ Tooltips dinámicos inicializados');
                    }}
                    
                    inicializarTooltips();
                    
                    // Ocultar provincias y comunas inicialmente (solo regiones visible)
                    if (capasGlobales.provincias) {{
                        mapaRef.removeLayer(capasGlobales.provincias);
                        console.log('🔒 Provincias ocultadas inicialmente');
                    }}
                    if (capasGlobales.comunas) {{
                        mapaRef.removeLayer(capasGlobales.comunas);
                        console.log('🔒 Comunas ocultadas inicialmente');
                    }}
                    
                    console.log('✅ Sistema de capas inicializado correctamente');
                    console.log('📌 Usa el selector "Nivel Geográfico" para cambiar entre regiones/provincias/comunas');
                    
                    // Agregar eventos de click a todas las features de cada capa
                    console.log('🔗 Agregando eventos de click a las features...');
                    
                    // Eventos para regiones
                    if (capasGlobales.regiones) {{
                        var regionesCount = 0;
                        
                        capasGlobales.regiones.eachLayer(function(layer) {{
                            // layer es un GeoJson, necesitamos iterar sobre sus sublayers
                            if (layer.eachLayer) {{
                                layer.eachLayer(function(sublayer) {{
                                    sublayer.on('click', function(e) {{
                                        console.log('🖱️ Click en región');
                                        
                                        // USAR EL NOMBRE NORMALIZADO QUE VIENE DE PYTHON (ya aplicó el diccionario)
                                        var nombreNormalizado = null;
                                        var nombreOriginal = null;
                                        
                                        // Intentar desde e.target.feature (el más directo)
                                        if (e.target && e.target.feature && e.target.feature.properties) {{
                                            // PRIORIDAD: usar nombre_normalizado que viene de Python
                                            nombreNormalizado = e.target.feature.properties.nombre_normalizado;
                                            nombreOriginal = e.target.feature.properties.Region || 
                                                            e.target.feature.properties.region ||
                                                            e.target.feature.properties.REGION;
                                        }}
                                        
                                        if (nombreNormalizado) {{
                                            console.log('   Nombre original:', nombreOriginal);
                                            console.log('   Nombre normalizado (desde Python):', nombreNormalizado);
                                            
                                            if (typeof window.actualizarPanel === 'function') {{
                                                window.actualizarPanel(nombreNormalizado, 'regiones');
                                            }}
                                        }} else {{
                                            console.error('   ❌ No se pudo recuperar el nombre normalizado de la región');
                                        }}
                                        
                                        L.DomEvent.stopPropagation(e);
                                    }});
                                    regionesCount++;
                                }});
                            }}
                        }});
                        console.log('✅ Eventos agregados a', regionesCount, 'regiones');
                    }}
                    
                    // Eventos para provincias
                    if (capasGlobales.provincias) {{
                        var provinciasCount = 0;
                        
                        capasGlobales.provincias.eachLayer(function(layer) {{
                            // layer es un GeoJson, necesitamos iterar sobre sus sublayers
                            if (layer.eachLayer) {{
                                layer.eachLayer(function(sublayer) {{
                                    sublayer.on('click', function(e) {{
                                        console.log('🖱️ Click en provincia');
                                        
                                        // USAR EL NOMBRE NORMALIZADO QUE VIENE DE PYTHON
                                        var nombreNormalizado = null;
                                        var nombreOriginal = null;
                                        
                                        if (e.target && e.target.feature && e.target.feature.properties) {{
                                            // PRIORIDAD: usar nombre_normalizado que viene de Python
                                            nombreNormalizado = e.target.feature.properties.nombre_normalizado;
                                            nombreOriginal = e.target.feature.properties.NOM_PROV || 
                                                            e.target.feature.properties.provincia ||
                                                            e.target.feature.properties.Provincia;
                                        }}
                                        
                                        if (nombreNormalizado) {{
                                            console.log('   Nombre original:', nombreOriginal);
                                            console.log('   Nombre normalizado (desde Python):', nombreNormalizado);
                                            
                                            if (typeof window.actualizarPanel === 'function') {{
                                                window.actualizarPanel(nombreNormalizado, 'provincias');
                                            }}
                                        }} else {{
                                            console.error('   ❌ No se pudo recuperar el nombre de la provincia');
                                        }}
                                        
                                        L.DomEvent.stopPropagation(e);
                                    }});
                                    provinciasCount++;
                                }});
                            }}
                        }});
                        console.log('✅ Eventos agregados a', provinciasCount, 'provincias');
                    }}
                    
                    // Eventos para comunas
                    if (capasGlobales.comunas) {{
                        var comunasCount = 0;
                        
                        capasGlobales.comunas.eachLayer(function(layer) {{
                            // layer es un GeoJson, necesitamos iterar sobre sus sublayers
                            if (layer.eachLayer) {{
                                layer.eachLayer(function(sublayer) {{
                                    sublayer.on('click', function(e) {{
                                        console.log('🖱️ Click en comuna');
                                        
                                        // USAR EL NOMBRE NORMALIZADO QUE VIENE DE PYTHON
                                        var nombreNormalizado = null;
                                        var nombreOriginal = null;
                                        
                                        if (e.target && e.target.feature && e.target.feature.properties) {{
                                            // PRIORIDAD: usar nombre_normalizado que viene de Python
                                            nombreNormalizado = e.target.feature.properties.nombre_normalizado;
                                            nombreOriginal = e.target.feature.properties.NOM_COMUNA || 
                                                            e.target.feature.properties.Comuna ||
                                                            e.target.feature.properties.comuna;
                                        }}
                                        
                                        if (nombreNormalizado) {{
                                            console.log('   Nombre original:', nombreOriginal);
                                            console.log('   Nombre normalizado (desde Python):', nombreNormalizado);
                                            
                                            if (typeof window.actualizarPanel === 'function') {{
                                                window.actualizarPanel(nombreNormalizado, 'comunas');
                                            }}
                                        }} else {{
                                            console.error('   ❌ No se pudo recuperar el nombre de la comuna');
                                        }}
                                        
                                        L.DomEvent.stopPropagation(e);
                                    }});
                                    comunasCount++;
                                }});
                            }}
                        }});
                        console.log('✅ Eventos agregados a', comunasCount, 'comunas');
                    }}
                }}, 1500);
            }});
        </script>
        """
        mapa.get_root().html.add_child(folium.Element(script))
        
        # Añadir control de capas para cambiar entre tiles (satélite, relieve, etc.)
        folium.LayerControl(
            position='bottomleft',
            collapsed=True
        ).add_to(mapa)
    
    def _preparar_estadisticas_regiones(self, df: pd.DataFrame) -> Dict:
        """Prepara estadísticas por región (reutiliza lógica existente)"""
        stats = {}
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_normalizado = df.copy()
        for col in df_normalizado.columns:
            df_normalizado[col] = _sanitizar_columna(df_normalizado[col])
        
        if 'region' in df_normalizado.columns:
            df_normalizado['region'] = df_normalizado['region'].apply(lambda x: self.normalizar_nombre_geografico(x, nivel='regiones'))
        
        # Debug: Mostrar regiones únicas normalizadas
        regiones_unicas = df_normalizado['region'].dropna().unique()
        logger.info(f"🗺️ Regiones normalizadas en estadísticas: {list(regiones_unicas)[:10]}")
        
        for region in regiones_unicas:
            df_region = df_normalizado[df_normalizado['region'] == region]
            if 'fecha' in df_region.columns:
                df_region = df_region.sort_values('fecha', ascending=False)
            
            noticias_list = []
            for _, row in df_region.iterrows():
                noticias_list.append({
                    'titulo': row.get('titulo', 'Sin título'),
                    'url': row.get('link_noticia', row.get('url', '#')),
                    'fecha': str(row.get('fecha', 'Sin fecha'))[:10],
                    'resumen': row.get('resumen', ''),
                    'tipo_conflicto': row.get('tipo_conflicto', ''),
                    'tipo_accion': row.get('tipo_accion', ''),
                    'explicacion_conflicto': row.get('explicacion_conflicto', ''),
                    'explicacion_accion': row.get('explicacion_accion', ''),
                    'actor_demandante': row.get('actor_demandante', ''),
                    'actor_demandado': row.get('actor_demandado', ''),
                    'explicacion_demandante': row.get('explicacion_demandante', ''),
                    'explicacion_demandado': row.get('explicacion_demandado', ''),
                    'region': row.get('region', ''),
                    'provincia': row.get('provincia', ''),
                    'comuna': row.get('comuna', ''),
                    'localidad': row.get('localidad', ''),
                    'sector_economico': row.get('sector_economico', '')
                })
            
            stats[region] = {
                'total_conflictos': len(df_region),
                'noticias': noticias_list
            }
        
        return stats
    
    def _preparar_estadisticas_provincias(self, df: pd.DataFrame) -> Dict:
        """Prepara estadísticas por provincia"""
        stats = {}
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_normalizado = df.copy()
        for col in df_normalizado.columns:
            df_normalizado[col] = _sanitizar_columna(df_normalizado[col])
        
        if 'provincia' in df_normalizado.columns:
            df_normalizado['provincia'] = df_normalizado['provincia'].apply(lambda x: self.normalizar_nombre_geografico(x, nivel='provincias'))
        
        for provincia in df_normalizado['provincia'].dropna().unique():
            df_provincia = df_normalizado[df_normalizado['provincia'] == provincia]
            if 'fecha' in df_provincia.columns:
                df_provincia = df_provincia.sort_values('fecha', ascending=False)
            
            noticias_list = []
            for _, row in df_provincia.iterrows():
                noticias_list.append({
                    'titulo': row.get('titulo', 'Sin título'),
                    'url': row.get('link_noticia', row.get('url', '#')),
                    'fecha': str(row.get('fecha', 'Sin fecha'))[:10],
                    'resumen': row.get('resumen', ''),
                    'tipo_conflicto': row.get('tipo_conflicto', ''),
                    'tipo_accion': row.get('tipo_accion', ''),
                    'explicacion_conflicto': row.get('explicacion_conflicto', ''),
                    'explicacion_accion': row.get('explicacion_accion', ''),
                    'actor_demandante': row.get('actor_demandante', ''),
                    'actor_demandado': row.get('actor_demandado', ''),
                    'explicacion_demandante': row.get('explicacion_demandante', ''),
                    'explicacion_demandado': row.get('explicacion_demandado', ''),
                    'region': row.get('region', ''),
                    'provincia': row.get('provincia', ''),
                    'comuna': row.get('comuna', ''),
                    'localidad': row.get('localidad', ''),
                    'sector_economico': row.get('sector_economico', '')
                })
            
            stats[provincia] = {
                'total_conflictos': len(df_provincia),
                'noticias': noticias_list
            }
        
        return stats
    
    def _preparar_estadisticas_comunas(self, df: pd.DataFrame) -> Dict:
        """Prepara estadísticas por comuna"""
        stats = {}
        # ✅ SANITIZAR DataFrame para evitar errores con valores no hashables (dict, list)
        df_normalizado = df.copy()
        for col in df_normalizado.columns:
            df_normalizado[col] = _sanitizar_columna(df_normalizado[col])
        
        if 'comuna' in df_normalizado.columns:
            df_normalizado['comuna'] = df_normalizado['comuna'].apply(lambda x: self.normalizar_nombre_geografico(x, nivel='comunas'))
        
        for comuna in df_normalizado['comuna'].dropna().unique():
            df_comuna = df_normalizado[df_normalizado['comuna'] == comuna]
            if 'fecha' in df_comuna.columns:
                df_comuna = df_comuna.sort_values('fecha', ascending=False)
            
            noticias_list = []
            for _, row in df_comuna.iterrows():
                noticias_list.append({
                    'titulo': row.get('titulo', 'Sin título'),
                    'url': row.get('link_noticia', row.get('url', '#')),
                    'fecha': str(row.get('fecha', 'Sin fecha'))[:10],
                    'resumen': row.get('resumen', ''),
                    'tipo_conflicto': row.get('tipo_conflicto', ''),
                    'tipo_accion': row.get('tipo_accion', ''),
                    'explicacion_conflicto': row.get('explicacion_conflicto', ''),
                    'explicacion_accion': row.get('explicacion_accion', ''),
                    'actor_demandante': row.get('actor_demandante', ''),
                    'actor_demandado': row.get('actor_demandado', ''),
                    'explicacion_demandante': row.get('explicacion_demandante', ''),
                    'explicacion_demandado': row.get('explicacion_demandado', ''),
                    'region': row.get('region', ''),
                    'provincia': row.get('provincia', ''),
                    'comuna': row.get('comuna', ''),
                    'localidad': row.get('localidad', ''),
                    'sector_economico': row.get('sector_economico', '')
                })
            
            stats[comuna] = {
                'total_conflictos': len(df_comuna),
                'noticias': noticias_list
            }
        
        return stats
