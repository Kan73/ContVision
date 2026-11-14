"""Historial: eventos filtrados y paginados (B3.8)."""

from contvision.ui import componentes as ui


def pagina_historial() -> None:
    ui.cabecera("Historial", "Registro completo de eventos")
    ui.pendiente("B3.8", "filtros (fechas, tipo, nivel, almacén, código), paginación por cursor y CSV")
