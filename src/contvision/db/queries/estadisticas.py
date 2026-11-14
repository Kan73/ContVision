"""Agregados globales (página Resumen y KPIs de Inicio)."""

from __future__ import annotations

import sqlite3


def resumen(conn: sqlite3.Connection, hoy: str | None = None) -> dict:
    """KPIs globales. ``hoy`` es ``YYYY-MM-DD`` (UTC); por defecto, la fecha actual."""
    return dict(conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM almacen)                                       AS almacenes,
             (SELECT COUNT(*) FROM contenedor)                                    AS contenedores,
             (SELECT COUNT(*) FROM avistamiento)                                  AS avistamientos,
             (SELECT COUNT(*) FROM estancia WHERE salida_ts IS NULL)              AS en_almacenes,
             (SELECT COUNT(*) FROM avistamiento WHERE estado = 'dudosa' AND revisado = 0) AS dudosas_pendientes,
             (SELECT COUNT(DISTINCT contenedor_id) FROM avistamiento
               WHERE substr(timestamp, 1, 10) = COALESCE(:hoy, date('now')))    AS contenedores_hoy,
             (SELECT COUNT(*) FROM evento WHERE nivel = 'aviso')                  AS avisos,
             (SELECT COUNT(*) FROM evento WHERE nivel = 'error')                  AS errores""",
        {"hoy": hoy},
    ).fetchone())


def avistamientos_por_estado(conn: sqlite3.Connection) -> dict[str, int]:
    return {r["estado"]: r["n"] for r in conn.execute(
        "SELECT estado, COUNT(*) AS n FROM avistamiento GROUP BY estado")}


def avistamientos_por_dia(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT substr(timestamp, 1, 10) AS dia, COUNT(*) AS n,
                  SUM(estado = 'valida') AS validas, SUM(estado = 'corregida') AS corregidas,
                  SUM(estado = 'dudosa') AS dudosas
             FROM avistamiento GROUP BY dia ORDER BY dia""")]


def actividad(
    conn: sqlite3.Connection, inicio_hoy: str, inicio_ayer: str, fin_ayer: str | None = None
) -> dict:
    """KPIs de la página de actividad. Los límites del día los da la interfaz (hora local → ISO UTC).

    ``eventos_ayer`` cuenta de ``inicio_ayer`` a ``fin_ayer``. Pasando «ahora − 24 h»
    se compara hoy con ayer *a esta misma hora*; por defecto, con el día de ayer completo.
    """
    return dict(conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM evento WHERE timestamp >= :hoy)                         AS eventos_hoy,
             (SELECT COUNT(*) FROM evento WHERE timestamp >= :ayer AND timestamp < :fin)   AS eventos_ayer,
             (SELECT COUNT(*) FROM contenedor WHERE primera_vez >= :hoy)                   AS contenedores_nuevos_hoy,
             (SELECT COUNT(*) FROM estancia WHERE salida_ts IS NULL)                       AS en_almacenes,
             (SELECT COUNT(DISTINCT almacen_id) FROM estancia WHERE salida_ts IS NULL)     AS almacenes_ocupados,
             (SELECT COUNT(*) FROM avistamiento WHERE estado = 'dudosa' AND revisado = 0)  AS dudosas_pendientes""",
        {"hoy": inicio_hoy, "ayer": inicio_ayer, "fin": fin_ayer or inicio_hoy},
    ).fetchone())
