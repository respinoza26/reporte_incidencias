

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
