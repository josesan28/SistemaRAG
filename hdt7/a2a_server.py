"""Servidor A2A que expone el sistema multiagente de Parachute S.A.

Ejecutar desde la raíz del repositorio::

    python -m hdt7.a2a_server
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from dotenv import load_dotenv
from starlette.applications import Starlette

from hdt5.shared.model_config import get_model
from hdt7.a2a_executor import ParachuteAgentExecutor
from hdt7.agent_card import build_agent_card
from hdt7.multi_agent import build_manager, create_mcp_client

LOGGER = logging.getLogger("hdt7.a2a")


def get_a2a_host() -> str:
    """Obtiene la interfaz donde escuchará el servidor A2A."""
    return os.getenv("A2A_HOST", "127.0.0.1")


def get_a2a_port() -> int:
    """Obtiene el puerto del servidor A2A."""
    return int(os.getenv("A2A_PORT", "9999"))


def get_a2a_public_url() -> str:
    """Obtiene la URL que se anunciará en el Agent Card."""
    default_url = f"http://{get_a2a_host()}:{get_a2a_port()}"
    return os.getenv("A2A_PUBLIC_URL", default_url).rstrip("/")


def create_app(
    *,
    agent_card: AgentCard | None = None,
    executor: ParachuteAgentExecutor | None = None,
) -> Starlette:
    """Construye la aplicación A2A y su ciclo de vida MCP compartido."""
    public_card = agent_card or build_agent_card(get_a2a_public_url())
    agent_executor = executor or ParachuteAgentExecutor()
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
        agent_card=public_card,
    )

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        LOGGER.info(
            "server.starting mcp_url=%s",
            os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"),
        )
        async with create_mcp_client() as mcp_server:
            try:
                manager = build_manager(get_model(), mcp_server)
                agent_executor.set_manager(manager)
                LOGGER.info(
                    "server.started public_url=%s",
                    public_card.supported_interfaces[0].url,
                )
                yield
            finally:
                await request_handler.aclose()
                agent_executor.clear_manager()
                LOGGER.info("server.stopped")

    routes = [
        *create_agent_card_routes(public_card),
        *create_jsonrpc_routes(request_handler, "/"),
    ]
    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.agent_card = public_card
    app.state.agent_executor = agent_executor
    app.state.request_handler = request_handler
    return app


def main() -> None:
    """Carga la configuración e inicia el servidor HTTP A2A."""
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = get_a2a_host()
    port = get_a2a_port()
    LOGGER.info("Servidor A2A Parachute iniciando en http://%s:%s", host, port)
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
