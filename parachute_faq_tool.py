"""Herramienta de consulta para la base de conocimiento de Parachute S.A."""

from __future__ import annotations

from functools import lru_cache
import os
from typing import TYPE_CHECKING, Any

from parachute_vector_store import (
    EMBEDDING_MODEL_NAME,
    connect_to_faq_store,
    to_pgvector_literal,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


DEFAULT_RESULT_COUNT = 5
MAX_RESULT_COUNT = 10
# Una búsqueda vectorial siempre devuelve vecinos, incluso para preguntas que
# no pertenecen al corpus. Este umbral evita presentar esos vecinos como
# evidencia. Se puede ajustar sin cambiar código al evaluar el corpus.
DEFAULT_MAX_COSINE_DISTANCE = 0.65

FAQ_SEARCH_SQL = """
    SELECT
        id,
        categoria,
        pregunta,
        respuesta,
        embedding <=> %s::vector AS distancia_coseno
    FROM faqs
    ORDER BY embedding <=> %s::vector
    LIMIT %s;
"""

BUSCAR_FAQ_TOOL = {
    "type": "function",
    "function": {
        "name": "buscar_faq",
        "description": (
            "Úsala antes de responder cualquier pregunta sobre los servicios, "
            "políticas o información de Parachute S.A. Busca exclusivamente en "
            "la base oficial de FAQs y devuelve las entradas más relacionadas. "
            "No debe utilizarse como fuente de conocimiento general."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pregunta": {
                    "type": "string",
                    "description": (
                        "Pregunta o necesidad del usuario expresada en español."
                    ),
                },
                "k": {
                    "type": "integer",
                    "description": "Cantidad de FAQs candidatas que se deben recuperar.",
                    "default": DEFAULT_RESULT_COUNT,
                    "minimum": 1,
                    "maximum": MAX_RESULT_COUNT,
                },
            },
            "required": ["pregunta"],
            "additionalProperties": False,
        },
    },
}


@lru_cache(maxsize=1)
def _get_embedding_model() -> SentenceTransformer:
    """Carga una sola vez el mismo modelo utilizado al poblar la tabla."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def prepare_faq_search() -> None:
    """Carga el modelo de embeddings antes de iniciar el loop conversacional."""
    _get_embedding_model()


def _validate_search(pregunta: str, k: int) -> tuple[str, int]:
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta debe contener texto.")

    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError("La cantidad de resultados debe ser un número entero.")

    if not 1 <= k <= MAX_RESULT_COUNT:
        raise ValueError(
            f"La cantidad de resultados debe estar entre 1 y {MAX_RESULT_COUNT}."
        )

    return pregunta.strip(), k


def _get_max_cosine_distance() -> float:
    """Obtiene y valida el umbral de relevancia configurado para el corpus."""
    raw_value = os.getenv(
        "FAQ_MAX_COSINE_DISTANCE",
        str(DEFAULT_MAX_COSINE_DISTANCE),
    )
    try:
        threshold = float(raw_value)
    except ValueError as error:
        raise ValueError(
            "FAQ_MAX_COSINE_DISTANCE debe ser un número entre 0 y 2."
        ) from error

    if not 0 <= threshold <= 2:
        raise ValueError("FAQ_MAX_COSINE_DISTANCE debe estar entre 0 y 2.")

    return threshold


def _embed_question(pregunta: str) -> str:
    embedding = _get_embedding_model().encode(
        pregunta,
        normalize_embeddings=True,
    )
    return to_pgvector_literal(embedding)


def buscar_faq(
    pregunta: str,
    k: int = DEFAULT_RESULT_COUNT,
) -> dict[str, Any]:
    """Recupera evidencia relevante mediante distancia coseno.

    Las coincidencias que superan el umbral de distancia no se devuelven como
    fuentes: de otro modo el modelo podría contestar una pregunta ajena usando
    el FAQ vectorialmente menos lejano.
    """
    pregunta, k = _validate_search(pregunta, k)
    max_cosine_distance = _get_max_cosine_distance()
    query_vector = _embed_question(pregunta)

    connection = connect_to_faq_store()
    try:
        with connection.cursor() as cursor:
            # Para el corpus actual (120 filas) esto conserva un recall alto
            # incluso si PostgreSQL elige el índice ivfflat.
            cursor.execute("SET LOCAL ivfflat.probes = 10;")
            cursor.execute(FAQ_SEARCH_SQL, (query_vector, query_vector, k))
            rows = cursor.fetchall()
    finally:
        connection.close()

    candidatos = [
        {
            "id": faq_id,
            "categoria": categoria,
            "pregunta": pregunta_faq,
            "respuesta": respuesta,
            "distancia_coseno": round(float(distancia), 6),
        }
        for faq_id, categoria, pregunta_faq, respuesta, distancia in rows
    ]
    resultados = [
        resultado
        for resultado in candidatos
        if resultado["distancia_coseno"] <= max_cosine_distance
    ]

    return {
        "consulta": pregunta,
        "cantidad": len(resultados),
        "informacion_suficiente": bool(resultados),
        "umbral_distancia_coseno": max_cosine_distance,
        "resultados": resultados,
    }
