"""Consultas de almacenes: listado con ocupación, presentes, entradas/salidas."""

from __future__ import annotations

import sqlite3

from ..conexion import dia_local_de_hora, limites_dia_local
from ._modelos import Almacen, AlmacenMapa, Estancia, Flujo, Fuente, KpisAlmacen

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
    sql = """SELECT f.*,
                    (SELECT COUNT(*) FROM avistamiento av WHERE av.fuente_id = f.id)       AS n_avistamientos,
                    (SELECT MAX(timestamp) FROM avistamiento av WHERE av.fuente_id = f.id) AS ultima_lectura
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
    """``[{dia, entradas, salidas}, …]`` por día **local** (Europe/Madrid) desde ``desde`` (``YYYY-MM-DD``).

    Solo aparecen los días con algún movimiento.
    """
    desde_utc = limites_dia_local(desde)[0] if desde else ""
    filas = conn.execute(
        """WITH movs AS (
               SELECT substr(entrada_ts, 1, 13) AS hora, 1 AS ent, 0 AS sal
                 FROM estancia WHERE almacen_id = :a AND entrada_ts >= :desde
               UNION ALL
               SELECT substr(salida_ts, 1, 13), 0, 1
                 FROM estancia WHERE almacen_id = :a AND salida_ts IS NOT NULL AND salida_ts >= :desde)
           SELECT hora, SUM(ent) AS entradas, SUM(sal) AS salidas FROM movs GROUP BY hora""",
        {"a": almacen_id, "desde": desde_utc},
    )
    dias: dict[str, dict] = {}
    for f in filas:
        dia = dia_local_de_hora(f["hora"])
        d = dias.setdefault(dia, {"dia": dia, "entradas": 0, "salidas": 0})
        d["entradas"] += f["entradas"]
        d["salidas"] += f["salidas"]
    return [dias[k] for k in sorted(dias)]


def resumen_mapa(conn: sqlite3.Connection, inicio_hoy: str, desde_24h: str) -> list[AlmacenMapa]:
    """Todo lo que necesita la página Mapa, en una sola consulta.

    ``inicio_hoy`` y ``desde_24h`` son timestamps ISO UTC (los calcula la interfaz).
    Cada subconsulta entra por un índice que empieza por ``almacen_id``.
    """
    return [AlmacenMapa.desde_fila(f) for f in conn.execute(
        """SELECT a.id, a.nombre, a.tipo, a.lat, a.lon, a.capacidad,
                  (SELECT COUNT(*) FROM estancia e
                    WHERE e.almacen_id = a.id AND e.salida_ts IS NULL)             AS presentes,
                  (SELECT COUNT(*) FROM estancia e
                    WHERE e.almacen_id = a.id AND e.entrada_ts >= :hoy)            AS entradas_hoy,
                  (SELECT COUNT(*) FROM evento ev
                    WHERE ev.almacen_id = a.id AND ev.timestamp >= :d24)           AS eventos_24h,
                  (SELECT COUNT(*) FROM evento ev
                    WHERE ev.almacen_id = a.id AND ev.timestamp >= :d24
                      AND ev.nivel IN ('aviso', 'error'))                          AS avisos_24h
             FROM almacen a ORDER BY a.nombre""",
        {"hoy": inicio_hoy, "d24": desde_24h},
    )]


def kpis(conn: sqlite3.Connection, almacen_id: int, inicio_hoy: str) -> KpisAlmacen | None:
    """Métricas de la página Almacén (None si el almacén no existe).

    La estancia media solo usa estancias cerradas con entrada y salida leídas de
    verdad: las inferidas no tienen una duración fiable.
    """
    fila = conn.execute(
        """SELECT a.capacidad,
                  (SELECT COUNT(*) FROM estancia WHERE almacen_id = :a AND salida_ts IS NULL)       AS presentes,
                  (SELECT COUNT(*) FROM estancia WHERE almacen_id = :a AND entrada_ts >= :hoy)      AS entradas_hoy,
                  (SELECT COUNT(*) FROM estancia WHERE almacen_id = :a AND salida_ts >= :hoy)       AS salidas_hoy,
                  m.horas AS estancia_media_horas, m.n AS estancias_cerradas
             FROM almacen a,
                  (SELECT AVG((julianday(salida_ts) - julianday(entrada_ts)) * 24) AS horas, COUNT(*) AS n
                     FROM estancia
                    WHERE almacen_id = :a AND salida_ts IS NOT NULL
                      AND entrada_inferida = 0 AND salida_inferida = 0) m
            WHERE a.id = :a""",
        {"a": almacen_id, "hoy": inicio_hoy},
    ).fetchone()
    return KpisAlmacen.desde_fila(fila) if fila else None


def flujos(conn: sqlite3.Connection, desde: str | None = None) -> list[Flujo]:
    """Traslados entre almacenes: estancias consecutivas de un mismo contenedor en almacenes distintos.

    ``desde`` (ISO UTC) limita a los traslados cuya llegada es posterior. De mayor a menor volumen.
    """
    return [Flujo.desde_fila(f) for f in conn.execute(
        """WITH pasos AS (
               SELECT almacen_id AS destino_id, entrada_ts,
                      LAG(almacen_id) OVER (PARTITION BY contenedor_id ORDER BY entrada_ts, id) AS origen_id
                 FROM estancia)
           SELECT origen_id, destino_id, COUNT(*) AS n
             FROM pasos
            WHERE origen_id IS NOT NULL AND origen_id != destino_id
              AND (:desde IS NULL OR entrada_ts >= :desde)
            GROUP BY origen_id, destino_id ORDER BY n DESC""",
        {"desde": desde},
    )]


def reparto_propietarios(conn: sqlite3.Connection, almacen_id: int) -> list[dict]:
    """Contenedores presentes agrupados por propietario."""
    return [dict(r) for r in conn.execute(
        """SELECT c.propietario, COUNT(*) AS n
             FROM estancia e JOIN contenedor c ON c.id = e.contenedor_id
            WHERE e.almacen_id = ? AND e.salida_ts IS NULL
            GROUP BY c.propietario ORDER BY n DESC""",
        (almacen_id,),
    )]
