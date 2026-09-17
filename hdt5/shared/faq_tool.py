"""Envuelve `buscar_faq` (HDT4) como function_tool del Agents SDK.

No se reimplementa nada de la HDT4: solo se importa `buscar_faq` y se le
pone una firma que el Agents SDK entiende. Corre `python -m hdt5.centralizada.main`
etc. desde la raíz del repo para que este import funcione.
"""

from __future__ import annotations

from typing import Any

from agents import function_tool

from parachute_faq_tool import buscar_faq as _buscar_faq
from parachute_faq_tool import prepare_faq_search  # noqa: F401  (re-exportado)


@function_tool
def buscar_faq(pregunta: str, k: int = 5) -> dict[str, Any]:
    """Busca en la base oficial de FAQs de Parachute S.A.

    Úsala para CUALQUIER pregunta sobre servicios, políticas o información
    general de Parachute S.A. No la uses para calendarizar citas ni para
    preguntas sobre el clima: para eso existe `calendarizar_cita`.

    Args:
        pregunta: Pregunta o necesidad del usuario, en español.
        k: Cantidad de FAQs candidatas a recuperar (1-10).
    """
    return _buscar_faq(pregunta=pregunta, k=k)
