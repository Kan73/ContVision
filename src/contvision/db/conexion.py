"""Apertura de conexiones SQLite con los PRAGMA del plan y manejo de transacciones."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path


def conectar(ruta: str | Path, *, inicializar: bool = True) -> sqlite3.Connection:
    """Abre la BD en ``ruta`` con ``foreign_keys``, WAL y ``busy_timeout``.

    La conexión trabaja en modo autocommit; las escrituras de varias sentencias
    se agrupan con :func:`transaccion`. Si ``inicializar`` es True se crea el
    esquema (es idempotente).
    """
    conn = sqlite3.connect(ruta, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if str(ruta) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    if inicializar:
        crear_esquema(conn)
    return conn


def crear_esquema(conn: sqlite3.Connection) -> None:
    sql = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(sql)


@contextmanager
def transaccion(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """``BEGIN IMMEDIATE`` … ``COMMIT`` (o ``ROLLBACK`` si hay excepción).

    Es reentrante: si ya hay una transacción abierta, se une a ella, de modo que
    funciones como ``recalcular()`` pueden llamarse sueltas o dentro de otra.
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def ahora_iso() -> str:
    return a_iso(datetime.now(UTC))


def a_iso(momento: datetime | str) -> str:
    """Normaliza a ISO 8601 UTC con milisegundos (``2026-11-14T15:30:00.000Z``).

    Un formato fijo hace que el orden de las cadenas coincida con el temporal.
    Las fechas sin zona horaria se asumen en UTC.
    """
    if isinstance(momento, str):
        momento = datetime.fromisoformat(momento.replace("Z", "+00:00"))
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
