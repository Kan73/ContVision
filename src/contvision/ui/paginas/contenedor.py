"""Ficha de contenedor (oculta en el menú, se llega con ?codigo=<código>) (B3.4′)."""

import streamlit as st

from contvision.db import queries as q
from contvision.ui import componentes as ui
from contvision.ui import navegacion
from contvision.ui.state import conexion


def pagina_contenedor() -> None:
    conn = conexion()
    codigo = st.query_params.get("codigo", "")
    cont = q.contenedores.obtener(conn, codigo) if codigo else None
    if cont is None:
        ui.cabecera("Contenedor")
        st.error(f"Contenedor no encontrado: {codigo or '(sin código)'}", icon=":material/search_off:")
        st.page_link(navegacion.pagina("busqueda"), label="Ir a búsqueda", icon=":material/search:")
        return

    ui.cabecera(cont.codigo, f"Propietario {cont.propietario} · categoría {cont.categoria}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avistamientos", cont.n_avistamientos)
    c2.metric("Última vez", ui.fecha_local(cont.ultima_vez))
    c3.metric("Ubicación", cont.almacen_actual or "Fuera")
    if cont.almacen_actual_id is not None:
        navegacion.enlace_almacen(cont.almacen_actual_id, f"Ver {cont.almacen_actual}")

    ui.pendiente("B3.4′", "avistamientos, recorrido por almacenes y mini-mapa")
