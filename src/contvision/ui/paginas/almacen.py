"""Almacén (oculta en el menú, se llega con ?almacen=<id>) (B3.10).

Métricas, entradas/salidas por día, reparto por propietario, contenedores
presentes, últimos eventos y cámaras del almacén.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from contvision.config import ZONA_HORARIA
from contvision.db import queries as q
from contvision.ui import componentes as ui
from contvision.ui import feed, navegacion
from contvision.ui.state import conexion

DIAS_GRAFICA = 30
MAX_PROPIETARIOS = 8
N_EVENTOS = 20
_ZONA = ZoneInfo(ZONA_HORARIA)


def pagina_almacen() -> None:
    conn = conexion()
    almacen_id = navegacion.param_int("almacen")
    almacen = q.almacenes.obtener(conn, almacen_id) if almacen_id is not None else None
    if almacen is None:
        ui.cabecera("Almacén")
        st.error("Almacén no encontrado. Elige uno en el mapa.", icon=":material/search_off:")
        st.page_link(navegacion.pagina("mapa"), label="Ir al mapa", icon=":material/map:")
        return

    c_volver, c_refresco = st.columns([5, 1], vertical_alignment="center")
    c_volver.page_link(navegacion.pagina("mapa"), label="Volver al mapa", icon=":material/arrow_back:")
    c_refresco.button("Actualizar", icon=":material/refresh:", width="stretch",
                      help="Vuelve a consultar los datos del almacén")   # cualquier click relanza la página
    detalle = f"{almacen.tipo.capitalize()} · {almacen.lat:.4f}, {almacen.lon:.4f}"
    if almacen.descripcion:
        detalle += f" · {almacen.descripcion}"
    ui.cabecera(almacen.nombre, detalle)

    ahora = datetime.now(UTC)
    _kpis(conn, almacen.id)

    col_flujo, col_prop = st.columns([1.7, 1], gap="medium")
    with col_flujo, st.container(border=True, height="stretch"):
        _entradas_salidas(conn, almacen.id)
    with col_prop, st.container(border=True, height="stretch"):
        _propietarios(conn, almacen.id)

    _presentes(conn, almacen.id, ahora)

    col_eventos, col_camaras = st.columns([1.7, 1], gap="medium")
    with col_eventos, st.container(border=True):
        st.markdown("**Últimos eventos**")
        eventos = q.eventos.feed(conn, limite=N_EVENTOS, almacen_id=almacen.id)
        with st.container(height=330, border=False):
            st.html(feed.html_feed(eventos, set(), ahora))
    with col_camaras, st.container(border=True):
        _camaras(conn, almacen.id, ahora)


# ------------------------------------------------------------------- métricas

def _kpis(conn, almacen_id: int) -> None:
    k = q.almacenes.kpis(conn, almacen_id, feed.inicio_dia_utc(0))
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1.container(border=True, height="stretch"):
        st.metric("Contenedores dentro", _miles(k.presentes))
    with c2.container(border=True, height="stretch"):
        if k.capacidad:
            st.metric("Ocupación", f"{k.ocupacion:.0%}".replace("%", " %"))
            st.progress(min(k.ocupacion, 1.0), text=f"de {_miles(k.capacidad)} plazas")
            if k.ocupacion > 1:
                st.caption(f":red[:material/warning: {_miles(k.presentes - k.capacidad)} por encima de la capacidad]")
        else:
            st.metric("Ocupación", "—", help="Este almacén no tiene capacidad definida")
    with c3.container(border=True, height="stretch"):
        st.metric("Entradas hoy", _miles(k.entradas_hoy))
    with c4.container(border=True, height="stretch"):
        st.metric("Salidas hoy", _miles(k.salidas_hoy))
    with c5.container(border=True, height="stretch"):
        st.metric(
            "Estancia media", _duracion(k.estancia_media_horas),
            help=f"Media de {_miles(k.estancias_cerradas)} estancias ya cerradas con entrada y salida "
                 "leídas (no cuenta las inferidas ni los contenedores que siguen dentro).",
        )


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _duracion(horas: float | None) -> str:
    if horas is None:
        return "—"
    if horas < 1:
        return f"{horas * 60:.0f} min"
    if horas < 48:
        return f"{horas:.1f} h".replace(".", ",")
    return f"{horas / 24:.1f} d".replace(".", ",")


# ------------------------------------------------------------------- gráficas

def _entradas_salidas(conn, almacen_id: int) -> None:
    st.markdown(f"**Entradas y salidas por día** · últimos {DIAS_GRAFICA} días")
    hoy = datetime.now(_ZONA).date()
    dias = [hoy - timedelta(days=i) for i in range(DIAS_GRAFICA - 1, -1, -1)]
    filas = {f["dia"]: f for f in q.almacenes.entradas_salidas_por_dia(conn, almacen_id, dias[0].isoformat())}
    tabla = pd.DataFrame(
        {"Entradas": [filas.get(d.isoformat(), {}).get("entradas", 0) for d in dias],
         "Salidas": [filas.get(d.isoformat(), {}).get("salidas", 0) for d in dias]},
        index=pd.to_datetime(dias),
    )
    if tabla.to_numpy().sum() == 0:
        st.caption("Sin movimientos en este periodo.")
        return
    st.bar_chart(tabla, color=["#2ea043", "#8c8c8c"], stack=False, height=260, x_label="", y_label="")


def _propietarios(conn, almacen_id: int) -> None:
    st.markdown("**Contenedores dentro por propietario**")
    reparto = q.almacenes.reparto_propietarios(conn, almacen_id)   # ya viene de mayor a menor
    if not reparto:
        st.caption("No hay contenedores dentro ahora mismo.")
        return
    filas = reparto[:MAX_PROPIETARIOS]
    resto = sum(r["n"] for r in reparto[MAX_PROPIETARIOS:])
    if resto:
        filas = [*filas, {"propietario": "Otros", "n": resto}]
    tabla = pd.DataFrame(filas).rename(columns={"propietario": "Propietario", "n": "Contenedores"})
    st.bar_chart(tabla, x="Propietario", y="Contenedores", horizontal=True, sort=False,
                 height=260, x_label="", y_label="")


# ------------------------------------------------------- contenedores presentes

def _presentes(conn, almacen_id: int, ahora: datetime) -> None:
    presentes = q.almacenes.presentes(conn, almacen_id)   # los que llevan más tiempo, primero
    total = len(presentes)
    cab, buscador, c_abrir = st.columns([3, 1.2, 1.2], vertical_alignment="bottom")
    cab.subheader(f"Contenedores presentes · {_miles(total)}", anchor=False)
    filtro = buscador.text_input("Filtrar por código", placeholder="Filtrar por código…",
                                 label_visibility="collapsed").strip().upper()
    if filtro:
        presentes = [e for e in presentes if filtro in e.codigo]

    # La clave incluye el filtro: al cambiarlo, la fila seleccionada se descarta (apuntaría a otro contenedor).
    clave = f"alm_presentes_{almacen_id}_{filtro}"
    try:
        fila = st.session_state[clave]["selection"]["rows"][0]
        elegido = presentes[fila].codigo
    except (KeyError, IndexError, TypeError):
        elegido = None
    if c_abrir.button(f"Abrir ficha de {elegido}" if elegido else "Abrir ficha", icon=":material/package_2:",
                      type="primary" if elegido else "secondary", disabled=elegido is None, width="stretch",
                      help=None if elegido else "Selecciona antes un contenedor en la tabla"):
        navegacion.ir_a_contenedor(elegido)

    if not presentes:
        st.caption("Ningún contenedor coincide." if filtro else "No hay contenedores dentro ahora mismo.")
        return

    tabla = pd.DataFrame([{
        "Código": e.codigo,
        "Propietario": e.codigo[:3],
        "Dentro desde": feed.a_datetime(e.entrada_ts).astimezone(_ZONA).replace(tzinfo=None),
        "Días dentro": (ahora - feed.a_datetime(e.entrada_ts)).total_seconds() / 86400,
        "Entrada": "inferida" if e.entrada_inferida else "leída",
    } for e in presentes])
    st.dataframe(
        tabla, hide_index=True, height=min(420, 38 + 35 * len(tabla)),
        key=clave, on_select="rerun", selection_mode="single-row",
        column_config={
            "Dentro desde": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Días dentro": st.column_config.NumberColumn(
                format="%.1f", help="Tiempo que lleva dentro del almacén, en días. Pulsa la cabecera para ordenar."),
            "Entrada": st.column_config.TextColumn(
                help="«inferida»: no se leyó en la cámara de entrada; se vio por primera vez en una interior"),
        },
    )
    if filtro:
        st.caption(f"{_miles(len(presentes))} de {_miles(total)} contenedores coinciden con «{filtro}».")


# -------------------------------------------------------------------- cámaras

def _camaras(conn, almacen_id: int, ahora: datetime) -> None:
    st.markdown("**Cámaras**")
    camaras = q.almacenes.fuentes(conn, almacen_id)
    if not camaras:
        st.caption("Este almacén no tiene cámaras registradas.")
        return
    tabla = pd.DataFrame([{
        "Cámara": c.nombre,
        "Tipo": c.tipo.capitalize(),
        "Activa": bool(c.activa),
        "Lecturas": c.n_avistamientos,
        "Última lectura": feed.hace(c.ultima_lectura, ahora) if c.ultima_lectura else "nunca",
    } for c in camaras])
    st.dataframe(tabla, hide_index=True, height=min(330, 38 + 35 * len(tabla)),
                 column_config={"Activa": st.column_config.CheckboxColumn(disabled=True)})
