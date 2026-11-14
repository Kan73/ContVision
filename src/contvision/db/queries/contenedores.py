"""Consultas de contenedores: ficha, avistamientos, recorrido, revisión."""

from __future__ import annotations

import sqlite3

from ._modelos import Avistamiento, Contenedor, Estancia
from .eventos import rango_prefijo

_SELECT_CONT = """
    SELECT c.*, a.nombre AS almacen_actual
      FROM contenedor c LEFT JOIN almacen a ON a.id = c.almacen_actual_id
"""

_SELECT_AVIST = """
    SELECT av.*, c.codigo, f.nombre AS fuente, f.tipo AS tipo_fuente, a.nombre AS almacen
      FROM avistamiento av
      JOIN fuente f  ON f.id = av.fuente_id
      JOIN almacen a ON a.id = f.almacen_id
      LEFT JOIN contenedor c ON c.id = av.contenedor_id
"""


def obtener(conn: sqlite3.Connection, codigo: str) -> Contenedor | None:
    fila = conn.execute(_SELECT_CONT + " WHERE c.codigo = ?", (codigo,)).fetchone()
    return Contenedor.desde_fila(fila) if fila else None


def listar(
    conn: sqlite3.Connection,
    *,
    almacen_id: int | None = None,
    propietario: str | None = None,
    prefijo: str | None = None,
    limite: int = 100,
) -> list[Contenedor]:
    """Contenedores filtrados, los vistos más recientemente primero."""
    condiciones, params = ["1 = 1"], []
    if almacen_id is not None:
        condiciones.append("c.almacen_actual_id = ?"); params.append(almacen_id)
    if propietario:
        condiciones.append("c.propietario = ?"); params.append(propietario)
    if prefijo:
        condiciones.append("c.codigo >= ? AND c.codigo < ?"); params += list(rango_prefijo(prefijo))
    sql = _SELECT_CONT + " WHERE " + " AND ".join(condiciones) + " ORDER BY c.ultima_vez DESC LIMIT ?"
    return [Contenedor.desde_fila(r) for r in conn.execute(sql, (*params, limite))]


def avistamientos(conn: sqlite3.Connection, codigo: str) -> list[Avistamiento]:
    """Histórico de lecturas de un contenedor, en orden cronológico."""
    return [Avistamiento.desde_fila(r) for r in conn.execute(
        _SELECT_AVIST + " WHERE c.codigo = ? ORDER BY av.timestamp, av.id", (codigo,))]


def recorrido(conn: sqlite3.Connection, codigo: str) -> list[Estancia]:
    """Estancias del contenedor por almacenes (con lat/lon para el mini-mapa)."""
    return [Estancia.desde_fila(r) for r in conn.execute(
        """SELECT e.*, c.codigo, a.nombre AS almacen, a.lat, a.lon
             FROM estancia e
             JOIN contenedor c ON c.id = e.contenedor_id
             JOIN almacen a    ON a.id = e.almacen_id
            WHERE c.codigo = ?
            ORDER BY e.entrada_ts, e.id""",
        (codigo,),
    )]


def pendientes_revision(conn: sqlite3.Connection, limite: int = 100) -> list[Avistamiento]:
    """Lecturas dudosas sin revisar (cola de la página Revisión)."""
    return [Avistamiento.desde_fila(r) for r in conn.execute(
        _SELECT_AVIST + " WHERE av.estado = 'dudosa' AND av.revisado = 0 ORDER BY av.timestamp LIMIT ?",
        (limite,))]


def alternativas(conn: sqlite3.Connection, avistamiento_id: int) -> list[tuple[str, float]]:
    return [(r["codigo"], r["puntuacion"]) for r in conn.execute(
        "SELECT codigo, puntuacion FROM alternativa WHERE avistamiento_id = ? ORDER BY puntuacion DESC",
        (avistamiento_id,))]
