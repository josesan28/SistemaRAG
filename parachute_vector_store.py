"""Configuración compartida para el conocimiento vectorial de Parachute S.A."""

from __future__ import annotations

import os
from collections.abc import Iterable

from dotenv import load_dotenv


# El corpus y las preguntas de los usuarios están en español. Este modelo
# multilingüe conserva 384 dimensiones (compatibles con VECTOR(384)) y ofrece
# una recuperación semántica mucho mejor para variantes como
# "estacionamiento" / "parqueo".
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSIONS = 384


def connect_to_faq_store():
    """Abre una conexión a la base de FAQs configurada en el entorno."""
    import psycopg2

    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "parachute_faqs"),
        user=os.getenv("POSTGRES_USER", "parachute"),
        password=os.getenv("POSTGRES_PASSWORD", "parachute"),
    )


def to_pgvector_literal(embedding: Iterable[float]) -> str:
    """Convierte un embedding al literal ``[x,y,...]`` aceptado por pgvector."""
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
