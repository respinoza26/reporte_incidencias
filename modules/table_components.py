


# =============================================================================
# TABLA OPTIMIZADA CON PAGINACIÓN
# =============================================================================

class OptimizedTablaIncidencias:
    ROWS_PER_PAGE = 50  # Paginación para mejorar rendimiento

    def __init__(self, data_manager: OptimizedDataManager):
        self.data_manager = data_manager

    def render(self, selected_jefe: str) -> None:
        st.header("📋 Registro de Incidencias de Personal")
        
        incidencias = st.session_state.incidencias
        
        with st.expander("Añadir Nueva Incidencia"):
            self._render_add_form(selected_jefe)
        
        if incidencias:
            self._render_main_table_paginated(incidencias, selected_jefe)
        else:
            st.info("No hay incidencias registradas")

    def _render_add_form(self, selected_jefe: str) -> None:
        todos_empleados = self.data_manager.get_all_employees()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            trabajador_seleccionado = st.selectbox(
                "Selecciona un trabajador para añadir:",
                [""] + todos_empleados,
                key="select_trabajador_unificado",
            )
            if trabajador_seleccionado:
                empleado_info = self.data_manager.get_empleado_info(trabajador_seleccionado)
                if empleado_info:
                    cod_centro = empleado_info.get('centro_preferente', 'N/A')
                    nombre_centro = empleado_info.get('nombre_centro_preferente', 'N/A')
                    nombre_empresa = empleado_info.get('cod_empresa', 'N/A')
                    st.info(f"Centro: **{cod_centro} - {nombre_centro} - {nombre_empresa}**")

        with col2:
            num_rows = st.number_input(
                "Número de filas:",
                min_value=1,
                value=1,
                step=1,
                key="num_rows_unificado"
            )

        if st.button("➕ Añadir a la tabla"):
            self._add_incidencia(trabajador_seleccionado, num_rows, selected_jefe)
            

    def _add_incidencia(self, nombre_trabajador: str, num_rows: int, selected_jefe: str) -> None:
        if not nombre_trabajador:
            st.warning("⚠️ Por favor, selecciona un trabajador.")
            return

        incidents = st.session_state.incidencias 
        
        for _ in range(num_rows):
            incidencia = Incidencia(imputacion_nomina=st.session_state.selected_imputacion)
            self._actualizar_datos_empleado(incidencia, nombre_trabajador, selected_jefe)
            incidents.append(incidencia)
        
        st.session_state.incidencias = incidents
        st.success(f"Agregado {num_rows} fila(s) para {nombre_trabajador}")
        st.rerun()

    def _actualizar_datos_empleado(self, incidencia: Incidencia, nombre_trabajador: str, jefe: str):
        if nombre_trabajador:
            empleado_info = self.data_manager.get_empleado_info(nombre_trabajador)
            if empleado_info:
                incidencia.trabajador = empleado_info.get('nombre_empleado', '')
                incidencia.categoria = empleado_info.get('cat_empleado', '')
                incidencia.servicio = empleado_info.get('servicio', '')
                incidencia.centro_preferente = empleado_info.get('centro_preferente')
                incidencia.codigo_crown_origen = empleado_info.get('cod_crown')
                incidencia.cod_reg_convenio = empleado_info.get('cod_reg_convenio', '')
                incidencia.coste_hora = empleado_info.get('coste_hora', 0.0)
                empleado_jefe = empleado_info.get('nombre_jefe_ope', '')
                incidencia.nombre_jefe_ope = empleado_jefe if empleado_jefe else "N/A"

    def _render_main_table_paginated(self, incidencias: List[Incidencia], selected_jefe: str) -> None:
        total_incidencias = len(incidencias)
        total_pages = (total_incidencias - 1) // self.ROWS_PER_PAGE + 1 if total_incidencias > 0 else 1
        
        # Controles de paginación
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            current_page = st.number_input(
                f"Página (Total: {total_pages})",
                min_value=1,
                max_value=total_pages,
                value=1,
                key="current_page"
            )
        
        # Calcular índices de la página actual
        start_idx = (current_page - 1) * self.ROWS_PER_PAGE
        end_idx = min(start_idx + self.ROWS_PER_PAGE, total_incidencias)
        
        # Mostrar solo las incidencias de la página actual
        incidencias_pagina = incidencias[start_idx:end_idx]
        
        st.info(f"Mostrando {len(incidencias_pagina)} de {total_incidencias} incidencias (página {current_page} de {total_pages})")
        
        # Renderizar tabla para esta página solamente
        self._render_table_page(incidencias_pagina, selected_jefe, start_idx)

    def _render_table_page(self, incidencias_pagina: List[Incidencia], selected_jefe: str, start_idx: int) -> None:
        # Optimización: Solo actualizar si hay cambios reales
        cache_key = "table_data_hash"
        current_hash = self._get_incidencias_hash(incidencias_pagina)
        
        if cache_key not in st.session_state or st.session_state[cache_key] != current_hash:
            # Pre-calcular todos los precios de nocturnidad en una sola pasada
            precios_nocturnidad = []
            for inc in incidencias_pagina:
                precio = self.data_manager.get_precio_nocturnidad(inc.categoria, inc.cod_reg_convenio)
                precios_nocturnidad.append(precio)
            
            # Crear DataFrame una sola vez
            df_data = []
            for i, inc in enumerate(incidencias_pagina):
                df_data.append(inc.to_dict(precios_nocturnidad[i]))
            
            df = pd.DataFrame(df_data)
            
            # Manejo seguro de fechas
            if not df.empty and 'Fecha' in df.columns:
                df['Fecha'] = df['Fecha'].apply(self._format_fecha_safe)
            
            st.session_state.cached_df = df
            st.session_state[cache_key] = current_hash
        else:
            df = st.session_state.cached_df

        if df.empty:
            st.info("No hay datos para mostrar")
            return

        # Configuración de columnas
        todos_empleados = self.data_manager.get_all_employees()
        centros_crown = self.data_manager.get_centros_crown()

        column_config = {
            "Borrar": st.column_config.CheckboxColumn("Borrar", help="Selecciona las filas a borrar", default=False),
            "Trabajador": st.column_config.SelectboxColumn("Trabajador", options=[""] + todos_empleados, required=True, width="medium"),
            "Imputación Nómina": st.column_config.SelectboxColumn("Imputación Nómina", options=[""] + ["01 Enero", "02 Febrero", "03 Marzo", "04 Abril", "05 Mayo", "06 Junio", "07 Julio", "08 Agosto", "09 Septiembre", "10 Octubre", "11 Noviembre", "12 Diciembre"], required=True, width="small", disabled=True),
            "Facturable": st.column_config.SelectboxColumn("Facturable", options=["", "Sí", "No"], required=True, width="small"),
            "Motivo": st.column_config.SelectboxColumn("Motivo", options=["Absentismo", "Refuerzo", "Eventos", "Festivos y Fines de Semana", "Permiso retribuido", "Puesto pendiente de cubrir","Formación","Otros","Nocturnidad"], required=True, width="small"),
            "Código Crown Origen": st.column_config.NumberColumn("Crown Origen", disabled=True),
            "Código Crown Destino": st.column_config.SelectboxColumn("Crown Destino", options=centros_crown, required=True, width="small"),
            "Empresa Destino": st.column_config.SelectboxColumn("Empresa Destino", options=["", "ALGADI","SMI","DISTEGSA"], width="small"),
            "Incidencia_horas": st.column_config.NumberColumn("Inc. Horas", width="small", min_value=0),
            "Incidencia_precio": st.column_config.NumberColumn("Inc. Precio", width="small", min_value=0, format="€%.2f"),
            "Nocturnidad_horas": st.column_config.NumberColumn("Noct. Horas", width="small", min_value=0),
            "Precio_nocturnidad": st.column_config.NumberColumn("Precio Noct.", width="small", min_value=0, disabled=True, format="€%.2f"),
            "Traslados_total": st.column_config.NumberColumn("Trasl. Total", width="small", min_value=0),
            "Coste hora empresa": st.column_config.NumberColumn("Coste/Hora", disabled=True, width="small", format="€%.2f"),
            "Fecha": st.column_config.TextColumn("Fecha", required=True, width="small", help="Formato: YYYY-MM-DD"),            
            "Observaciones": st.column_config.TextColumn("Observaciones", required=True, width="medium"),
            "Centro preferente": st.column_config.NumberColumn("Centro Pref.", disabled=True),
            "Supervisor de operaciones": st.column_config.TextColumn("Supervisor", disabled=True),
            "Categoría": st.column_config.TextColumn("Categoría", disabled=True, width="small"),
            "Servicio": st.column_config.TextColumn("Servicio", disabled=True, width="small"),
        }

        st.data_editor(
            df,
            column_config=column_config,
            width='stretch',
            num_rows="fixed",
            # height=1000,  # Altura máxima recomendada
            key=f"unificado_editor_page_{st.session_state.get('current_page', 1)}"
)

        # Botón para guardar cambios
        if st.button("💾 Guardar cambios"):
            self._process_page_changes(start_idx, selected_jefe)

    def _format_fecha_safe(self, fecha):
        """Formateo seguro de fechas"""
        if fecha is None or pd.isna(fecha):
            return ""
        if isinstance(fecha, datetime):
            return fecha.strftime('%Y-%m-%d')
        if isinstance(fecha, str):
            try:
                fecha_dt = pd.to_datetime(fecha, errors='coerce')
                if not pd.isna(fecha_dt):
                    return fecha_dt.strftime('%Y-%m-%d')
                else:
                    return fecha
            except:
                return fecha
        return str(fecha)

    def _get_incidencias_hash(self, incidencias: List[Incidencia]) -> str:
        """Genera hash para detectar cambios en las incidencias"""
        data = []
        for inc in incidencias:
            data.append(f"{inc.trabajador}|{inc.motivo}|{inc.fecha}|{inc.incidencia_horas}|{inc.incidencia_precio}")
        return hashlib.md5("||".join(data).encode()).hexdigest()

    def _process_page_changes(self, start_idx: int, selected_jefe: str) -> None:
        """Procesa cambios solo de la página actual"""
        editor_key = f"unificado_editor_page_{st.session_state.get('current_page', 1)}"
        
        if editor_key not in st.session_state:
            return
            
        edited_rows = st.session_state[editor_key]["edited_rows"]
        incidents_to_update = st.session_state.incidencias
        
        for local_row_idx, row_data in edited_rows.items():
            global_row_idx = start_idx + local_row_idx
            
            if global_row_idx >= len(incidents_to_update):
                continue
                
            if row_data.get('Borrar', False):
                continue
                
            incidencia = incidents_to_update[global_row_idx]
            
            if "Trabajador" in row_data and row_data["Trabajador"]:
                self._actualizar_datos_empleado(incidencia, row_data["Trabajador"], selected_jefe)
            
            # Mapeo de campos
            attr_map = {
                "Imputación Nómina": "imputacion_nomina",
                "Facturable": "facturable",
                "Motivo": "motivo",
                "Código Crown Destino": "codigo_crown_destino",
                "Empresa Destino": "empresa_destino",
                "Incidencia_horas": "incidencia_horas",
                "Incidencia_precio": "incidencia_precio",
                "Nocturnidad_horas": "nocturnidad_horas",
                "Traslados_total": "traslados_total",
                "Fecha": "fecha",
                "Observaciones": "observaciones"
            }
            
            for field_name, value in row_data.items():
                if field_name in attr_map and field_name != "Trabajador":
                    setattr(incidencia, attr_map[field_name], value)
        
        # Eliminar filas marcadas para borrar
        new_incidents = []
        for i, inc in enumerate(incidents_to_update):
            local_idx = i - start_idx
            if start_idx <= i < start_idx + self.ROWS_PER_PAGE:
                if not edited_rows.get(local_idx, {}).get("Borrar", False):
                    new_incidents.append(inc)
            else:
                new_incidents.append(inc)
        
        st.session_state.incidencias = new_incidents
        
        # Limpiar cache para forzar recálculo en próximo render
        if "table_data_hash" in st.session_state:
            del st.session_state["table_data_hash"]
        if "cached_df" in st.session_state:
            del st.session_state["cached_df"]
        
        st.success("✅ ¡Cambios guardados con éxito!")
        st.rerun()