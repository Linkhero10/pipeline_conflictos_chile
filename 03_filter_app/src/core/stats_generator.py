"""
estadisticas.py - Módulo de generación de estadísticas
"""

from datetime import datetime
import pandas as pd


class EstadisticasManager:
    """Genera estadísticas consolidadas del análisis"""
    
    def generar_estadisticas(
        self, 
        writer, 
        df: pd.DataFrame, 
        df_filtradas: pd.DataFrame,
        df_excluidas: pd.DataFrame, 
        df_revision: pd.DataFrame
    ):
        """Genera hoja de estadísticas consolidadas"""
        stats_rows = []
        
        # ═══ SECCIÓN 1: RESUMEN GENERAL ═══
        stats_rows.append({
            'Sección': '═══ 1. RESUMEN GENERAL ═══',
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': '', 'Notas': ''
        })
        
        stats_rows.append({
            'Sección': 'General',
            'Categoría': 'Totales',
            'Métrica': 'Total Procesadas',
            'Valor': len(df),
            'Porcentaje': '100.0%',
            'Notas': 'Base completa'
        })
        
        stats_rows.append({
            'Sección': 'General',
            'Categoría': 'Totales',
            'Métrica': 'Incluidas (Válidas)',
            'Valor': len(df_filtradas),
            'Porcentaje': f"{len(df_filtradas)/len(df)*100:.2f}%" if len(df) > 0 else '0.0%',
            'Notas': 'Cumplen criterios'
        })
        
        stats_rows.append({
            'Sección': 'General',
            'Categoría': 'Totales',
            'Métrica': 'Excluidas',
            'Valor': len(df_excluidas),
            'Porcentaje': f"{len(df_excluidas)/len(df)*100:.2f}%" if len(df) > 0 else '0.0%',
            'Notas': 'No cumplen criterios'
        })
        
        stats_rows.append({
            'Sección': 'General',
            'Categoría': 'Totales',
            'Métrica': 'Revisión Manual',
            'Valor': len(df_revision),
            'Porcentaje': f"{len(df_revision)/len(df)*100:.2f}%" if len(df) > 0 else '0.0%',
            'Notas': 'Requieren validación humana'
        })
        
        stats_rows.append({
            'Sección': 'General',
            'Categoría': 'Metadata',
            'Métrica': 'Fecha Análisis',
            'Valor': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Porcentaje': '',
            'Notas': ''
        })
        
        stats_rows.append({
            'Sección': '', 'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': '', 'Notas': ''
        })
        
        # ═══ SECCIÓN 2: TIPO DE CONFLICTO ═══
        stats_rows.append({
            'Categoría': '═══ TIPO DE CONFLICTO ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0:
            for tipo, count in df_filtradas['tipo_conflicto'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Conflicto',
                    'Métrica': tipo,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 3: DISTRIBUCIÓN POR REGIÓN ═══
        stats_rows.append({
            'Categoría': '═══ DISTRIBUCIÓN POR REGIÓN ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0:
            for region, count in df_filtradas['region'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Región',
                    'Métrica': region,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 4: TIPO DE ACCIÓN ═══
        stats_rows.append({
            'Categoría': '═══ TIPO DE ACCIÓN ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0:
            for accion, count in df_filtradas['tipo_accion'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Acción',
                    'Métrica': accion,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 5: ACTORES DEMANDANTES ═══
        stats_rows.append({
            'Categoría': '═══ ACTORES DEMANDANTES ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0:
            for actor, count in df_filtradas['actor_demandante'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Demandante',
                    'Métrica': actor,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 6: ACTORES DEMANDADOS ═══
        stats_rows.append({
            'Categoría': '═══ ACTORES DEMANDADOS ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0:
            for actor, count in df_filtradas['actor_demandado'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Demandado',
                    'Métrica': actor,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 7: MOTIVOS DE EXCLUSIÓN ═══
        stats_rows.append({
            'Categoría': '═══ MOTIVOS DE EXCLUSIÓN ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_excluidas) > 0:
            for motivo, count in df_excluidas['motivo_exclusion'].value_counts().head(10).items():
                stats_rows.append({
                    'Categoría': 'Exclusión',
                    'Métrica': motivo,
                    'Valor': count,
                    'Porcentaje': f"{count/len(df_excluidas)*100:.1f}%"
                })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 8: DISTRIBUCIÓN TEMPORAL ═══
        stats_rows.append({
            'Categoría': '═══ DISTRIBUCIÓN TEMPORAL ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0 and 'fecha' in df_filtradas.columns:
            df_temp = df_filtradas.copy()
            df_temp['año'] = pd.to_datetime(df_temp['fecha'], errors='coerce').dt.year
            for año, count in df_temp['año'].value_counts().sort_index().items():
                if pd.notna(año):
                    stats_rows.append({
                        'Categoría': 'Temporal',
                        'Métrica': str(int(año)),
                        'Valor': count,
                        'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                    })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 9: SECTORES ECONÓMICOS ═══
        stats_rows.append({
            'Categoría': '═══ SECTORES ECONÓMICOS ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0 and 'sector_economico' in df_filtradas.columns:
            for sector, count in df_filtradas['sector_economico'].value_counts().head(10).items():
                if pd.notna(sector):
                    stats_rows.append({
                        'Categoría': 'Sector',
                        'Métrica': sector,
                        'Valor': count,
                        'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                    })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 10: TONO EMOCIONAL ═══
        stats_rows.append({
            'Categoría': '═══ TONO EMOCIONAL ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if len(df_filtradas) > 0 and 'tono_emocional' in df_filtradas.columns:
            # Extraer palabras clave del tono emocional
            tonos = df_filtradas['tono_emocional'].dropna().str.lower()
            emociones_comunes = ['indignación', 'frustración', 'temor', 'preocupación', 
                                'esperanza', 'determinación', 'desesperanza', 'rabia',
                                'incertidumbre', 'desconfianza']
            for emocion in emociones_comunes:
                count = tonos.str.contains(emocion, na=False).sum()
                if count > 0:
                    stats_rows.append({
                        'Categoría': 'Emoción',
                        'Métrica': emocion.capitalize(),
                        'Valor': count,
                        'Porcentaje': f"{count/len(df_filtradas)*100:.1f}%"
                    })
        
        stats_rows.append({
            'Categoría': '', 'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        # ═══ SECCIÓN 11: MÉTRICAS DE IA ═══
        stats_rows.append({
            'Categoría': '═══ MÉTRICAS DE IA ═══',
            'Métrica': '', 'Valor': '', 'Porcentaje': ''
        })
        
        if 'tokens_totales' in df.columns:
            total_tokens = df['tokens_totales'].sum()
            avg_tokens = df['tokens_totales'].mean()
            stats_rows.append({
                'Categoría': 'Tokens',
                'Métrica': 'Total Tokens Usados',
                'Valor': f"{int(total_tokens):,}",
                'Porcentaje': ''
            })
            stats_rows.append({
                'Categoría': 'Tokens',
                'Métrica': 'Promedio por Noticia',
                'Valor': f"{int(avg_tokens):,}",
                'Porcentaje': ''
            })
        
        if 'costo_estimado_usd' in df.columns:
            costo_total = df['costo_estimado_usd'].sum()
            costo_promedio = df['costo_estimado_usd'].mean()
            stats_rows.append({
                'Categoría': 'Costo',
                'Métrica': 'Costo Total USD',
                'Valor': f"${costo_total:.4f}",
                'Porcentaje': ''
            })
            stats_rows.append({
                'Categoría': 'Costo',
                'Métrica': 'Costo Promedio por Noticia',
                'Valor': f"${costo_promedio:.6f}",
                'Porcentaje': ''
            })
        
        if 'latencia_ms' in df.columns:
            latencia_promedio = df['latencia_ms'].mean()
            latencia_max = df['latencia_ms'].max()
            stats_rows.append({
                'Categoría': 'Latencia',
                'Métrica': 'Latencia Promedio',
                'Valor': f"{latencia_promedio:.0f} ms",
                'Porcentaje': ''
            })
            stats_rows.append({
                'Categoría': 'Latencia',
                'Métrica': 'Latencia Máxima',
                'Valor': f"{latencia_max:.0f} ms",
                'Porcentaje': ''
            })
        
        if 'modelo_usado' in df.columns:
            for modelo, count in df['modelo_usado'].value_counts().items():
                if pd.notna(modelo) and modelo:
                    stats_rows.append({
                        'Categoría': 'Modelo',
                        'Métrica': modelo,
                        'Valor': count,
                        'Porcentaje': f"{count/len(df)*100:.1f}%"
                    })
        
        # Guardar en Excel
        stats_df = pd.DataFrame(stats_rows)
        stats_df.to_excel(writer, sheet_name='Estadisticas', index=False)
