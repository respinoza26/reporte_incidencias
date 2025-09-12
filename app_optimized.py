import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import hashlib
import pickle

st.set_page_config(
    page_title="Registro de Incidencias",
    page_icon="📋",
    layout="wide"
)

# =============================================================================
# FUNCIONES DE CARGA OPTIMIZADAS
# =============================================================================

@st.cache_data(ttl=3600)  # Cache por 1 hora
def _load_single_sheet(file_path: str, sheet_name: str, **kwargs) -> pd.DataFrame:
    """Carga una sola hoja del Excel bajo demanda"""
    try:
        return pd.read_excel(file_path, sheet_name=sheet_name, **kwargs)
    except Exception as e:
        st.error(f"Error cargando hoja '{sheet_name}': {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def _get_sheet_names(file_path: str) -> List[str]:
    """Obtiene los nombres de las hojas sin cargar el contenido"""
    try:
        with pd.ExcelFile(file_path) as xls:
            return xls.sheet_names
    except Exception:
        return []

def preprocess_centros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = [
        'codigo_centro', 'nombre_centro', 'cod_jefe', 'nombre_jefe_ope',
        'fecha_alta_centro', 'fecha_baja_centro', 'cod_centro_preferente',
        'desc_centro_preferente', 'almacen_centro'
    ]
    df = df[df['fecha_baja_centro'].isna()] \
           .drop(columns=['fecha_baja_centro', 'fecha_alta_centro', 'almacen_centro'])
    df = df[df['cod_jefe'].notna()]
    return df

def preprocess_trabajadores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df.columns = df.columns.str.strip().str.replace('\n', ' ')
    
    df = df.rename(columns={
        'Empresa': 'cod_empresa',
        'Empleado - Código': 'cod_empleado',
        'Nombre empleado': 'nombre_empleado',
        'Nombre de la empresa': 'nombre_empresa',
        'Código contrato': 'cod_contrato',
        'Contrato': 'tipo_contrato',
        'Porcentaje de jornada': 'porcen_contrato',
        'Sección': 'desc_seccion',
        'Categoría': 'cat_empleado',
        'Código sección': 'cod_seccion',
        'Código reg. convenio': 'cod_reg_convenio',
        'Departamento': 'desc_dpto',
        'Puesto de trabajo': 'puesto_empleado',
        'Coste hora empresa': 'coste_hora',
        'empresa/seccion': 'empresa_codigo',
        'codigo Cwon': 'cod_crown',
        'Nombre Código Crown': 'nombre_cod_crown',
        'empresa2': 'nombre_empresa_final',
        'centro preferente': 'centro_preferente'
    })

    if 'cod_empresa' in df.columns:
        df['cod_empresa'] = np.select(
            [
                df['cod_empresa'].astype(str).str.startswith('20', na=False),
                df['cod_empresa'].astype(str).str.startswith('19', na=False),
                df['cod_empresa'].astype(str).str.startswith('50', na=False)
            ],
            ['SMI', 'ALGADI', 'DISTEGSA'], default='Otros'
        )
    
    if 'nombre_empleado' in df.columns:
        df['nombre_empleado'] = df['nombre_empleado'].str.upper()

    if 'servicio' not in df.columns and 'cat_empleado' in df.columns:
        df['servicio'] = np.where(
            df['cat_empleado'].str.contains('limp|asl', case=False, na=False),
            '020 Limpieza',
            '010 Restauración'
        )
    
    return df

def preprocess_maestro_centros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[['ccentro', 'dcentro', 'centropref']]
    df.columns = ['codigo_centro', 'nombre_centro', 'cod_centro_preferente']
    return df

def preprocess_tarifas_incidencias(df: pd.DataFrame) -> pd.DataFrame:
    return df

# =============================================================================
# MODELO DE DATOS
# =============================================================================

@dataclass
class Incidencia:
    trabajador: str = ""
    imputacion_nomina: str = ""
    facturable: str = ""
    motivo: str = ""
    codigo_crown_origen: Optional[int] = None
    codigo_crown_destino: Optional[int] = None
    empresa_destino: str = ""
    incidencia_horas: float = 0.0
    incidencia_precio: float = 0.0
    nocturnidad_horas: float = 0.0
    traslados_total: float = 0.0
    coste_hora: float = 0.0
    fecha: Optional[datetime] = None
    observaciones: str = ""
    centro_preferente: Optional[int] = None
    nombre_jefe_ope: str = ""
    categoria: str = ""
    servicio: str = ""
    cod_reg_convenio: str = ""
    
    def to_dict(self, precio_nocturnidad: float = 0.0) -> Dict:
        """Optimizado: Recibe el precio pre-calculado"""
        return {
            "Borrar": False,
            "Trabajador": self.trabajador,
            "Imputación Nómina": self.imputacion_nomina,
            "Facturable": self.facturable,
            "Motivo": self.motivo,
            "Código Crown Origen": self.codigo_crown_origen,
            "Código Crown Destino": self.codigo_crown_destino,
            "Empresa Destino": self.empresa_destino,
            "Incidencia_horas": self.incidencia_horas,
            "Incidencia_precio": self.incidencia_precio,
            "Nocturnidad_horas": self.nocturnidad_horas,
            "Precio_nocturnidad": precio_nocturnidad,
            "Traslados_total": self.traslados_total,
            "Coste hora empresa": self.coste_hora,
            "Fecha": self.fecha,
            "Observaciones": self.observaciones,
            "Centro preferente": self.centro_preferente,
            "Supervisor de operaciones": self.nombre_jefe_ope,
            "Categoría": self.categoria,
            "Servicio": self.servicio,
        }

    def is_valid(self) -> bool:
        required_fields = [
            self.trabajador, self.imputacion_nomina, self.facturable,
            self.motivo, self.codigo_crown_destino, self.fecha, self.observaciones
        ]
        return all(field is not None and field != "" and (not isinstance(field, (float, int)) or field >= 0) for field in required_fields)

# =============================================================================
# DATA MANAGER OPTIMIZADO
# =============================================================================

class OptimizedDataManager:
    def __init__(self):
        self.file_path = 'data/maestros.xlsx'
        
        # Lazy loading - solo cargar cuando sea necesario
        self._df_centros = None
        self._df_trabajadores = None
        
        # Lookup tables para búsquedas rápidas
        self._tarifa_lookup = None
        self._empleado_lookup = None
        self._jefes_list = None
        self._empleados_list = None
        self._centros_list = None
        
        # Estado de cache
        self._cache_built = False

    @property
    def df_centros(self) -> pd.DataFrame:
        if self._df_centros is None:
            self._df_centros = preprocess_centros(
                _load_single_sheet(self.file_path, 'centros')
            )
        return self._df_centros

    @property
    def df_trabajadores(self) -> pd.DataFrame:
        if self._df_trabajadores is None:
            df = _load_single_sheet(self.file_path, 'trabajadores')
            df = preprocess_trabajadores(df)
            
            # Merge con centros
            if not df.empty and not self.df_centros.empty and 'cod_crown' in df.columns:
                df['cod_crown'] = df['cod_crown'].astype(str)
                df = pd.merge(
                    df,
                    self.df_centros[['codigo_centro', 'nombre_jefe_ope']],
                    left_on='cod_crown',
                    right_on='codigo_centro',
                    how='left'
                ).drop(columns='codigo_centro')
            
            # Merge con maestro_centros
            df_maestro = preprocess_maestro_centros(
                _load_single_sheet(self.file_path, 'maestro_centros')
            )
            if not df.empty and not df_maestro.empty and 'centro_preferente' in df.columns:
                df['centro_preferente'] = df['centro_preferente'].astype(str).str.replace('.0', '', regex=False)
                df_maestro['codigo_centro'] = df_maestro['codigo_centro'].astype(str)
                
                df = pd.merge(
                    df,
                    df_maestro[['codigo_centro', 'nombre_centro']],
                    left_on='centro_preferente',
                    right_on='codigo_centro',
                    how='left'
                ).rename(columns={'codigo_centro': 'codigo_centro_preferente', 'nombre_centro': 'nombre_centro_preferente'})
            
            self._df_trabajadores = df
        return self._df_trabajadores

    @st.cache_data
    def _build_tarifa_lookup(_self, file_path: str) -> Dict[Tuple[str, str], float]:
        """Construir lookup table de tarifas - O(1) lookup"""
        df_tarifas = _load_single_sheet(file_path, 'tarifas_incidencias', skiprows=3, usecols="A:C")
        df_tarifas = preprocess_tarifas_incidencias(df_tarifas)
        
        lookup = {}
        if not df_tarifas.empty and 'Descripción' in df_tarifas.columns:
            for _, row in df_tarifas.iterrows():
                if pd.notna(row['Descripción']) and pd.notna(row['cod_convenio']) and pd.notna(row['tarifa_noct']):
                    categoria_norm = str(row['Descripción']).strip().upper()
                    convenio_norm = str(row['cod_convenio']).strip()
                    try:
                        tarifa = float(row['tarifa_noct'])
                        lookup[(categoria_norm, convenio_norm)] = tarifa
                    except (ValueError, TypeError):
                        continue
        return lookup

    @st.cache_data
    def _build_empleado_lookup(_self, df_trabajadores: pd.DataFrame) -> Dict[str, Dict]:
        """Construir lookup table de empleados - O(1) lookup"""
        lookup = {}
        if df_trabajadores.empty:
            return lookup
        
        for _, empleado in df_trabajadores.iterrows():
            info = empleado.to_dict()
            default_values = { 
                'servicio': '', 
                'cat_empleado': '', 
                'cod_crown': '', 
                'centro_preferente': '',
                'nombre_centro_preferente': '', 
                'nombre_jefe_ope': '',
                'coste_hora': 0.0,
                'cod_reg_convenio': ''
            }
            
            for key, default_value in default_values.items():
                if key not in info or pd.isna(info[key]) or info[key] == '':
                    info[key] = default_value
            
            lookup[info['nombre_empleado']] = info
        
        return lookup

    def _ensure_cache_built(self):
        """Construir todas las lookup tables si no existen"""
        if not self._cache_built:
            # Lookup de tarifas
            self._tarifa_lookup = self._build_tarifa_lookup(self.file_path)
            
            # Lookup de empleados
            self._empleado_lookup = self._build_empleado_lookup(self.df_trabajadores)
            
            # Listas pre-computadas
            if not self.df_centros.empty:
                jefes = set()
                if 'nombre_jefe_ope' in self.df_centros.columns:
                    jefes.update(self.df_centros['nombre_jefe_ope'].dropna().unique())
                if not self.df_trabajadores.empty and 'nombre_jefe_ope' in self.df_trabajadores.columns:
                    jefes.update(self.df_trabajadores['nombre_jefe_ope'].dropna().unique())
                self._jefes_list = sorted(list(jefes))
                
                self._centros_list = sorted(self.df_centros['codigo_centro'].dropna().astype(int).unique().tolist())
            else:
                self._jefes_list = []
                self._centros_list = []
            
            if not self.df_trabajadores.empty:
                self._empleados_list = sorted(self.df_trabajadores['nombre_empleado'].dropna().unique())
            else:
                self._empleados_list = []
            
            self._cache_built = True

    def get_precio_nocturnidad(self, categoria: str, cod_convenio: str) -> float:
        """Lookup O(1) optimizado"""
        self._ensure_cache_built()
        
        if not self._tarifa_lookup:
            return 0.0
            
        categoria_norm = str(categoria).strip().upper() if pd.notna(categoria) else ""
        convenio_norm = str(cod_convenio).strip() if pd.notna(cod_convenio) else ""
        
        if not categoria_norm or not convenio_norm:
            return 0.0
        
        return self._tarifa_lookup.get((categoria_norm, convenio_norm), 0.0)

    def get_empleado_info(self, nombre_empleado: str) -> Dict:
        """Lookup O(1) optimizado"""
        self._ensure_cache_built()
        return self._empleado_lookup.get(nombre_empleado, {})

    def get_jefes(self) -> List[str]:
        """Lista pre-computada"""
        self._ensure_cache_built()
        return self._jefes_list

    def get_all_employees(self) -> List[str]:
        """Lista pre-computada"""
        self._ensure_cache_built()
        return self._empleados_list

    def get_centros_crown(self) -> List[str]:
        """Lista pre-computada"""
        self._ensure_cache_built()
        return [""] + [str(centro) for centro in self._centros_list]

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
                
            # 🔧 Normalización de columnas numéricas
            numeric_cols = [
                "Código Crown Origen", "Código Crown Destino", "Incidencia_horas",
                "Incidencia_precio", "Nocturnidad_horas", "Precio_nocturnidad",
                "Traslados_total", "Coste hora empresa", "Centro preferente"
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            # Guardar en cache
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
            "Motivo": st.column_config.SelectboxColumn("Motivo", options=["Absentismo", "Refuerzo", "Eventos", "Festivos y Fines de Semana", "Permiso retribuido", "Puesto pendiente de cubrir","Formación","Otros","Nocturnidad"], required=True, width="medium"),
            "Código Crown Origen": st.column_config.NumberColumn("Crown Origen", disabled=True),
            "Código Crown Destino": st.column_config.SelectboxColumn("Crown Destino", options=centros_crown, required=True, width="medium"),
            "Empresa Destino": st.column_config.SelectboxColumn("Empresa Destino", options=["", "ALGADI","SMI","DISTEGSA"], width="medium"),
            "Incidencia_horas": st.column_config.NumberColumn("Inc. Horas", width="medium", min_value=0),
            "Incidencia_precio": st.column_config.NumberColumn("Inc. Precio", width="medium", min_value=0, format="€%.2f"),
            "Nocturnidad_horas": st.column_config.NumberColumn("Noct. Horas", width="medium", min_value=0),
            "Precio_nocturnidad": st.column_config.NumberColumn("Precio Noct.", width="medium", min_value=0, disabled=True, format="€%.2f"),
            "Traslados_total": st.column_config.NumberColumn("Trasl. Total", width="medium", min_value=0),
            "Coste hora empresa": st.column_config.NumberColumn("Coste/Hora", disabled=True, width="medium", format="€%.2f"),
            "Fecha": st.column_config.DateColumn("Fecha", required=True, width="medium"),
            "Observaciones": st.column_config.TextColumn("Observaciones", required=True, width="medium"),
            "Centro preferente": st.column_config.NumberColumn("Centro Pref.", disabled=True),
            "Supervisor de operaciones": st.column_config.TextColumn("Supervisor", disabled=True),
            "Categoría": st.column_config.TextColumn("Categoría", disabled=True, width="medium"),
            "Servicio": st.column_config.TextColumn("Servicio", disabled=True, width="medium"),
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
            return pd.NaT
        if isinstance(fecha, datetime):
            return fecha
        if isinstance(fecha, str):
            try:
                fecha_dt = pd.to_datetime(fecha, errors='coerce')
                return fecha_dt if not pd.isna(fecha_dt) else pd.NaT
            except:
                return pd.NaT
        return pd.NaT


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

# =============================================================================
# APLICACIÓN PRINCIPAL OPTIMIZADA
# =============================================================================

class OptimizedIncidenciasApp:
    def __init__(self):
        if 'app_initialized_optimized' not in st.session_state:
            st.session_state.app_initialized_optimized = True
            st.session_state.selected_jefe = ""
            st.session_state.selected_imputacion = ""
            st.session_state.incidencias = []
    
    def run(self):
        # Mostrar indicador de carga solo la primera vez
        if not hasattr(st.session_state, 'data_manager_initialized'):
            with st.spinner("Inicializando aplicación..."):
                data_manager = OptimizedDataManager()
                # Forzar inicialización de cache
                data_manager._ensure_cache_built()
                st.session_state.data_manager_initialized = True
                st.session_state.data_manager = data_manager
        else:
            data_manager = st.session_state.data_manager

        if data_manager.df_centros.empty and data_manager.df_trabajadores.empty:
            st.error("⚠️ No se pudieron cargar los datos. Verifica que el archivo 'data/maestros.xlsx' exista y tenga las hojas necesarias.")
            return

        self._render_header(data_manager)
        
        if not st.session_state.selected_jefe or not st.session_state.selected_imputacion:
            st.warning("⚠️ Por favor, selecciona la imputación de nómina y un jefe para comenzar.")
            return
            
        tabla_optimizada = OptimizedTablaIncidencias(data_manager)
        tabla_optimizada.render(st.session_state.selected_jefe)
        
        self._render_export_section(data_manager)
    
    def _render_header(self, data_manager: OptimizedDataManager):
        st.title("Plantilla de Registro de Incidencias")
        
        imputacion_opciones = [""] + ["01 Enero", "02 Febrero", "03 Marzo", "04 Abril", "05 Mayo", "06 Junio", "07 Julio", "08 Agosto", "09 Septiembre", "10 Octubre", "11 Noviembre", "12 Diciembre"]
        jefes_list = data_manager.get_jefes()

        col1, col2 = st.columns(2)
        with col1:
            new_imputacion = st.selectbox(
                "📅 Imputación Nómina:",
                imputacion_opciones,
                index=imputacion_opciones.index(st.session_state.selected_imputacion) if st.session_state.selected_imputacion in imputacion_opciones else 0,
                key="imputacion_nomina_main"
            )
            
        with col2:
            new_jefe = st.selectbox(
                "👤 Seleccionar nombre de supervisor:", 
                [""] + jefes_list,
                index=jefes_list.index(st.session_state.selected_jefe) + 1 if st.session_state.selected_jefe in jefes_list else 0,
                key="jefe_main"
            )
        
        # Verificar cambios y actualizar estado
        if new_imputacion != st.session_state.selected_imputacion:
            st.session_state.selected_imputacion = new_imputacion
            st.session_state.incidencias = []
            st.rerun()
            
        if new_jefe != st.session_state.selected_jefe:
            st.session_state.selected_jefe = new_jefe
            st.session_state.incidencias = []
            st.rerun()

    def _render_export_section(self, data_manager: OptimizedDataManager):
        st.markdown("---")
        st.header("📊 Exportar Datos")
        
        incidencias_validas = [inc for inc in st.session_state.incidencias if inc.is_valid()]
        
        if not incidencias_validas:
            st.warning("⚠️ No hay incidencias válidas para exportar.")
            st.info("💡 Complete todos los campos obligatorios: Trabajador, Imputación Nómina, Facturable, Motivo, Código Crown Destino, Fecha y Observaciones.")
            return
        
        # Pre-calcular métricas optimizadas
        with st.spinner("Calculando métricas..."):
            metricas = self._calculate_metrics_optimized(incidencias_validas, data_manager)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📋 Total Incidencias", f"€{metricas['total_incidencias']:,.2f}")
        with col2:
            st.metric("✅ Total Nocturnidad", f"€{metricas['total_nocturnidad']:,.2f}")
        with col3:
            st.metric("⚠️ Total Traslados", f"€{metricas['total_traslados']:,.2f}")
        with col4:
            st.metric("🔧 Total", f"€{metricas['total_simple']:,.2f}")
        with col5:
            st.metric("📊 Total coste", f"€{metricas['total_con_ss']:,.2f}")

        # Botón de descarga optimizado
        with st.spinner("Generando Excel..."):
            excel_data = OptimizedExportManager.export_to_excel(incidencias_validas, data_manager)
        
        if excel_data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"incidencias_{st.session_state.selected_jefe.replace(' ', '_')}_{timestamp}.xlsx"
            
            st.download_button(
                label="💾 Descargar Excel de Incidencias",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Descarga todas las incidencias válidas en formato Excel (.xlsx)"
            )
            
            st.success(f"✅ Listo para descargar: {len(incidencias_validas)} incidencias válidas")

    def _calculate_metrics_optimized(self, incidencias_validas: List[Incidencia], data_manager: OptimizedDataManager) -> Dict[str, float]:
        """Calcula métricas de forma optimizada con cache de precios"""
        # Pre-calcular precios únicos para evitar lookups repetidos
        precio_cache = {}
        
        monto_total_incidencias = 0.0
        monto_total_nocturnidad = 0.0
        monto_total_traslados = 0.0
        
        for inc in incidencias_validas:
            # Incidencias
            monto_total_incidencias += inc.incidencia_precio * inc.incidencia_horas
            
            # Nocturnidad con cache
            key = (inc.categoria, inc.cod_reg_convenio)
            if key not in precio_cache:
                precio_cache[key] = data_manager.get_precio_nocturnidad(inc.categoria, inc.cod_reg_convenio)
            
            precio_noct = precio_cache[key]
            monto_total_nocturnidad += precio_noct * inc.nocturnidad_horas
            
            # Traslados
            monto_total_traslados += inc.traslados_total * inc.coste_hora
        
        total_simple = monto_total_incidencias + monto_total_nocturnidad + monto_total_traslados
        total_con_ss = (monto_total_incidencias + monto_total_nocturnidad) * 1.3195 + monto_total_traslados
        
        return {
            'total_incidencias': monto_total_incidencias,
            'total_nocturnidad': monto_total_nocturnidad,
            'total_traslados': monto_total_traslados,
            'total_simple': total_simple,
            'total_con_ss': total_con_ss
        }

if __name__ == "__main__":
    # Configuración adicional para mejor rendimiento
    
    app = OptimizedIncidenciasApp()
    app.run()