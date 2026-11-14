"""Simulador en vivo mínimo: inserta una lectura aleatoria cada N segundos.

Sirve para ver el feed de la página de actividad moviéndose. Usa los almacenes
y fuentes que ya haya en la BD (carga antes la demo si está vacía).

Uso:
    uv run python scripts/simular_vivo.py                 # BD por defecto (config.ruta_bd)
    uv run python scripts/simular_vivo.py --cada 1 --db data/contvision.db
    uv run python scripts/simular_vivo.py --rafaga 200    # inserta 200 lecturas en la última hora y sale
"""

from __future__ import annotations

import argparse
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from contvision import db
from contvision.config import ruta_bd
from contvision.db import queries as q
from contvision.lectura import Lectura, digito_control

PREFIJOS = ["MSCU", "MAEU", "CMAU", "HLXU", "TGHU", "OOLU", "CSQU"]


def codigo_aleatorio(rng: random.Random, pool: int) -> str:
    base = f"{rng.choice(PREFIJOS)}{rng.randrange(pool):06d}"
    return base + str(digito_control(base))


def lectura_aleatoria(rng: random.Random, fuentes: list[str], cuando: datetime, pool: int) -> Lectura:
    codigo = codigo_aleatorio(rng, pool)
    r = rng.random()
    if r < 0.01:
        return Lectura(codigo, "camara-desconocida", cuando, 0.9, "valida")
    fuente = rng.choice(fuentes)
    if r < 0.07:
        ocr = codigo[:5] + "?" + codigo[6:]
        return Lectura(ocr, fuente, cuando, round(rng.uniform(0.3, 0.6), 2), "dudosa",
                       alternativas=((codigo, 0.6),))
    if r < 0.17:
        ocr = codigo[:-1] + str((int(codigo[-1]) + 1) % 10)
        return Lectura(codigo, fuente, cuando, round(rng.uniform(0.7, 0.9), 2), "corregida", lectura_ocr=ocr)
    return Lectura(codigo, fuente, cuando, round(rng.uniform(0.85, 1.0), 2), "valida",
                   orientacion=rng.choice(["horizontal", "vertical"]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=None, help="por defecto, la de config.ruta_bd()")
    p.add_argument("--cada", type=float, default=3.0, help="segundos entre lecturas (por defecto 3)")
    p.add_argument("--pool", type=int, default=300, help="nº de códigos distintos posibles por prefijo")
    p.add_argument("--rafaga", type=int, default=0, help="inserta N lecturas repartidas en la última hora y sale")
    p.add_argument("--semilla", type=int, default=None)
    args = p.parse_args()

    ruta = args.db or ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = db.conectar(ruta)
    fuentes = [f.nombre for f in q.almacenes.fuentes(conn) if f.activa]
    if not fuentes:
        raise SystemExit("No hay fuentes en la BD. Carga antes la demo:\n"
                         f"  uv run python scripts/demo_bd.py --db {ruta}")
    rng = random.Random(args.semilla)

    if args.rafaga:
        ahora = datetime.now(UTC)
        momentos = sorted(ahora - timedelta(seconds=rng.uniform(0, 3600)) for _ in range(args.rafaga))
        for m in momentos:
            db.registrar(conn, lectura_aleatoria(rng, fuentes, m, args.pool))
        print(f"{args.rafaga} lecturas insertadas en la última hora ({ruta}).")
        return

    print(f"Insertando una lectura cada {args.cada:g} s en {ruta}. Ctrl+C para parar.")
    try:
        while True:
            lec = lectura_aleatoria(rng, fuentes, datetime.now(UTC), args.pool)
            r = db.registrar(conn, lec)
            print(f"{datetime.now():%H:%M:%S}  {lec.codigo:<12} @ {lec.fuente:<28} → {', '.join(r.eventos) or '—'}")
            time.sleep(args.cada)
    except KeyboardInterrupt:
        print("\nParado.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
