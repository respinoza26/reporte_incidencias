


# =============================================================================
# EXPORT MANAGER OPTIMIZADO
# =============================================================================

class OptimizedExportManager:
    @staticmethod
    def export_to_excel(incidencias: List[Incidencia], data_manager: OptimizedDataManager) -> Optional[bytes]:
        incidencias_validas = [inc for inc in incidencias if inc.is_valid()]
        if not incidencias_validas:
            return None
        
        # Pre-calcular todos los precios de nocturnidad en una sola pasada
        precios_nocturnidad = {}
        for inc in incidencias_validas:
            key = (inc.categoria, inc.cod_reg_convenio)
            if key not in precios_nocturnidad:
                precios_nocturnidad[key] = data_manager.get_precio_nocturnidad(inc.categoria, inc.cod_reg_convenio)
        
        data = []
        for inc in incidencias_validas:
            key = (inc.categoria, inc.cod_reg_convenio)
            precio_nocturnidad = precios_nocturnidad[key]
            
            data.append({
                'jefe_ope': inc.nombre_jefe_ope,
                'nombre_empleado': inc.trabajador,
                'imputacion_nomina': inc.imputacion_nomina,
                'facturable': inc.facturable,
                'motivo': inc.motivo,
                'codigo_crown_origen': inc.codigo_crown_origen,
                'codigo_crown_destino': inc.codigo_crown_destino,
                'empresa_destino': inc.empresa_destino,
                'incidencia_horas': inc.incidencia_horas,
                'incidencia_precio': inc.incidencia_precio,
                'nocturnidad_horas': inc.nocturnidad_horas,
                'precio_nocturnidad': precio_nocturnidad,
                'traslados_total': inc.traslados_total,
                'coste_hora': inc.coste_hora,
                'fecha': inc.fecha,
                'observaciones': inc.observaciones,
                'centro_preferente': inc.centro_preferente,
                'categoria': inc.categoria,
                'servicio': inc.servicio,
                'cod_reg_convenio': inc.cod_reg_convenio,

            })
        
        df = pd.DataFrame(data)
        
        # Agregar columnas calculadas adicionales para el Excel
        OptimizedExportManager._add_calculated_columns(df, data_manager)
        OptimizedExportManager._add_final_calculations(df)

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        return excel_buffer.getvalue()
    
    @staticmethod
    def _add_calculated_columns(df: pd.DataFrame, data_manager: OptimizedDataManager) -> None:
        """Agrega columnas calculadas basadas en los valores de cuenta_motivos."""
        # Calcular el total de incidencia por fila
        df['total_incidencia'] = df['incidencia_precio'] * df['incidencia_horas']
        
        # Inicializar las columnas calculadas en 0
        df['73_plus_sustitucion'] = 0.0
        df['72_incentivos'] = 0.0 
        df['70_71_festivos'] = 0.0
        df['74_plus_nocturnidad'] = 0.0
        
        # Obtener el mapeo de motivos a cuentas
        try:
            df_motivos = _load_single_sheet('data/maestros.xlsx', 'cuenta_motivos')
        except:
            df_motivos = pd.DataFrame()
        
        if not df_motivos.empty and 'Motivo' in df_motivos.columns and 'desc_cuenta' in df_motivos.columns:
            # Crear diccionario de mapeo motivo -> código de cuenta
            motivo_to_cuenta = {}
            for _, row in df_motivos.iterrows():
                motivo = row['Motivo']
                desc_cuenta = str(row['desc_cuenta'])
                
                # Extraer el código numérico de desc_cuenta
                if '70/71' in desc_cuenta:
                    codigo_cuenta = '70/71'
                elif desc_cuenta.startswith('73'):
                    codigo_cuenta = '73'
                elif desc_cuenta.startswith('72'):
                    codigo_cuenta = '72'
                elif desc_cuenta.startswith('74'):
                    codigo_cuenta = '74'
                else:
                    # Intentar extraer el primer número
                    import re
                    match = re.search(r'(\d+)', desc_cuenta)
                    codigo_cuenta = match.group(1) if match else None
                
                if codigo_cuenta:
                    motivo_to_cuenta[motivo] = codigo_cuenta
            
            # Aplicar el mapeo y calcular valores para cada fila
            for idx, row in df.iterrows():
                motivo = row['motivo']
                cuenta = motivo_to_cuenta.get(motivo, None)
                total_incidencia = row['total_incidencia']
                
                # Asignar a la columna correspondiente según la cuenta
                if cuenta == '73':
                    df.at[idx, '73_plus_sustitucion'] = total_incidencia
                elif cuenta == '72':
                    df.at[idx, '72_incentivos'] = total_incidencia
                elif cuenta in ['70/71', '70', '71']:
                    df.at[idx, '70_71_festivos'] = total_incidencia
                elif cuenta == '74':
                    df.at[idx, '74_plus_nocturnidad'] = 0.0  # Se calcula después
        
        # Eliminar la columna auxiliar total_incidencia
        df.drop('total_incidencia', axis=1, inplace=True)
    
    @staticmethod
    def _add_final_calculations(df: pd.DataFrame) -> None:
        """Agrega los cálculos finales"""
        # 1. Calcular 74_plus_nocturnidad
        if 'precio_nocturnidad' in df.columns and 'nocturnidad_horas' in df.columns:
            df['74_plus_nocturnidad'] = df['precio_nocturnidad'] * df['nocturnidad_horas']
        else:
            df['74_plus_nocturnidad'] = 0.0
        
        # 2. Calcular Coste_total
        required_cols_coste = ['incidencia_horas', 'incidencia_precio', 'nocturnidad_horas', 'precio_nocturnidad', 'traslados_total']
        missing_cols = [col for col in required_cols_coste if col not in df.columns]
        
        if not missing_cols:
            coste_incidencias = df['incidencia_horas'] * df['incidencia_precio']
            coste_nocturnidad = df['nocturnidad_horas'] * df['precio_nocturnidad']
            coste_con_ss = (coste_incidencias + coste_nocturnidad) * 1.3195
            df['Coste_total'] = coste_con_ss + df['traslados_total']
        else:
            df['Coste_total'] = 0.0