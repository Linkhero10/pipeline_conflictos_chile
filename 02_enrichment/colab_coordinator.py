"""
Sistema de Coordinación para Enriquecimiento Distribuido en Múltiples Google Colab
==================================================================================

ESTRATEGIA SEGURA: Cada Colab trabaja en un RANGO FIJO de filas y guarda en archivo SEPARADO.
Esto evita race conditions y pérdida de datos en Google Drive.

⚠️ IMPORTANTE: Google Drive NO soporta bloqueos de archivo tradicionales.
   Por eso usamos rangos fijos en lugar de coordinación dinámica.

CONFIGURACIÓN ACTUAL:
- Filas ya procesadas: 0 - 14596 (id_noticia 0 - 14596)
- Filas pendientes: 14597 - 24178 (id_noticia 14597 - 24178)
- Total pendientes: 9582 filas
- Cada worker procesa 2 tandas de 500 = 1000 filas por sesión

CARACTERÍSTICAS:
- Cada worker procesa un rango de filas pre-asignado
- Cada worker guarda en su propio archivo (resultado_colab_N.xlsx)
- Respeta los datos existentes en Datos_enriquecidos (no sobrescribe)
- Al final se fusionan todos los archivos
- Sin race conditions ni pérdida de datos

USO EN COLAB:
```python
# Celda 1: Montar Drive e instalar
from google.colab import drive
drive.mount('/content/drive')
!pip install pandas openpyxl googlenewsdecoder requests beautifulsoup4 trafilatura newspaper3k dateparser

# Celda 2: Ejecutar worker (CAMBIAR --worker-id según tu asignación: 1-10)
!python /content/drive/MyDrive/scraper/sistema_colab_coordinado.py --worker-id 1
```

VER ESTADÍSTICAS:
```python
!python /content/drive/MyDrive/scraper/sistema_colab_coordinado.py --stats
```

FUSIONAR RESULTADOS (ejecutar en UN solo Colab al final):
```python
!python /content/drive/MyDrive/scraper/sistema_colab_coordinado.py --merge
```
"""

import json
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import logging
import argparse
import os
import subprocess
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN - MODIFICAR SEGÚN TU ENTORNO
# ============================================================================

# Ruta base en Google Drive
GOOGLE_DRIVE_PATH = Path("/content/drive/MyDrive/scraper")

# Excel
EXCEL_ORIGINAL = GOOGLE_DRIVE_PATH / "conflictos_transicion_energetica.xlsx"

# Configuración de procesamiento
PRIMERA_FILA_PENDIENTE = 14597  # Primera fila sin procesar (0-indexed)
ULTIMA_FILA = 24178             # Última fila a procesar (0-indexed, id_noticia 24178)
TOTAL_PENDIENTES = ULTIMA_FILA - PRIMERA_FILA_PENDIENTE + 1  # 9582 filas

BATCH_SIZE = 500       # Procesar en tandas de 500 filas
TANDAS_POR_SESION = 2  # 2 tandas de 500 = 1000 filas por sesión
FILAS_POR_WORKER = BATCH_SIZE * TANDAS_POR_SESION  # 1000 filas por worker
SAVE_FREQUENCY = 50    # Guardar cada 50 filas

TOTAL_WORKERS = 10     # Número de workers (ajustar según necesidad)

# Hojas del Excel
INPUT_SHEET = "Datos"
OUTPUT_SHEET = "Datos_enriquecidos"


def calcular_rango(worker_id: int, total_workers: int = TOTAL_WORKERS) -> Tuple[int, int]:
    """
    Calcula el rango de filas que debe procesar cada worker.
    
    Cada worker procesa 1000 filas (2 tandas de 500).
    Los rangos empiezan desde PRIMERA_FILA_PENDIENTE (14597).
    
    Args:
        worker_id: ID del worker (1-indexed: 1, 2, 3, ... 10)
        total_workers: Número total de workers
    
    Returns:
        Tupla (start_row, end_row) - ambos inclusivos (0-indexed)
    
    Ejemplo con 10 workers:
        Worker 1: 14597 - 15596 (1000 filas)
        Worker 2: 15597 - 16596 (1000 filas)
        ...
        Worker 10: 23597 - 24178 (582 filas - el resto)
    """
    # Calcular inicio basado en worker_id
    start = PRIMERA_FILA_PENDIENTE + (worker_id - 1) * FILAS_POR_WORKER
    
    # Calcular fin (no exceder ULTIMA_FILA)
    end = min(start + FILAS_POR_WORKER - 1, ULTIMA_FILA)
    
    # Si el inicio ya excede la última fila, no hay nada que procesar
    if start > ULTIMA_FILA:
        return -1, -1
    
    return start, end


class ColabWorker:
    """
    Worker para enriquecimiento distribuido.
    Cada worker procesa un rango fijo de filas (2 tandas de 500 = 1000) y guarda en archivo separado.
    """
    
    def __init__(self, worker_id: int):
        """
        Inicializa el worker.
        
        Args:
            worker_id: ID del worker (1-indexed: 1, 2, 3, ... 10)
        """
        self.worker_id = worker_id
        
        # Calcular rango asignado
        self.start_row, self.end_row = calcular_rango(worker_id)
        
        if self.start_row == -1:
            raise ValueError(f"Worker {worker_id} no tiene filas asignadas (ya se procesaron todas)")
        
        self.rows_to_process = self.end_row - self.start_row + 1
        
        # Archivos
        self.output_file = GOOGLE_DRIVE_PATH / f"resultado_colab_{worker_id}.xlsx"
        self.progress_file = GOOGLE_DRIVE_PATH / f"progreso_colab_{worker_id}.json"
        self.local_excel = Path("/content/conflictos_transicion_energetica.xlsx")
        self.local_tools = Path("/content/tools")
        
        logger.info(f"✅ Worker {worker_id}/{TOTAL_WORKERS} inicializado")
        logger.info(f"   Rango asignado: filas {self.start_row} - {self.end_row} ({self.rows_to_process} filas)")
        logger.info(f"   IDs de noticia: {self.start_row} - {self.end_row}")
    
    def setup(self):
        """Prepara el entorno de trabajo copiando archivos a memoria local."""
        # Crear carpeta tools
        self.local_tools.mkdir(parents=True, exist_ok=True)
        
        # Copiar Excel a memoria local (más rápido)
        if EXCEL_ORIGINAL.exists():
            shutil.copy(str(EXCEL_ORIGINAL), str(self.local_excel))
            logger.info(f"📋 Excel copiado a {self.local_excel}")
        else:
            raise FileNotFoundError(f"No se encontró: {EXCEL_ORIGINAL}")
        
        # Copiar codigo_final.py
        codigo_final = GOOGLE_DRIVE_PATH / "codigo_final.py"
        if codigo_final.exists():
            shutil.copy(str(codigo_final), str(self.local_tools / "codigo_final.py"))
            logger.info(f"📋 codigo_final.py copiado a {self.local_tools}")
        else:
            raise FileNotFoundError(f"No se encontró: {codigo_final}")
    
    def get_last_processed_row(self) -> int:
        """Obtiene la última fila procesada desde el archivo de progreso."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return data.get('last_row', self.start_row)
            except:
                pass
        return self.start_row
    
    def save_progress(self, last_row: int, urls_processed: int):
        """Guarda el progreso actual."""
        data = {
            'worker_id': self.worker_id,
            'start_row': self.start_row,
            'end_row': self.end_row,
            'last_row': last_row,
            'urls_processed': urls_processed,
            'updated_at': datetime.now().isoformat()
        }
        with open(self.progress_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def run(self):
        """
        Ejecuta el enriquecimiento para el rango asignado.
        Procesa en 2 tandas de 500 filas cada una.
        """
        # Obtener última fila procesada (para continuar si se interrumpió)
        current_row = self.get_last_processed_row()
        
        logger.info(f"🚀 Iniciando desde fila {current_row}")
        logger.info(f"📋 Procesando {TANDAS_POR_SESION} tandas de {BATCH_SIZE} filas cada una")
        
        tanda_num = 0
        
        while current_row <= self.end_row:
            tanda_num += 1
            
            # Calcular límite de esta tanda
            remaining = self.end_row - current_row + 1
            limit = min(BATCH_SIZE, remaining)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 TANDA {tanda_num}/{TANDAS_POR_SESION}")
            logger.info(f"   Filas: {current_row} - {current_row + limit - 1}")
            logger.info(f"   IDs de noticia: {current_row} - {current_row + limit - 1}")
            logger.info(f"{'='*60}")
            
            # Ejecutar codigo_final.py con las hojas correctas
            # IMPORTANTE: --start-from usa 1-indexed en codigo_final.py
            cmd = [
                "python", str(self.local_tools / "codigo_final.py"),
                "--excel", str(self.local_excel),
                "--url-column", "enlace",
                "--input-sheet", INPUT_SHEET,
                "--output-sheet", OUTPUT_SHEET,
                "--start-from", str(current_row + 1),  # +1 porque codigo_final usa 1-indexed
                "--limit", str(limit),
                "--workers", "1",
                "--save-frequency", str(SAVE_FREQUENCY),
                "--use-cache"
            ]
            
            logger.info(f"📝 Comando: {' '.join(cmd)}")
            
            try:
                # Ejecutar sin capturar output para ver progreso en tiempo real
                result = subprocess.run(cmd, timeout=3600)
                if result.returncode != 0:
                    logger.warning(f"⚠️ codigo_final.py terminó con código {result.returncode}")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Timeout en tanda (1 hora), guardando progreso...")
            except Exception as e:
                logger.error(f"❌ Error ejecutando codigo_final.py: {e}")
            
            # Actualizar progreso
            current_row += limit
            
            # Guardar a Drive después de cada tanda
            logger.info(f"💾 Guardando progreso a Drive...")
            shutil.copy(str(self.local_excel), str(self.output_file))
            self.save_progress(current_row, current_row - self.start_row)
            
            logger.info(f"✅ Tanda {tanda_num} completada - Guardado en {self.output_file.name}")
            
            # Mostrar progreso total
            processed = min(current_row - self.start_row, self.rows_to_process)
            progress = processed / self.rows_to_process * 100
            logger.info(f"📊 Progreso Worker {self.worker_id}: {progress:.1f}% ({processed}/{self.rows_to_process})")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Worker {self.worker_id} COMPLETADO!")
        logger.info(f"   Filas procesadas: {self.start_row} - {self.end_row}")
        logger.info(f"   Total: {self.rows_to_process} filas")
        logger.info(f"   Archivo: {self.output_file}")
        logger.info(f"{'='*60}")
        return True
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del worker."""
        last_row = self.get_last_processed_row()
        processed = last_row - self.start_row
        
        return {
            'worker_id': self.worker_id,
            'start_row': self.start_row,
            'end_row': self.end_row,
            'last_row': last_row,
            'processed': processed,
            'total': self.rows_to_process,
            'progress': f"{processed / self.rows_to_process * 100:.1f}%"
        }


def merge_results():
    """
    Fusiona los resultados de todos los workers en un solo archivo.
    Ejecutar DESPUÉS de que todos los workers terminen.
    
    IMPORTANTE: Respeta los datos existentes en Datos_enriquecidos (filas 0-14596).
    Solo fusiona las filas nuevas procesadas por los workers.
    """
    logger.info(f"🔄 Fusionando resultados de {TOTAL_WORKERS} workers...")
    logger.info(f"   Rango a fusionar: filas {PRIMERA_FILA_PENDIENTE} - {ULTIMA_FILA}")
    
    # Cargar Excel original con ambas hojas
    df_datos = pd.read_excel(EXCEL_ORIGINAL, sheet_name=INPUT_SHEET)
    
    try:
        df_enriquecido = pd.read_excel(EXCEL_ORIGINAL, sheet_name=OUTPUT_SHEET)
        logger.info(f"📋 Cargada hoja {OUTPUT_SHEET} existente con {len(df_enriquecido)} filas")
    except:
        df_enriquecido = df_datos.copy()
        logger.info(f"📋 Creando nueva hoja {OUTPUT_SHEET}")
    
    total_rows = len(df_datos)
    
    # Columnas de enriquecimiento
    ENRICH_COLS = [
        'URL_Directa', 'Metodo_Resolucion', 'Titulo_Extraido', 'Fecha_Extraida_ISO',
        'Contenido_Completo', 'Descripcion_Breve', 'Autor', 'Palabras', 'HTTP_Status',
        'Estado_Procesamiento', 'Error_Tipo', 'Hash_Contenido', 'Confianza_Extraccion',
        'Fecha_Procesamiento', 'Intentos_Resolucion', 'Tiempo_Procesamiento', 'Fuente_Dominio'
    ]
    
    # Asegurar que las columnas de enriquecimiento existen
    for col in ENRICH_COLS:
        if col not in df_enriquecido.columns:
            df_enriquecido[col] = None
    
    # Asegurar que df_enriquecido tiene el mismo tamaño que df_datos
    if len(df_enriquecido) < len(df_datos):
        # Expandir con filas vacías
        for i in range(len(df_enriquecido), len(df_datos)):
            new_row = df_datos.iloc[i].to_dict()
            for col in ENRICH_COLS:
                new_row[col] = None
            df_enriquecido = pd.concat([df_enriquecido, pd.DataFrame([new_row])], ignore_index=True)
    
    total_fusionadas = 0
    
    # Fusionar cada archivo de worker
    for worker_id in range(1, TOTAL_WORKERS + 1):
        result_file = GOOGLE_DRIVE_PATH / f"resultado_colab_{worker_id}.xlsx"
        
        if not result_file.exists():
            logger.warning(f"⚠️ No se encontró: {result_file}")
            continue
        
        try:
            # Calcular rango de este worker
            start_row, end_row = calcular_rango(worker_id)
            
            if start_row == -1:
                continue
            
            # Cargar resultados del worker
            df_worker = pd.read_excel(result_file, sheet_name=OUTPUT_SHEET)
            
            # Copiar datos del rango correspondiente (solo las columnas de enriquecimiento)
            for col in ENRICH_COLS:
                if col in df_worker.columns:
                    # Usar .loc para asegurar que se respetan los índices
                    for idx in range(start_row, min(end_row + 1, len(df_worker))):
                        if idx < len(df_enriquecido):
                            valor = df_worker.iloc[idx][col] if idx < len(df_worker) else None
                            if pd.notna(valor) and valor != '':
                                df_enriquecido.at[idx, col] = valor
            
            # Contar procesadas
            rango_worker = df_worker.iloc[start_row:end_row+1] if end_row < len(df_worker) else df_worker.iloc[start_row:]
            procesadas = (rango_worker['URL_Directa'].notna() & (rango_worker['URL_Directa'] != '')).sum()
            total_fusionadas += procesadas
            
            logger.info(f"✅ Worker {worker_id}: {procesadas:,} filas fusionadas (rango {start_row}-{end_row})")
            
        except Exception as e:
            logger.error(f"❌ Error fusionando Worker {worker_id}: {e}")
            import traceback
            traceback.print_exc()
    
    # Guardar archivo fusionado (actualizar el original)
    output_file = EXCEL_ORIGINAL
    
    with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_enriquecido.to_excel(writer, sheet_name=OUTPUT_SHEET, index=False)
    
    # Verificar integridad
    urls_previas = 14597  # Filas 0-14596 ya procesadas
    urls_nuevas = total_fusionadas
    urls_totales = (df_enriquecido['URL_Directa'].notna() & (df_enriquecido['URL_Directa'] != '')).sum()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 FUSIÓN COMPLETADA")
    logger.info(f"{'='*60}")
    logger.info(f"   URLs previas (0-14596): ~{urls_previas:,}")
    logger.info(f"   URLs nuevas fusionadas: {urls_nuevas:,}")
    logger.info(f"   Total URLs en archivo: {urls_totales:,}")
    logger.info(f"   Archivo actualizado: {output_file}")
    logger.info(f"{'='*60}")
    
    return output_file


def show_all_stats():
    """Muestra estadísticas de todos los workers y el progreso general."""
    print("\n" + "=" * 60)
    print("📊 ESTADÍSTICAS DEL ENRIQUECIMIENTO DISTRIBUIDO")
    print("=" * 60)
    print(f"\n📋 CONFIGURACIÓN:")
    print(f"   Filas pendientes: {PRIMERA_FILA_PENDIENTE} - {ULTIMA_FILA}")
    print(f"   Total pendientes: {TOTAL_PENDIENTES:,} filas")
    print(f"   Workers: {TOTAL_WORKERS}")
    print(f"   Filas por worker: {FILAS_POR_WORKER} (2 tandas de {BATCH_SIZE})")
    
    print(f"\n📊 PROGRESO POR WORKER:")
    
    total_processed = 0
    
    for worker_id in range(1, TOTAL_WORKERS + 1):
        start_row, end_row = calcular_rango(worker_id)
        
        if start_row == -1:
            print(f"   Worker {worker_id}: ⏭️ Sin filas asignadas")
            continue
        
        total_worker = end_row - start_row + 1
        progress_file = GOOGLE_DRIVE_PATH / f"progreso_colab_{worker_id}.json"
        
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    last_row = data.get('last_row', start_row)
                    processed = last_row - start_row
                    progress = processed / total_worker * 100 if total_worker > 0 else 0
                    
                    total_processed += processed
                    
                    status = "✅" if processed >= total_worker else "🔄"
                    print(f"   Worker {worker_id}: {status} {progress:.1f}% ({processed:,}/{total_worker:,}) - Filas {start_row}-{end_row}")
            except:
                print(f"   Worker {worker_id}: ❓ Error leyendo progreso - Filas {start_row}-{end_row}")
        else:
            print(f"   Worker {worker_id}: ⏳ No iniciado - Filas {start_row}-{end_row}")
    
    # Progreso total
    overall = total_processed / TOTAL_PENDIENTES * 100 if TOTAL_PENDIENTES > 0 else 0
    print(f"\n{'='*60}")
    print(f"📈 PROGRESO TOTAL: {overall:.1f}% ({total_processed:,}/{TOTAL_PENDIENTES:,})")
    print(f"   Filas restantes: {TOTAL_PENDIENTES - total_processed:,}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Sistema de Enriquecimiento Distribuido para Google Colab',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Ejecutar worker 1
  python sistema_colab_coordinado.py --worker-id 1
  
  # Ver estadísticas
  python sistema_colab_coordinado.py --stats
  
  # Fusionar resultados
  python sistema_colab_coordinado.py --merge

Distribución de filas (10 workers, 9582 filas pendientes):
  Worker 1:  14597 - 15596 (1000 filas)
  Worker 2:  15597 - 16596 (1000 filas)
  Worker 3:  16597 - 17596 (1000 filas)
  Worker 4:  17597 - 18596 (1000 filas)
  Worker 5:  18597 - 19596 (1000 filas)
  Worker 6:  19597 - 20596 (1000 filas)
  Worker 7:  20597 - 21596 (1000 filas)
  Worker 8:  21597 - 22596 (1000 filas)
  Worker 9:  22597 - 23596 (1000 filas)
  Worker 10: 23597 - 24178 (582 filas)
        """
    )
    parser.add_argument('--worker-id', type=int, help='ID del worker (1-10)')
    parser.add_argument('--stats', action='store_true', help='Mostrar estadísticas de todos los workers')
    parser.add_argument('--merge', action='store_true', help='Fusionar resultados de todos los workers')
    
    args = parser.parse_args()
    
    # Mostrar estadísticas
    if args.stats:
        show_all_stats()
        return
    
    # Fusionar resultados
    if args.merge:
        merge_results()
        return
    
    # Ejecutar worker
    if args.worker_id is None:
        # Si no se especifica nada, mostrar ayuda
        parser.print_help()
        print("\n" + "=" * 60)
        show_all_stats()
        return
    
    # Validar worker_id
    if args.worker_id < 1 or args.worker_id > TOTAL_WORKERS:
        parser.error(f"--worker-id debe estar entre 1 y {TOTAL_WORKERS}")
    
    # Crear y ejecutar worker
    try:
        worker = ColabWorker(args.worker_id)
        worker.setup()
        worker.run()
    except ValueError as e:
        logger.error(f"❌ {e}")
        return 1
    except FileNotFoundError as e:
        logger.error(f"❌ Archivo no encontrado: {e}")
        logger.info("💡 Asegúrate de subir los archivos a Google Drive:")
        logger.info(f"   - {EXCEL_ORIGINAL}")
        logger.info(f"   - {GOOGLE_DRIVE_PATH / 'codigo_final.py'}")
        return 1


if __name__ == "__main__":
    main()
