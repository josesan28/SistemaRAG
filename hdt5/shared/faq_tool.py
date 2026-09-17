"""Tool compartida que reutiliza el RAG simple de la HDT4.

La HDT4 usa el documento completo de FAQs como contexto del modelo. Esta
adaptación conserva ese tipo de retrieval y lo expone como una ``function_tool``
para que las tres arquitecturas consuman la misma fuente.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from agents import function_tool

FAQ_FILE = Path(__file__).resolve().parents[2] / "FAQs_Parachute_SA_Guatemala_2026.txt"


@lru_cache(maxsize=1)
def prepare_faq_search() -> str:
    """Carga y mantiene en memoria la base de conocimiento de la HDT4."""
    if not FAQ_FILE.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de FAQs: {FAQ_FILE}")
    return FAQ_FILE.read_text(encoding="utf-8")


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

    return {
        "valido": True,
        "informacion_suficiente": True,
        "query": query,
        "fuente": FAQ_FILE.name,
        "resultados": prepare_faq_search(),
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
