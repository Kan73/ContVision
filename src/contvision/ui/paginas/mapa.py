"""Mapa: un punto por almacén con su ocupación (B3.9)."""

from contvision.db import queries as q
from contvision.ui import componentes as ui
from contvision.ui import navegacion
from contvision.ui.state import conexion


def pagina_mapa() -> None:
    ui.cabecera("Mapa", "Almacenes y ocupación")
    ui.pendiente("B3.9", "mapa interactivo (pydeck o folium); click en un punto → página Almacén")

    almacenes = q.almacenes.listar(conexion())
    if not almacenes:
        ui.aviso_bd_vacia()
        return
    for a in almacenes:
        ocup = f" · {a.ocupacion:.0%}" if a.ocupacion is not None else ""
        navegacion.enlace_almacen(a.id, f"{a.nombre} — {a.presentes} presentes{ocup}")
