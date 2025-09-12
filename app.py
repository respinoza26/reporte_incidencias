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
import streamlit as st
from modules.models import Incidencia
from modules.data_manager import OptimizedDataManager
from modules.table_component import OptimizedTablaIncidencias
from modules.export_manager import OptimizedExportManager
from config.settings import *

st.set_page_config(
    page_title="Registro de Incidencias",
    page_icon="📋",
    layout="wide"
)

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