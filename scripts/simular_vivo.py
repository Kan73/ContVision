"""Simulador de lecturas con itinerarios: entra en A → cámaras interiores → sale → entra en B…

Cada contenedor sigue un recorrido coherente, así que la mayoría de eventos son
ENTRADA/SALIDA normales. Los avisos salen de fallos simulados con probabilidad
pequeña: lectura de salida perdida, salida sin entrada, lectura dudosa y cámara
desconocida. Usa los almacenes y fuentes que haya en la BD y continúa desde su
estado actual (quién está dentro de cada almacén).

Uso:
    uv run python scripts/simular_vivo.py                       # una lectura cada 3 s (BD por defecto)
    uv run python scripts/simular_vivo.py --cada 1 --db data/contvision.db
    uv run python scripts/simular_vivo.py --rafaga 250          # 250 lecturas repartidas en la última hora
    uv run python scripts/simular_vivo.py --rafaga 100000 --horas 720   # histórico de 30 días
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
from contvision.db.eventos import TIPOS_EVENTO
from contvision.lectura import Lectura, digito_control

PREFIJOS = ["MSCU", "MAEU", "CMAU", "HLXU", "TGHU", "OOLU", "CSQU"]
TAM_LOTE = 1000   # lecturas por transacción en modo ráfaga

# Probabilidades de fallo (por lectura)
P_SALIDA_PERDIDA = 0.02     # entra en otro almacén sin leerse su salida → TRASLADO_SIN_SALIDA
P_SALIDA_SIN_ENTRADA = 0.01
P_DUDOSA = 0.03
P_CORREGIDA = 0.08
P_FUENTE_DESCONOCIDA = 0.003


class Bolsa:
    """Conjunto con elección aleatoria y borrado en O(1)."""

    def __init__(self, elementos=()):
        self._lista: list[str] = []
        self._pos: dict[str, int] = {}
        for e in elementos:
            self.meter(e)

    def __len__(self) -> int:
        return len(self._lista)

    def __contains__(self, e: str) -> bool:
        return e in self._pos

    def meter(self, e: str) -> None:
        if e not in self._pos:
            self._pos[e] = len(self._lista)
            self._lista.append(e)

    def sacar(self, e: str) -> None:
        i = self._pos.pop(e, None)
        if i is None:
            return
        ultimo = self._lista.pop()
        if i < len(self._lista):
            self._lista[i] = ultimo
            self._pos[ultimo] = i

    def uno(self, rng: random.Random) -> str:
        return rng.choice(self._lista)


class Simulador:
    """Modelo en memoria de dónde está cada contenedor; genera la siguiente lectura."""

    def __init__(self, conn, rng: random.Random, objetivo: int, pool: int):
        self.rng, self.objetivo, self.pool = rng, objetivo, pool
        # almacén → {tipo de fuente: [nombres]}
        self.camaras: dict[int, dict[str, list[str]]] = {}
        for f in q.almacenes.fuentes(conn):
            if f.activa:
                self.camaras.setdefault(f.almacen_id, {"entrada": [], "salida": [], "interior": []})[f.tipo].append(f.nombre)
        self.camaras = {a: c for a, c in self.camaras.items() if c["entrada"] and c["salida"]}
        if not self.camaras:
            raise SystemExit("No hay ningún almacén con cámara de entrada y de salida. Carga antes la demo:\n"
                             "  uv run python scripts/demo_bd.py --db <ruta>")
        self.almacenes = list(self.camaras)

        # Estado inicial tomado de la BD
        self.donde: dict[str, int] = {}
        self.dentro = Bolsa()
        for a in self.almacenes:
            for e in q.almacenes.presentes(conn, a):
                self.donde[e.codigo] = a
                self.dentro.meter(e.codigo)
        self.fuera = Bolsa(c.codigo for c in q.contenedores.listar(conn, limite=5000)
                           if c.almacen_actual_id is None)

    # ---------------------------------------------------------------- piezas
    def _codigo_nuevo(self) -> str:
        while True:
            base = f"{self.rng.choice(PREFIJOS)}{self.rng.randrange(self.pool):06d}"
            codigo = base + str(digito_control(base))
            if codigo not in self.dentro and codigo not in self.fuera:
                return codigo

    def _entra(self, codigo: str, almacen: int) -> None:
        self.fuera.sacar(codigo)
        self.dentro.meter(codigo)
        self.donde[codigo] = almacen

    def _sale(self, codigo: str) -> None:
        self.dentro.sacar(codigo)
        self.donde.pop(codigo, None)
        self.fuera.meter(codigo)

    # ------------------------------------------------------------- siguiente
    def siguiente(self, cuando: datetime) -> Lectura:
        rng = self.rng
        if rng.random() < P_FUENTE_DESCONOCIDA:
            return Lectura(self._codigo_nuevo(), "camara-desconocida", cuando, 0.9, "valida")

        # Qué pasa: entrar, verse en una cámara interior o salir. Se tiende a `objetivo` dentro.
        n = len(self.dentro)
        p_entrar = 1.0 if n == 0 else (0.6 if n < self.objetivo else 0.3)
        r = rng.random()
        if r < p_entrar:
            almacen = rng.choice(self.almacenes)
            otros = n and rng.random() < P_SALIDA_PERDIDA
            if otros:   # ya estaba dentro de otro almacén y no se leyó su salida
                codigo = self.dentro.uno(rng)
            elif len(self.fuera) and rng.random() < 0.5:
                codigo = self.fuera.uno(rng)
            else:
                codigo = self._codigo_nuevo()
            fuente, efecto = rng.choice(self.camaras[almacen]["entrada"]), ("entra", almacen)
        elif len(self.fuera) and rng.random() < P_SALIDA_SIN_ENTRADA:
            codigo = self.fuera.uno(rng)
            fuente, efecto = rng.choice(self.camaras[rng.choice(self.almacenes)]["salida"]), None
        else:
            codigo = self.dentro.uno(rng)
            almacen = self.donde[codigo]
            interiores = self.camaras[almacen]["interior"]
            if interiores and r < p_entrar + (1 - p_entrar) * 0.35:
                fuente, efecto = rng.choice(interiores), None
            else:
                fuente, efecto = rng.choice(self.camaras[almacen]["salida"]), ("sale", None)

        # Ruido del OCR
        r = rng.random()
        if r < P_DUDOSA:   # no se asigna a ningún contenedor: el estado no cambia
            ocr = codigo[:5] + "?" + codigo[6:]
            return Lectura(ocr, fuente, cuando, round(rng.uniform(0.3, 0.6), 2), "dudosa",
                           alternativas=((codigo, 0.6),))
        if efecto:
            self._entra(codigo, efecto[1]) if efecto[0] == "entra" else self._sale(codigo)
        if r < P_DUDOSA + P_CORREGIDA:
            ocr = codigo[:-1] + str((int(codigo[-1]) + 1) % 10)
            return Lectura(codigo, fuente, cuando, round(rng.uniform(0.7, 0.9), 2), "corregida", lectura_ocr=ocr)
        return Lectura(codigo, fuente, cuando, round(rng.uniform(0.85, 1.0), 2), "valida",
                       orientacion=rng.choice(["horizontal", "vertical"]))


def rafaga(conn, sim: Simulador, n: int, horas: float) -> None:
    ahora = datetime.now(UTC)
    momentos = sorted(ahora - timedelta(seconds=sim.rng.uniform(0, horas * 3600)) for _ in range(n))
    id_antes = q.eventos.ultimo_id(conn)
    inicio = time.perf_counter()
    for i in range(0, n, TAM_LOTE):
        with db.transaccion(conn):   # un lote = una transacción (un solo commit a disco)
            for m in momentos[i:i + TAM_LOTE]:
                db.registrar(conn, sim.siguiente(m))
    seg = time.perf_counter() - inicio

    nuevos = q.eventos.ultimo_id(conn) - id_antes
    por_nivel = {"info": 0, "aviso": 0, "error": 0}
    for ev in q.eventos.feed(conn, desde_id=id_antes, limite=nuevos):
        por_nivel[TIPOS_EVENTO[ev.tipo]] += 1
    print(f"{n} lecturas en {seg:.1f} s ({n / seg:,.0f}/s), repartidas en las últimas {horas:g} h.")
    if nuevos:
        print(f"{nuevos} eventos: " + ", ".join(f"{k} {v} ({v / nuevos:.1%})" for k, v in por_nivel.items()))
    print(f"Contenedores dentro de almacenes: {len(sim.dentro)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=None, help="por defecto, la de config.ruta_bd()")
    p.add_argument("--cada", type=float, default=3.0, help="segundos entre lecturas (por defecto 3)")
    p.add_argument("--rafaga", type=int, default=0, help="inserta N lecturas de golpe y sale")
    p.add_argument("--horas", type=float, default=1.0, help="con --rafaga: periodo en el que se reparten (por defecto 1 h)")
    p.add_argument("--objetivo", type=int, default=150, help="nº aproximado de contenedores dentro de almacenes")
    p.add_argument("--pool", type=int, default=100_000, help="nº de series posibles por prefijo")
    p.add_argument("--semilla", type=int, default=None)
    args = p.parse_args()

    ruta = args.db or ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = db.conectar(ruta)
    sim = Simulador(conn, random.Random(args.semilla), args.objetivo, args.pool)

    if args.rafaga:
        rafaga(conn, sim, args.rafaga, args.horas)
        return

    print(f"Insertando una lectura cada {args.cada:g} s en {ruta}. Ctrl+C para parar.")
    try:
        while True:
            lec = sim.siguiente(datetime.now(UTC))
            r = db.registrar(conn, lec)
            print(f"{datetime.now():%H:%M:%S}  {lec.codigo:<12} @ {lec.fuente:<28} → {', '.join(r.eventos) or '—'}", flush=True)
            time.sleep(args.cada)
    except KeyboardInterrupt:
        print("\nParado.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
