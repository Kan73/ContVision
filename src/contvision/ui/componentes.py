"""Piezas reutilizables entre páginas."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from contvision.config import ZONA_HORARIA

_ZONA = ZoneInfo(ZONA_HORARIA)
ICONO_NIVEL = {"info": ":material/info:", "aviso": ":material/warning:", "error": ":material/error:"}
COLOR_NIVEL = {"info": "blue", "aviso": "orange", "error": "red"}


def fecha_local(iso: str | None, formato: str = "%d/%m/%Y %H:%M") -> str:
    """Timestamp ISO UTC de la BD → hora de Madrid para mostrar."""
    if not iso:
        return "—"
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_ZONA).strftime(formato)


def cabecera(titulo: str, subtitulo: str | None = None) -> None:
    st.title(titulo)
    if subtitulo:
        st.caption(subtitulo)


def pendiente(tarea: str, descripcion: str) -> None:
    """Marcador de una sección aún no implementada (ids de tarea del plan)."""
    st.info(f"**{tarea}** · {descripcion}", icon=":material/construction:")


def aviso_bd_vacia() -> None:
    st.warning(
        "La base de datos está vacía. Para cargar datos de ejemplo:\n\n"
        "`uv run python scripts/demo_bd.py --db data/contvision.db`",
        icon=":material/database:",
    )


def fila_evento(ev) -> None:
    """Una línea del log: hora · nivel · mensaje."""
    nivel = f":{COLOR_NIVEL[ev.nivel]}-badge[{ICONO_NIVEL[ev.nivel]} {ev.tipo}]"
    st.markdown(f"`{fecha_local(ev.timestamp, '%d/%m %H:%M')}` {nivel} {ev.mensaje}")
