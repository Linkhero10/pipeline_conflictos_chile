#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para recuperar URLs faltantes del cache SQLite y completar el Excel
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys
import os

def recuperar_urls_faltantes():
    """Recupera URLs del cache y completa las filas faltantes en el Excel"""
    
    try:
        # 1. Cargar datos del Excel
        print("📖 Cargando datos del Excel...")
        excel_path = '../conflictos_ambientales_chile.xlsx'
        
        # Cargar hoja de entrada para obtener URLs originales
        df_input = pd.read_excel(excel_path, sheet_name='Limpieza')
        print(f"   Hoja 'Limpieza': {len(df_input)} filas")
        
        # Cargar hoja de salida
        df_output = pd.read_excel(excel_path, sheet_name='Limpieza_enriquecida')
        print(f"   Hoja 'Limpieza_enriquecida': {len(df_output)} filas")
        
        # 2. Conectar al cache SQLite
        print("\n💾 Conectando al cache SQLite...")
        cache_path = 'news_enrichment_cache.db'
        if not os.path.exists(cache_path):
            print(f"❌ Error: Cache no encontrado en {cache_path}")
            return False
            
        conn = sqlite3.connect(cache_path)
        
        # Obtener todas las resoluciones exitosas del cache
        cache_df = pd.read_sql_query("""
            SELECT google_url, direct_url, method, resolved_at 
            FROM url_resolution 
            WHERE success = 1
            ORDER BY resolved_at DESC
        """, conn)
        
        print(f"   Cache: {len(cache_df)} URLs resueltas exitosamente")
        
        # 3. Identificar filas que necesitan completarse (rango 11-110, índices 10-109)
        print("\n🔍 Identificando filas faltantes...")
        start_idx = 10  # Fila 11 (0-indexed)
        end_idx = 110   # Fila 110
        
        processed_range = df_output.iloc[start_idx:end_idx].copy()
        
        # Encontrar filas sin URL_Directa
        missing_mask = processed_range['URL_Directa'].isna() | (processed_range['URL_Directa'] == '')
        missing_indices = processed_range[missing_mask].index.tolist()
        
        print(f"   Filas faltantes: {len(missing_indices)} de 100")
        
        if len(missing_indices) == 0:
            print("✅ No hay filas faltantes. Todas las URLs ya están procesadas.")
            return True
        
        # 4. Recuperar URLs del cache para las filas faltantes
        print(f"\n🔄 Recuperando {len(missing_indices)} URLs del cache...")
        
        urls_recuperadas = 0
        contenido_recuperado = 0
        
        for idx in missing_indices:
            # Obtener URL original de la hoja de entrada
            url_original = df_input.iloc[idx]['enlace']
            
            # Buscar en el cache
            cache_match = cache_df[cache_df['google_url'] == url_original]
            
            if not cache_match.empty:
                # Recuperar datos del cache
                direct_url = cache_match.iloc[0]['direct_url']
                method = cache_match.iloc[0]['method']
                resolved_at = cache_match.iloc[0]['resolved_at']
                
                # Actualizar DataFrame
                df_output.loc[idx, 'URL_Directa'] = direct_url
                df_output.loc[idx, 'Metodo_Resolucion'] = method
                df_output.loc[idx, 'Fecha_Procesamiento'] = resolved_at
                df_output.loc[idx, 'Estado_Procesamiento'] = 'recuperado_cache'
                
                urls_recuperadas += 1
                
                # Intentar obtener contenido del cache de contenido
                try:
                    content_cache = pd.read_sql_query("""
                        SELECT title, content, author, date_iso, word_count, confidence
                        FROM content_cache 
                        WHERE url = ?
                    """, conn, params=[direct_url])
                    
                    if not content_cache.empty:
                        content_row = content_cache.iloc[0]
                        df_output.loc[idx, 'Titulo_Extraido'] = content_row['title'] or ''
                        df_output.loc[idx, 'Contenido_Completo'] = content_row['content'] or ''
                        df_output.loc[idx, 'Autor'] = content_row['author'] or ''
                        df_output.loc[idx, 'Fecha_Extraida_ISO'] = content_row['date_iso'] or ''
                        df_output.loc[idx, 'Palabras'] = content_row['word_count'] or 0
                        df_output.loc[idx, 'Confianza_Extraccion'] = content_row['confidence'] or 0.0
                        contenido_recuperado += 1
                        
                except Exception as e:
                    print(f"   ⚠️ Error recuperando contenido para fila {idx+1}: {e}")
                    
            else:
                print(f"   ⚠️ URL no encontrada en cache para fila {idx+1}")
        
        conn.close()
        
        print(f"   ✅ URLs recuperadas: {urls_recuperadas}")
        print(f"   ✅ Contenidos recuperados: {contenido_recuperado}")
        
        # 5. Guardar resultados actualizados
        if urls_recuperadas > 0:
            print(f"\n💾 Guardando {urls_recuperadas} URLs recuperadas al Excel...")
            
            # Crear backup antes de escribir
            backup_path = f'../conflictos_ambientales_chile_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            print(f"   📋 Creando backup: {backup_path}")
            
            # Copiar archivo original como backup
            import shutil
            shutil.copy2(excel_path, backup_path)
            
            # Escribir datos actualizados
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_output.to_excel(writer, sheet_name='Limpieza_enriquecida', index=False)
            
            print("   ✅ Excel actualizado exitosamente")
            
            # Verificar escritura
            df_verify = pd.read_excel(excel_path, sheet_name='Limpieza_enriquecida')
            verify_range = df_verify.iloc[start_idx:end_idx]
            final_filled = (verify_range['URL_Directa'].notna() & (verify_range['URL_Directa'] != '')).sum()
            
            print(f"\n📊 VERIFICACIÓN FINAL:")
            print(f"   URLs directas en rango 11-110: {final_filled}/100")
            print(f"   Mejora: +{urls_recuperadas} URLs recuperadas")
            
            return True
        else:
            print("❌ No se pudieron recuperar URLs del cache")
            return False
            
    except Exception as e:
        print(f"❌ Error durante la recuperación: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔄 RECUPERADOR DE URLs DESDE CACHE")
    print("=" * 50)
    
    success = recuperar_urls_faltantes()
    
    if success:
        print("\n🎉 ¡Recuperación completada exitosamente!")
    else:
        print("\n❌ La recuperación falló")
        sys.exit(1)
