"""Configuración de consola común para los programas interactivos."""

from __future__ import annotations

import sys


def configure_console() -> None:
    """Evita fallos al imprimir respuestas Unicode en consolas de Windows."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
