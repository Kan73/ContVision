"""Apertura de conexiones SQLite con los PRAGMA del plan y manejo de transacciones."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import cache
from importlib import resources
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import ZONA_HORARIA

# Versión del esquema (PRAGMA user_version). Súbela al cambiar schema.sql y añade el paso en _migrar().
#   1 → esquema inicial (sin user_version)      2 → estancia.inferida separada en entrada_/salida_inferida
#   3 → índices de estancia por almacén y fecha (los crea schema.sql; no necesita paso en _migrar)
#   4 → ix_avist_fuente pasa a ser ix_avist_fuente_ts (fuente_id, timestamp)
VERSION_ESQUEMA = 4


def conectar(ruta: str | Path, *, inicializar: bool = True) -> sqlite3.Connection:
    """Abre la BD en ``ruta`` con ``foreign_keys``, WAL, ``synchronous = NORMAL`` y ``busy_timeout``.

    Con WAL, ``synchronous = NORMAL`` no puede corromper la BD: ante un corte de
    luz se pierde como mucho la última transacción, y cada commit es mucho más rápido.

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
        conn.execute("PRAGMA synchronous = NORMAL")
    if inicializar:
        crear_esquema(conn)
    return conn


def crear_esquema(conn: sqlite3.Connection) -> None:
    """Crea el esquema o migra una BD de una versión anterior. No hace nada si ya está al día."""
    if conn.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA:
        return
    conn.executescript(_sql_esquema())
    _migrar(conn)


def _migrar(conn: sqlite3.Connection) -> None:
    with transaccion(conn):
        if conn.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA:
            return   # otro proceso migró mientras esperábamos el bloqueo
        conn.execute("DROP INDEX IF EXISTS ix_avist_fuente")   # v3 → v4: lo sustituye ix_avist_fuente_ts
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(estancia)")}
        if "inferida" in columnas:   # v1 → v2
            conn.execute("ALTER TABLE estancia ADD COLUMN entrada_inferida INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE estancia ADD COLUMN salida_inferida INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE estancia DROP COLUMN inferida")
            from .estancias import recalcular_todos   # las estancias son datos derivados
            recalcular_todos(conn)
        conn.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")


@cache
def _sql_esquema() -> str:
    """El esquema se lee del disco una sola vez por proceso.

    La app abre una conexión por refresco; así no depende de que el fichero
    siga en el disco (p. ej. durante un cambio de rama con la app en marcha).
    """
    return resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")


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


# ------------------------------------------------------------- días en hora local

def limites_dia_local(dia: str | None = None, zona: str = ZONA_HORARIA) -> tuple[str, str]:
    """``(inicio, fin)`` en ISO UTC del día local ``YYYY-MM-DD`` (por defecto, hoy)."""
    tz = ZoneInfo(zona)
    fecha = datetime.strptime(dia, "%Y-%m-%d").date() if dia else datetime.now(tz).date()
    inicio = datetime(fecha.year, fecha.month, fecha.day, tzinfo=tz)
    fin = datetime.combine(fecha + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return a_iso(inicio), a_iso(fin)


def dia_local_de_hora(hora_utc: str, zona: str = ZONA_HORARIA) -> str:
    """Día local (``YYYY-MM-DD``) de una hora UTC ``YYYY-MM-DDTHH``.

    Permite agrupar por día local sin traer todas las filas: SQL agrupa por hora
    UTC (``substr(ts, 1, 13)``) y Python reagrupa esas pocas filas. Vale para
    zonas con desfase de horas enteras, como Europe/Madrid.
    """
    momento = datetime.strptime(hora_utc, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    return momento.astimezone(ZoneInfo(zona)).strftime("%Y-%m-%d")
