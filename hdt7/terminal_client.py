"""Cliente A2A de terminal para el agente de Parachute S.A.

La terminal ya no ejecuta el sistema multiagente: se comporta como un cliente
A2A que descubre el Agent Card del servidor y le envía cada mensaje del
usuario. Toda la comunicación usa el SDK oficial ``a2a-sdk``; este módulo no
importa el Agents SDK ni el MAS, solo conoce el protocolo A2A.

Ejecutar desde la raíz del repositorio (con el servidor A2A activo)::

    python -m hdt7.terminal_client
"""

from __future__ import annotations

import os

import httpx
from a2a.client import (
    A2ACardResolver,
    AgentCardResolutionError,
    Client,
    ClientConfig,
    create_client,
)
from a2a.types import AgentCard

DEFAULT_A2A_URL = "http://127.0.0.1:9999"
# Un turno del MAS (manager + especialista + MCP + Groq) tarda 15-40 s; el
# timeout por defecto de httpx (5 s) cortaría casi todas las respuestas.
DEFAULT_TIMEOUT_SECONDS = 120.0
CONNECT_TIMEOUT_SECONDS = 5.0
JSONRPC_BINDING = "JSONRPC"


class TerminalClientError(Exception):
    """Error con un mensaje pensado para mostrarse tal cual al usuario."""


class ServerUnavailableError(TerminalClientError):
    """No hay un servidor A2A escuchando en la URL configurada."""


class InvalidAgentCardError(TerminalClientError):
    """El Agent Card no existe, no es JSON válido o no es utilizable."""


def get_a2a_url() -> str:
    """URL base del servidor A2A, la misma que anuncia su Agent Card."""
    return os.getenv("A2A_PUBLIC_URL", DEFAULT_A2A_URL).rstrip("/")


def get_timeout() -> float:
    """Segundos máximos de espera por la respuesta de cada mensaje."""
    valor = os.getenv("A2A_CLIENT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(valor)
    except ValueError as error:
        raise ValueError(
            f"A2A_CLIENT_TIMEOUT debe ser un número de segundos: {valor!r}"
        ) from error
    if timeout <= 0:
        raise ValueError("A2A_CLIENT_TIMEOUT debe ser mayor que cero.")
    return timeout


def validate_agent_card(card: AgentCard) -> None:
    """Comprueba que la tarjeta permita conversar con el agente."""
    if not card.name.strip():
        raise InvalidAgentCardError("El Agent Card no declara un nombre de agente.")
    if not any(
        interface.protocol_binding == JSONRPC_BINDING and interface.url
        for interface in card.supported_interfaces
    ):
        raise InvalidAgentCardError(
            "El Agent Card no anuncia una interfaz JSON-RPC con URL; la "
            "terminal no tiene a dónde enviar los mensajes."
        )


async def discover_agent_card(
    http_client: httpx.AsyncClient, base_url: str
) -> AgentCard:
    """Descarga ``/.well-known/agent-card.json`` y lo valida."""
    resolver = A2ACardResolver(http_client, base_url)
    try:
        card = await resolver.get_agent_card()
    except AgentCardResolutionError as error:
        if isinstance(error.__cause__, httpx.RequestError):
            raise ServerUnavailableError(
                f"No se pudo conectar con el servidor A2A en {base_url}. "
                "Verifica que `python -m hdt7.a2a_server` esté en ejecución."
            ) from error
        raise InvalidAgentCardError(
            f"El servidor en {base_url} no publicó un Agent Card válido: {error}"
        ) from error
    except (AttributeError, TypeError) as error:
        # El SDK asume que el JSON es un objeto; una lista o un número rompe
        # su compatibilidad con versiones anteriores antes de validar.
        raise InvalidAgentCardError(
            f"El Agent Card de {base_url} no es un objeto JSON válido."
        ) from error
    validate_agent_card(card)
    return card


class A2ATerminalSession:
    """Conversación con un agente remoto A2A."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_SECONDS)
        )
        self._client: Client | None = None
        self.agent_card: AgentCard | None = None

    async def connect(self) -> AgentCard:
        """Descubre el Agent Card y crea el cliente oficial no streaming."""
        card = await discover_agent_card(self._http_client, self.base_url)
        try:
            self._client = await create_client(
                card,
                client_config=ClientConfig(
                    streaming=False, httpx_client=self._http_client
                ),
            )
        except ValueError as error:
            raise InvalidAgentCardError(
                f"El Agent Card no ofrece un transporte compatible: {error}"
            ) from error
        self.agent_card = card
        return card

    async def close(self) -> None:
        """Libera la conexión HTTP (el cliente A2A cierra la que recibe)."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        else:
            await self._http_client.aclose()
