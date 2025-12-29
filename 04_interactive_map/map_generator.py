"""
Script para generar el mapa interactivo con la base de datos real
Usa: conflictos_transicion_energetica_filtrado.xlsx - Hoja: Datos_filtrados
"""

from map_engine import GeneradorMapas
import os
import sys
import pandas as pd

def main():
    print("🗺️  Generando mapa con base de datos real...")
    print("📂 Archivo: conflictos_transicion_energetica_filtrado.xlsx")
    print("📄 Hoja: Datos_filtrados\n")
    
    # Ruta al archivo Excel - puede pasarse como argumento o buscar en directorio padre
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Buscar archivo en directorio padre por defecto
        default_path = os.path.join(os.path.dirname(__file__), '..', 'conflictos_transicion_energetica_filtrado.xlsx')
        if os.path.exists(default_path):
            excel_path = default_path
        else:
            print("❌ ERROR: Debes proporcionar la ruta al archivo Excel como argumento:")
            print("   python map_generator.py <ruta_al_excel>")
            print("   Ejemplo: python map_generator.py ../mi_archivo_filtrado.xlsx")
            return
    
    # Verificar que existe
    if not os.path.exists(excel_path):
        print(f"❌ ERROR: No se encontró el archivo: {excel_path}")
        return
    
    # Leer la hoja Datos_filtrados
    try:
        df = pd.read_excel(excel_path, sheet_name='Datos_filtrados')
        print(f"✅ Datos cargados: {len(df)} conflictos encontrados")
        print(f"📊 Columnas: {list(df.columns)}\n")
    except Exception as e:
        print(f"❌ ERROR al leer Excel: {e}")
        return
    
    # Crear generador de mapas
    generador = GeneradorMapas()
    
    # Generar mapa unificado con panel
    output_path = "mapa_conflictos_interactivo.html"
    
    try:
        mapa = generador.generar_mapa_unificado_con_panel(
            df=df,
            output_path=output_path
        )
        
        print(f"\n✅ Mapa generado exitosamente: {output_path}")
        print(f"\n📂 Abre el archivo en tu navegador para ver:")
        print(f"   - Todas las regiones/provincias/comunas con conflictos")
        print(f"   - Haz clic en las zonas para ver los conflictos")
        print(f"   - Usa el selector de nivel geográfico")
        print(f"   - Usa el selector de territorio")
        print(f"   - Revisa la consola del navegador (F12) para depuración")
        
    except Exception as e:
        print(f"❌ ERROR al generar mapa: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
