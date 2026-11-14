"""Conexión a la BD y estado de sesión."""

from __future__ import annotations

import os
import sqlite3
import threading

import streamlit as st

from contvision import db
from contvision.config import ruta_bd

# Valores iniciales de st.session_state
_ESTADO_INICIAL = {
    "ultimo_evento_id": 0,   # feed en vivo de Inicio: último id mostrado
    "en_vivo": True,         # refresco automático de Inicio
}

_local = threading.local()


def init_state() -> None:
    """Crea las claves de sesión que falten (se llama en cada rerun)."""
    for clave, valor in _ESTADO_INICIAL.items():
        st.session_state.setdefault(clave, valor)


def conexion() -> sqlite3.Connection:
    """Conexión a la BD propia del hilo que la pide.

    Streamlit ejecuta cada sesión en su propio hilo y una conexión ``sqlite3``
    compartida entre hilos falla de forma intermitente (``InterfaceError``), así
    que no se cachea con ``st.cache_resource``. Abrir una conexión SQLite cuesta
    menos de 1 ms. Si el fichero se sustituye con la app en marcha (p. ej. al
    recargar la demo), se detecta y se vuelve a abrir.
    """
    ruta = ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = getattr(_local, "conn", None)
    if conn is not None and _local.huella == _huella(ruta):
        return conn
    if conn is not None:
        conn.close()
    _local.conn = db.conectar(ruta)
    _local.huella = _huella(ruta)
    return _local.conn


def _huella(ruta) -> tuple[str, int] | None:
    """Identifica el fichero concreto (ruta + inodo); None si no existe."""
    try:
        return str(ruta), os.stat(ruta).st_ino
    except FileNotFoundError:
        return None
