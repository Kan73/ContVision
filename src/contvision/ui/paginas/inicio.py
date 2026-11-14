"""Inicio · Actividad: KPIs + feed de eventos en vivo (B3.7).

Componentes (numerados como en el boceto):
  1 cabecera con estado en vivo y botón pausar   5 eventos de la última hora por nivel
  2 tarjetas KPI                                 6 avisos recientes
  3 filtros (nivel, tipo, almacén)               7 enlace al historial completo
  4 feed de eventos
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import streamlit as st

from contvision.db import queries as q
from contvision.db.eventos import TIPOS_EVENTO
from contvision.ui import componentes as ui
from contvision.ui import feed, navegacion
from contvision.ui.state import conexion

REFRESCO_S = 5
LIMITE_FEED = 50
NIVELES = ("info", "aviso", "error")
COLORES_NIVEL = ["#3884ff", "#e68c1e", "#dc3c3c"]   # mismo orden que NIVELES


def pagina_inicio() -> None:
    refresco = REFRESCO_S if st.session_state.en_vivo else None

    if not q.almacenes.listar(conexion()):
        ui.aviso_bd_vacia()

    # 1 · Cabecera. El botón queda fuera de los fragmentos: pausar cambia su run_every.
    c_titulo, c_estado, c_boton = st.columns([5, 4, 1.3], vertical_alignment="center")
    c_titulo.header("Actividad", anchor=False)
    with c_estado:
        st.fragment(_estado, run_every=refresco)()
    etiqueta, icono = (("Pausar", ":material/pause:") if st.session_state.en_vivo
                       else ("Reanudar", ":material/play_arrow:"))
    c_boton.button(etiqueta, icon=icono, on_click=_alternar_vivo, width="stretch")

    st.fragment(_cuerpo, run_every=refresco)()

    # 7 · Historial completo
    _, centro, _ = st.columns([2, 1.2, 2])
    centro.page_link(navegacion.pagina("historial"), label="Ver historial completo",
                     icon=":material/arrow_forward:", icon_position="right", width="stretch")


def _alternar_vivo() -> None:
    st.session_state.en_vivo = not st.session_state.en_vivo


def _estado() -> None:
    ultimo = q.eventos.feed(conexion(), limite=1)
    detalle = f" · último evento {feed.hace(ultimo[0].timestamp)}" if ultimo else ""
    if st.session_state.en_vivo:
        st.html(f'<div class="cv-estado vivo"><span class="cv-punto"></span>En vivo{detalle}</div>')
    else:
        st.html(f'<div class="cv-estado pausa"><span class="cv-punto"></span>Pausado{detalle}</div>')


def _cuerpo() -> None:
    conn = conexion()
    ahora = datetime.now(UTC)

    dudosas = _kpis(conn, ahora)
    niveles, tipos, almacen_id = _filtros(conn)

    col_feed, col_lateral = st.columns([2.2, 1], gap="medium")
    with col_feed:
        _feed(conn, ahora, niveles, tipos, almacen_id)
    with col_lateral:
        _ultima_hora(conn, ahora)
        _avisos(conn, ahora, dudosas)


# 2 · KPIs ---------------------------------------------------------------------

def _kpis(conn, ahora: datetime) -> int:
    """Dibuja las tarjetas y devuelve el nº de dudosas pendientes (lo reutiliza el panel de avisos)."""
    # «vs ayer» compara con ayer hasta esta misma hora, no con el día completo.
    a = q.estadisticas.actividad(conn, feed.inicio_dia_utc(0), feed.inicio_dia_utc(1),
                                 fin_ayer=feed.iso_utc(ahora - timedelta(hours=24)))
    delta = None
    if a["eventos_ayer"]:
        cambio = (a["eventos_hoy"] - a["eventos_ayer"]) / a["eventos_ayer"]
        delta = f"{cambio:+.0%} vs ayer a esta hora".replace("%", " %")

    k1, k2, k3, k4 = st.columns(4)
    with k1.container(border=True, height="stretch"):
        st.metric("Eventos hoy", _miles(a["eventos_hoy"]), delta=delta)
    with k2.container(border=True, height="stretch"):
        st.metric("Contenedores nuevos", _miles(a["contenedores_nuevos_hoy"]))
        st.caption("hoy")
    with k3.container(border=True, height="stretch"):
        st.metric("En almacenes", _miles(a["en_almacenes"]))
        n = a["almacenes_ocupados"]
        st.caption(f"{n} almacén" if n == 1 else f"{n} almacenes")
    # El resalte naranja solo aparece cuando hay algo que revisar.
    clave = "kpi_dudosas_alerta" if a["dudosas_pendientes"] else "kpi_dudosas"
    with k4.container(border=True, height="stretch", key=clave):
        st.metric("Dudosas pendientes", _miles(a["dudosas_pendientes"]))
        st.page_link(navegacion.pagina("revision"), label="Revisar",
                     icon=":material/arrow_forward:", icon_position="right")
    return a["dudosas_pendientes"]


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# 3 · Filtros -------------------------------------------------------------------

def _filtros(conn) -> tuple[list[str], list[str] | None, int | None]:
    f_nivel, f_tipo, f_almacen, _ = st.columns([1.6, 1.3, 1.3, 1.8], vertical_alignment="bottom")
    niveles = f_nivel.pills(
        "Nivel", NIVELES, selection_mode="multi", default=list(NIVELES), key="filtro_niveles",
        format_func=str.capitalize, label_visibility="collapsed",
    )
    tipo = f_tipo.selectbox(
        "Tipo", [None, *TIPOS_EVENTO], key="filtro_tipo", label_visibility="collapsed",
        format_func=lambda t: "Tipo: todos" if t is None else f"Tipo: {feed.ESTILO_TIPO.get(t, (t,))[0]}",
    )
    almacenes = {a.id: a.nombre for a in q.almacenes.listar(conn)}
    almacen_id = f_almacen.selectbox(
        "Almacén", [None, *almacenes], key="filtro_almacen", label_visibility="collapsed",
        format_func=lambda i: "Almacén: todos" if i is None else f"Almacén: {almacenes.get(i, i)}",
    )
    return list(niveles), ([tipo] if tipo else None), almacen_id


# 4 · Feed ----------------------------------------------------------------------

def _feed(conn, ahora, niveles, tipos, almacen_id) -> None:
    eventos = q.eventos.feed(conn, limite=LIMITE_FEED, niveles=niveles, tipos=tipos, almacen_id=almacen_id)

    # Resalta lo llegado desde el refresco anterior (no en la primera carga).
    visto = st.session_state.ultimo_evento_id
    ids_nuevos = {e.id for e in eventos if e.id > visto} if visto else set()
    if eventos:
        st.session_state.ultimo_evento_id = max(visto, eventos[0].id)

    with st.container(border=True):
        cab, info = st.columns([3, 1], vertical_alignment="center")
        cab.markdown("**Feed de eventos**")
        info.caption(f"últimos {LIMITE_FEED}", text_alignment="right")
        with st.container(height=470, border=False):
            st.html(feed.html_feed(eventos, ids_nuevos, ahora))


# 5 · Última hora ---------------------------------------------------------------

def _ultima_hora(conn, ahora: datetime) -> None:
    paso = timedelta(minutes=5)
    fin = ahora.replace(second=0, microsecond=0) - timedelta(minutes=ahora.minute % 5)
    inicios = [fin - paso * i for i in range(11, -1, -1)]   # 12 intervalos de 5 min
    filas = q.eventos.por_intervalo(conn, feed.iso_utc(inicios[0]), minutos=5)

    tabla = pd.DataFrame(0, index=[int(t.timestamp()) for t in inicios], columns=list(NIVELES))
    for f in filas:
        if f["inicio"] in tabla.index:
            tabla.loc[f["inicio"], f["nivel"]] = f["n"]
    tabla.index = [feed.hora_local(t) for t in tabla.index]
    tabla.columns = [n.capitalize() for n in NIVELES]

    with st.container(border=True):
        st.markdown("**Última hora**")
        if tabla.to_numpy().sum() == 0:
            st.caption("Sin eventos en la última hora.")
        else:
            st.bar_chart(tabla, color=COLORES_NIVEL, height=150, stack=True,
                         x_label="", y_label="", sort=False)
            st.caption("eventos cada 5 min, por nivel")


# 6 · Avisos --------------------------------------------------------------------

def _avisos(conn, ahora: datetime, dudosas: int) -> None:
    por_tipo = q.eventos.conteo_por_tipo(conn, feed.iso_utc(ahora - timedelta(hours=24)))

    def plural(n, uno, varios):
        return uno if n == 1 else varios

    t, s, f = (por_tipo.get(k, 0) for k in ("TRASLADO_SIN_SALIDA", "SALIDA_SIN_ENTRADA", "FUENTE_DESCONOCIDA"))
    avisos = [
        (plural(dudosas, "lectura dudosa por revisar", "lecturas dudosas por revisar"), dudosas, "aviso"),
        (plural(t, "traslado sin salida", "traslados sin salida"), t, "aviso"),
        (plural(s, "salida sin entrada", "salidas sin entrada"), s, "aviso"),
        (plural(f, "fuente desconocida", "fuentes desconocidas"), f, "error"),
    ]
    with st.container(border=True):
        st.markdown("**Avisos recientes**")
        st.html(feed.html_avisos(avisos))
        st.caption("últimas 24 h · dudosas: todas las pendientes")
