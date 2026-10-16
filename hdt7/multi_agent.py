"""Sistema multiagente de Parachute S.A. conectado al servidor MCP.

Este modulo es la frontera que reutilizara el servidor A2A. No contiene una
interfaz de terminal: la HDT7 exige que esa interfaz sea un cliente A2A.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from agents import Agent, FunctionTool, ModelSettings, Runner, function_tool
from agents.mcp import MCPServerStreamableHttp, ToolFilterContext

from hdt5.shared.agents_factory import (
    FAQ_AGENT_INSTRUCTIONS,
    WEATHER_AGENT_INSTRUCTIONS,
    contiene_fecha_concreta,
)

FAQ_AGENT_NAME = "Agente FAQ"
WEATHER_AGENT_NAME = "Agente de Citas y Clima"

MANAGER_INSTRUCTIONS = """
Eres el asistente virtual de Parachute S.A. Coordinas dos especialistas y
NUNCA respondes con conocimiento propio:

- `consultar_faq`: servicios, precios, politicas e informacion general.
- `calendarizar_cita`: solicitudes de cita o viabilidad climatica de una fecha.

Identifica todas las intenciones. Si el mensaje combina informacion general y
una fecha, llama a ambos especialistas y combina fielmente sus resultados.
Nunca afirmes que una reserva fue creada. Rechaza solicitudes ajenas a
Parachute S.A. y responde siempre en espanol.
""".strip()


def get_mcp_url() -> str:
    """Obtiene el endpoint MCP compartido a partir del entorno."""
    return os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")


def _filter_tools_by_agent(context: ToolFilterContext, tool: Any) -> bool:
    """Aplica minimo privilegio a las tools del servidor MCP unico."""
    allowed_by_agent = {
        FAQ_AGENT_NAME: "faq_tool",
        WEATHER_AGENT_NAME: "weather_tool",
    }
    expected_tool = allowed_by_agent.get(context.agent.name)
    return expected_tool is not None and tool.name == expected_tool


def create_mcp_client(url: str | None = None) -> MCPServerStreamableHttp:
    """Crea el cliente; el llamador controla su ciclo de vida asincrono."""
    return MCPServerStreamableHttp(
        name="Herramientas Parachute",
        params={"url": url or get_mcp_url(), "timeout": 30},
        cache_tools_list=True,
        max_retry_attempts=3,
        tool_filter=_filter_tools_by_agent,
    )


def _weather_instructions() -> str:
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7 or 7
    next_saturday = today + timedelta(days=days_until_saturday)
    return (
        WEATHER_AGENT_INSTRUCTIONS
        + f"\n7. La fecha actual es {today.isoformat()}; usala para interpretar "
        "expresiones relativas."
        + f"\n8. El proximo sabado posterior a hoy es {next_saturday.isoformat()}."
    )


def _build_weather_delegation_tool(
    model: Any, mcp_server: MCPServerStreamableHttp
) -> FunctionTool:
    """Delega al especialista y obliga MCP solo cuando hay fecha concreta."""
    agent = Agent(
        name=WEATHER_AGENT_NAME,
        instructions=_weather_instructions(),
        model=model,
        mcp_servers=[mcp_server],
    )
    agent_with_date = agent.clone(
        model_settings=agent.model_settings.resolve(ModelSettings(tool_choice="required"))
    )

    @function_tool(
        name_override="calendarizar_cita",
        description_override=(
            "Delega en el especialista de citas cualquier solicitud de "
            "agendar o consultar si una fecha es apta para saltar."
        ),
    )
    async def calendarizar_cita(input: str) -> str:
        """Procesa una solicitud de cita o de clima.

        Args:
            input: Solicitud completa del usuario, incluida la fecha mencionada.
        """
        selected = agent_with_date if contiene_fecha_concreta(input) else agent
        result = await Runner.run(selected, input)
        return str(result.final_output)

    return calendarizar_cita


def build_manager(model: Any, mcp_server: MCPServerStreamableHttp) -> Agent:
    """Construye el MAS centralizado cuyos especialistas consumen MCP."""
    faq_agent = Agent(
        name=FAQ_AGENT_NAME,
        instructions=FAQ_AGENT_INSTRUCTIONS,
        model=model,
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(tool_choice="required"),
    )
    return Agent(
        name="Manager Parachute S.A.",
        instructions=MANAGER_INSTRUCTIONS,
        model=model,
        tools=[
            faq_agent.as_tool(
                tool_name="consultar_faq",
                tool_description=(
                    "Delega preguntas sobre servicios, precios, politicas e "
                    "informacion general de Parachute S.A."
                ),
            ),
            _build_weather_delegation_tool(model, mcp_server),
        ],
    )


async def run_multi_agent(
    manager: Agent, message: str, history: Sequence[dict[str, Any]] | None = None
) -> tuple[str, list[Any]]:
    """Ejecuta un turno y devuelve texto mas historial serializable por SDK.

    Esta funcion es el contrato destinado al executor A2A de la Persona 2.
    El `manager` debe haberse creado dentro de un cliente MCP conectado.
    """
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("El mensaje no puede estar vacio.")
    input_items = list(history or [])
    input_items.append({"role": "user", "content": clean_message})
    result = await Runner.run(manager, input_items)
    return str(result.final_output), result.to_input_list()

