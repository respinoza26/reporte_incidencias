-----

### README.md

Hay un priblema porque se queda deteneida con el ingrso de inputacion y jefe






### Plantilla de Registro de Incidencias con Streamlit 📋

Este proyecto es una aplicación web interactiva desarrollada con **Streamlit** para simplificar y centralizar el registro de incidencias de personal. Está diseñada para ser utilizada por jefes de operaciones, permitiéndoles gestionar incidencias de su personal a cargo y también de personal de otros centros.

#### Características Principales

  * **Interfaz Intuitiva**: Utiliza un menú lateral (`st.sidebar`) para la configuración global (selección de jefe y mes de imputación) y la sección principal para el registro de datos, lo que permite una navegación limpia y eficiente.
  * **Gestión de Datos por Roles**: La aplicación distingue entre **Centros Propios** (personal bajo el cargo directo del jefe) y **Otros Centros** (personal de otros departamentos), ofreciendo una experiencia de usuario optimizada para cada caso.
  * **Editor de Datos Interactivo**: Las tablas se gestionan con `st.data_editor`, lo que permite a los usuarios añadir, editar y eliminar filas directamente en la interfaz. La aplicación maneja de manera inteligente la actualización de datos de empleados al seleccionar un trabajador.
  * **Validación de Datos en Tiempo Real**: El sistema valida la información antes de la exportación, asegurando que todos los campos obligatorios estén completos y sean coherentes.
  * **Exportación Sencilla**: Permite descargar todas las incidencias válidas en un único archivo `.csv`, listo para su uso en hojas de cálculo o sistemas de gestión de nómina.
  * **Resumen Financiero**: Muestra un resumen en tiempo real del costo total de las incidencias, nocturnidad y traslados.
  * **Manejo de Sesión**: Utiliza `st.session_state` para mantener el estado de la aplicación a través de los `reruns` de Streamlit, lo que hace que la experiencia de usuario sea fluida.

-----

### Estructura del Código

El código está organizado en varias clases y funciones para mejorar la modularidad y la legibilidad.

  * `preprocess_*` funciones: Encargadas de la limpieza y transformación inicial de los datos de las diferentes hojas del archivo `maestros.xlsx`.
  * `Incidencia` (dataclass): Define el modelo de datos para una incidencia, con métodos para convertir a y desde un diccionario, y para validar sus campos.
  * `DataManager`: Gestiona la carga y el preprocesamiento de los datos maestros desde el archivo `maestros.xlsx`. Utiliza `st.cache_data` para evitar recargar los archivos en cada interacción.
  * `BaseTablaIncidencias` (clase abstracta): Proporciona la estructura común para las clases de tabla de incidencias, definiendo métodos abstractos y propiedades compartidas.
  * `TablaCentrosPropios`: Hereda de `BaseTablaIncidencias`. Gestiona la lógica específica para las tablas de los centros bajo el cargo del jefe, permitiendo añadir y eliminar tablas por centro.
  * `TablaOtrosCentros`: Hereda de `BaseTablaIncidencias`. Gestiona la tabla unificada para las incidencias de trabajadores de otros centros.
  * `ExportManager`: Contiene un método estático para convertir la lista de objetos `Incidencia` a un `DataFrame` de Pandas y luego a una cadena de texto en formato CSV.
  * `IncidenciasApp`: La clase principal que orquesta toda la aplicación. Contiene el método `run()` que define el *layout* y la lógica de la interfaz de usuario de Streamlit.

-----

### Cómo Ejecutar la Aplicación

1.  **Clonar el repositorio**:

    ```bash
    git clone [URL_DEL_REPOSITORIO]
    cd [nombre_del_repositorio]
    ```

2.  **Preparar el entorno virtual e instalar dependencias con `uv`**:
    Como me has recordado que usas **uv**, el proceso es más rápido y sencillo. Primero, asegúrate de tener `uv` instalado. Si no lo tienes:

    ```bash
    pip install uv
    ```

    Luego, crea el entorno virtual e instala las dependencias:

    ```bash
    uv venv
    source .venv/bin/activate  # En Windows: .venv\Scripts\activate
    uv pip install streamlit pandas numpy openpyxl
    ```

3.  **Asegurar la estructura de archivos**:
    Asegúrate de que tienes una carpeta `data` y que el archivo `maestros.xlsx` está dentro de ella, tal como lo espera el `DataManager`.

4.  **Ejecutar la aplicación**:

    ```bash
    streamlit run app1.py
    ```

La aplicación se abrirá automáticamente en tu navegador web.