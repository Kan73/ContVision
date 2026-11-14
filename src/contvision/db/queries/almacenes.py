"""Consultas de almacenes: listado con ocupación, presentes, entradas/salidas."""

from __future__ import annotations

import sqlite3

from ..conexion import dia_local_de_hora
from ._modelos import Almacen, Estancia, Fuente

_SELECT_ALMACEN = """
    SELECT a.*, (SELECT COUNT(*) FROM estancia e
                  WHERE e.almacen_id = a.id AND e.salida_ts IS NULL) AS presentes
      FROM almacen a
"""


def listar(conn: sqlite3.Connection) -> list[Almacen]:
    """Todos los almacenes con su nº de contenedores presentes."""
    return [Almacen.desde_fila(f) for f in conn.execute(_SELECT_ALMACEN + " ORDER BY a.nombre")]


def obtener(conn: sqlite3.Connection, almacen: int | str) -> Almacen | None:
    """Un almacén por id o por nombre."""
    campo = "a.id" if isinstance(almacen, int) else "a.nombre"
    fila = conn.execute(_SELECT_ALMACEN + f" WHERE {campo} = ?", (almacen,)).fetchone()
    return Almacen.desde_fila(fila) if fila else None


def fuentes(conn: sqlite3.Connection, almacen_id: int | None = None) -> list[Fuente]:
    sql = """SELECT f.*, (SELECT COUNT(*) FROM avistamiento av WHERE av.fuente_id = f.id) AS n_avistamientos
               FROM fuente f"""
    params: tuple = ()
    if almacen_id is not None:
        sql += " WHERE f.almacen_id = ?"
        params = (almacen_id,)
    return [Fuente.desde_fila(r) for r in conn.execute(sql + " ORDER BY f.almacen_id, f.nombre", params)]


def presentes(conn: sqlite3.Connection, almacen_id: int) -> list[Estancia]:
    """Contenedores dentro del almacén ahora (estancias abiertas), más antiguos primero."""
    return [Estancia.desde_fila(r) for r in conn.execute(
        """SELECT e.*, c.codigo, a.nombre AS almacen
             FROM estancia e
             JOIN contenedor c ON c.id = e.contenedor_id
             JOIN almacen a    ON a.id = e.almacen_id
            WHERE e.almacen_id = ? AND e.salida_ts IS NULL
            ORDER BY e.entrada_ts""",
        (almacen_id,),
    )]


def entradas_salidas_por_dia(
    conn: sqlite3.Connection, almacen_id: int, desde: str | None = None
) -> list[dict]:
    """``[{dia, entradas, salidas}, …]`` por día **local** (Europe/Madrid) desde ``desde`` (``YYYY-MM-DD``)."""
    filas = conn.execute(
        """WITH movs AS (
               SELECT substr(entrada_ts, 1, 13) AS hora, 1 AS ent, 0 AS sal
                 FROM estancia WHERE almacen_id = :a
               UNION ALL
               SELECT substr(salida_ts, 1, 13), 0, 1
                 FROM estancia WHERE almacen_id = :a AND salida_ts IS NOT NULL)
           SELECT hora, SUM(ent) AS entradas, SUM(sal) AS salidas FROM movs GROUP BY hora""",
        {"a": almacen_id},
    )
    dias: dict[str, dict] = {}
    for f in filas:
        dia = dia_local_de_hora(f["hora"])
        if desde and dia < desde:
            continue
        d = dias.setdefault(dia, {"dia": dia, "entradas": 0, "salidas": 0})
        d["entradas"] += f["entradas"]
        d["salidas"] += f["salidas"]
    return [dias[k] for k in sorted(dias)]


def reparto_propietarios(conn: sqlite3.Connection, almacen_id: int) -> list[dict]:
    """Contenedores presentes agrupados por propietario."""
    return [dict(r) for r in conn.execute(
        """SELECT c.propietario, COUNT(*) AS n
             FROM estancia e JOIN contenedor c ON c.id = e.contenedor_id
            WHERE e.almacen_id = ? AND e.salida_ts IS NULL
            GROUP BY c.propietario ORDER BY n DESC""",
        (almacen_id,),
    )]
