"""
FEATURES ÚTILES DE V3
Funcionalidades mejoradas extraídas de la versión 3.0 unificada
"""

import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from tkinter import messagebox
import google.generativeai as genai

# ===== 1. VALIDACIÓN EXHAUSTIVA DE CONFIGURACIÓN =====

def validar_configuracion_exhaustiva(app):
    """
    Validación exhaustiva de todos los parámetros antes de iniciar
    Retorna (bool, str): (es_valido, mensaje_error)
    """
    # 1. Validar API Key
    if not app.api_key.get() or len(app.api_key.get()) < 10:
        return False, "❌ API Key inválida o muy corta"
    
    # 2. Validar archivo Excel
    if not app.archivo_excel.get():
        return False, "❌ Debes seleccionar un archivo Excel"
    
    if not os.path.exists(app.archivo_excel.get()):
        return False, "❌ El archivo seleccionado no existe"
    
    if not app.archivo_excel.get().endswith(('.xlsx', '.xls')):
        return False, "❌ El archivo debe ser formato Excel (.xlsx o .xls)"
    
    # 3. Validar hoja del Excel
    if not app.hoja_excel.get():
        return False, "❌ Debes especificar el nombre de la hoja a procesar"
    
    # 4. Validar rango de procesamiento
    inicio = app.indice_inicio.get()
    fin = app.indice_fin.get()
    
    if inicio < 0:
        return False, "❌ El índice de inicio no puede ser negativo"
    
    if fin < 0 and fin != 0:
        return False, "❌ El índice de fin debe ser 0 (todas) o mayor que 0"
    
    if fin > 0 and fin <= inicio:
        return False, "❌ El índice de fin debe ser mayor que el de inicio"
    
    # 5. Validar provider y modelo
    if not app.provider.get():
        return False, "❌ Debes seleccionar un provider"
    
    if not app.modelo.get():
        return False, "❌ Debes seleccionar un modelo"
    
    # 6. Verificar espacio en disco (al menos 100MB libres)
    try:
        import shutil
        stats = shutil.disk_usage(os.path.dirname(app.archivo_excel.get()) or '.')
        espacio_libre_mb = stats.free / (1024 * 1024)
        if espacio_libre_mb < 100:
            return False, f"❌ Espacio en disco insuficiente ({espacio_libre_mb:.1f} MB). Se requieren al menos 100 MB"
    except Exception as e:
        # No bloquear si no se puede verificar espacio
        pass
    
    # 7. Verificar permisos de escritura
    try:
        test_file = os.path.join(os.path.dirname(app.archivo_excel.get()), '.test_write')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        return False, f"❌ Sin permisos de escritura en el directorio: {e}"
    
    return True, "✅ Configuración válida"


# ===== 2. SISTEMA DE LOGGING CON ROTACIÓN =====

def configurar_logging(log_dir="logs"):
    """
    Configura sistema de logging con rotación automática
    - Archivos de máximo 5MB
    - Mantiene últimos 5 archivos
    - Formato detallado con timestamp
    """
    # Crear directorio de logs si no existe
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Nombre del archivo con fecha
    log_file = os.path.join(log_dir, f'filtrador_{datetime.now().strftime("%Y%m%d")}.log')
    
    # Configurar handler con rotación
    handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # Formato detallado
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Configurar logger
    logger = logging.getLogger('FiltradorIA')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    # También agregar handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.info("=" * 80)
    logger.info("INICIO DE SESIÓN - Filtrador IA FONDECYT")
    logger.info("=" * 80)
    
    return logger


# ===== 3. BOTÓN "PROBAR API" =====

def probar_api(provider, modelo, api_key):
    """
    Prueba la conexión con la API antes de procesar
    Retorna (bool, str): (exitoso, mensaje)
    """
    try:
        if provider == "google":
            # Configurar Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(modelo)
            
            # Hacer una consulta simple
            response = model.generate_content("Di 'OK' si puedes leerme")
            
            if response and response.text:
                return True, f"✅ Conexión exitosa con {modelo}\nRespuesta: {response.text[:50]}"
            else:
                return False, "❌ La API respondió pero sin contenido"
        
        elif provider == "abacus":
            # Para Abacus.ai, usar OpenAI SDK compatible
            from openai import OpenAI
            
            try:
                client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.abacus.ai/v0"
                )
                
                response = client.chat.completions.create(
                    model=modelo,
                    messages=[{"role": "user", "content": "Di 'OK' si puedes leerme"}],
                    max_tokens=10,
                    temperature=0.1
                )
                
                if response and response.choices:
                    return True, f"✅ Conexión exitosa con Abacus.ai\nModelo: {modelo}\nRespuesta: {response.choices[0].message.content}"
                else:
                    return False, "❌ La API respondió pero sin contenido"
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg:
                    return False, f"❌ Error 404: Verifica que el modelo '{modelo}' esté disponible en tu plan de Abacus.ai"
                elif "401" in error_msg or "403" in error_msg:
                    return False, "❌ Error de autenticación: Verifica tu API key de Abacus.ai"
                else:
                    return False, f"❌ Error: {error_msg[:150]}"
        
        elif provider == "openrouter":
            # Para OpenRouter
            from openai import OpenAI
            
            try:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/fondecyt-filtrador",
                        "X-Title": "FONDECYT Filtrador de Conflictos"
                    }
                )
                
                response = client.chat.completions.create(
                    model=modelo,
                    messages=[{"role": "user", "content": "Di 'OK' si puedes leerme"}],
                    max_tokens=10,
                    temperature=0.1
                )
                
                if response and response.choices:
                    return True, f"✅ Conexión exitosa con OpenRouter\nModelo: {modelo}\nRespuesta: {response.choices[0].message.content}"
                else:
                    return False, "❌ La API respondió pero sin contenido"
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg:
                    return False, f"❌ Error 404: Verifica que el modelo '{modelo}' esté disponible en OpenRouter"
                elif "401" in error_msg or "403" in error_msg:
                    return False, "❌ Error de autenticación: Verifica tu API key de OpenRouter"
                else:
                    return False, f"❌ Error: {error_msg[:150]}"
        
        else:
            return False, f"❌ Provider '{provider}' no soportado"
    
    except Exception as e:
        return False, f"❌ Error al probar API: {str(e)}"


# ===== 4. GUARDAR/CARGAR CONFIGURACIÓN AUTOMÁTICA =====

CONFIG_FILE = "config_filtrador.json"

def guardar_configuracion(app):
    """Guarda la configuración actual en un archivo JSON (SIN API KEY por seguridad)"""
    try:
        config = {
            "provider": app.provider.get(),
            "modelo": app.modelo.get(),
            # ⚠️ NUNCA guardar api_key por seguridad - solo en .env
            "archivo_excel": app.archivo_excel.get(),
            "hoja_excel": app.hoja_excel.get(),
            "indice_inicio": app.indice_inicio.get(),
            "indice_fin": app.indice_fin.get(),
            "ultima_actualizacion": datetime.now().isoformat()
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True, "✅ Configuración guardada"
    
    except Exception as e:
        return False, f"❌ Error al guardar configuración: {e}"


def cargar_configuracion(app):
    """Carga la configuración desde el archivo JSON (API key solo desde .env)"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return False, "No hay configuración guardada"
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Aplicar configuración
        if "provider" in config:
            app.provider.set(config["provider"])
        if "modelo" in config:
            app.modelo.set(config["modelo"])
        # ⚠️ NUNCA cargar api_key del JSON - solo desde .env por seguridad
        # La API key ya se cargó desde .env al iniciar la app
        if "archivo_excel" in config:
            app.archivo_excel.set(config["archivo_excel"])
        if "hoja_excel" in config:
            app.hoja_excel.set(config["hoja_excel"])
        if "indice_inicio" in config:
            app.indice_inicio.set(config["indice_inicio"])
        if "indice_fin" in config:
            app.indice_fin.set(config["indice_fin"])
        
        ultima_act = config.get("ultima_actualizacion", "desconocida")
        return True, f"✅ Configuración cargada (última actualización: {ultima_act[:10]})"
    
    except Exception as e:
        return False, f"❌ Error al cargar configuración: {e}"


# ===== 5. SISTEMA DE CLEANUP AL CERRAR =====

def cleanup_al_cerrar(app):
    """
    Limpieza automática al cerrar la aplicación
    - Guarda configuración
    - Cierra logs
    - Libera recursos
    """
    try:
        # 1. Guardar configuración automáticamente
        guardar_configuracion(app)
        
        # 2. Cerrar logger
        logger = logging.getLogger('FiltradorIA')
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        
        # 3. Si hay procesamiento en curso, advertir
        if app.procesando:
            respuesta = messagebox.askyesno(
                "Procesamiento en curso",
                "Hay un procesamiento en curso. ¿Deseas cancelarlo y salir?"
            )
            if not respuesta:
                return False  # No cerrar
        
        # 4. Cerrar ventana
        app.root.destroy()
        return True
    
    except Exception as e:
        print(f"Error en cleanup: {e}")
        app.root.destroy()
        return True
