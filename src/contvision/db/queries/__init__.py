"""Consultas de solo lectura. La interfaz solo usa estas funciones (nunca SQL)."""

from . import almacenes, contenedores, estadisticas, eventos

__all__ = ["almacenes", "contenedores", "estadisticas", "eventos"]
