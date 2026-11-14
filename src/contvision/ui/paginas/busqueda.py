"""Búsqueda de contenedores por código (B3.2–B3.3)."""

import streamlit as st

from contvision.db import queries as q
from contvision.lectura import normalizar_codigo
from contvision.ui import componentes as ui
from contvision.ui import navegacion
from contvision.ui.state import conexion


def pagina_busqueda() -> None:
    ui.cabecera("Búsqueda", "Buscar contenedores por código")
    ui.pendiente("B3.2–B3.3", "búsqueda aproximada (M2-B), resaltado de diferencias y filtro por almacén")

    texto = normalizar_codigo(st.text_input("Código o prefijo", placeholder="MSCU123…"))
    if not texto:
        return
    resultados = q.contenedores.listar(conexion(), prefijo=texto, limite=50)
    if not resultados:
        st.caption("Sin resultados.")
    for c in resultados:
        navegacion.enlace_contenedor(c.codigo, f"{c.codigo} · {c.almacen_actual or 'fuera de almacén'}")
