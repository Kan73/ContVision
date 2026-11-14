"""Configuración global de ContVision."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
ZONA_HORARIA = "Europe/Madrid"


def ruta_bd() -> Path:
    """Ruta de la BD: variable de entorno ``CONTVISION_DB`` o ``data/contvision.db``."""
    return Path(os.environ.get("CONTVISION_DB", RAIZ_PROYECTO / "data" / "contvision.db"))


@dataclass(frozen=True)
class PageConfig:
    page_title: str = "ContVision"
    page_icon: str = ":material/directions_boat:"
    layout: str = "wide"
