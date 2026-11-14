"""Almacén (oculta en el menú, se llega con ?almacen=<id>) (B3.10)."""

import streamlit as st

from contvision.db import queries as q
from contvision.ui import componentes as ui
from contvision.ui import navegacion
from contvision.ui.state import conexion


def pagina_almacen() -> None:
    conn = conexion()
    almacen_id = navegacion.param_int("almacen")
    almacen = q.almacenes.obtener(conn, almacen_id) if almacen_id is not None else None
    if almacen is None:
        ui.cabecera("Almacén")
        st.error("Almacén no encontrado. Elige uno en el mapa.", icon=":material/search_off:")
        st.page_link(navegacion.pagina("mapa"), label="Ir al mapa", icon=":material/map:")
        return

    ui.cabecera(almacen.nombre, f"{almacen.tipo.capitalize()} · {almacen.lat:.4f}, {almacen.lon:.4f}")
    c1, c2 = st.columns(2)
    c1.metric("Presentes", almacen.presentes)
    c2.metric("Ocupación", f"{almacen.ocupacion:.0%}" if almacen.ocupacion is not None else "—")

    ui.pendiente("B3.10", "entradas/salidas por día, reparto por propietario y eventos del almacén")
    st.subheader("Contenedores presentes")
    for e in q.almacenes.presentes(conn, almacen.id)[:20]:
        navegacion.enlace_contenedor(e.codigo, f"{e.codigo} · desde {ui.fecha_local(e.entrada_ts)}")
