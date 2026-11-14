"""Componentes de la página de actividad: feed de eventos, avisos y utilidades de tiempo."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from contvision.config import ZONA_HORARIA

_ZONA = ZoneInfo(ZONA_HORARIA)
_RE_CODIGO = re.compile(r"\b[A-Z]{3}[UJZ]\d{7}\b")

# tipo de evento -> (etiqueta corta, clase de color)
ESTILO_TIPO: dict[str, tuple[str, str]] = {
    "ENTRADA": ("Entrada", "verde"),
    "SALIDA": ("Salida", "gris"),
    "CONTENEDOR_NUEVO": ("Nuevo", "azul"),
    "LECTURA_CORREGIDA": ("Corregida", "azul"),
    "CORRECCION_MANUAL": ("Revisada", "violeta"),
    "TRASLADO_SIN_SALIDA": ("Traslado", "naranja"),
    "SALIDA_SIN_ENTRADA": ("Sin entrada", "naranja"),
    "LECTURA_DUDOSA": ("Dudosa", "naranja"),
    "FUENTE_DESCONOCIDA": ("Fuente ?", "rojo"),
    "ALMACEN_CREADO": ("Almacén +", "gris"),
    "ALMACEN_ELIMINADO": ("Almacén −", "gris"),
    "FUENTE_CREADA": ("Cámara +", "gris"),
    "FUENTE_ELIMINADA": ("Cámara −", "gris"),
    "CONTENEDOR_ELIMINADO": ("Eliminado", "rojo"),
}


# ------------------------------------------------------------------ tiempo

def a_datetime(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def hace(iso: str, ahora: datetime | None = None) -> str:
    """``hace 3 s`` / ``hace 2 min`` / ``hace 4 h`` / ``hace 3 d`` / fecha si es antiguo."""
    momento = a_datetime(iso)
    segundos = int(((ahora or datetime.now(UTC)) - momento).total_seconds())
    if segundos < 0:
        return "ahora"
    if segundos < 60:
        return f"hace {segundos} s"
    if segundos < 3600:
        return f"hace {segundos // 60} min"
    if segundos < 86400:
        return f"hace {segundos // 3600} h"
    if segundos < 7 * 86400:
        return f"hace {segundos // 86400} d"
    return momento.astimezone(_ZONA).strftime("%d/%m/%y")


def inicio_dia_utc(dias_atras: int = 0) -> str:
    """Medianoche (hora local) de hoy − ``dias_atras``, como ISO UTC para comparar en la BD."""
    medianoche = datetime.now(_ZONA).replace(hour=0, minute=0, second=0, microsecond=0)
    medianoche -= timedelta(days=dias_atras)
    return medianoche.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def hora_local(epoch: int, formato: str = "%H:%M") -> str:
    return datetime.fromtimestamp(epoch, UTC).astimezone(_ZONA).strftime(formato)


def iso_utc(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# -------------------------------------------------------------------- HTML

def _mensaje_html(mensaje: str, codigo_evento: str | None = None) -> str:
    """Escapa el mensaje y pone los códigos en monoespaciada.

    Solo se enlaza a la ficha el código del contenedor del evento: otros textos
    con forma de código (p. ej. la lectura OCR errónea de una corrección) no
    corresponden a ningún contenedor, y un contenedor borrado ya no tiene ficha.
    """
    def formato(m: re.Match) -> str:
        codigo = m.group(0)
        if codigo == codigo_evento:
            return f'<a class="cv-mono cv-codigo" href="contenedor?codigo={codigo}" target="_self">{codigo}</a>'
        return f'<span class="cv-mono">{codigo}</span>'
    return _RE_CODIGO.sub(formato, escape(mensaje))


def badge(tipo: str) -> str:
    etiqueta, color = ESTILO_TIPO.get(tipo, (tipo.title(), "gris"))
    return f'<span class="cv-badge cv-{color}">{escape(etiqueta)}</span>'


def html_feed(eventos, ids_nuevos: set[int], ahora: datetime) -> str:
    if not eventos:
        return '<div class="cv-vacio">No hay eventos con estos filtros.</div>'
    filas = []
    for ev in eventos:
        clase = "cv-fila cv-nueva" if ev.id in ids_nuevos else "cv-fila"
        fecha = a_datetime(ev.timestamp).astimezone(_ZONA).strftime("%d/%m/%Y %H:%M:%S")
        filas.append(
            f'<div class="{clase}">'
            f'<span class="cv-hace" title="{fecha}">{hace(ev.timestamp, ahora)}</span>'
            f'<span class="cv-tipo">{badge(ev.tipo)}</span>'
            f'<span class="cv-msg">{_mensaje_html(ev.mensaje, ev.codigo)}</span>'
            "</div>"
        )
    return '<div class="cv-feed">' + "".join(filas) + "</div>"


def html_avisos(avisos: list[tuple[str, int, str]]) -> str:
    """``avisos = [(texto, n, nivel), …]`` → lista con icono por nivel (solo los n > 0)."""
    filas = [
        f'<li class="cv-aviso-{nivel}"><span class="cv-icono"></span><b>{n}</b>&nbsp;{escape(texto)}</li>'
        for texto, n, nivel in avisos if n
    ]
    if not filas:
        return '<div class="cv-vacio">Sin avisos. Todo en orden.</div>'
    return '<ul class="cv-avisos">' + "".join(filas) + "</ul>"
