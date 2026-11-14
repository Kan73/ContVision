"""Dataclasses que devuelven las consultas."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, fields
from typing import Any, Self


class _DesdeFila:
    @classmethod
    def desde_fila(cls, fila: sqlite3.Row) -> Self:
        claves = fila.keys()
        return cls(**{f.name: fila[f.name] for f in fields(cls) if f.name in claves})


@dataclass(slots=True, frozen=True)
class Almacen(_DesdeFila):
    id: int
    nombre: str
    tipo: str
    lat: float
    lon: float
    capacidad: int | None
    descripcion: str | None
    presentes: int = 0

    @property
    def ocupacion(self) -> float | None:
        return self.presentes / self.capacidad if self.capacidad else None


@dataclass(slots=True, frozen=True)
class Fuente(_DesdeFila):
    id: int
    nombre: str
    almacen_id: int
    tipo: str
    activa: int
    n_avistamientos: int = 0


@dataclass(slots=True, frozen=True)
class Contenedor(_DesdeFila):
    id: int
    codigo: str
    propietario: str
    categoria: str
    primera_vez: str
    ultima_vez: str
    n_avistamientos: int
    almacen_actual_id: int | None
    almacen_actual: str | None = None


@dataclass(slots=True, frozen=True)
class Avistamiento(_DesdeFila):
    id: int
    contenedor_id: int | None
    codigo: str | None
    fuente: str
    tipo_fuente: str
    almacen: str
    timestamp: str
    lectura_ocr: str
    confianza: float
    estado: str
    orientacion: str
    revisado: int
    ruta_recorte: str | None = None


@dataclass(slots=True, frozen=True)
class Estancia(_DesdeFila):
    id: int
    contenedor_id: int
    codigo: str
    almacen_id: int
    almacen: str
    entrada_ts: str
    salida_ts: str | None
    entrada_inferida: int   # 1 = la entrada se dedujo de una cámara interior
    salida_inferida: int    # 1 = la salida se dedujo al aparecer en otro almacén
    lat: float | None = None
    lon: float | None = None


@dataclass(slots=True, frozen=True)
class Evento(_DesdeFila):
    id: int
    timestamp: str
    tipo: str
    nivel: str
    mensaje: str
    contenedor_id: int | None
    almacen_id: int | None
    avistamiento_id: int | None
    datos: str | None
    codigo: str | None = None
    almacen: str | None = None

    @property
    def datos_dict(self) -> dict[str, Any]:
        return json.loads(self.datos) if self.datos else {}
