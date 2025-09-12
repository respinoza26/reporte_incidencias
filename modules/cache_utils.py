


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