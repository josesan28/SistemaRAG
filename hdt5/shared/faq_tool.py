"""Tool de FAQs con fuente configurable para las tres arquitecturas.

El backend `file` carga el documento local completo. El backend `database`
reutiliza la búsqueda vectorial de HDT4 sobre PostgreSQL/pgvector. La selección
se realiza con la variable de entorno `FAQ_BACKEND`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from agents import function_tool

FAQ_FILE = Path(__file__).resolve().parents[2] / "FAQs_Parachute_SA_Guatemala_2026.txt"
FAQ_BACKEND_ENV = "FAQ_BACKEND"
FILE_BACKEND = "file"
DATABASE_BACKEND = "database"
VALID_BACKENDS = {FILE_BACKEND, DATABASE_BACKEND}


def _get_backend() -> str:
    """Obtiene y valida la fuente configurada para las FAQs."""
    backend = os.getenv(FAQ_BACKEND_ENV, FILE_BACKEND).strip().lower()
    if backend not in VALID_BACKENDS:
        opciones = ", ".join(sorted(VALID_BACKENDS))
        raise ValueError(
            f"{FAQ_BACKEND_ENV} debe ser una de estas opciones: {opciones}."
        )
    return backend


@lru_cache(maxsize=1)
def _load_faq_file() -> str:
    """Carga y mantiene en memoria la base local de FAQs."""
    if not FAQ_FILE.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de FAQs: {FAQ_FILE}")
    return FAQ_FILE.read_text(encoding="utf-8")


def prepare_faq_search() -> str | None:
    """Prepara el backend configurado antes de iniciar el loop."""
    if _get_backend() == DATABASE_BACKEND:
        from parachute_faq_tool import prepare_faq_search as prepare_vector_search

        prepare_vector_search()
        return None
    return _load_faq_file()


def _faq_tool_impl(query: str) -> dict[str, Any]:
    """Implementación pura, separada del decorador para facilitar pruebas."""
    query = query.strip()
    if not query:
        return {
            "valido": False,
            "informacion_suficiente": False,
            "error": "La consulta no puede estar vacía.",
            "resultados": "",
        }

    backend = _get_backend()
    if backend == DATABASE_BACKEND:
        from parachute_faq_tool import buscar_faq as buscar_faq_vectorial

        resultado = buscar_faq_vectorial(query)
        return {
            "valido": True,
            "backend": backend,
            "query": query,
            "fuente": "PostgreSQL/pgvector",
            **resultado,
        }

    return {
        "valido": True,
        "backend": backend,
        "informacion_suficiente": True,
        "query": query,
        "fuente": FAQ_FILE.name,
        "resultados": _load_faq_file(),
    }


@function_tool
def faq_tool(query: str) -> dict[str, Any]:
    """Recupera la base oficial de FAQs para contestar una consulta.

    Args:
        query: Pregunta o necesidad del usuario, en español.
    """
    return _faq_tool_impl(query)


# Alias temporal para no romper imports escritos antes de acordar la interfaz.
buscar_faq = faq_tool
