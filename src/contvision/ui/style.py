"""Estilos globales.

Los colores usan fondos semitransparentes para verse bien con el tema claro y el oscuro.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* Menos margen superior: la navegación ya está arriba */
.block-container { padding-top: 3.5rem; }

/* Tarjetas KPI */
div[data-testid="stMetric"] { padding: 0.1rem 0.2rem; }
.st-key-kpi_dudosas_alerta { border-color: rgba(230, 140, 30, 0.75) !important; }
.st-key-kpi_dudosas_alerta div[data-testid="stMetricValue"] { color: rgb(230, 140, 30); }

/* Estado en vivo */
.cv-estado { text-align: right; font-size: 0.85rem; padding-top: 0.9rem; }
.cv-estado.vivo { color: rgb(46, 160, 67); }
.cv-estado.pausa { color: rgba(128, 128, 128, 0.9); }
.cv-punto { display: inline-block; width: 0.5rem; height: 0.5rem; border-radius: 50%;
            background: currentColor; margin-right: 0.4rem; vertical-align: middle; }
.cv-estado.vivo .cv-punto { animation: cv-latido 1.6s ease-in-out infinite; }
@keyframes cv-latido { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }

/* Feed de eventos */
.cv-feed { display: flex; flex-direction: column; }
.cv-fila { display: grid; grid-template-columns: 5.5rem 6.8rem 1fr; gap: 0.6rem; align-items: center;
           padding: 0.45rem 0.6rem; border-top: 1px solid rgba(128, 128, 128, 0.18); font-size: 0.9rem; }
.cv-fila:first-child { border-top: none; }
.cv-fila.cv-nueva { background: rgba(56, 132, 255, 0.10); animation: cv-aparece 2.5s ease-out; }
@keyframes cv-aparece { from { background: rgba(56, 132, 255, 0.30); } }
.cv-hace { color: rgba(128, 128, 128, 0.95); font-size: 0.82rem; white-space: nowrap; }
.cv-msg { overflow: hidden; text-overflow: ellipsis; }
.cv-mono { font-family: ui-monospace, "JetBrains Mono", "SFMono-Regular", monospace; letter-spacing: 0.02em; }
.cv-codigo { color: inherit !important; text-decoration: none;
             border-bottom: 1px dotted rgba(128, 128, 128, 0.6); }
.cv-codigo:hover { border-bottom-style: solid; }
.cv-vacio { color: rgba(128, 128, 128, 0.95); padding: 1rem 0.6rem; font-size: 0.9rem; }

/* Insignias por tipo de evento */
.cv-badge { display: inline-block; min-width: 5.6rem; text-align: center; font-size: 0.78rem;
            padding: 0.12rem 0.5rem; border-radius: 0.4rem; border: 1px solid transparent; }
.cv-verde   { color: rgb(46, 160, 67);   background: rgba(46, 160, 67, 0.14);   border-color: rgba(46, 160, 67, 0.30); }
.cv-azul    { color: rgb(56, 132, 255);  background: rgba(56, 132, 255, 0.14);  border-color: rgba(56, 132, 255, 0.30); }
.cv-naranja { color: rgb(220, 130, 20);  background: rgba(230, 140, 30, 0.14);  border-color: rgba(230, 140, 30, 0.32); }
.cv-rojo    { color: rgb(220, 60, 60);   background: rgba(220, 60, 60, 0.14);   border-color: rgba(220, 60, 60, 0.32); }
.cv-violeta { color: rgb(150, 100, 230); background: rgba(150, 100, 230, 0.14); border-color: rgba(150, 100, 230, 0.32); }
.cv-gris    { color: rgba(128, 128, 128, 1); background: rgba(128, 128, 128, 0.12); border-color: rgba(128, 128, 128, 0.28); }

/* Avisos */
.cv-avisos { list-style: none; padding: 0; margin: 0; font-size: 0.9rem; }
.cv-avisos li { padding: 0.2rem 0; display: flex; align-items: center; }
.cv-icono { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; margin-right: 0.55rem; }
.cv-aviso-aviso .cv-icono { background: rgb(230, 140, 30); }
.cv-aviso-error .cv-icono { background: rgb(220, 60, 60); }

/* Leyenda del mapa */
.cv-leyenda { display: flex; flex-wrap: wrap; gap: 0.3rem 1.1rem; font-size: 0.82rem;
              color: rgba(128, 128, 128, 1); margin-top: -0.4rem; }
.cv-ley { display: inline-flex; align-items: center; }
.cv-ley-punto { display: inline-block; width: 0.65rem; height: 0.65rem; border-radius: 50%; margin-right: 0.4rem; }

/* Códigos sueltos fuera del feed */
.codigo { font-family: ui-monospace, "JetBrains Mono", monospace; letter-spacing: 0.04em; }
</style>
"""


def apply() -> None:
    st.html(_CSS)
