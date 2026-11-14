"""Crea almacenes de ejemplo repartidos por España (para probar el mapa).

Es idempotente: los almacenes que ya existan (por nombre) se dejan como están.

Uso:
    uv run python scripts/sembrar_almacenes.py                 # BD por defecto (config.ruta_bd)
    uv run python scripts/sembrar_almacenes.py --db data/contvision.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from contvision import db
from contvision.config import ruta_bd
from contvision.db import queries as q

# (nombre, tipo, lat, lon, capacidad, prefijo de cámaras, nº de cámaras interiores)
ALMACENES = [
    ("Puerto de Vigo", "puerto", 42.2328, -8.7226, 500, "vigo", 1),
    ("Puerto de A Coruña", "puerto", 43.3623, -8.3891, 350, "coruna", 1),
    ("Puerto de Bilbao", "puerto", 43.3486, -3.0353, 600, "bilbao", 2),
    ("Puerto de Barcelona", "puerto", 41.3497, 2.1563, 1200, "bcn", 2),
    ("Terminal Valencia", "terminal", 39.4445, -0.3170, 800, "vlc", 1),
    ("Puerto de Algeciras", "puerto", 36.1335, -5.4370, 1500, "alg", 2),
    ("Depósito Coslada", "deposito", 40.4237, -3.5613, 200, "coslada", 0),
    ("Terminal Ferroviaria Zaragoza", "ferroviario", 41.6563, -1.0414, None, "zgz", 0),
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=None, help="por defecto, la de config.ruta_bd()")
    args = p.parse_args()

    ruta = args.db or ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = db.conectar(ruta)
    existentes = {a.nombre for a in q.almacenes.listar(conn)}
    camaras = {f.nombre for f in q.almacenes.fuentes(conn)}

    creados = 0
    for nombre, tipo, lat, lon, capacidad, pref, interiores in ALMACENES:
        if nombre in existentes:
            continue
        fuentes = [(f"{pref}-in", "entrada"), (f"{pref}-out", "salida")]
        fuentes += [(f"{pref}-patio-{i + 1}", "interior") for i in range(interiores)]
        fuentes = [(n, t) for n, t in fuentes if n not in camaras]
        db.crear_almacen(conn, nombre, tipo, lat, lon, capacidad=capacidad, fuentes=fuentes)
        creados += 1
        print(f"  + {nombre} ({len(fuentes)} cámaras)")
    print(f"{creados} almacenes creados, {len(ALMACENES) - creados} ya existían ({ruta}).")


if __name__ == "__main__":
    main()
