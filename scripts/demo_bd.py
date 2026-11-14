"""Demo / prueba de concepto de la capa de base de datos (terminal).

Uso:
    uv run python scripts/demo_bd.py              # BD temporal, se borra al final
    uv run python scripts/demo_bd.py --db demo.db # deja la BD en ese fichero
"""

from __future__ import annotations

import argparse
import os
import random
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from contvision import db
from contvision.db import queries as q
from contvision.lectura import Lectura, digito_control

# ----------------------------------------------------------------- utilidades

USE_COLOR = os.isatty(1) and not os.environ.get("NO_COLOR")
COLORES = {"info": "36", "aviso": "33", "error": "31", "ok": "32", "titulo": "1;35", "gris": "90"}


def c(texto: str, estilo: str) -> str:
    return f"\033[{COLORES[estilo]}m{texto}\033[0m" if USE_COLOR else texto


def titulo(texto: str) -> None:
    print("\n" + c(f"━━ {texto} " + "━" * max(0, 70 - len(texto)), "titulo"))


def tabla(filas: list[dict], columnas: list[str] | None = None) -> None:
    if not filas:
        print(c("  (vacío)", "gris"))
        return
    columnas = columnas or list(filas[0])
    celdas = [[("—" if f.get(k) is None else str(f.get(k))) for k in columnas] for f in filas]
    anchos = [max(len(k), *(len(r[i]) for r in celdas)) for i, k in enumerate(columnas)]
    print("  " + "  ".join(c(k.ljust(w), "gris") for k, w in zip(columnas, anchos)))
    for r in celdas:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, anchos)))


def comprobar(condicion: bool, descripcion: str) -> None:
    marca = c("✔", "ok") if condicion else c("✘", "error")
    print(f"  {marca} {descripcion}")
    if not condicion:
        raise SystemExit(f"Fallo en la comprobación: {descripcion}")


def codigo(prefijo: str, serie: int) -> str:
    base = f"{prefijo}{serie:06d}"
    return base + str(digito_control(base))


def hora(t: datetime) -> str:
    return t.strftime("%d/%m %H:%M")


def mostrar_eventos(eventos) -> None:
    for ev in eventos:
        print(f"  {c(f'#{ev.id:<3}', 'gris')} {ev.timestamp[5:16].replace('T', ' ')}  "
              f"{c(ev.nivel.upper().ljust(5), ev.nivel)}  {ev.tipo:<21} {ev.mensaje}")


# ------------------------------------------------------------------- la demo

def demo(conn) -> None:
    # Fechas relativas a hoy y siempre en el pasado: la historia empieza hace 30 días.
    t0 = (datetime.now(UTC) - timedelta(days=30)).replace(hour=8, minute=0, second=0, microsecond=0)

    # 1 ─ Almacenes a demanda ------------------------------------------------
    titulo("1. Crear almacenes y sus fuentes (cámaras)")
    vigo = db.crear_almacen(conn, "Puerto de Vigo", "puerto", 42.2328, -8.7226, capacidad=500,
                            fuentes=[("vigo-in", "entrada"), ("vigo-out", "salida"), ("vigo-patio", "interior")])
    valencia = db.crear_almacen(conn, "Terminal Valencia", "terminal", 39.4445, -0.3170, capacidad=800,
                                fuentes=[("vlc-in", "entrada"), ("vlc-out", "salida")])
    madrid = db.crear_almacen(conn, "Depósito Coslada", "deposito", 40.4237, -3.5613, capacidad=200)
    print("  Creados 3 almacenes. El último con las fuentes por defecto (entrada/salida).")
    tabla([{"id": a.id, "nombre": a.nombre, "tipo": a.tipo, "lat": a.lat, "lon": a.lon,
            "capacidad": a.capacidad} for a in q.almacenes.listar(conn)])
    print()
    tabla([{"fuente": f.nombre, "almacén_id": f.almacen_id, "tipo": f.tipo} for f in q.almacenes.fuentes(conn)])

    # 2 ─ Registrar lecturas -------------------------------------------------
    titulo("2. Registrar lecturas del pipeline")
    A, B, C, D = codigo("MSCU", 123456), codigo("MAEU", 765432), codigo("CMAU", 111111), codigo("HLXU", 222222)
    mal_A = A[:4] + "8" + A[5:]   # el OCR confunde un dígito
    lecturas = [
        # A: ciclo completo Vigo → Valencia
        Lectura(A, "vigo-in",    t0,                       0.97, "valida"),
        Lectura(A, "vigo-patio", t0 + timedelta(hours=5),  0.91, "valida", "vertical"),
        Lectura(A, "vigo-out",   t0 + timedelta(days=2),   0.95, "valida"),
        Lectura(A, "vlc-in",     t0 + timedelta(days=4),   0.88, "corregida", lectura_ocr=mal_A),
        # B: entra en Vigo y aparece en Valencia sin leer su salida
        Lectura(B, "vigo-in",    t0 + timedelta(hours=1),  0.96, "valida"),
        Lectura(B, "vlc-in",     t0 + timedelta(days=3),   0.93, "valida"),
        # C: primera lectura en el patio interior (entrada inferida)
        Lectura(C, "vigo-patio", t0 + timedelta(hours=2),  0.90, "valida"),
        # D: sale de Coslada sin entrada registrada
        Lectura(D, "Depósito Coslada · salida", t0 + timedelta(days=1), 0.94, "valida"),
        # Lectura dudosa → cola de revisión
        Lectura("HLXU22?222", "vlc-in", t0 + timedelta(days=3, hours=2), 0.41, "dudosa",
                alternativas=((D, 0.62), (codigo("HLXU", 222232), 0.31))),
        # Fuente que no existe
        Lectura(A, "camara-fantasma", t0 + timedelta(days=5), 0.99, "valida"),
    ]
    for lec in lecturas:
        r = db.registrar(conn, lec)
        estado = c("ok", "ok") if r.ok else c("rechazada", "error")
        print(f"  {hora(lec.timestamp)}  "
              f"{lec.codigo:<12} @ {lec.fuente:<27} {estado:<4}  → {', '.join(r.eventos) or '—'}")

    # 3 ─ Acceso a los datos -------------------------------------------------
    titulo("3. Ocupación de almacenes")
    tabla([{"almacén": a.nombre, "presentes": a.presentes, "capacidad": a.capacidad,
            "ocupación": f"{a.ocupacion:.1%}" if a.ocupacion is not None else None}
           for a in q.almacenes.listar(conn)])

    titulo("Contenedores presentes en Terminal Valencia")
    tabla([{"código": e.codigo, "desde": e.entrada_ts[:16], "inferida": bool(e.inferida)}
           for e in q.almacenes.presentes(conn, valencia)])

    titulo(f"Ficha de {A}")
    cont = q.contenedores.obtener(conn, A)
    print(f"  propietario={cont.propietario}  categoría={cont.categoria}  avistamientos={cont.n_avistamientos}  "
          f"ubicación actual={cont.almacen_actual}")
    print(c("  Avistamientos:", "gris"))
    tabla([{"ts": a.timestamp[:16], "fuente": a.fuente, "tipo": a.tipo_fuente, "ocr": a.lectura_ocr,
            "conf": a.confianza, "estado": a.estado} for a in q.contenedores.avistamientos(conn, A)])
    print(c("  Recorrido (estancias):", "gris"))
    tabla([{"almacén": e.almacen, "entrada": e.entrada_ts[:16], "salida": (e.salida_ts or "")[:16] or None,
            "inferida": bool(e.inferida)} for e in q.contenedores.recorrido(conn, A)])

    titulo(f"Recorrido de {B} (traslado sin salida)")
    tabla([{"almacén": e.almacen, "entrada": e.entrada_ts[:16], "salida": (e.salida_ts or "")[:16] or None,
            "inferida": bool(e.inferida)} for e in q.contenedores.recorrido(conn, B)])

    # 4 ─ Revisión manual ----------------------------------------------------
    titulo("4. Cola de revisión y corrección manual")
    pendientes = q.contenedores.pendientes_revision(conn)
    tabla([{"avist.": a.id, "ocr": a.lectura_ocr, "conf": a.confianza, "almacén": a.almacen,
            "alternativas": ", ".join(c_ for c_, _ in q.contenedores.alternativas(conn, a.id))} for a in pendientes])
    dudosa = pendientes[0]
    elegido = q.contenedores.alternativas(conn, dudosa.id)[0][0]
    db.registrar_correccion(conn, dudosa.id, elegido, usuario="revisor")
    print(f"  Avistamiento {dudosa.id} asignado a {elegido}.")
    tabla([{"almacén": e.almacen, "entrada": e.entrada_ts[:16], "salida": (e.salida_ts or "")[:16] or None,
            "inferida": bool(e.inferida)} for e in q.contenedores.recorrido(conn, elegido)])
    comprobar(not q.contenedores.pendientes_revision(conn), "la cola de revisión queda vacía")

    # 5 ─ Historial de eventos ----------------------------------------------
    titulo("5. Historial de eventos (feed, más recientes primero)")
    mostrar_eventos(q.eventos.feed(conn, limite=100))

    titulo("Historial filtrado: solo avisos y errores, páginas de 2")
    pagina = q.eventos.historial(conn, niveles=["aviso", "error"], limite=2)
    n = 1
    while True:
        print(c(f"  página {n}", "gris"))
        mostrar_eventos(pagina.eventos)
        if pagina.cursor is None:
            break
        pagina = q.eventos.historial(conn, niveles=["aviso", "error"], limite=2, antes_de=pagina.cursor)
        n += 1

    titulo(f"Historial de un almacén (Puerto de Vigo) y de un contenedor ({A})")
    mostrar_eventos(q.eventos.historial(conn, almacen_id=vigo, tipos=["ENTRADA", "SALIDA"]).eventos)
    print()
    mostrar_eventos(q.eventos.historial(conn, codigo=A).eventos)

    ultimo = q.eventos.ultimo_id(conn)
    db.registrar(conn, Lectura(C, "vigo-out", t0 + timedelta(days=6), 0.92, "valida"))
    nuevos = q.eventos.feed(conn, desde_id=ultimo)
    print(c(f"\n  Feed en vivo: tras el id {ultimo} llegan {len(nuevos)} eventos nuevos:", "gris"))
    mostrar_eventos(nuevos)

    # 6 ─ Consistencia --------------------------------------------------------
    titulo("6. Consistencia: estancias incrementales == recalculadas")
    def instantanea():
        return conn.execute("""SELECT contenedor_id, almacen_id, entrada_ts, salida_ts, inferida
                                 FROM estancia ORDER BY contenedor_id, entrada_ts""").fetchall()
    antes = [tuple(r) for r in instantanea()]
    db.recalcular_todos(conn)
    comprobar(antes == [tuple(r) for r in instantanea()], f"{len(antes)} estancias idénticas tras recalcular")

    random.seed(7)
    fuentes = [f.nombre for f in q.almacenes.fuentes(conn)]
    t = t0 + timedelta(days=10)
    for i in range(500):
        t += timedelta(minutes=random.randint(1, 50))   # ~9 días en total: acaba antes de hoy
        db.registrar(conn, Lectura(codigo("TGHU", random.randint(0, 40)), random.choice(fuentes), t,
                                   round(random.uniform(0.7, 1), 2), "valida"))
    antes = [tuple(r) for r in instantanea()]
    db.recalcular_todos(conn)
    comprobar(antes == [tuple(r) for r in instantanea()],
              f"tras 500 lecturas aleatorias: {len(antes)} estancias idénticas tras recalcular")
    try:
        conn.execute("INSERT INTO estancia (contenedor_id, almacen_id, entrada_ts) "
                     "SELECT contenedor_id, almacen_id, '2030-01-01' FROM estancia WHERE salida_ts IS NULL LIMIT 1")
        comprobar(False, "la BD impide dos estancias abiertas del mismo contenedor")
    except Exception:
        comprobar(True, "la BD impide dos estancias abiertas del mismo contenedor")

    # 7 ─ Altas y bajas ----------------------------------------------------
    titulo("7. Altas y bajas")
    bilbao = db.crear_almacen(conn, "Puerto de Bilbao", "puerto", 43.3486, -3.0353)
    db.crear_fuente(conn, "bilbao-grua-3", bilbao, "interior")
    print(f"  Creado 'Puerto de Bilbao' (id {bilbao}) con {len(q.almacenes.fuentes(conn, bilbao))} fuentes.")
    db.eliminar_almacen(conn, bilbao)
    comprobar(q.almacenes.obtener(conn, bilbao) is None, "un almacén vacío se elimina directamente")

    try:
        db.eliminar_almacen(conn, madrid)
        comprobar(False, "un almacén con datos no se elimina sin forzar")
    except db.EnUsoError as e:
        comprobar(True, f"un almacén con datos no se elimina sin forzar ({e})")
    db.eliminar_almacen(conn, madrid, forzar=True)
    comprobar(q.almacenes.obtener(conn, madrid) is None, "…pero sí con forzar=True")
    comprobar(not any(e.almacen_id == madrid for c_ in [D] for e in q.contenedores.recorrido(conn, c_)),
              f"{D} ya no tiene estancias en el almacén eliminado")

    db.eliminar_contenedor(conn, B)
    comprobar(q.contenedores.obtener(conn, B) is None and not q.contenedores.avistamientos(conn, B),
              f"{B} eliminado con sus avistamientos")
    comprobar(bool(q.eventos.historial(conn, tipos=["TRASLADO_SIN_SALIDA"]).eventos),
              "los eventos antiguos siguen en el historial")

    titulo("Últimos eventos de administración")
    mostrar_eventos(q.eventos.historial(
        conn, tipos=["ALMACEN_CREADO", "ALMACEN_ELIMINADO", "FUENTE_CREADA", "CONTENEDOR_ELIMINADO"], limite=5).eventos)

    # 8 ─ Resumen -----------------------------------------------------------
    titulo("8. Resumen global")
    tabla([q.estadisticas.resumen(conn, hoy=(t0 + timedelta(days=3)).strftime("%Y-%m-%d"))])
    print()
    tabla([{"estado": k, "n": v} for k, v in q.estadisticas.avistamientos_por_estado(conn).items()])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, help="fichero SQLite a usar (se sobrescribe). Por defecto, uno temporal")
    args = parser.parse_args()

    if args.db:
        ruta, temporal = args.db, None
        for sufijo in ("", "-wal", "-shm"):
            Path(f"{ruta}{sufijo}").unlink(missing_ok=True)
    else:
        temporal = tempfile.TemporaryDirectory(prefix="contvision-")
        ruta = Path(temporal.name) / "demo.db"

    print(c(f"Base de datos: {ruta}", "gris"))
    conn = db.conectar(ruta)
    try:
        demo(conn)
        print("\n" + c("Demo completada.", "ok"))
    finally:
        conn.close()
        if temporal:
            temporal.cleanup()


if __name__ == "__main__":
    main()
