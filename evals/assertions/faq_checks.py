"""Asserts personalizados para evaluar la fidelidad al contexto de FAQs.

`context_faithfulness`: misma idea que la métrica `context-faithfulness` de promptfoo
(¿cada afirmación de la respuesta está respaldada por el contexto?), pero con un
prompt que el grader de Groq sí respeta.

Por qué no usamos la nativa: con `openai/gpt-oss-120b` el prompt NLI de promptfoo
0.123 no se cumple (el modelo repite las afirmaciones en vez de dar veredictos
Yes/No) y la aserción termina en "Could not parse context-faithfulness verdicts".
Cambiar su `rubricPrompt` solo se puede a nivel de test, lo que también cambiaría
el prompt de `factuality`/`llm-rubric` del mismo caso.

Uso en un test:

    vars:
      mensaje: "..."
      context: file://../FAQs_Parachute_SA_Guatemala_2026.txt
    assert:
      - type: python
        value: file://assertions/faq_checks.py:context_faithfulness
        config:
          threshold: 0.8        # fracción mínima de afirmaciones respaldadas
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GRADER_MODEL = "openai/gpt-oss-120b"  # el mismo grader de promptfooconfig.yaml

NLI_PROMPT = """
Eres un evaluador de fidelidad (faithfulness) de un sistema RAG.

1. Divide la RESPUESTA en afirmaciones factuales atómicas. Ignora saludos,
   ofrecimientos de ayuda y frases sin contenido factual.
2. Para cada afirmación decide si está respaldada por el CONTEXTO (explícitamente
   o por inferencia directa). Si el contexto no la menciona o la contradice, NO
   está respaldada.

Responde SOLO con JSON con esta forma:
{"afirmaciones": [{"afirmacion": "...", "respaldada": true, "motivo": "..."}]}

PREGUNTA:
{pregunta}

CONTEXTO:
{contexto}

RESPUESTA:
{respuesta}
""".strip()


def _resultado(ok: bool, score: float, motivo: str) -> dict:
    return {"pass": ok, "score": score, "reason": motivo}


def _pedir_veredictos(pregunta: str, respuesta: str, contexto: str) -> list[dict]:
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(ROOT / ".env")
    cliente = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url=GROQ_BASE_URL,
        max_retries=2,
        timeout=45.0,
    )
    prompt = (
        NLI_PROMPT.replace("{pregunta}", pregunta)
        .replace("{contexto}", contexto)
        .replace("{respuesta}", respuesta)
    )
    completion = cliente.chat.completions.create(
        model=GRADER_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(completion.choices[0].message.content)["afirmaciones"]


def puntuar(veredictos: list[dict]) -> float:
    """Fracción de afirmaciones respaldadas. Sin afirmaciones no hay nada infiel."""
    if not veredictos:
        return 1.0
    respaldadas = sum(1 for v in veredictos if v.get("respaldada") is True)
    return respaldadas / len(veredictos)


def context_faithfulness(output: str, context: dict) -> dict:
    cfg = context.get("config") or {}
    variables = context.get("vars") or {}
    contexto = variables.get("context")
    if not contexto:
        return _resultado(False, 0.0, "Falta vars.context con el .txt de FAQs.")
    pregunta = variables.get("query") or variables.get("mensaje") or context.get("prompt", "")
    umbral = float(cfg.get("threshold", 0.8))

    try:
        veredictos = _pedir_veredictos(pregunta, output, contexto)
    except Exception as error:  # noqa: BLE001 — cualquier fallo del grader es un fail
        return _resultado(False, 0.0, f"El grader falló: {type(error).__name__}: {error}")

    score = puntuar(veredictos)
    no_respaldadas = [v.get("afirmacion", "?") for v in veredictos if v.get("respaldada") is not True]
    motivo = f"Faithfulness {score:.2f} (umbral {umbral}, {len(veredictos)} afirmaciones)."
    if no_respaldadas:
        motivo += f" No respaldadas: {no_respaldadas}"
    return _resultado(score >= umbral, score, motivo)
