import streamlit as st
from typing import List, Dict

class ValidationManager:
    @staticmethod
    def init_session_state():
        if 'app_initialized_minimalist' not in st.session_state:
            st.session_state.app_initialized_minimalist = True
            st.session_state.selected_jefe = ""
            st.session_state.selected_imputacion = ""
            st.session_state.incidencias = []
            st.session_state.validation_state = {
                'jefe_validated': False,
                'director_validated': False
            }
            st.session_state.incidencias_validadas = []

    @staticmethod
    def is_jefe_validated() -> bool:
        return st.session_state.validation_state.get('jefe_validated', False)

    @staticmethod
    def is_director_validated() -> bool:
        return st.session_state.validation_state.get('director_validated', False)

    @staticmethod
    def set_jefe_validated(status: bool):
        st.session_state.validation_state['jefe_validated'] = status
        if status:
            # Si el jefe valida, guarda una copia de las incidencias para el director
            st.session_state.incidencias_validadas = st.session_state.incidencias.copy()
            
    @staticmethod
    def set_director_validated(status: bool):
        st.session_state.validation_state['director_validated'] = status
        
    @staticmethod
    def reset_state():
        st.session_state.validation_state['jefe_validated'] = False
        st.session_state.validation_state['director_validated'] = False
        st.session_state.incidencias = []
        st.session_state.selected_jefe = ""
        st.session_state.selected_imputacion = ""