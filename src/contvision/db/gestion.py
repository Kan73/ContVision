"""Altas y bajas administrativas: almacenes, fuentes (cámaras) y contenedores.

Cada almacén es una **fila** de la tabla ``almacen`` (no una tabla propia, ver
nota de diseño del plan §0); sus contenedores se obtienen de ``estancia``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from .conexion import transaccion
from .estancias import recalcular
from .eventos import emitir

TIPOS_ALMACEN = ("puerto", "terminal", "deposito", "ferroviario")
TIPOS_FUENTE = ("entrada", "salida", "interior")


class EnUsoError(RuntimeError):
    """El elemento tiene datos asociados y no se ha pedido ``forzar=True``."""


# ---------------------------------------------------------------- almacenes

def crear_almacen(
    conn: sqlite3.Connection,
    nombre: str,
    tipo: str,
    lat: float,
    lon: float,
    *,
    capacidad: int | None = None,
    descripcion: str | None = None,
    fuentes: Iterable[tuple[str, str]] | None = None,
) -> int:
    """Crea un almacén (y opcionalmente sus fuentes ``[(nombre, tipo), …]``).

    Si ``fuentes`` es None se crean dos por defecto: ``"<nombre> · entrada"`` y
    ``"<nombre> · salida"``. Pasa ``fuentes=[]`` para no crear ninguna.
    """
    if tipo not in TIPOS_ALMACEN:
        raise ValueError(f"tipo de almacén debe ser uno de {TIPOS_ALMACEN}")
    if fuentes is None:
        fuentes = [(f"{nombre} · entrada", "entrada"), (f"{nombre} · salida", "salida")]
    with transaccion(conn):
        if conn.execute("SELECT 1 FROM almacen WHERE nombre = ?", (nombre,)).fetchone():
            raise ValueError(f"Ya existe un almacén llamado {nombre!r}")
        cur = conn.execute(
            """INSERT INTO almacen (nombre, tipo, lat, lon, capacidad, descripcion)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nombre, tipo, lat, lon, capacidad, descripcion),
        )
        almacen_id = cur.lastrowid
        emitir(conn, "ALMACEN_CREADO", f"Almacén creado: {nombre} ({tipo})",
               almacen_id=almacen_id, datos={"lat": lat, "lon": lon, "capacidad": capacidad})
        for nombre_f, tipo_f in fuentes:
            crear_fuente(conn, nombre_f, almacen_id, tipo_f)
    return almacen_id


def actualizar_almacen(conn: sqlite3.Connection, almacen_id: int, **campos) -> None:
    """Modifica nombre, tipo, lat, lon, capacidad y/o descripcion."""
    permitidos = {"nombre", "tipo", "lat", "lon", "capacidad", "descripcion"}
    if not campos or not set(campos) <= permitidos:
        raise ValueError(f"Campos permitidos: {sorted(permitidos)}")
    asignaciones = ", ".join(f"{k} = :{k}" for k in campos)
    with transaccion(conn):
        cur = conn.execute(f"UPDATE almacen SET {asignaciones} WHERE id = :id", {**campos, "id": almacen_id})
        if cur.rowcount == 0:
            raise LookupError(f"No existe el almacén {almacen_id}")


def eliminar_almacen(conn: sqlite3.Connection, almacen_id: int, *, forzar: bool = False) -> None:
    """Elimina un almacén.

    Sin ``forzar`` falla con :class:`EnUsoError` si tiene avistamientos o
    estancias. Con ``forzar`` borra también sus fuentes, los avistamientos de
    esas fuentes y sus estancias, recalcula los contenedores afectados y deja
    los eventos antiguos en el historial (sin el enlace al almacén).
    """
    with transaccion(conn):
        alm = conn.execute("SELECT nombre FROM almacen WHERE id = ?", (almacen_id,)).fetchone()
        if alm is None:
            raise LookupError(f"No existe el almacén {almacen_id}")

        n_avist = conn.execute(
            """SELECT COUNT(*) FROM avistamiento av JOIN fuente f ON f.id = av.fuente_id
                WHERE f.almacen_id = ?""", (almacen_id,)).fetchone()[0]
        n_est = conn.execute("SELECT COUNT(*) FROM estancia WHERE almacen_id = ?", (almacen_id,)).fetchone()[0]
        if (n_avist or n_est) and not forzar:
            raise EnUsoError(
                f"El almacén {alm['nombre']!r} tiene {n_avist} avistamientos y {n_est} estancias; "
                "usa forzar=True para borrarlo con sus datos"
            )

        afectados = [r[0] for r in conn.execute(
            """SELECT DISTINCT av.contenedor_id FROM avistamiento av JOIN fuente f ON f.id = av.fuente_id
                WHERE f.almacen_id = ? AND av.contenedor_id IS NOT NULL
               UNION SELECT contenedor_id FROM estancia WHERE almacen_id = ?""",
            (almacen_id, almacen_id))]

        sub_avist = "SELECT av.id FROM avistamiento av JOIN fuente f ON f.id = av.fuente_id WHERE f.almacen_id = ?"
        conn.execute(f"DELETE FROM estancia WHERE contenedor_id IN ({_marcadores(afectados)})", afectados)
        conn.execute(f"UPDATE evento SET avistamiento_id = NULL WHERE avistamiento_id IN ({sub_avist})", (almacen_id,))
        conn.execute(f"DELETE FROM avistamiento WHERE id IN ({sub_avist})", (almacen_id,))
        conn.execute("DELETE FROM fuente WHERE almacen_id = ?", (almacen_id,))
        conn.execute("UPDATE evento SET almacen_id = NULL WHERE almacen_id = ?", (almacen_id,))
        conn.execute("UPDATE contenedor SET almacen_actual_id = NULL WHERE almacen_actual_id = ?", (almacen_id,))
        conn.execute("DELETE FROM almacen WHERE id = ?", (almacen_id,))

        for cid in afectados:
            recalcular(conn, cid)
            eliminar_si_sin_avistamientos(conn, cid)

        emitir(conn, "ALMACEN_ELIMINADO", f"Almacén eliminado: {alm['nombre']}",
               datos={"almacen_id": almacen_id, "nombre": alm["nombre"],
                      "avistamientos_borrados": n_avist, "contenedores_afectados": len(afectados)})


# ------------------------------------------------------------------ fuentes

def crear_fuente(conn: sqlite3.Connection, nombre: str, almacen_id: int, tipo: str, *, activa: bool = True) -> int:
    if tipo not in TIPOS_FUENTE:
        raise ValueError(f"tipo de fuente debe ser uno de {TIPOS_FUENTE}")
    with transaccion(conn):
        if conn.execute("SELECT 1 FROM almacen WHERE id = ?", (almacen_id,)).fetchone() is None:
            raise LookupError(f"No existe el almacén {almacen_id}")
        if conn.execute("SELECT 1 FROM fuente WHERE nombre = ?", (nombre,)).fetchone():
            raise ValueError(f"Ya existe una fuente llamada {nombre!r}")
        cur = conn.execute(
            "INSERT INTO fuente (nombre, almacen_id, tipo, activa) VALUES (?, ?, ?, ?)",
            (nombre, almacen_id, tipo, int(activa)),
        )
        emitir(conn, "FUENTE_CREADA", f"Fuente creada: {nombre} ({tipo})", almacen_id=almacen_id)
        return cur.lastrowid


def activar_fuente(conn: sqlite3.Connection, fuente_id: int, activa: bool = True) -> None:
    cur = conn.execute("UPDATE fuente SET activa = ? WHERE id = ?", (int(activa), fuente_id))
    if cur.rowcount == 0:
        raise LookupError(f"No existe la fuente {fuente_id}")


def eliminar_fuente(conn: sqlite3.Connection, fuente_id: int) -> None:
    """Elimina una fuente sin avistamientos. Si tiene, desactívala en su lugar."""
    with transaccion(conn):
        f = conn.execute("SELECT nombre, almacen_id FROM fuente WHERE id = ?", (fuente_id,)).fetchone()
        if f is None:
            raise LookupError(f"No existe la fuente {fuente_id}")
        n = conn.execute("SELECT COUNT(*) FROM avistamiento WHERE fuente_id = ?", (fuente_id,)).fetchone()[0]
        if n:
            raise EnUsoError(f"La fuente {f['nombre']!r} tiene {n} avistamientos; usa activar_fuente(…, False)")
        conn.execute("DELETE FROM fuente WHERE id = ?", (fuente_id,))
        emitir(conn, "FUENTE_ELIMINADA", f"Fuente eliminada: {f['nombre']}", almacen_id=f["almacen_id"])


# ------------------------------------------------------------- contenedores

def eliminar_contenedor(conn: sqlite3.Connection, codigo: str) -> None:
    """Elimina un contenedor con sus avistamientos y estancias.

    Los eventos pasados se conservan en el historial (sin enlace).
    """
    with transaccion(conn):
        c = conn.execute("SELECT id FROM contenedor WHERE codigo = ?", (codigo,)).fetchone()
        if c is None:
            raise LookupError(f"No existe el contenedor {codigo}")
        cid = c["id"]
        conn.execute("DELETE FROM estancia WHERE contenedor_id = ?", (cid,))
        conn.execute(
            """UPDATE evento SET avistamiento_id = NULL
                WHERE avistamiento_id IN (SELECT id FROM avistamiento WHERE contenedor_id = ?)""", (cid,))
        conn.execute("DELETE FROM avistamiento WHERE contenedor_id = ?", (cid,))
        conn.execute("UPDATE evento SET contenedor_id = NULL WHERE contenedor_id = ?", (cid,))
        conn.execute("DELETE FROM contenedor WHERE id = ?", (cid,))
        emitir(conn, "CONTENEDOR_ELIMINADO", f"Contenedor eliminado: {codigo}", datos={"codigo": codigo})


def eliminar_si_sin_avistamientos(conn: sqlite3.Connection, contenedor_id: int) -> bool:
    """Borra un contenedor que se ha quedado sin lecturas (tras una corrección o un borrado).

    Sus eventos pasados se conservan sin enlace. Devuelve True si lo borró.
    """
    with transaccion(conn):
        if conn.execute("SELECT 1 FROM avistamiento WHERE contenedor_id = ? LIMIT 1",
                        (contenedor_id,)).fetchone():
            return False
        conn.execute("DELETE FROM estancia WHERE contenedor_id = ?", (contenedor_id,))
        conn.execute("UPDATE evento SET contenedor_id = NULL WHERE contenedor_id = ?", (contenedor_id,))
        conn.execute("DELETE FROM contenedor WHERE id = ?", (contenedor_id,))
        return True


def _marcadores(valores: list) -> str:
    return ",".join("?" * len(valores)) or "NULL"
