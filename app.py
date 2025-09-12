import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import sqlite3
import hashlib
import pickle
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

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
    nocturnidad_precio: float = 0.0
    traslados_total: float = 0.0
    coste_hora: float = 0.0
    fecha: Optional[datetime] = None
    observaciones: str = ""
    centro_preferente: Optional[int] = None
    nombre_jefe_ope: str = ""
    categoria: str = ""
    servicio: str = ""
    cod_reg_convenio: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "trabajador": self.trabajador,
            "imputacion_nomina": self.imputacion_nomina,
            "facturable": self.facturable,
            "motivo": self.motivo,
            "codigo_crown_origen": self.codigo_crown_origen,
            "codigo_crown_destino": self.codigo_crown_destino,
            "empresa_destino": self.empresa_destino,
            "incidencia_horas": self.incidencia_horas,
            "incidencia_precio": self.incidencia_precio,
            "nocturnidad_horas": self.nocturnidad_horas,
            "nocturnidad_precio": self.nocturnidad_precio,
            "traslados_total": self.traslados_total,
            "coste_hora": self.coste_hora,
            "fecha": self.fecha.strftime('%Y-%m-%d') if self.fecha else None,
            "observaciones": self.observaciones,
            "centro_preferente": self.centro_preferente,
            "nombre_jefe_ope": self.nombre_jefe_ope,
            "categoria": self.categoria,
            "servicio": self.servicio,
            "cod_reg_convenio": self.cod_reg_convenio,
        }

# =============================================================================
# FUNCIONES DE PREPROCESAMIENTO
# =============================================================================

def _preprocess_df(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocesa un DataFrame estandarizando los nombres de columna."""
    if df.empty:
        return df
    try:
        df.columns = df.iloc[0].astype(str).str.strip()
        return df.iloc[1:].copy()
    except Exception as e:
        st.error(f"Error durante el preprocesamiento de la hoja. Es posible que el formato no sea el esperado. Error: {e}")
        return pd.DataFrame()

# =============================================================================
# DATA MANAGER OPTIMIZADO
# =============================================================================

@st.cache_data(ttl=3600)
def _load_all_sheets(file_data: Any) -> Dict[str, pd.DataFrame]:
    """Carga todas las hojas de un archivo de Excel y las preprocesa."""
    sheets = {}
    if not file_data:
        return sheets
    try:
        file_buffer = io.BytesIO(file_data.getvalue())
        with pd.ExcelFile(file_buffer) as xls:
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                if not df.empty:
                    sheets[sheet_name] = _preprocess_df(df)
                else:
                    st.warning(f"La hoja '{sheet_name}' está vacía y no se pudo cargar.")
    except Exception as e:
        st.error(f"Error cargando el archivo de Excel. Asegúrate de que sea un archivo .xlsx válido. Error: {e}")
        return {}
    return sheets

class OptimizedDataManager:
    def __init__(self, uploaded_file: Any):
        self._cache = {}
        self._uploaded_file = uploaded_file
        self._ensure_cache_built()

    def _ensure_cache_built(self):
        if not self._cache and self._uploaded_file:
            self._cache = _load_all_sheets(self._uploaded_file)
        elif not self._uploaded_file:
             st.warning("⚠️ No se ha subido ningún archivo maestro.")

    def get_df(self, sheet_name: str) -> pd.DataFrame:
        df = self._cache.get(sheet_name, pd.DataFrame())
        if df.empty and st.session_state.debug_mode:
            st.warning(f"La hoja '{sheet_name}' no se pudo cargar o está vacía.")
        return df.copy()

    def get_jefes(self) -> List[str]:
        df = self.get_df("centros")
        try:
            if "Jefe de operaciones (Descripción)" in df.columns:
                return sorted(df["Jefe de operaciones (Descripción)"].dropna().unique().tolist())
            else:
                st.error("Columna 'Jefe de operaciones (Descripción)' no encontrada en la hoja 'centros'.")
                return []
        except Exception as e:
            st.error(f"Error al obtener la lista de jefes. Error: {e}")
            return []

    def get_imputaciones(self) -> List[str]:
        if self._uploaded_file:
            return [self._uploaded_file.name]
        return []

    def get_trabajadores_by_jefe(self, jefe_name: str) -> pd.DataFrame:
        df = self.get_df("trabajadores")
        return df.copy()

    def get_cod_crown(self, centro_preferente: str) -> Optional[int]:
        df = self.get_df("centros")
        try:
            if "Centro preferente (Códigos)" in df.columns and "Código" in df.columns:
                result = df[df['Centro preferente (Códigos)'] == centro_preferente]['Código'].values
                if result.size > 0:
                    return int(result[0])
            return None
        except Exception as e:
            st.error(f"Error al obtener el código Crown para el centro preferente {centro_preferente}. Error: {e}")
            return None

    def get_empresa_destino(self, cod_crown: int) -> Optional[str]:
        df = self.get_df("maestro_centros")
        try:
            if "ccentro" in df.columns and "dcentro" in df.columns:
                result = df[df["ccentro"] == str(cod_crown)]["dcentro"].values
                if result.size > 0:
                    return result[0]
            return None
        except Exception as e:
            st.error(f"Error al obtener la empresa de destino para el código Crown {cod_crown}. Error: {e}")
            return None

    def get_precios_incidencia(self, cod_reg_convenio: str, servicio: str) -> Tuple[float, float]:
        df = self.get_df("tarifas_incidencias")
        # Aquí iría la lógica para buscar en la hoja "tarifas_incidencias"
        # Por ahora, devolvemos valores por defecto
        return 15.0, 20.0

    def get_precio_nocturnidad(self, categoria: str, cod_reg_convenio: str) -> float:
        df = self.get_df("tarifas_incidencias")
        # Aquí iría la lógica para buscar el precio de nocturnidad
        # Por ahora, devolvemos un valor por defecto
        return 5.0

# =============================================================================
# GESTOR DE BASE DE DATOS
# =============================================================================

class DatabaseManager:
    def __init__(self, db_path='incidencias.db'):
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS incidencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabajador TEXT,
                imputacion_nomina TEXT,
                facturable TEXT,
                motivo TEXT,
                codigo_crown_origen TEXT,
                codigo_crown_destino TEXT,
                empresa_destino TEXT,
                incidencia_horas REAL,
                incidencia_precio REAL,
                nocturnidad_horas REAL,
                nocturnidad_precio REAL,
                traslados_total REAL,
                coste_hora REAL,
                fecha TEXT,
                observaciones TEXT,
                centro_preferente TEXT,
                nombre_jefe_ope TEXT,
                categoria TEXT,
                servicio TEXT,
                cod_reg_convenio TEXT,
                estado TEXT DEFAULT 'pending_supervisor_submission',
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_incidencia(self, incidencia: Incidencia):
        conn = sqlite3.connect(self.db_path)
        incidencia_dict = incidencia.to_dict()
        incidencia_dict['estado'] = 'pending_supervisor_submission'
        incidencia_dict['timestamp'] = datetime.now().isoformat()
        
        df = pd.DataFrame([incidencia_dict])
        df.to_sql('incidencias', conn, if_exists='append', index=False)
        conn.close()

    def get_incidencias_by_estado(self, estado: str) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT * FROM incidencias WHERE estado = '{estado}'"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def update_incidencias_estado(self, ids: List[int], new_estado: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            for id in ids:
                c.execute("UPDATE incidencias SET estado = ? WHERE id = ?", (new_estado, id))
            conn.commit()
        except Exception as e:
            st.error(f"Error al actualizar el estado de las incidencias. Error: {e}")
        finally:
            conn.close()

    def update_incidencia(self, incidencia_id: int, data: Dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            fields = ', '.join([f"{col} = ?" for col in data.keys()])
            values = list(data.values())
            values.append(incidencia_id)
            c.execute(f"UPDATE incidencias SET {fields} WHERE id = ?", values)
            conn.commit()
        except Exception as e:
            st.error(f"Error al guardar los cambios en la incidencia. Error: {e}")
        finally:
            conn.close()

# =============================================================================
# EXPORT MANAGER
# =============================================================================

class OptimizedExportManager:
    @staticmethod
    def export_to_excel(incidencias: List[Dict], sheet_name: Optional[str] = "Incidencias"):
        if not incidencias:
            st.warning("No hay incidencias para exportar.")
            return None

        df = pd.DataFrame(incidencias)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return buffer.getvalue()

# =============================================================================
# TABLA Y VISTAS DE USUARIO
# =============================================================================

class OptimizedTablaIncidencias:
    def __init__(self, data_manager: OptimizedDataManager):
        self._data_manager = data_manager
        self.column_mapping = {
            "trabajador": "Trabajador",
            "imputacion_nomina": "Imputación nómina",
            "facturable": "Facturable",
            "motivo": "Motivo",
            "codigo_crown_origen": "Código Crown Origen",
            "codigo_crown_destino": "Código Crown Destino",
            "empresa_destino": "Empresa Destino",
            "incidencia_horas": "Incidencia (horas)",
            "incidencia_precio": "Incidencia (precio)",
            "nocturnidad_horas": "Nocturnidad (horas)",
            "nocturnidad_precio": "Nocturnidad (precio)",
            "traslados_total": "Traslados (total)",
            "coste_hora": "Coste hora",
            "fecha": "Fecha",
            "observaciones": "Observaciones",
            "centro_preferente": "Centro Preferente",
            "nombre_jefe_ope": "Nombre Jefe Ope",
            "categoria": "Categoría",
            "servicio": "Servicio",
            "cod_reg_convenio": "Cod Reg Convenio",
            "estado": "Estado",
            "timestamp": "Timestamp"
        }
        self.inverse_mapping = {v: k for k, v in self.column_mapping.items()}

    def _actualizar_datos_empleado(self, incidencia: Incidencia, nombre_trabajador: str, selected_jefe: str) -> None:
        trabajadores_df = self._data_manager.get_df("trabajadores")
        try:
            trabajador_data = trabajadores_df[trabajadores_df["Nombre empleado"] == nombre_trabajador].iloc[0]
            
            incidencia.categoria = trabajador_data.get("Categoria", "N/A")
            incidencia.cod_reg_convenio = trabajador_data.get("Cod Reg Convenio", "N/A")
            incidencia.servicio = trabajador_data.get("Servicio", "N/A")
            incidencia.coste_hora = float(trabajador_data.get("coste hora \nempresa", 0.0))
            incidencia.nombre_jefe_ope = selected_jefe
        except IndexError:
            st.error(f"Error: No se encontraron datos para el trabajador '{nombre_trabajador}'.")
        except KeyError as e:
            st.error(f"Error: Una o más columnas del trabajador no se encontraron. Revisa la hoja 'trabajadores'. Error: {e}")

    def render_supervisor_view(self):
        st.subheader("📋 Registro de Incidencias")
        
        # Obtener datos de trabajadores para el selectbox
        trabajadores_df = self._data_manager.get_df("trabajadores")
        trabajadores = sorted(trabajadores_df["Nombre empleado"].unique().tolist()) if "Nombre empleado" in trabajadores_df.columns else []
        motivos_df = self._data_manager.get_df("cuenta_motivos")
        motivos = motivos_df['Motivo'].unique().tolist() if 'Motivo' in motivos_df.columns else []

        with st.form("form_incidencia"):
            selected_trabajador = st.selectbox("Seleccione Trabajador", options=[""] + trabajadores)
            
            if selected_trabajador:
                # Mostrar campos de formulario cuando se selecciona un trabajador
                col1, col2 = st.columns(2)
                with col1:
                    fecha = st.date_input("Fecha")
                    motivo = st.selectbox("Motivo", options=[""] + motivos)
                    incidencia_horas = st.number_input("Horas de Incidencia", min_value=0.0, step=0.5)
                    traslados_total = st.number_input("Total Traslados (€)", min_value=0.0, step=0.1)
                with col2:
                    facturable = st.selectbox("Facturable", ["Sí", "No"])
                    nocturnidad_horas = st.number_input("Horas de Nocturnidad", min_value=0.0, step=0.5)
                    centro_preferente = st.text_input("Centro Preferente (Código)")
                    observaciones = st.text_area("Observaciones")

            submit_button = st.form_submit_button("➕ Añadir a la tabla")

        if submit_button and selected_trabajador:
            incidencia = Incidencia()
            incidencia.trabajador = selected_trabajador
            incidencia.imputacion_nomina = st.session_state.selected_imputacion
            incidencia.facturable = facturable
            incidencia.motivo = motivo
            incidencia.incidencia_horas = incidencia_horas
            incidencia.nocturnidad_horas = nocturnidad_horas
            incidencia.traslados_total = traslados_total
            incidencia.fecha = datetime.combine(fecha, datetime.min.time())
            incidencia.observaciones = observaciones
            incidencia.centro_preferente = centro_preferente

            self._actualizar_datos_empleado(incidencia, selected_trabajador, st.session_state.selected_jefe)
            
            # Cálculo de precios automáticos
            incidencia.incidencia_precio, incidencia.nocturnidad_precio = self._data_manager.get_precios_incidencia(incidencia.cod_reg_convenio, incidencia.servicio)

            # Obtener códigos Crown y empresa
            if centro_preferente:
                incidencia.codigo_crown_origen = self._data_manager.get_cod_crown(centro_preferente)
                if incidencia.codigo_crown_origen:
                    incidencia.empresa_destino = self._data_manager.get_empresa_destino(incidencia.codigo_crown_origen)

            st.session_state.db_manager.add_incidencia(incidencia)
            st.success(f"Incidencia para {selected_trabajador} añadida a la tabla.")
            st.rerun()

        # Vista y envío de incidencias para el supervisor
        st.subheader("📝 Incidencias Pendientes de Envío")
        df_pendientes = st.session_state.db_manager.get_incidencias_by_estado('pending_supervisor_submission')
        
        if df_pendientes.empty:
            st.info("No hay incidencias pendientes de envío al jefe.")
            return

        df_pendientes = df_pendientes[df_pendientes["nombre_jefe_ope"] == st.session_state.selected_jefe]

        edited_df = st.data_editor(
            df_pendientes.rename(columns=self.column_mapping),
            key="supervisor_editor",
            use_container_width=True,
            disabled=("id", "timestamp", "estado")
        )

        if st.button("➡️ Enviar seleccionadas al Jefe"):
            try:
                # Obtener los IDs de las filas editadas
                ids_a_enviar = edited_df[edited_df.index.isin(st.session_state.supervisor_editor['edited_rows'])]['id'].tolist()
                
                # Actualizar el estado de las incidencias seleccionadas
                st.session_state.db_manager.update_incidencias_estado(ids_a_enviar, 'pending_jefe_validation')
                st.success(f"¡{len(ids_a_enviar)} incidencias enviadas al jefe para su validación!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al enviar las incidencias. Por favor, revisa el formato de los datos. Error: {e}")

    def render_jefe_view(self, selected_jefe: str):
        db_manager = st.session_state.db_manager
        df_incidencias = db_manager.get_incidencias_by_estado('pending_jefe_validation')
        df_incidencias = df_incidencias[df_incidencias["nombre_jefe_ope"] == selected_jefe]

        if df_incidencias.empty:
            st.info("No hay incidencias pendientes de validación para este jefe.")
            return
            
        st.subheader("📝 Revisión y Validación de Incidencias")
        st.write(f"Incidencias pendientes para {selected_jefe}:")
        
        edited_df = st.data_editor(
            df_incidencias.rename(columns=self.column_mapping).reset_index(drop=True),
            num_rows="dynamic",
            key="jefe_validation_editor"
        )
        
        if st.button("✅ Enviar Incidencias a RRHH"):
            try:
                ids_to_update = edited_df['id'].tolist()
                db_manager.update_incidencias_estado(ids_to_update, 'ready_for_hr')
                
                edited_rows_data = [
                    edited_df.loc[edited_df['id'] == incidencia_id].to_dict('records')[0]
                    for incidencia_id in ids_to_update
                ]
                
                send_email_to_hr(pd.DataFrame(edited_rows_data))
                st.success("¡Incidencias enviadas a RRHH!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al enviar. Error: {e}")

        if st.button("💾 Guardar cambios"):
            try:
                for index, row_data in st.session_state.jefe_validation_editor['edited_rows'].items():
                    incidencia_id = edited_df.loc[index, self.inverse_mapping['id']]
                    updated_data = {self.inverse_mapping[key]: value for key, value in row_data.items()}
                    db_manager.update_incidencia(incidencia_id, updated_data)
                st.success("¡Cambios guardados!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar los cambios. Error: {e}")

def send_email_to_hr(df_incidencias: pd.DataFrame):
    st.info("Simulando el envío de correo electrónico a RRHH...")
    st.write("Datos que serían enviados:")
    st.dataframe(df_incidencias)

# =============================================================================
# APLICACIÓN PRINCIPAL OPTIMIZADA
# =============================================================================

class OptimizedIncidenciasApp:
    def __init__(self):
        if 'app_initialized_optimized' not in st.session_state:
            st.session_state.app_initialized_optimized = True
            st.session_state.selected_jefe = ""
            st.session_state.selected_imputacion = ""
            st.session_state.uploaded_file = None
            st.session_state.debug_mode = False
    
    def run(self):
        st.title("📋 App de Registro de Incidencias")
        st.caption("Versión Optimizada para un Flujo de Aprobación")

        st.sidebar.header("📁 Carga del Archivo Maestro")
        uploaded_file = st.sidebar.file_uploader(
            "Sube el archivo 'maestros.xlsx'",
            type=["xlsx"],
            key="maestros_excel"
        )
        
        if uploaded_file != st.session_state.uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            if 'data_manager' in st.session_state:
                del st.session_state.data_manager
        
        if not st.session_state.uploaded_file:
            st.warning("⚠️ Por favor, sube el archivo maestro de Excel para continuar.")
            return

        if 'data_manager' not in st.session_state:
            with st.spinner("Inicializando aplicación y procesando datos..."):
                st.session_state.data_manager = OptimizedDataManager(st.session_state.uploaded_file)
                st.session_state.db_manager = DatabaseManager()

        data_manager = st.session_state.data_manager
        
        jefes = data_manager.get_jefes()
        imputaciones = data_manager.get_imputaciones()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.selectbox("Imputación Nómina", imputaciones, key="selected_imputacion")
        with col2:
            st.selectbox("Nombre Jefe Ope", [""] + jefes, key="selected_jefe")
        
        if not st.session_state.selected_jefe or not st.session_state.selected_imputacion:
            st.warning("⚠️ Por favor, selecciona la imputación de nómina y un jefe para comenzar.")
            return

        st.subheader("Seleccionar Rol")
        rol = st.selectbox("Eres un:", ["Supervisor", "Jefe"], key="rol_selector")

        tabla_optimizada = OptimizedTablaIncidencias(data_manager)

        if rol == "Supervisor":
            tabla_optimizada.render_supervisor_view()
        elif rol == "Jefe":
            tabla_optimizada.render_jefe_view(st.session_state.selected_jefe)
    
if __name__ == "__main__":
    st.set_page_config(
        page_title="Registro de Incidencias",
        page_icon="📋",
        layout="wide"
    )
    app = OptimizedIncidenciasApp()
    app.run()
