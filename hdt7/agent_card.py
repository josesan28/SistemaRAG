"""Agent Card público del sistema multiagente de Parachute S.A."""

from __future__ import annotations

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

DEFAULT_A2A_URL = "http://127.0.0.1:9999"
TEXT_MODE = "text/plain"


def build_agent_card(base_url: str = DEFAULT_A2A_URL) -> AgentCard:
    """Construye la tarjeta pública que descubrirán los clientes A2A."""
    faq_skill = AgentSkill(
        id="preguntas_frecuentes",
        name="Preguntas frecuentes",
        description=(
            "Responde preguntas sobre servicios, precios, políticas y requisitos "
            "de Parachute S.A."
        ),
        tags=["paracaidismo", "preguntas frecuentes", "servicios"],
        examples=["¿Cuál es el peso máximo permitido?"],
        input_modes=[TEXT_MODE],
        output_modes=[TEXT_MODE],
    )
    weather_skill = AgentSkill(
        id="evaluacion_climatica",
        name="Evaluación climática y calendarización",
        description=(
            "Evalúa si el clima de una fecha permite realizar un salto y orienta "
            "solicitudes de calendarización."
        ),
        tags=["clima", "calendarización", "fechas"],
        examples=["¿Es recomendable saltar el 24 de octubre de 2026?"],
        input_modes=[TEXT_MODE],
        output_modes=[TEXT_MODE],
    )

    return AgentCard(
        name="Parachute S.A.",
        description=(
            "Asistente virtual para preguntas frecuentes y evaluación climática "
            "de fechas de salto."
        ),
        version="1.0.0",
        default_input_modes=[TEXT_MODE],
        default_output_modes=[TEXT_MODE],
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
            extended_agent_card=False,
        ),
        supported_interfaces=[
            AgentInterface(
                url=base_url.rstrip("/"),
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        skills=[faq_skill, weather_skill],
    )
