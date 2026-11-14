"""Capa de base de datos de ContVision (SQLite).

Escritura: :func:`registrar`, :func:`registrar_correccion` y las funciones de
:mod:`.gestion`. Lectura: :mod:`.queries`.
"""

from . import queries
from .conexion import a_iso, ahora_iso, conectar, transaccion
from .estancias import recalcular, recalcular_todos
from .gestion import (
    EnUsoError,
    activar_fuente,
    actualizar_almacen,
    crear_almacen,
    crear_fuente,
    eliminar_almacen,
    eliminar_contenedor,
    eliminar_fuente,
)
from .registrar import ResultadoRegistro, registrar, registrar_correccion

__all__ = [
    "EnUsoError", "ResultadoRegistro", "a_iso", "activar_fuente", "actualizar_almacen",
    "ahora_iso", "conectar", "crear_almacen", "crear_fuente", "eliminar_almacen",
    "eliminar_contenedor", "eliminar_fuente", "queries", "recalcular", "recalcular_todos",
    "registrar", "registrar_correccion", "transaccion",
]
