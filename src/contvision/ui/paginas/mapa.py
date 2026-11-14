"""Mapa: un círculo por almacén, ficha rápida al seleccionarlo y tabla de respaldo (B3.9).

Todos los círculos miden lo mismo en pantalla, a cualquier zoom. El color indica
la ocupación o (según el selector) la proporción de avisos de las últimas 24 h.

La selección llega del mapa o de la tabla. El objeto ``Deck`` no cambia al
seleccionar (la ficha va aparte), para que el mapa no se recentre en cada rerun.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from math import log2

import pandas as pd
import pydeck as pdk
import streamlit as st

from contvision.config import ruta_bd
from contvision.db import queries as q
from contvision.db.queries._modelos import AlmacenMapa, Flujo
from contvision.ui import componentes as ui
from contvision.ui import feed, navegacion
from contvision.ui.state import conexion

TTL_S = 30                      # los datos del mapa se recalculan como mucho cada 30 s
CAPA_ALMACENES = "almacenes"    # id de la capa: necesario para leer la selección
CLAVE_MAPA, CLAVE_TABLA = "mapa_deck", "mapa_tabla"
RADIO_PX = 11                   # radio fijo de cada punto, en píxeles de pantalla

VERDE, AMBAR, ROJO, GRIS = [46, 160, 67], [230, 140, 30], [220, 60, 60], [140, 140, 140]
MODOS = {"ocupacion": "Ocupación", "avisos": "Avisos 24 h"}
# (límite superior exclusivo, color, texto de la leyenda)
ESCALA = {
    "ocupacion": [(0.70, VERDE, "< 70 %"), (0.90, AMBAR, "70–90 %"), (float("inf"), ROJO, "≥ 90 %")],
    "avisos": [(0.05, VERDE, "< 5 % de avisos"), (0.10, AMBAR, "5–10 %"), (float("inf"), ROJO, "≥ 10 %")],
}
SIN_DATO = {"ocupacion": "sin capacidad definida", "avisos": "sin eventos"}


# ---------------------------------------------------------------------- datos

@st.cache_data(ttl=TTL_S, show_spinner=False)
def _datos(ruta: str) -> list[AlmacenMapa]:
    ahora = datetime.now(UTC)
    return q.almacenes.resumen_mapa(conexion(), feed.inicio_dia_utc(0), feed.iso_utc(ahora - timedelta(hours=24)))


@st.cache_data(ttl=TTL_S, show_spinner=False)
def _flujos(ruta: str) -> list[Flujo]:
    hace_30d = feed.iso_utc(datetime.now(UTC) - timedelta(days=30))
    return q.almacenes.flujos(conexion(), hace_30d)


def _valor(a: AlmacenMapa, modo: str) -> float | None:
    return a.ocupacion if modo == "ocupacion" else a.tasa_avisos


def _color(a: AlmacenMapa, modo: str) -> list[int]:
    valor = _valor(a, modo)
    if valor is None:
        return GRIS
    return next(color for limite, color, _ in ESCALA[modo] if valor < limite)


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.0%}".replace("%", " %")


# ------------------------------------------------------------------ selección

def id_de_mapa(estado) -> int | None:
    """Id del almacén pulsado en el mapa, a partir del estado del ``st.pydeck_chart``."""
    try:
        objetos = estado["selection"]["objects"].get(CAPA_ALMACENES) or []
        return int(objetos[0]["id"]) if objetos else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def id_de_tabla(estado, ids: list[int]) -> int | None:
    """Id del almacén de la fila seleccionada (las filas se identifican por su posición original)."""
    try:
        filas = estado["selection"]["rows"]
        return ids[filas[0]] if filas else None
    except (KeyError, TypeError, IndexError, AttributeError):
        return None


def _seleccionado(ids: list[int]) -> int | None:
    """Manda el último control que haya cambiado (mapa o tabla).

    Se lee de ``session_state`` antes de dibujar, porque la ficha va por encima de la tabla.
    Hay dos casos en los que los controles «cambian» sin que el usuario haya hecho nada,
    y entonces se conserva la selección que había:

    - al volver de otra página, Streamlit ha borrado el estado de los controles
      (sus claves no están en ``session_state``);
    - si cambia la lista de almacenes, la fila seleccionada de la tabla pasa a apuntar a otro.
    """
    ss = st.session_state
    en_mapa = id_de_mapa(ss.get(CLAVE_MAPA))
    en_tabla = id_de_tabla(ss.get(CLAVE_TABLA), ids)
    recien_llegado = CLAVE_MAPA not in ss and CLAVE_TABLA not in ss
    lista_cambiada = ss.get("_mapa_ids") not in (None, ids)
    if not (recien_llegado or lista_cambiada):
        if en_mapa != ss.get("_mapa_prev"):
            ss["mapa_sel"] = en_mapa
        elif en_tabla != ss.get("_tabla_prev"):
            ss["mapa_sel"] = en_tabla
    ss["_mapa_prev"], ss["_tabla_prev"], ss["_mapa_ids"] = en_mapa, en_tabla, list(ids)
    return ss.get("mapa_sel") if ss.get("mapa_sel") in ids else None


# ----------------------------------------------------------------------- mapa

def _deck(almacenes: list[AlmacenMapa], modo: str, flujos: list[Flujo]) -> pdk.Deck:
    puntos = [{
        "id": a.id,
        "t_nombre": escape(a.nombre),   # el tooltip se inserta como HTML
        "lon": a.lon,
        "lat": a.lat,
        "color": _color(a, modo) + [215],
        # Textos del tooltip, ya formateados
        "t_dentro": f"{a.presentes:,}".replace(",", "."),
        "t_ocupacion": _pct(a.ocupacion) if a.capacidad else "sin capacidad definida",
        "t_entradas": a.entradas_hoy,
        "t_avisos": f"{a.avisos_24h} ({_pct(a.tasa_avisos)})" if a.eventos_24h else "0",
    } for a in almacenes]

    capas = []
    if flujos:
        pos = {a.id: [a.lon, a.lat] for a in almacenes}
        max_n = max(f.n for f in flujos)
        capas.append(pdk.Layer(
            "ArcLayer", id="traslados",
            # Ida y vuelta entre dos almacenes se inclinan a lados opuestos para que no se tapen.
            data=[{"origen": pos[f.origen_id], "destino": pos[f.destino_id], "ancho": 1 + 7 * f.n / max_n,
                   "inclinacion": 20 if f.origen_id < f.destino_id else -20}
                  for f in flujos if f.origen_id in pos and f.destino_id in pos],
            get_source_position="origen", get_target_position="destino", get_width="ancho",
            get_tilt="inclinacion",
            get_source_color=[56, 132, 255, 120], get_target_color=[150, 100, 230, 200],
            pickable=False,
        ))
    capas.append(pdk.Layer(
        "ScatterplotLayer", id=CAPA_ALMACENES, data=puntos,
        # Ojo: pydeck trata las cadenas como expresiones; un texto literal va con comillas dentro.
        get_position="[lon, lat]", get_radius=RADIO_PX, radius_units='"pixels"',
        get_fill_color="color", get_line_color=[255, 255, 255, 230], line_width_min_pixels=1.5, stroked=True,
        pickable=True, auto_highlight=True,
    ))

    return pdk.Deck(
        layers=capas,
        initial_view_state=_vista(almacenes),
        map_style=None,   # el estilo del mapa sigue al tema de Streamlit
        tooltip={
            "html": "<b>{t_nombre}</b><br/>{t_dentro} contenedores dentro · ocupación {t_ocupacion}"
                    "<br/>{t_entradas} entradas hoy · {t_avisos} avisos en 24 h",
            "style": {"fontSize": "13px", "borderRadius": "6px", "padding": "8px 10px"},
        },
    )


def _vista(almacenes: list[AlmacenMapa]) -> pdk.ViewState:
    """Encuadre fijo que contiene todos los almacenes (no depende de la selección)."""
    lats, lons = [a.lat for a in almacenes], [a.lon for a in almacenes]
    # Grados que deben caber: el mapa es más ancho que alto, así que la longitud pesa menos.
    extension = max(max(lats) - min(lats), (max(lons) - min(lons)) * 0.45, 0.02)
    zoom = max(2.0, min(11.0, log2(360 / extension) + 0.1))   # ≈ 5,6 para la península
    return pdk.ViewState(latitude=(max(lats) + min(lats)) / 2, longitude=(max(lons) + min(lons)) / 2,
                         zoom=round(zoom, 1), pitch=0)


def _leyenda(modo: str) -> str:
    def punto(color, texto):
        return (f'<span class="cv-ley"><span class="cv-ley-punto" style="background: rgb({color[0]},{color[1]},'
                f'{color[2]})"></span>{texto}</span>')
    partes = [punto(color, texto) for _, color, texto in ESCALA[modo]] + [punto(GRIS, SIN_DATO[modo])]
    return '<div class="cv-leyenda">' + "".join(partes) + "</div>"


# ---------------------------------------------------------------------- ficha

def _ficha(a: AlmacenMapa | None) -> None:
    with st.container(border=True):
        if a is None:
            st.markdown("**Ningún almacén seleccionado**")
            st.caption("Pulsa un círculo del mapa o una fila de la tabla para ver su resumen.")
            return
        st.markdown(f"### {a.nombre}")
        st.caption(a.tipo.capitalize())
        c1, c2 = st.columns(2)
        c1.metric("Dentro", f"{a.presentes:,}".replace(",", "."))
        c2.metric("Ocupación", _pct(a.ocupacion))
        if a.capacidad:
            st.progress(min(a.ocupacion, 1.0),
                        text=f"{a.presentes:,} de {a.capacidad:,} plazas".replace(",", "."))
        else:
            st.caption("Sin capacidad definida.")
        c3, c4 = st.columns(2)
        c3.metric("Entradas hoy", a.entradas_hoy)
        c4.metric("Avisos 24 h", a.avisos_24h,
                  help=f"{_pct(a.tasa_avisos)} de los {a.eventos_24h} eventos de las últimas 24 h"
                  if a.eventos_24h else "Sin eventos en las últimas 24 h")
        if st.button("Abrir almacén", type="primary", icon=":material/warehouse:", width="stretch"):
            navegacion.ir_a_almacen(a.id)


# ---------------------------------------------------------------------- tabla

def _tabla(almacenes: list[AlmacenMapa]) -> None:
    datos = pd.DataFrame([{
        "Almacén": a.nombre,
        "Tipo": a.tipo.capitalize(),
        "Dentro": a.presentes,
        "Capacidad": a.capacidad,   # puede faltar: se convierte a entero «nullable» más abajo
        "Ocupación": None if a.ocupacion is None else round(a.ocupacion * 100, 1),
        "Entradas hoy": a.entradas_hoy,
        "Avisos 24 h": a.avisos_24h,
        "% avisos": None if a.tasa_avisos is None else round(a.tasa_avisos * 100, 1),
    } for a in almacenes])
    datos["Capacidad"] = datos["Capacidad"].astype("Int64")
    st.dataframe(
        datos, hide_index=True, key=CLAVE_TABLA, on_select="rerun", selection_mode="single-row",
        column_config={
            "Ocupación": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
            "% avisos": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )


# --------------------------------------------------------------------- página

def pagina_mapa() -> None:
    ui.cabecera("Mapa", "Almacenes, ocupación y avisos")
    ruta = str(ruta_bd())
    almacenes = _datos(ruta)
    if not almacenes:
        _datos.clear()   # que no se quede 30 s diciendo «vacía» tras cargar datos
        ui.aviso_bd_vacia()
        return

    c_modo, c_arcos, c_refresco = st.columns([2.2, 2.2, 1], vertical_alignment="bottom")
    modo = c_modo.segmented_control("Color por", list(MODOS), format_func=MODOS.get, default="ocupacion",
                                    required=True, key="mapa_modo")
    arcos = c_arcos.toggle("Mostrar traslados entre almacenes (30 días)", key="mapa_arcos")
    if c_refresco.button("Actualizar", icon=":material/refresh:", width="stretch",
                         help=f"Los datos se renuevan solos cada {TTL_S} s"):
        _datos.clear()
        _flujos.clear()
        st.rerun()

    por_id = {a.id: a for a in almacenes}
    seleccionado = por_id.get(_seleccionado(list(por_id)))

    col_mapa, col_ficha = st.columns([2.4, 1], gap="medium")
    with col_mapa:
        st.pydeck_chart(_deck(almacenes, modo, _flujos(ruta) if arcos else []),
                        on_select="rerun", selection_mode="single-object", key=CLAVE_MAPA, height=470,
                        alt="Mapa con un punto por almacén. La tabla «Almacenes» de debajo contiene los mismos datos.")
        st.html(_leyenda(modo))
    with col_ficha:
        _ficha(seleccionado)

    st.subheader("Almacenes", anchor=False)
    st.caption("Selecciona una fila para ver su ficha. Se puede ordenar pulsando en las cabeceras.")
    _tabla(almacenes)
