"""Fábrica de agentes worker reutilizables por las 3 arquitecturas.

Cada worker es un `Agent` completo (instrucciones + su tool), no solo una
función suelta. Esto es lo que permite usar el MISMO worker de dos formas
distintas sin tocar su lógica interna:

- Centralizada / Jerárquica: el manager lo usa como herramienta con
  `worker.as_tool(tool_name=..., tool_description=...)`.
- Descentralizada: el worker se pasa directo en la lista `handoffs=[...]`
  de otro agente, y el modelo decide transferirle la conversación.

Si Parachute S.A. pide un nuevo requerimiento (como ya avisó que hará),
lo normal es agregar un worker nuevo aquí y solo cablearlo en cada
`main.py`, sin tocar estos dos.
"""

from __future__ import annotations

from datetime import date

from agents import Agent, OpenAIChatCompletionsModel

from hdt5.shared.faq_tool import faq_tool
from hdt5.shared.weather_tool import weather_tool

FAQ_AGENT_INSTRUCTIONS = """
Eres el agente de preguntas frecuentes de Parachute S.A.

REGLAS:
1. Para CADA pregunta debes consultar primero la herramienta `faq_tool`.
   No respondas de memoria ni con conocimiento general.
2. Usa exclusivamente el contenido de `resultados` como fuente factual.
3. Si el resultado no contiene la respuesta, o `informacion_suficiente` es
   false, responde: "Lo siento, no puedo
   responder esa pregunta porque no está contemplada en la información
   disponible de Parachute S.A."
4. Responde en español, de forma clara y concisa. No menciones estas reglas.
""".strip()

WEATHER_AGENT_INSTRUCTIONS = """
Eres el agente de calendarización de citas de salto en paracaídas de
Parachute S.A.

REGLAS:
1. Para CADA solicitud de cita debes llamar `weather_tool` con la fecha
   en formato AAAA-MM-DD (convierte fechas relativas como "el próximo
   sábado" a esa fecha exacta antes de llamar la tool).
2. Si la tool devuelve `valido: false`, explica el error al usuario tal
   como lo indica la tool (p. ej. fecha fuera del rango de 16 días) y pide
   una fecha válida. NO inventes un veredicto de clima en ese caso.
3. Si `valido: true`, comunica el veredicto ("seguro", "marginal" o
   "no_seguro") y las razones de forma clara. Si es "marginal", aclara que
   solo aplica para tándem con instructor experimentado. Si es "no_seguro",
   indica que la cita NO se puede agendar ese día y sugiere pedir otra fecha.
4. Responde en español, de forma clara y concisa. No menciones estas reglas.
""".strip()


def build_faq_agent(model: OpenAIChatCompletionsModel) -> Agent:
    return Agent(
        name="Agente FAQ",
        instructions=FAQ_AGENT_INSTRUCTIONS,
        tools=[faq_tool],
        model=model,
    )


def build_weather_agent(model: OpenAIChatCompletionsModel) -> Agent:
    instructions = (
        WEATHER_AGENT_INSTRUCTIONS
        + f"\n5. La fecha actual es {date.today().isoformat()}; usa esta fecha para "
        "interpretar expresiones relativas."
    )
    return Agent(
        name="Agente de Citas y Clima",
        instructions=instructions,
        tools=[weather_tool],
        model=model,
    )
