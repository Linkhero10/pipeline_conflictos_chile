"""
config.py - Configuración y constantes del proyecto FONDECYT

NOTA: Las categorías de clasificación se cargan dinámicamente desde clasificaciones.yaml
Esto garantiza una única fuente de verdad (Single Source of Truth - SSOT)
"""

import os
import yaml
from pathlib import Path

# ============================================================================
# CARGA DINÁMICA DESDE YAML
# ============================================================================

def _cargar_categorias_yaml():
    """
    Carga las categorías de clasificación desde clasificaciones.yaml
    Retorna un diccionario con todas las listas de tipos
    """
    yaml_path = Path(__file__).parent / "clasificaciones.yaml"
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"No se encontró {yaml_path}. El archivo YAML es requerido.")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Extraer listas de nombres de cada categoría
    # IMPORTANTE: Las llaves deben coincidir EXACTAMENTE con clasificaciones.yaml
    tipos_conflicto = [item['nombre'] for item in data.get('tipos_conflicto', [])]
    tipos_accion = [item['nombre'] for item in data.get('tipos_accion', [])]
    actores_demandante = [item['nombre'] for item in data.get('actores_demandante', [])]
    actores_demandado = [item['nombre'] for item in data.get('actores_demandado', [])]
    escalas = [item['nombre'] for item in data.get('escalas_conflicto', [])]
    vinculos = [item['nombre'] for item in data.get('tipos_vinculo_transicion', [])]
    
    # Sectores principales (sin alias)
    sectores = {item['nombre']: item.get('codigo', idx+1) for idx, item in enumerate(data.get('sectores_economico', []))}
    
    # Agregar alias de sectores para compatibilidad
    sectores_alias = data.get('sectores_alias', [])
    alias_nombres = []
    for alias_item in sectores_alias:
        alias = alias_item.get('alias')
        codigo = alias_item.get('codigo')
        if alias and codigo:
            sectores[alias] = codigo
            alias_nombres.append(alias)
    
    motivos = data.get('motivos_exclusion', [])
    
    # Cargar componentes del prompt (SSOT - Single Source of Truth)
    prompt_components = data.get('prompt_components', {})
    
    # Validación: asegurar que se cargaron datos críticos
    if not tipos_conflicto:
        raise ValueError("YAML leído pero sin tipos_conflicto - verificar estructura del archivo")
    if not tipos_accion:
        raise ValueError("YAML leído pero sin tipos_accion - verificar estructura del archivo")
    if not prompt_components:
        raise ValueError("YAML leído pero sin prompt_components - verificar estructura del archivo")
    
    return {
        'tipos_conflicto': tipos_conflicto,
        'tipos_accion': tipos_accion,
        'actores_demandante': actores_demandante,
        'actores_demandado': actores_demandado,
        'escalas': escalas,
        'vinculos': vinculos,
        'sectores': sectores,
        'sectores_alias': alias_nombres,  # Lista de nombres que son alias
        'motivos_exclusion': motivos,
        'prompt_components': prompt_components,
    }

# Cargar categorías al importar el módulo - FAIL FAST (sin fallbacks)
import logging as _logging

try:
    _CATEGORIAS = _cargar_categorias_yaml()
    _YAML_LOADED = True
except Exception as e:
    # FAIL FAST: Sin configuración no hay análisis. No usar fallbacks.
    _logging.critical(f"🔥 ERROR CRÍTICO: No se pudo cargar clasificaciones.yaml: {e}")
    raise SystemExit(f"ERROR FATAL: clasificaciones.yaml es requerido. {e}")

# ============================================================================
# TIPOS DE CLASIFICACIÓN FONDECYT
# NOTA: Las definiciones de "acción contenciosa" y "criterios de exclusión"
# están en clasificaciones.yaml (SSOT - Single Source of Truth)
# Cargados dinámicamente desde clasificaciones.yaml (FAIL FAST - sin fallbacks)
# ============================================================================

# Exportar directamente desde _CATEGORIAS (ya validado que existe)
TIPOS_CONFLICTO = _CATEGORIAS['tipos_conflicto']
TIPOS_ACCION = _CATEGORIAS['tipos_accion']
TIPOS_ACTOR_DEMANDANTE = _CATEGORIAS['actores_demandante']
TIPOS_ACTOR_DEMANDADO = _CATEGORIAS['actores_demandado']
ESCALAS_CONFLICTO = _CATEGORIAS['escalas']
TIPOS_VINCULO_TRANSICION = _CATEGORIAS['vinculos']
TIPOS_SECTOR_ECONOMICO = _CATEGORIAS['sectores']
SECTORES_ALIAS = _CATEGORIAS.get('sectores_alias', [])
PROMPT_COMPONENTS = _CATEGORIAS.get('prompt_components', {})
MOTIVOS_EXCLUSION = _CATEGORIAS.get('motivos_exclusion', [])  # Para prompt dinámico

# Verificar que los alias estén presentes (por compatibilidad)
if TIPOS_SECTOR_ECONOMICO:
    # Verificar que los alias estén presentes (por compatibilidad)
    if "Energía" not in TIPOS_SECTOR_ECONOMICO:
        TIPOS_SECTOR_ECONOMICO["Infraestructura"] = TIPOS_SECTOR_ECONOMICO.get("Infraestructura energética", 5)
    if "Transporte" not in TIPOS_SECTOR_ECONOMICO:
        TIPOS_SECTOR_ECONOMICO["Transporte"] = TIPOS_SECTOR_ECONOMICO.get("Transporte/Electromovilidad", 7)

# ============================================================================
# CLASIFICACIONES ADICIONALES (compatibilidad)
# ============================================================================

REGIONES_CHILE = {
    "Región de Arica y Parinacota": 15,
    "Región de Tarapacá": 1,
    "Región de Antofagasta": 2,
    "Región de Atacama": 3,
    "Región de Coquimbo": 4,
    "Región de Valparaíso": 5,
    "Región Metropolitana de Santiago": 13,
    "Región del Libertador General Bernardo O'Higgins": 6,
    "Región del Maule": 7,
    "Región de Ñuble": 16,
    "Región del Biobío": 8,
    "Región de La Araucanía": 9,
    "Región de Los Ríos": 14,
    "Región de Los Lagos": 10,
    "Región de Aysén del General Carlos Ibáñez del Campo": 11,
    "Región de Magallanes y de la Antártica Chilena": 12
}

# ============================================================================
# CONFIGURACIÓN DE SCRAPING
# ============================================================================

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# Configuración de timeouts
TIMEOUT_REQUESTS = 20
TIMEOUT_API = 120

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2
RETRY_BACKOFF = 2


# ============================================================================
# VALIDACIÓN DE COHERENCIA MAPEOS vs YAML
# ============================================================================

def validar_coherencia_mapeos():
    """
    Valida que los destinos de los mapeos en MapeoTipos existan en las 
    categorías cargadas desde el YAML.
    
    Esta validación detecta desincronización entre mapeos hardcoded y YAML.
    Se ejecuta al inicio para fallar rápido si hay inconsistencias.
    """
    from .mapeos_clasificacion import MapeoTipos
    
    errores = []
    
    # Validar mapeos de conflictos
    for origen, destino in MapeoTipos.CONFLICTOS.items():
        if destino not in TIPOS_CONFLICTO:
            errores.append(f"CONFLICTO: '{origen}' → '{destino}' (NO existe en YAML)")
    
    # Validar mapeos de acciones (None es válido para exclusión Motivo 7)
    for origen, destino in MapeoTipos.ACCIONES.items():
        if destino is not None and destino not in TIPOS_ACCION:
            errores.append(f"ACCIÓN: '{origen}' → '{destino}' (NO existe en YAML)")
    
    # Validar mapeos de demandantes
    for origen, destino in MapeoTipos.DEMANDANTES.items():
        if destino not in TIPOS_ACTOR_DEMANDANTE:
            errores.append(f"DEMANDANTE: '{origen}' → '{destino}' (NO existe en YAML)")
    
    # Validar mapeos de demandados (None es válido para exclusión)
    for origen, destino in MapeoTipos.DEMANDADOS.items():
        if destino is not None and destino not in TIPOS_ACTOR_DEMANDADO:
            errores.append(f"DEMANDADO: '{origen}' → '{destino}' (NO existe en YAML)")
    
    if errores:
        _logging.warning("⚠️ ADVERTENCIAS DE COHERENCIA MAPEOS vs YAML:")
        for error in errores:
            _logging.warning(f"   {error}")
        _logging.warning("   → Considera actualizar mapeos_clasificacion.py o clasificaciones.yaml")
    else:
        _logging.debug("✅ Mapeos coherentes con YAML")
    
    return len(errores) == 0

# Ejecutar validación al cargar (solo warning, no bloquea)
try:
    validar_coherencia_mapeos()
except Exception as e:
    _logging.warning(f"⚠️ No se pudo validar coherencia de mapeos: {e}")
