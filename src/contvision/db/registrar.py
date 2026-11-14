"""Alta de lecturas (plan §2) y correcciones manuales."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..lectura import Lectura, es_codigo_bien_formado, normalizar_codigo
from . import estancias
from .conexion import a_iso, ahora_iso, transaccion
from .eventos import emitir
from .gestion import eliminar_si_sin_avistamientos


@dataclass(slots=True)
class ResultadoRegistro:
    ok: bool
    avistamiento_id: int | None = None
    contenedor_id: int | None = None
    contenedor_nuevo: bool = False
    eventos: list[str] = field(default_factory=list)   # tipos emitidos, en orden
    fuera_de_orden: bool = False   # la lectura era anterior a otra ya registrada del contenedor


_ESTADOS = ("valida", "corregida", "dudosa")
_ORIENTACIONES = ("horizontal", "vertical")


def _validar(lectura: Lectura, codigo: str) -> None:
    """Errores claros antes de tocar la BD (en vez de un IntegrityError a medias)."""
    if lectura.estado not in _ESTADOS:
        raise ValueError(f"estado debe ser uno de {_ESTADOS}: {lectura.estado!r}")
    if lectura.orientacion not in _ORIENTACIONES:
        raise ValueError(f"orientacion debe ser una de {_ORIENTACIONES}: {lectura.orientacion!r}")
    if not 0.0 <= lectura.confianza <= 1.0:
        raise ValueError(f"confianza debe estar entre 0 y 1: {lectura.confianza!r}")
    if lectura.estado != "dudosa" and not es_codigo_bien_formado(codigo):
        raise ValueError(f"Código mal formado en una lectura '{lectura.estado}': {lectura.codigo!r}")


def _obtener_o_crear_contenedor(conn, codigo: str, ts: str) -> tuple[int, bool]:
    fila = conn.execute("SELECT id FROM contenedor WHERE codigo = ?", (codigo,)).fetchone()
    if fila is not None:
        return fila["id"], False
    cur = conn.execute(
        """INSERT INTO contenedor (codigo, propietario, categoria, primera_vez, ultima_vez)
           VALUES (?, ?, ?, ?, ?)""",
        (codigo, codigo[:3], codigo[3], ts, ts),
    )
    return cur.lastrowid, True


def registrar(conn: sqlite3.Connection, lectura: Lectura) -> ResultadoRegistro:
    """Registra una lectura del pipeline en una única transacción.

    Crea/actualiza el contenedor, inserta el avistamiento y sus alternativas,
    actualiza las estancias y escribe los eventos correspondientes.

    Si la lectura llega fuera de orden (su timestamp es anterior al de otra ya
    registrada del mismo contenedor), las estancias se reconstruyen con
    ``recalcular()`` en vez de aplicarse de forma incremental, y no se emiten
    eventos de movimiento (ENTRADA/SALIDA…), que estarían describiendo el pasado.
    """
    ts = a_iso(lectura.timestamp)
    codigo = normalizar_codigo(lectura.codigo)
    lectura_ocr = lectura.lectura_ocr if lectura.lectura_ocr is not None else lectura.codigo
    res = ResultadoRegistro(ok=False)

    _validar(lectura, codigo)

    def _evento(tipo, mensaje, **kw):
        emitir(conn, tipo, mensaje, timestamp=ts, **kw)
        res.eventos.append(tipo)

    with transaccion(conn):
        # 1. Fuente
        fuente = conn.execute(
            """SELECT f.id, f.tipo, f.almacen_id, a.nombre AS almacen
                 FROM fuente f JOIN almacen a ON a.id = f.almacen_id
                WHERE f.nombre = ?""",
            (lectura.fuente,),
        ).fetchone()
        if fuente is None:
            _evento(
                "FUENTE_DESCONOCIDA",
                f"Lectura de {codigo or lectura_ocr!r} desde una fuente no registrada: {lectura.fuente!r}",
                datos={"fuente": lectura.fuente, "codigo": codigo, "confianza": lectura.confianza},
            )
            return res

        def _insertar_avistamiento(contenedor_id):
            cur = conn.execute(
                """INSERT INTO avistamiento (contenedor_id, fuente_id, timestamp, lectura_ocr,
                                             confianza, estado, orientacion, ruta_recorte)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (contenedor_id, fuente["id"], ts, lectura_ocr, lectura.confianza,
                 lectura.estado, lectura.orientacion, lectura.ruta_recorte),
            )
            av_id = cur.lastrowid
            conn.executemany(
                "INSERT OR REPLACE INTO alternativa (avistamiento_id, codigo, puntuacion) VALUES (?, ?, ?)",
                [(av_id, normalizar_codigo(c), p) for c, p in lectura.alternativas],
            )
            return av_id

        # 2. Dudosa: se guarda sin contenedor y va a la cola de revisión.
        if lectura.estado == "dudosa":
            av_id = _insertar_avistamiento(None)
            _evento(
                "LECTURA_DUDOSA",
                f"Lectura dudosa {lectura_ocr!r} en {fuente['almacen']} (confianza {lectura.confianza:.2f})",
                almacen_id=fuente["almacen_id"],
                avistamiento_id=av_id,
                datos={"lectura_ocr": lectura_ocr, "confianza": lectura.confianza,
                       "alternativas": [c for c, _ in lectura.alternativas]},
            )
            res.ok, res.avistamiento_id = True, av_id
            return res

        # 3. Contenedor
        cont_id, nuevo = _obtener_o_crear_contenedor(conn, codigo, ts)
        ultima_previa = conn.execute(
            "SELECT MAX(timestamp) FROM avistamiento WHERE contenedor_id = ?", (cont_id,)).fetchone()[0]
        res.fuera_de_orden = ultima_previa is not None and ts < ultima_previa
        conn.execute(
            """UPDATE contenedor SET n_avistamientos = n_avistamientos + 1,
                      primera_vez = MIN(primera_vez, ?), ultima_vez = MAX(ultima_vez, ?)
                WHERE id = ?""",
            (ts, ts, cont_id),
        )

        # 4. Avistamiento
        av_id = _insertar_avistamiento(cont_id)
        if nuevo:
            _evento("CONTENEDOR_NUEVO", f"Nuevo contenedor {codigo} visto en {fuente['almacen']}",
                    contenedor_id=cont_id, almacen_id=fuente["almacen_id"], avistamiento_id=av_id)
        if lectura.estado == "corregida":
            _evento("LECTURA_CORREGIDA",
                    f"Lectura {lectura_ocr!r} corregida a {codigo} por el dígito de control",
                    contenedor_id=cont_id, almacen_id=fuente["almacen_id"], avistamiento_id=av_id,
                    datos={"lectura_ocr": lectura_ocr, "confianza": lectura.confianza})

        # 5-6. Estancias + almacén actual
        if res.fuera_de_orden:
            estancias.recalcular(conn, cont_id)
        else:
            for ev in estancias.aplicar(
                conn,
                contenedor_id=cont_id,
                codigo=codigo,
                almacen_id=fuente["almacen_id"],
                almacen_nombre=fuente["almacen"],
                tipo_fuente=fuente["tipo"],
                ts=ts,
                avistamiento_id=av_id,
            ):
                _evento(ev.tipo, ev.mensaje, contenedor_id=cont_id, almacen_id=ev.almacen_id,
                        avistamiento_id=av_id, datos=ev.datos or None)

        res.ok, res.avistamiento_id, res.contenedor_id, res.contenedor_nuevo = True, av_id, cont_id, nuevo
        return res


def registrar_correccion(
    conn: sqlite3.Connection,
    avistamiento_id: int,
    codigo_nuevo: str,
    usuario: str | None = None,
) -> int:
    """Corrige a mano el código de un avistamiento (página Revisión).

    Reasigna el avistamiento al contenedor correcto (creándolo si hace falta),
    lo marca como revisado, guarda la corrección y recalcula las estancias del
    contenedor anterior y del nuevo. Devuelve el id del contenedor nuevo.

    Si el avistamiento ya pertenece a ese código solo se marca como revisado.
    Si el contenedor anterior se queda sin avistamientos, se elimina (era un
    código que en realidad nunca se vio).
    """
    codigo_nuevo = normalizar_codigo(codigo_nuevo)
    if not es_codigo_bien_formado(codigo_nuevo):
        raise ValueError(f"Código mal formado: {codigo_nuevo!r}")

    with transaccion(conn):
        av = conn.execute(
            """SELECT av.id, av.contenedor_id, av.timestamp, av.lectura_ocr, c.codigo,
                      f.almacen_id
                 FROM avistamiento av
                 JOIN fuente f ON f.id = av.fuente_id
                 LEFT JOIN contenedor c ON c.id = av.contenedor_id
                WHERE av.id = ?""",
            (avistamiento_id,),
        ).fetchone()
        if av is None:
            raise LookupError(f"No existe el avistamiento {avistamiento_id}")

        codigo_anterior = av["codigo"]
        if codigo_anterior == codigo_nuevo:
            conn.execute("UPDATE avistamiento SET revisado = 1 WHERE id = ?", (avistamiento_id,))
            return av["contenedor_id"]
        cont_id, nuevo = _obtener_o_crear_contenedor(conn, codigo_nuevo, av["timestamp"])
        conn.execute(
            "UPDATE avistamiento SET contenedor_id = ?, revisado = 1 WHERE id = ?",
            (cont_id, avistamiento_id),
        )
        conn.execute(
            """INSERT INTO correccion (avistamiento_id, codigo_anterior, codigo_nuevo, usuario, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (avistamiento_id, codigo_anterior, codigo_nuevo, usuario, ahora_iso()),
        )
        if nuevo:
            emitir(conn, "CONTENEDOR_NUEVO", f"Nuevo contenedor {codigo_nuevo} (por corrección manual)",
                   contenedor_id=cont_id, almacen_id=av["almacen_id"], avistamiento_id=avistamiento_id)
        if codigo_anterior:
            mensaje = f"Avistamiento de {codigo_anterior} reasignado a {codigo_nuevo}"
        else:
            mensaje = f"Lectura dudosa {av['lectura_ocr']!r} asignada a {codigo_nuevo}"
        emitir(conn, "CORRECCION_MANUAL",
               mensaje + (f" por {usuario}" if usuario else ""),
               contenedor_id=cont_id, almacen_id=av["almacen_id"], avistamiento_id=avistamiento_id,
               datos={"codigo_anterior": codigo_anterior, "codigo_nuevo": codigo_nuevo,
                      "usuario": usuario})

        estancias.recalcular(conn, cont_id)
        if av["contenedor_id"] is not None:
            estancias.recalcular(conn, av["contenedor_id"])
            eliminar_si_sin_avistamientos(conn, av["contenedor_id"])
        return cont_id
