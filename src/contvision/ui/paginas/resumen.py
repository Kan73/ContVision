"""Resumen global (B3.5)."""

from contvision.ui import componentes as ui


def pagina_resumen() -> None:
    ui.cabecera("Resumen", "Estadísticas globales")
    ui.pendiente("B3.5", "avistamientos por fecha y % válidas / corregidas / dudosas")
