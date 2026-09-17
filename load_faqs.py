"""
Script de carga (Persona 1 - HDT4).

Lee el corpus de FAQs de Parachute S.A., genera un embedding por cada
FAQ a partir de su pregunta con sentence-transformers, y hace un
UPSERT a la tabla `faqs` en PostgreSQL/pgvector.

Uso:
    python load_faqs.py [ruta_al_corpus.txt]

Si no se pasa ruta, usa "Corpus_FAQs_Parachute_SA_2026.txt" en el
mismo directorio.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg2.extras
from sentence_transformers import SentenceTransformer

from parachute_vector_store import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL_NAME,
    connect_to_faq_store,
    to_pgvector_literal,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS = BASE_DIR / "Corpus_FAQs_Parachute_SA_2026.txt"
# Cada FAQ viene separada por una línea de guiones (>= 10 seguidos)
BLOCK_SEPARATOR = re.compile(r"^-{10,}\s*$", re.MULTILINE)

FIELD_PATTERN = re.compile(
    r"ID:\s*(?P<id>.+?)\s*\n"
    r"CATEGOR[ÍI]A:\s*(?P<categoria>.+?)\s*\n"
    r"PREGUNTA:\s*(?P<pregunta>.+?)\s*\n"
    r"RESPUESTA:\s*(?P<respuesta>.+?)\s*\n"
    r"METADATA:\s*(?P<metadata>\{.*\})\s*$",
    re.DOTALL,
)


@dataclass
class Faq:
    id: str
    categoria: str
    pregunta: str
    respuesta: str
    metadata: dict


def parse_corpus(path: Path) -> list[Faq]:
    """Parsea el .txt de FAQs en una lista de objetos Faq."""
    text = path.read_text(encoding="utf-8")
    raw_blocks = [b.strip() for b in BLOCK_SEPARATOR.split(text) if b.strip()]

    faqs: list[Faq] = []
    for block in raw_blocks:
        match = FIELD_PATTERN.search(block)
        if not match:
            # Bloque no reconocible (p.ej. el encabezado del archivo con "="),
            # lo ignoramos en vez de tronar la carga completa.
            continue

        data = match.groupdict()
        try:
            metadata = json.loads(data["metadata"])
        except json.JSONDecodeError:
            metadata = {}

        faqs.append(
            Faq(
                id=data["id"].strip(),
                categoria=data["categoria"].strip(),
                pregunta=data["pregunta"].strip(),
                respuesta=data["respuesta"].strip(),
                metadata=metadata,
            )
        )

    return faqs


def upsert_faqs(conn, faqs: list[Faq], embeddings) -> None:
    # Se castea explícitamente a ::vector porque psycopg2 no tiene un adaptador
    # nativo para el tipo `vector` de pgvector (evita depender del paquete extra
    # `pgvector` solo para esto).
    upsert_sql = """
        INSERT INTO faqs (id, categoria, pregunta, respuesta, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s::vector)
        ON CONFLICT (id) DO UPDATE SET
            categoria = EXCLUDED.categoria,
            pregunta  = EXCLUDED.pregunta,
            respuesta = EXCLUDED.respuesta,
            metadata  = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding;
    """
    if len(faqs) != len(embeddings):
        raise ValueError(
            "La cantidad de embeddings no coincide con la cantidad de FAQs."
        )

    rows = [
        (
            faq.id,
            faq.categoria,
            faq.pregunta,
            faq.respuesta,
            json.dumps(faq.metadata, ensure_ascii=False),
            to_pgvector_literal(embedding),
        )
        for faq, embedding in zip(faqs, embeddings)
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, upsert_sql, rows)
    conn.commit()


def main() -> None:
    corpus_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CORPUS

    if not corpus_path.exists():
        print(f"No se encontró el archivo de corpus: {corpus_path}")
        sys.exit(1)

    print(f"Parseando corpus: {corpus_path.name}")
    faqs = parse_corpus(corpus_path)
    print(f"  -> {len(faqs)} FAQs encontradas")

    if not faqs:
        print("No se encontraron FAQs válidas en el archivo. Abortando.")
        sys.exit(1)
    if len({faq.id for faq in faqs}) != len(faqs):
        print("El corpus contiene IDs de FAQ duplicados. Abortando.")
        sys.exit(1)

    print(f"Cargando modelo de embeddings: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # El dump tiene respuestas con texto muy parecido entre FAQs. Embebemos la
    # pregunta (la parte distintiva de cada entrada) para que variantes como
    # "estacionamiento" encuentren "parqueo" sin que ese texto repetido
    # domine la similitud. La respuesta completa sigue guardada en PostgreSQL
    # y es la que se entrega al agente como evidencia.
    textos = [faq.pregunta for faq in faqs]
    print("Generando embeddings...")
    embeddings = model.encode(textos, show_progress_bar=True, normalize_embeddings=True)
    if len(embeddings[0]) != EMBEDDING_DIMENSIONS:
        print(
            "El modelo generó embeddings con una dimensión inesperada: "
            f"{len(embeddings[0])} (se esperaban {EMBEDDING_DIMENSIONS})."
        )
        sys.exit(1)

    print("Conectando a PostgreSQL...")
    conn = connect_to_faq_store()
    try:
        upsert_faqs(conn, faqs, embeddings)
        print(f"Carga completa: {len(faqs)} FAQs insertadas/actualizadas en la tabla 'faqs'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
