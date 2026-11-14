"""Agregados globales (página Resumen y KPIs de Inicio)."""

from __future__ import annotations

import sqlite3

from ..conexion import dia_local_de_hora, limites_dia_local


def resumen(conn: sqlite3.Connection, hoy: str | None = None) -> dict:
    """KPIs globales. ``hoy`` es un día local ``YYYY-MM-DD`` (Europe/Madrid); por defecto, hoy."""
    inicio, fin = limites_dia_local(hoy)
    return dict(conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM almacen)                                       AS almacenes,
             (SELECT COUNT(*) FROM contenedor)                                    AS contenedores,
             (SELECT COUNT(*) FROM avistamiento)                                  AS avistamientos,
             (SELECT COUNT(*) FROM estancia WHERE salida_ts IS NULL)              AS en_almacenes,
             (SELECT COUNT(*) FROM avistamiento WHERE estado = 'dudosa' AND revisado = 0) AS dudosas_pendientes,
             (SELECT COUNT(DISTINCT contenedor_id) FROM avistamiento
               WHERE timestamp >= :ini AND timestamp < :fin)                       AS contenedores_hoy,
             (SELECT COUNT(*) FROM evento WHERE nivel = 'aviso')                  AS avisos,
             (SELECT COUNT(*) FROM evento WHERE nivel = 'error')                  AS errores""",
        {"ini": inicio, "fin": fin},
    ).fetchone())


# Una dudosa ya corregida a mano conserva estado = 'dudosa' (es lo que hizo el OCR) con
# revisado = 1. En las estadísticas cuenta como «revisada», no como dudosa pendiente.
_ESTADO_EFECTIVO = "CASE WHEN estado = 'dudosa' AND revisado = 1 THEN 'revisada' ELSE estado END"
ESTADOS = ("valida", "corregida", "dudosa", "revisada")


def avistamientos_por_estado(conn: sqlite3.Connection) -> dict[str, int]:
    """``{valida, corregida, dudosa (pendientes), revisada (dudosas resueltas a mano)}``."""
    conteo = dict.fromkeys(ESTADOS, 0)
    conteo.update({r["e"]: r["n"] for r in conn.execute(
        f"SELECT {_ESTADO_EFECTIVO} AS e, COUNT(*) AS n FROM avistamiento GROUP BY e")})
    return conteo


def avistamientos_por_dia(conn: sqlite3.Connection) -> list[dict]:
    """``[{dia, n, validas, corregidas, dudosas, revisadas}, …]`` por día **local** (Europe/Madrid)."""
    plural = {"valida": "validas", "corregida": "corregidas", "dudosa": "dudosas", "revisada": "revisadas"}
    dias: dict[str, dict] = {}
    for f in conn.execute(
        f"""SELECT substr(timestamp, 1, 13) AS hora, {_ESTADO_EFECTIVO} AS e, COUNT(*) AS n
              FROM avistamiento GROUP BY hora, e"""):
        dia = dia_local_de_hora(f["hora"])
        d = dias.setdefault(dia, {"dia": dia, "n": 0, **dict.fromkeys(plural.values(), 0)})
        d["n"] += f["n"]
        d[plural[f["e"]]] += f["n"]
    return [dias[k] for k in sorted(dias)]


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
