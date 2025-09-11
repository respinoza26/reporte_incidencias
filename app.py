import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

st.set_page_config(
    page_title="Registro de Incidencias",
    page_icon="📋",
    layout="wide"
)

def preprocess_centros(df: pd.DataFrame) -> pd.DataFrame:
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
        'Departamento': 'desc_dpto',
        'Puesto de trabajo': 'puesto_empleado',
        'coste hora  empresa': 'coste_hora_empresa',
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
    
    # if 'cod_seccion' in df.columns:
        # df = df[~df['cod_seccion'].isna()] # Por  ahora lo vamos a dejar pero luego esto se debe conversar con RRHH
    
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
    df = df[['ccentro', 'dcentro', 'centropref']]
    df.columns = ['codigo_centro', 'nombre_centro', 'cod_centro_preferente']
    return df

def preprocess_tarifas_incidencias(df: pd.DataFrame) -> pd.DataFrame:
    return df

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
    nocturnidad_precio: float = 0.0
    traslados_horas: float = 0.0
    traslados_precio: float = 0.0
    fecha: Optional[datetime] = None
    observaciones: str = ""
    centro_preferente: Optional[int] = None
    nombre_jefe_ope: str = ""
    categoria: str = ""
    servicio: str = ""
    
    def to_dict(self) -> Dict:
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
            "Nocturnidad_precio": self.nocturnidad_precio,
            "Traslados_horas": self.traslados_horas,
            "Traslados_precio": self.traslados_precio,
            "Fecha": self.fecha,
            "Observaciones": self.observaciones,
            "Centro preferente": self.centro_preferente,
            "Supervisor de operaciones": self.nombre_jefe_ope,
            "Categoría": self.categoria,
            "Servicio": self.servicio
        }

    def is_valid(self) -> bool:
        required_fields = [
            self.trabajador, self.imputacion_nomina, self.facturable,
            self.motivo, self.codigo_crown_destino, self.fecha, self.observaciones
        ]
        return all(field is not None and field != "" and (not isinstance(field, (float, int)) or field > 0 or field == 0) for field in required_fields)

@st.cache_data
def _load_and_preprocess_excel(file_path: str) -> Dict[str, pd.DataFrame]:
    try:
        preprocessors = {
            'centros': preprocess_centros,
            'trabajadores': preprocess_trabajadores,
            'maestro_centros': preprocess_maestro_centros,
            'tarifas_incidencias': preprocess_tarifas_incidencias,
            'cuenta_motivos': lambda df: df,  

        }
        xls = pd.ExcelFile(file_path)
        sheets_df = {}
        for sheet_name in xls.sheet_names:
            # Leer cada hoja con las configuraciones específicas
            if sheet_name == 'tarifas_incidencias':
                df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=3, usecols="A:C")
            elif sheet_name == 'cuenta_motivos':
                df = pd.read_excel(xls, sheet_name=sheet_name)
            else:
                df = pd.read_excel(xls, sheet_name=sheet_name)
            if sheet_name in preprocessors:
                df = preprocessors[sheet_name](df)
            sheets_df[sheet_name] = df
        return sheets_df
    except FileNotFoundError:
        st.error(f"Error: El archivo '{file_path}' no se encuentra.")
        return {}
    except Exception as e:
        st.error(f"Error leyendo el archivo Excel: {e}")
        return {}

class DataManager:
    def __init__(self):
        #  Cargar y preprocesar los datos usando la clase DataManager 
        self.maestros = _load_and_preprocess_excel('data/maestros.xlsx')

        df_centros = self.maestros.get('centros', pd.DataFrame())
        df_trabajadores = self.maestros.get('trabajadores', pd.DataFrame())
        df_maestro_centros = self.maestros.get('maestro_centros', pd.DataFrame())
        
        # Merge de trabajadores con la información de centros para el nombre del jefe
        if not df_trabajadores.empty and 'cod_crown' in df_trabajadores.columns and not df_centros.empty:
            df_trabajadores['cod_crown'] = df_trabajadores['cod_crown'].astype(str)
            df_trabajadores = pd.merge(
                df_trabajadores,
                df_centros[['codigo_centro', 'nombre_jefe_ope']],
                left_on='cod_crown',
                right_on='codigo_centro',
                how='left'
            ).drop(columns='codigo_centro')
        
        # Asegurarse de que las columnas a unir sean del mismo tipo (string)
        if not df_maestro_centros.empty and 'centro_preferente' in df_trabajadores.columns and 'codigo_centro' in df_maestro_centros.columns:
            df_trabajadores['centro_preferente'] = df_trabajadores['centro_preferente'].astype(str).str.replace('.0', '', regex=False)
            df_maestro_centros['codigo_centro'] = df_maestro_centros['codigo_centro'].astype(str)
            
            df_trabajadores = pd.merge(
                df_trabajadores,
                df_maestro_centros[['codigo_centro', 'nombre_centro']],
                left_on='centro_preferente',
                right_on='codigo_centro',
                how='left'
            ).rename(columns={'codigo_centro': 'codigo_centro_preferente', 'nombre_centro': 'nombre_centro_preferente'})
        
        self.df_trabajadores = df_trabajadores
        self.df_centros = df_centros

    def get_jefes(self) -> List[str]:
        jefes = set()
        if not self.df_centros.empty and 'nombre_jefe_ope' in self.df_centros.columns:
            jefes.update(self.df_centros['nombre_jefe_ope'].dropna().unique())
        if not self.df_trabajadores.empty and 'nombre_jefe_ope' in self.df_trabajadores.columns:
            jefes.update(self.df_trabajadores['nombre_jefe_ope'].dropna().unique())
        return sorted(list(jefes))
    
    def get_all_employees(self) -> List[str]:
        if self.df_trabajadores.empty:
            return []
        return sorted(self.df_trabajadores['nombre_empleado'].dropna().unique())

    def get_empleado_info(self, nombre_empleado: str) -> Dict:
            if self.df_trabajadores.empty:
                return {}
            try:
                empleado = self.df_trabajadores[self.df_trabajadores['nombre_empleado'] == nombre_empleado].iloc[0]
                info = empleado.to_dict()
                default_values = { 
                    'servicio': '', 
                    'cat_empleado': '', 
                    'cod_crown': '', 
                    'centro_preferente': '',
                    'nombre_centro_preferente': '', 
                    'nombre_jefe_ope': ''
                }
                for key, default_value in default_values.items():
                    if key not in info or pd.isna(info[key]) or info[key] == '':
                        info[key] = default_value
                return info
            except (IndexError, KeyError):
                return {}

class TablaUnificadaIncidencias:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def render(self, selected_jefe: str) -> None:
        st.header("📋 Registro de Incidencias de Personal")
        
        incidencias = st.session_state.incidencias
        
        with st.expander("Añadir Nueva Incidencia"):
            self._render_add_form(selected_jefe)
            
        self._render_main_table(incidencias, selected_jefe)

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
                
                empleado_jefe = empleado_info.get('nombre_jefe_ope', '')
                incidencia.nombre_jefe_ope = empleado_jefe if empleado_jefe else "N/A"

    def _render_main_table(self, incidencias: List[Incidencia], selected_jefe: str) -> None:
        # Actualizar datos de empleados antes de mostrar la tabla
        for incidencia in incidencias:
            if incidencia.trabajador:
                self._actualizar_datos_empleado(incidencia, incidencia.trabajador, selected_jefe)
        
        df = pd.DataFrame([inc.to_dict() for inc in incidencias])
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        
        todos_empleados = self.data_manager.get_all_employees()
        
        # CRÍTICO: Obtener los códigos de centros únicos para el desplegable
        # Se añade un valor vacío y se ordenan los resultados
        centros_crown = [""] + sorted(self.data_manager.df_centros['codigo_centro'].dropna().astype(int).unique().tolist())
    
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
            "Incidencia_precio": st.column_config.NumberColumn("Inc. Precio", width="small", min_value=0),
            "Nocturnidad_horas": st.column_config.NumberColumn("Noct. Horas", width="small", min_value=0),
            "Nocturnidad_precio": st.column_config.NumberColumn("Noct. Precio", width="small", min_value=0),
            "Traslados_horas": st.column_config.NumberColumn("Trasl. Horas", width="small", min_value=0),
            "Traslados_precio": st.column_config.NumberColumn("Trasl. Precio", width="small", min_value=0),
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YY", required=True),
            "Observaciones": st.column_config.TextColumn("Observaciones", required=True, width="medium"),
            "Centro preferente": st.column_config.NumberColumn("Centro Pref.", disabled=True),
            "Supervisor de operaciones": st.column_config.TextColumn("Supervisor", disabled=True),
            "Categoría": st.column_config.TextColumn("Categoría", disabled=True, width="small"),
            "Servicio": st.column_config.TextColumn("Servicio", disabled=True, width="small"),
        }
        
        # Eliminamos el on_change para mejorar la UX y añadimos un botón
        st.data_editor(
            df,
            column_config=column_config,
            width='stretch',
            num_rows="fixed",
            key="unificado_editor"
        )
        
        # st.caption("ℹ️ El campo 'Supervisor de operaciones' se completa automáticamente al seleccionar un trabajador.")
        
        # Botón para procesar los cambios después de que el usuario haya terminado de editar
        if st.button("💾 Guardar cambios"):
            edited_rows = st.session_state["unificado_editor"]["edited_rows"]
            incidents_to_update = st.session_state.incidencias
            
            for row_idx, row_data in edited_rows.items():
                if row_data.get('Borrar', False):
                    continue
                    
                incidencia = incidents_to_update[row_idx]
                
                if "Trabajador" in row_data and row_data["Trabajador"]:
                    self._actualizar_datos_empleado(incidencia, row_data["Trabajador"], selected_jefe)
                
                for field_name, value in row_data.items():
                    if field_name == "Trabajador":
                        continue
                    attr_map = {
                        "Imputación Nómina": "imputacion_nomina",
                        "Facturable": "facturable",
                        "Motivo": "motivo",
                        "Código Crown Destino": "codigo_crown_destino",
                        "Empresa Destino": "empresa_destino",
                        "Incidencia_horas": "incidencia_horas",
                        "Incidencia_precio": "incidencia_precio",
                        "Nocturnidad_horas": "nocturnidad_horas",
                        "Nocturnidad_precio": "nocturnidad_precio",
                        "Traslados_horas": "traslados_horas",
                        "Traslados_precio": "traslados_precio",
                        "Fecha": "fecha",
                        "Observaciones": "observaciones"
                    }
                    if field_name in attr_map:
                        setattr(incidencia, attr_map[field_name], value)
                        
            new_incidents = [inc for i, inc in enumerate(incidents_to_update) if not edited_rows.get(i, {}).get("Borrar", False)]
            st.session_state.incidencias = new_incidents
            st.success("✅ ¡Cambios guardados con éxito!")
            st.rerun()

class ExportManager:
    @staticmethod
    def export_to_excel(incidencias: List[Incidencia], data_manager: DataManager) -> Optional[bytes]:
        incidencias_validas = [inc for inc in incidencias if inc.is_valid()]
        if not incidencias_validas:
            return None
        
        data = []
        for inc in incidencias_validas:
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
                'nocturnidad_precio': inc.nocturnidad_precio,
                'traslados_horas': inc.traslados_horas,
                'traslados_precio': inc.traslados_precio,
                'fecha': inc.fecha,
                'observaciones': inc.observaciones,
                'centro_preferente': inc.centro_preferente,
                'categoria': inc.categoria,
                'servicio': inc.servicio,
            })
        
        df = pd.DataFrame(data)
        # Obtener los datos de la tabla de motivos
        df_motivos = data_manager.maestros.get('cuenta_motivos', pd.DataFrame())

        # Si la tabla de motivos existe, crear el diccionario de mapeo
        # Tu código espera 'Motivo' y 'desc_cuenta'
        if not df_motivos.empty and 'Motivo' in df_motivos.columns and 'desc_cuenta' in df_motivos.columns:
            motivo_map = dict(zip(df_motivos['Motivo'], df_motivos['desc_cuenta']))
            # Crear la nueva columna 'cuenta_motivo' en el DataFrame final
            df['cuenta_motivos'] = df['motivo'].map(motivo_map).fillna("N/A")


        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        return excel_buffer.getvalue()

class IncidenciasApp:
    def __init__(self):
        if 'app_initialized_minimalist' not in st.session_state:
            st.session_state.app_initialized_minimalist = True
            st.session_state.selected_jefe = ""
            st.session_state.selected_imputacion = ""
            st.session_state.incidencias = []
    
    def run(self):
        data_manager = DataManager()
        if data_manager.df_centros.empty and data_manager.df_trabajadores.empty:
            st.error("❌ No se pudieron cargar los datos. Verifica que el archivo 'data/maestros.xlsx' exista y tenga las hojas necesarias.")
            return

        self._render_header(data_manager)
        
        if not st.session_state.selected_jefe or not st.session_state.selected_imputacion:
            st.warning("⚠️ Por favor, selecciona la imputación de nómina y un jefe para comenzar.")
            return
            
        tabla_unificada = TablaUnificadaIncidencias(data_manager)
        tabla_unificada.render(st.session_state.selected_jefe)
        
        self._render_export_section(data_manager)
    
    # --- Mejora 2: Manejo de Estado con Callbacks ---
    def _handle_imputacion_change(self):
        st.session_state.selected_imputacion = st.session_state.imputacion_nomina_main
        st.session_state.incidencias = []

    def _handle_jefe_change(self):
        st.session_state.selected_jefe = st.session_state.jefe_main
        st.session_state.incidencias = []

    def _render_header(self, data_manager: DataManager):
        st.title("Plantilla de Registro de Incidencias")
        
        imputacion_opciones = [""] + ["01 Enero", "02 Febrero", "03 Marzo", "04 Abril", "05 Mayo", "06 Junio", "07 Julio", "08 Agosto", "09 Septiembre", "10 Octubre", "11 Noviembre", "12 Diciembre"]
        jefes_list = data_manager.get_jefes()

        col1, col2 = st.columns(2)
        with col1:
            st.selectbox(
                "📅 Imputación Nómina:",
                imputacion_opciones,
                index=imputacion_opciones.index(st.session_state.selected_imputacion) if st.session_state.selected_imputacion in imputacion_opciones else 0,
                key="imputacion_nomina_main",
                on_change=self._handle_imputacion_change
            )
        with col2:
            st.selectbox(
                "👤 Selecionar nombre de supervisor:", 
                [""] + jefes_list,
                index=jefes_list.index(st.session_state.selected_jefe) + 1 if st.session_state.selected_jefe in jefes_list else 0,
                key="jefe_main",
                on_change=self._handle_jefe_change
            )

    def _render_export_section(self,data_manager: DataManager):
        st.markdown("---")
        st.header("📊 Exportar Datos")
        
        incidencias_validas = [inc for inc in st.session_state.incidencias if inc.is_valid()]
        monto_total_incidencias = sum(inc.incidencia_precio * inc.incidencia_horas for inc in incidencias_validas)
        monto_total_nocturnidad = sum(inc.nocturnidad_precio * inc.nocturnidad_horas for inc in incidencias_validas)
        monto_total_traslados = sum(inc.traslados_precio * inc.traslados_horas for inc in incidencias_validas)
        monto_total_con_ss = monto_total_incidencias * 1.3195 + monto_total_nocturnidad * 1.3195 + monto_total_traslados

        col1, col2, col3, col4 , col5 = st.columns(5)
        with col1:
            st.metric("📋 Total Incidencias", f"€{monto_total_incidencias:,.2f}")
        with col2:
            st.metric("✅ Total Nocturnidad", f"€{monto_total_nocturnidad:,.2f}")
        with col3:
            st.metric("⚠️ Total Traslados", f"€{monto_total_traslados:,.2f}")
        with col4:
            st.metric("🔧 Total", f"€{monto_total_incidencias + monto_total_nocturnidad + monto_total_traslados:,.2f}")
        with col5:
            st.metric("📁 Total coste", f"€{monto_total_con_ss:,.2f}")

        if not incidencias_validas:
            st.warning("⚠️ No hay incidencias válidas para exportar.")
            st.info("💡 Complete todos los campos obligatorios: Trabajador, Imputación Nómina, Facturable, Motivo, Código Crown Destino, Fecha y Observaciones.")
            return
            
        excel_data = ExportManager.export_to_excel(incidencias_validas, data_manager)        
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

if __name__ == "__main__":
    app = IncidenciasApp()
    app.run()