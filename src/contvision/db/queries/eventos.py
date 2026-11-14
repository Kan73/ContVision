"""Consultas del log de eventos: feed en vivo e historial paginado por cursor."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from ._modelos import Evento

_SELECT = """
    SELECT ev.*, c.codigo, a.nombre AS almacen
      FROM evento ev
      LEFT JOIN contenedor c ON c.id = ev.contenedor_id
      LEFT JOIN almacen a    ON a.id = ev.almacen_id
"""


def feed(
    conn: sqlite3.Connection,
    desde_id: int = 0,
    limite: int = 50,
    *,
    niveles: Sequence[str] | None = None,
    tipos: Sequence[str] | None = None,
    almacen_id: int | None = None,
) -> list[Evento]:
    """Eventos con ``id > desde_id`` (los más nuevos primero), con filtros opcionales.

    Con ``desde_id=0`` devuelve los últimos ``limite``. La interfaz guarda el
    mayor id visto y pide solo lo nuevo en cada refresco.
    """
    if (niveles is not None and not niveles) or (tipos is not None and not tipos):
        return []   # filtro vacío = nada seleccionado
    condiciones, params = ["ev.id > ?"], [desde_id]
    if niveles is not None:
        condiciones.append(f"ev.nivel IN ({','.join('?' * len(niveles))})"); params += list(niveles)
    if tipos is not None:
        condiciones.append(f"ev.tipo IN ({','.join('?' * len(tipos))})"); params += list(tipos)
    if almacen_id is not None:
        condiciones.append("ev.almacen_id = ?"); params.append(almacen_id)
    return [Evento.desde_fila(r) for r in conn.execute(
        _SELECT + " WHERE " + " AND ".join(condiciones) + " ORDER BY ev.id DESC LIMIT ?",
        (*params, limite))]


def conteo_por_tipo(conn: sqlite3.Connection, desde: str) -> dict[str, int]:
    """``{tipo: n}`` de los eventos con ``timestamp >= desde``."""
    return {r["tipo"]: r["n"] for r in conn.execute(
        "SELECT tipo, COUNT(*) AS n FROM evento WHERE timestamp >= ? GROUP BY tipo", (desde,))}


def por_intervalo(conn: sqlite3.Connection, desde: str, minutos: int = 5) -> list[dict]:
    """Eventos desde ``desde`` agrupados en intervalos de ``minutos`` y por nivel.

    Devuelve ``[{inicio (epoch UTC), nivel, n}, …]``; los intervalos vacíos no aparecen.
    """
    paso = 60 * minutos
    return [dict(r) for r in conn.execute(
        """SELECT (CAST(strftime('%s', timestamp) AS INTEGER) / :paso) * :paso AS inicio,
                  nivel, COUNT(*) AS n
             FROM evento WHERE timestamp >= :desde
            GROUP BY inicio, nivel ORDER BY inicio""",
        {"paso": paso, "desde": desde})]


@dataclass(slots=True, frozen=True)
class Pagina:
    eventos: list[Evento]
    cursor: tuple[str, int] | None   # pásalo como ``antes_de`` para la página siguiente; None = no hay más


def historial(
    conn: sqlite3.Connection,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    tipos: Sequence[str] | None = None,
    niveles: Sequence[str] | None = None,
    almacen_id: int | None = None,
    codigo: str | None = None,
    antes_de: tuple[str, int] | None = None,
    limite: int = 100,
) -> Pagina:
    """Historial filtrado, del más reciente al más antiguo, paginado por cursor.

    ``desde``/``hasta`` son timestamps ISO (``hasta`` exclusivo). ``codigo``
    filtra por prefijo del código del contenedor.
    """
    condiciones, params = [], []
    if desde:
        condiciones.append("ev.timestamp >= ?"); params.append(desde)
    if hasta:
        condiciones.append("ev.timestamp < ?"); params.append(hasta)
    if tipos:
        condiciones.append(f"ev.tipo IN ({','.join('?' * len(tipos))})"); params += list(tipos)
    if niveles:
        condiciones.append(f"ev.nivel IN ({','.join('?' * len(niveles))})"); params += list(niveles)
    if almacen_id is not None:
        condiciones.append("ev.almacen_id = ?"); params.append(almacen_id)
    if codigo:
        # Rango en vez de LIKE: usa el índice de contenedor.codigo y luego ix_evento_contenedor.
        condiciones.append(
            "ev.contenedor_id IN (SELECT id FROM contenedor WHERE codigo >= ? AND codigo < ?)")
        params += list(rango_prefijo(codigo))
    if antes_de:
        condiciones.append("(ev.timestamp < ? OR (ev.timestamp = ? AND ev.id < ?))")
        params += [antes_de[0], antes_de[0], antes_de[1]]

    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    filas = conn.execute(
        _SELECT + where + " ORDER BY ev.timestamp DESC, ev.id DESC LIMIT ?", (*params, limite + 1)
    ).fetchall()
    eventos = [Evento.desde_fila(r) for r in filas[:limite]]
    cursor = (eventos[-1].timestamp, eventos[-1].id) if len(filas) > limite else None
    return Pagina(eventos, cursor)


def rango_prefijo(prefijo: str) -> tuple[str, str]:
    """``(desde, hasta)`` tal que ``desde <= codigo < hasta`` equivale a «empieza por prefijo».

    Los códigos solo llevan A-Z y 0-9, así que ``~`` (posterior a todos ellos) cierra el rango.
    """
    prefijo = prefijo.upper()
    return prefijo, prefijo + "~"


def ultimo_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COALESCE(MAX(id), 0) FROM evento").fetchone()[0]
