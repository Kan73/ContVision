"""Registro de páginas y enlaces entre ellas con ids en ``st.query_params``.

``app.build_pages()`` registra las páginas aquí; las páginas usan estas
funciones para enlazarse sin importarse entre sí (evita ciclos de import).
URLs resultantes: ``/almacen?almacen=3``, ``/contenedor?codigo=MSCU1234566``.
"""

from __future__ import annotations

from collections.abc import Iterable

import streamlit as st

_PAGINAS: dict[str, st.Page] = {}
INICIO = "inicio"   # la página por defecto tiene url_path "" en Streamlit; se registra con esta clave


def registrar(paginas: Iterable[st.Page]) -> None:
    for p in paginas:
        _PAGINAS[p.url_path or INICIO] = p


def pagina(url_path: str) -> st.Page:
    return _PAGINAS[url_path]


def enlace_almacen(almacen_id: int, etiqueta: str, **kw) -> None:
    st.page_link(pagina("almacen"), label=etiqueta, icon=":material/warehouse:",
                 query_params={"almacen": almacen_id}, **kw)


def enlace_contenedor(codigo: str, etiqueta: str | None = None, **kw) -> None:
    st.page_link(pagina("contenedor"), label=etiqueta or codigo, icon=":material/package_2:",
                 query_params={"codigo": codigo}, **kw)


def ir_a_almacen(almacen_id: int) -> None:
    st.switch_page(pagina("almacen"), query_params={"almacen": almacen_id})


def ir_a_contenedor(codigo: str) -> None:
    st.switch_page(pagina("contenedor"), query_params={"codigo": codigo})


def param_int(nombre: str) -> int | None:
    """Lee un parámetro entero de la URL (None si falta o no es válido)."""
    valor = st.query_params.get(nombre)
    try:
        return int(valor) if valor is not None else None
    except ValueError:
        return None
