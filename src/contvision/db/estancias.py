"""Lógica de estancias (plan §2, paso 5) y su recálculo (§2.1).

Las estancias son datos derivados de los avistamientos: :func:`aplicar` las
actualiza de forma incremental con cada lectura y :func:`recalcular` las
reconstruye desde cero para un contenedor.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .conexion import transaccion


@dataclass(slots=True)
class EventoPendiente:
    tipo: str
    mensaje: str
    almacen_id: int | None
    datos: dict[str, Any] = field(default_factory=dict)


def _estancia_abierta(conn: sqlite3.Connection, contenedor_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT e.id, e.almacen_id, a.nombre AS almacen
             FROM estancia e JOIN almacen a ON a.id = e.almacen_id
            WHERE e.contenedor_id = ? AND e.salida_ts IS NULL""",
        (contenedor_id,),
    ).fetchone()


def _abrir(conn, contenedor_id, almacen_id, ts, avistamiento_id, inferida: bool) -> None:
    conn.execute(
        """INSERT INTO estancia (contenedor_id, almacen_id, entrada_ts,
                                 avistamiento_entrada_id, inferida)
           VALUES (?, ?, ?, ?, ?)""",
        (contenedor_id, almacen_id, ts, avistamiento_id, int(inferida)),
    )


def aplicar(
    conn: sqlite3.Connection,
    *,
    contenedor_id: int,
    codigo: str,
    almacen_id: int,
    almacen_nombre: str,
    tipo_fuente: str,
    ts: str,
    avistamiento_id: int,
) -> list[EventoPendiente]:
    """Aplica un avistamiento a las estancias del contenedor.

    Devuelve los eventos que habría que emitir (``registrar`` los emite;
    ``recalcular`` los descarta para no duplicar el log).
    """
    eventos: list[EventoPendiente] = []
    abierta = _estancia_abierta(conn, contenedor_id)
    misma = abierta is not None and abierta["almacen_id"] == almacen_id

    if tipo_fuente in ("entrada", "interior"):
        if not misma:
            if abierta is not None:
                # Entró en otro almacén sin leer su salida: se cierra como inferida.
                conn.execute(
                    "UPDATE estancia SET salida_ts = ?, inferida = 1 WHERE id = ?",
                    (ts, abierta["id"]),
                )
                eventos.append(EventoPendiente(
                    "TRASLADO_SIN_SALIDA",
                    f"{codigo} aparece en {almacen_nombre} sin haber salido de {abierta['almacen']}",
                    almacen_id,
                    {"almacen_anterior_id": abierta["almacen_id"],
                     "almacen_anterior": abierta["almacen"]},
                ))
            inferida = tipo_fuente == "interior"
            _abrir(conn, contenedor_id, almacen_id, ts, avistamiento_id, inferida)
            mensaje = f"{codigo} entra en {almacen_nombre}"
            if inferida:
                mensaje += " (entrada inferida por cámara interior)"
            eventos.append(EventoPendiente("ENTRADA", mensaje, almacen_id, {"inferida": inferida}))

    elif tipo_fuente == "salida":
        if misma:
            conn.execute(
                "UPDATE estancia SET salida_ts = ?, avistamiento_salida_id = ? WHERE id = ?",
                (ts, avistamiento_id, abierta["id"]),
            )
            eventos.append(EventoPendiente("SALIDA", f"{codigo} sale de {almacen_nombre}", almacen_id))
        else:
            datos = {}
            if abierta is not None:
                datos = {"estancia_abierta_en": abierta["almacen"]}
            eventos.append(EventoPendiente(
                "SALIDA_SIN_ENTRADA",
                f"{codigo} sale de {almacen_nombre} sin entrada registrada",
                almacen_id,
                datos,
            ))
    else:
        raise ValueError(f"Tipo de fuente desconocido: {tipo_fuente!r}")

    _sincronizar_almacen_actual(conn, contenedor_id)
    return eventos


def _sincronizar_almacen_actual(conn: sqlite3.Connection, contenedor_id: int) -> None:
    conn.execute(
        """UPDATE contenedor SET almacen_actual_id = (
               SELECT almacen_id FROM estancia
                WHERE contenedor_id = ? AND salida_ts IS NULL)
            WHERE id = ?""",
        (contenedor_id, contenedor_id),
    )


def recalcular(conn: sqlite3.Connection, contenedor_id: int) -> None:
    """Borra y reconstruye las estancias de un contenedor a partir de sus avistamientos.

    También refresca ``primera_vez``, ``ultima_vez``, ``n_avistamientos`` y
    ``almacen_actual_id``. No emite eventos.
    """
    with transaccion(conn):
        fila = conn.execute("SELECT codigo FROM contenedor WHERE id = ?", (contenedor_id,)).fetchone()
        if fila is None:
            raise LookupError(f"No existe el contenedor {contenedor_id}")
        codigo = fila["codigo"]

        conn.execute("DELETE FROM estancia WHERE contenedor_id = ?", (contenedor_id,))
        avistamientos = conn.execute(
            """SELECT av.id, av.timestamp, f.tipo AS tipo_fuente, f.almacen_id, a.nombre AS almacen
                 FROM avistamiento av
                 JOIN fuente f  ON f.id = av.fuente_id
                 JOIN almacen a ON a.id = f.almacen_id
                WHERE av.contenedor_id = ?
                ORDER BY av.timestamp, av.id""",
            (contenedor_id,),
        ).fetchall()
        for av in avistamientos:
            aplicar(
                conn,
                contenedor_id=contenedor_id,
                codigo=codigo,
                almacen_id=av["almacen_id"],
                almacen_nombre=av["almacen"],
                tipo_fuente=av["tipo_fuente"],
                ts=av["timestamp"],
                avistamiento_id=av["id"],
            )
        _sincronizar_almacen_actual(conn, contenedor_id)
        conn.execute(
            """UPDATE contenedor SET
                   n_avistamientos = (SELECT COUNT(*) FROM avistamiento WHERE contenedor_id = :id),
                   primera_vez = COALESCE((SELECT MIN(timestamp) FROM avistamiento WHERE contenedor_id = :id), primera_vez),
                   ultima_vez  = COALESCE((SELECT MAX(timestamp) FROM avistamiento WHERE contenedor_id = :id), ultima_vez)
                WHERE id = :id""",
            {"id": contenedor_id},
        )


def recalcular_todos(conn: sqlite3.Connection) -> int:
    """Recalcula las estancias de todos los contenedores. Devuelve cuántos."""
    ids = [r[0] for r in conn.execute("SELECT id FROM contenedor ORDER BY id")]
    with transaccion(conn):
        for cid in ids:
            recalcular(conn, cid)
    return len(ids)
