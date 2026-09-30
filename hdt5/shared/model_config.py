"""Configura el Agents SDK de OpenAI para hablar con Groq.

Groq expone un endpoint compatible con Chat Completions (no con la API de
Responses), así que forzamos ese modo con `set_default_openai_api`. Todas
las arquitecturas (centralizada, jerárquica, descentralizada) deben llamar
`get_model()` una sola vez al arrancar su `main.py`, y usar el objeto que
devuelve como `model=` en cada `Agent(...)`.
"""

from __future__ import annotations

import os

from agents import (
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)

DEFAULT_MODEL_NAME = "openai/gpt-oss-20b"


def get_model() -> OpenAIChatCompletionsModel:
    """Crea el modelo Groq-compatible para usar en cualquier Agent().

    Requiere GROQ_API_KEY en el entorno (mismo .env de la HDT4).
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No se encontró GROQ_API_KEY. Crea/usa el mismo .env de la HDT4."
        )

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # Groq no soporta la Responses API del SDK; usamos Chat Completions.
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions")
    # Evita que el SDK intente exportar traces a platform.openai.com (que no
    # tenemos configurado con esta API key de Groq).
    set_tracing_disabled(True)

    model_name = os.getenv("GROQ_MODEL", DEFAULT_MODEL_NAME)
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)
