"""Servidor MCP unico para las herramientas de Parachute S.A.

Expone las implementaciones de FAQ y clima de la HDT5 mediante el transporte
Streamable HTTP. Este proceso no ejecuta agentes ni modelos: solamente
centraliza las capacidades de negocio que los agentes pueden invocar.

Ejecutar desde la raiz del repositorio::

    python -m hdt7.mcp_server
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from hdt5.shared.faq_tool import _faq_tool_impl
from hdt5.shared.weather_tool import _weather_tool_impl

LOGGER = logging.getLogger("hdt7.mcp")

mcp = MCPServer(
    "parachute-tools",
    instructions=(
        "Herramientas oficiales de Parachute S.A. para consultar preguntas "
        "frecuentes y evaluar el clima de una fecha de salto."
    ),
)


@mcp.tool()
def faq_tool(query: str) -> dict[str, Any]:
    """Busca informacion oficial para una pregunta sobre Parachute S.A.

    Args:
        query: Pregunta o necesidad del usuario, en espanol.
    """
    LOGGER.info("tool.start name=faq_tool query=%r", query)
    try:
        result = _faq_tool_impl(query)
    except Exception:  # noqa: BLE001 - el servidor debe registrar el fallo real
        LOGGER.exception("tool.error name=faq_tool")
        raise
    LOGGER.info(
        "tool.end name=faq_tool valido=%s informacion_suficiente=%s",
        result.get("valido"),
        result.get("informacion_suficiente"),
    )
    return result


@mcp.tool()
def weather_tool(fecha: str) -> dict[str, Any]:
    """Evalua si una fecha es apta para saltar segun el clima.

    Args:
        fecha: Fecha deseada en formato AAAA-MM-DD.
    """
    LOGGER.info("tool.start name=weather_tool fecha=%r", fecha)
    try:
        result = _weather_tool_impl(fecha)
    except Exception:  # noqa: BLE001 - el servidor debe registrar el fallo real
        LOGGER.exception("tool.error name=weather_tool")
        raise
    LOGGER.info(
        "tool.end name=weather_tool valido=%s veredicto=%s",
        result.get("valido"),
        result.get("veredicto"),
    )
    return result


def main() -> None:
    """Inicia el servidor MCP sobre Streamable HTTP."""
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")
    LOGGER.info(
        "Servidor MCP Parachute iniciando en http://%s:%s%s", host, port, path
    )
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()

