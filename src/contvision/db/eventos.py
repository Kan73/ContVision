"""Escritura del log de actividad (tabla ``evento``). Uso interno de la capa db."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .conexion import ahora_iso

# tipo -> nivel (plan §1.3, más los eventos de administración)
TIPOS_EVENTO: dict[str, str] = {
    "CONTENEDOR_NUEVO": "info",
    "ENTRADA": "info",
    "SALIDA": "info",
    "TRASLADO_SIN_SALIDA": "aviso",
    "SALIDA_SIN_ENTRADA": "aviso",
    "LECTURA_CORREGIDA": "info",
    "LECTURA_DUDOSA": "aviso",
    "CORRECCION_MANUAL": "info",
    "FUENTE_DESCONOCIDA": "error",
    # Administración
    "ALMACEN_CREADO": "info",
    "ALMACEN_ELIMINADO": "aviso",
    "FUENTE_CREADA": "info",
    "FUENTE_ELIMINADA": "aviso",
    "CONTENEDOR_ELIMINADO": "aviso",
}


def emitir(
    conn: sqlite3.Connection,
    tipo: str,
    mensaje: str,
    *,
    timestamp: str | None = None,
    contenedor_id: int | None = None,
    almacen_id: int | None = None,
    avistamiento_id: int | None = None,
    datos: dict[str, Any] | None = None,
) -> int:
    """Inserta un evento y devuelve su id. El nivel se deduce del tipo."""
    try:
        nivel = TIPOS_EVENTO[tipo]
    except KeyError:
        raise ValueError(f"Tipo de evento desconocido: {tipo!r}") from None
    cur = conn.execute(
        """INSERT INTO evento (timestamp, tipo, nivel, contenedor_id, almacen_id,
                               avistamiento_id, mensaje, datos)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            timestamp or ahora_iso(),
            tipo,
            nivel,
            contenedor_id,
            almacen_id,
            avistamiento_id,
            mensaje,
            json.dumps(datos, ensure_ascii=False) if datos else None,
        ),
    )
    return cur.lastrowid
