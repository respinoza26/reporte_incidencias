

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