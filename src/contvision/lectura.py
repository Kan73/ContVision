"""Contrato ``Lectura``: lo que el pipeline de visión entrega a la base de datos.

PROVISIONAL: el contrato definitivo se fija en M0.7. Aquí están solo los campos
que necesita la capa de BD (plan_interfaz_bd §2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Estado = Literal["valida", "corregida", "dudosa"]
Orientacion = Literal["horizontal", "vertical"]

_PATRON_CODIGO = re.compile(r"^[A-Z]{3}[UJZ]\d{7}$")
# Valores ISO 6346: A=10 … Z=38, saltando los múltiplos de 11.
_VALOR_LETRA = {}
_v = 10
for _letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if _v % 11 == 0:
        _v += 1
    _VALOR_LETRA[_letra] = _v
    _v += 1


@dataclass(frozen=True, slots=True)
class Lectura:
    codigo: str                 # código final (tras corrección); en una dudosa, la mejor hipótesis
    fuente: str                 # == fuente.nombre
    timestamp: datetime | str
    confianza: float
    estado: Estado
    orientacion: Orientacion = "horizontal"
    lectura_ocr: str | None = None          # texto bruto del OCR; por defecto == codigo
    alternativas: tuple[tuple[str, float], ...] = ()
    ruta_recorte: str | None = None


def normalizar_codigo(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def es_codigo_bien_formado(codigo: str) -> bool:
    return bool(_PATRON_CODIGO.match(codigo))


def digito_control(codigo10: str) -> int:
    """Dígito de control ISO 6346 de los 10 primeros caracteres."""
    total = 0
    for i, c in enumerate(codigo10[:10]):
        valor = _VALOR_LETRA[c] if c.isalpha() else int(c)
        total += valor * (2**i)
    return total % 11 % 10


def es_codigo_valido(codigo: str) -> bool:
    return es_codigo_bien_formado(codigo) and digito_control(codigo) == int(codigo[10])
