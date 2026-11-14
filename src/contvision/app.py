"""Punto de entrada de Streamlit: configuración, estado de sesión y navegación superior.

Ejecutar con:  uv run streamlit run src/contvision/app.py
"""

import streamlit as st

from contvision.config import PageConfig
from contvision.ui import navegacion, state, style
from contvision.ui.paginas.almacen import pagina_almacen
from contvision.ui.paginas.busqueda import pagina_busqueda
from contvision.ui.paginas.contenedor import pagina_contenedor
from contvision.ui.paginas.historial import pagina_historial
from contvision.ui.paginas.inicio import pagina_inicio
from contvision.ui.paginas.mapa import pagina_mapa
from contvision.ui.paginas.resumen import pagina_resumen
from contvision.ui.paginas.revision import pagina_revision


def build_pages() -> tuple[st.Page, ...]:
    """Páginas de la navegación superior, en orden. ``url_path`` es la URL de cada una.

    Almacén y Contenedor están ocultas: se llega a ellas desde otras páginas
    con el id en la URL (``?almacen=3``, ``?codigo=MSCU1234566``).
    """
    return (
        st.Page(pagina_inicio, title="Inicio", icon=":material/home:", default=True, url_path="inicio"),
        st.Page(pagina_historial, title="Historial", icon=":material/history:", url_path="historial"),
        st.Page(pagina_mapa, title="Mapa", icon=":material/map:", url_path="mapa"),
        st.Page(pagina_busqueda, title="Búsqueda", icon=":material/search:", url_path="busqueda"),
        st.Page(pagina_resumen, title="Resumen", icon=":material/bar_chart:", url_path="resumen"),
        st.Page(pagina_revision, title="Revisión", icon=":material/fact_check:", url_path="revision"),
        st.Page(pagina_almacen, title="Almacén", icon=":material/warehouse:",
                url_path="almacen", visibility="hidden"),
        st.Page(pagina_contenedor, title="Contenedor", icon=":material/package_2:",
                url_path="contenedor", visibility="hidden"),
    )


def main() -> None:
    """Se ejecuta en cada rerun: configura la página, asegura el estado y dibuja la página."""
    config = PageConfig()
    st.set_page_config(page_title=config.page_title, page_icon=config.page_icon, layout=config.layout)
    style.apply()
    state.init_state()

    paginas = build_pages()
    navegacion.registrar(paginas)
    nav = st.navigation(pages=paginas, position="top")

    nav.run()


if __name__ == "__main__":
    main()
