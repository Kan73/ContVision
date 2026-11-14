"""Revisión de lecturas dudosas (B3.6′)."""

import streamlit as st

from contvision.db import queries as q
from contvision.ui import componentes as ui
from contvision.ui.state import conexion


def pagina_revision() -> None:
    ui.cabecera("Revisión", "Lecturas dudosas pendientes de corregir")
    n = len(q.contenedores.pendientes_revision(conexion()))
    st.metric("Pendientes", n)
    ui.pendiente("B3.6′", "corrección manual con `registrar_correccion()` y recálculo de estancias")
