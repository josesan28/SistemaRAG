"""Cliente A2A de terminal para el agente de Parachute S.A.

La terminal ya no ejecuta el sistema multiagente: se comporta como un cliente
A2A que descubre el Agent Card del servidor y le envía cada mensaje del
usuario. Toda la comunicación usa el SDK oficial ``a2a-sdk``; este módulo no
importa el Agents SDK ni el MAS, solo conoce el protocolo A2A.

Ejecutar desde la raíz del repositorio (con el servidor A2A activo)::

    python -m hdt7.terminal_client
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Callable

import httpx
from a2a.client import (
    A2ACardResolver,
    A2AClientError,
    A2AClientTimeoutError,
    AgentCardResolutionError,
    Client,
    ClientConfig,
    create_client,
)
from a2a.helpers import get_artifact_text, get_message_text, new_text_message
from a2a.types import (
    AgentCard,
    Role,
    SendMessageRequest,
    StreamResponse,
    Task,
    TaskState,
)
from a2a.utils.errors import A2AError
from dotenv import load_dotenv

DEFAULT_A2A_URL = "http://127.0.0.1:9999"
# Un turno del MAS (manager + especialista + MCP + Groq) tarda 15-40 s; el
# timeout por defecto de httpx (5 s) cortaría casi todas las respuestas.
DEFAULT_TIMEOUT_SECONDS = 120.0
CONNECT_TIMEOUT_SECONDS = 5.0
JSONRPC_BINDING = "JSONRPC"
EXIT_COMMAND = "bye"
SEPARADOR = "=" * 70


class TerminalClientError(Exception):
    """Error con un mensaje pensado para mostrarse tal cual al usuario."""


class ServerUnavailableError(TerminalClientError):
    """No hay un servidor A2A escuchando en la URL configurada."""


class InvalidAgentCardError(TerminalClientError):
    """El Agent Card no existe, no es JSON válido o no es utilizable."""


class TaskFailedError(TerminalClientError):
    """El servidor procesó la tarea, pero no terminó en COMPLETED."""


class EmptyResponseError(TerminalClientError):
    """La respuesta no contiene texto que mostrar."""


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


def build_request(text: str, context_id: str | None = None) -> SendMessageRequest:
    """Envuelve el texto del usuario en un mensaje A2A.

    No se envía ``task_id``: cada turno es una tarea nueva, porque una tarea
    COMPLETED es terminal. Lo que une los turnos es el ``context_id``.
    """
    message = new_text_message(text, context_id=context_id, role=Role.ROLE_USER)
    return SendMessageRequest(message=message)


def response_context_id(response: StreamResponse) -> str | None:
    """Obtiene el ``context_id`` que asignó el servidor a la respuesta."""
    payload = response.WhichOneof("payload")
    if payload == "task":
        return response.task.context_id or None
    if payload == "message":
        return response.message.context_id or None
    return None


def _status_text(task: Task) -> str:
    if not task.status.HasField("message"):
        return ""
    return get_message_text(task.status.message).strip()


def extract_task_reply(task: Task) -> str:
    """Devuelve el texto de los artefactos de una tarea COMPLETED."""
    state = task.status.state
    if state == TaskState.TASK_STATE_FAILED:
        detalle = _status_text(task) or "sin detalle del servidor"
        raise TaskFailedError(
            f"El agente no pudo completar la solicitud ({detalle}). "
            "Intenta de nuevo o reformula tu mensaje."
        )
    if state != TaskState.TASK_STATE_COMPLETED:
        detalle = _status_text(task)
        raise TaskFailedError(
            f"La tarea terminó en el estado {TaskState.Name(state)}"
            + (f": {detalle}" if detalle else ".")
        )

    textos = [get_artifact_text(artifact).strip() for artifact in task.artifacts]
    textos = [texto for texto in textos if texto]
    if not textos:
        raise EmptyResponseError(
            "La tarea se completó, pero no incluye artefactos de texto con la "
            "respuesta del agente."
        )
    return "\n\n".join(textos)


def extract_reply(response: StreamResponse) -> str:
    """Traduce un ``StreamResponse`` no streaming al texto para el usuario."""
    payload = response.WhichOneof("payload")
    if payload == "task":
        return extract_task_reply(response.task)
    if payload == "message":
        texto = get_message_text(response.message).strip()
        if texto:
            return texto
    raise EmptyResponseError("El servidor A2A respondió sin contenido de texto.")


class A2ATerminalSession:
    """Conversación con un agente remoto A2A que conserva su ``context_id``."""

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
        self.context_id: str | None = None

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

    async def ask(self, text: str) -> str:
        """Envía un turno y devuelve la respuesta del agente remoto."""
        if self._client is None:
            raise RuntimeError("Llama a connect() antes de enviar mensajes.")

        request = build_request(text, self.context_id)
        try:
            responses = [
                response async for response in self._client.send_message(request)
            ]
        except A2AClientTimeoutError as error:
            raise TerminalClientError(
                f"El servidor A2A no respondió en {self.timeout:.0f} s."
            ) from error
        except A2AClientError as error:
            raise ServerUnavailableError(
                f"Se perdió la comunicación con el servidor A2A ({error}). "
                "Verifica que siga en ejecución."
            ) from error
        except A2AError as error:
            raise TaskFailedError(
                f"El servidor A2A rechazó la solicitud: {error}"
            ) from error
        except ValueError as error:
            # BaseClient lanza ValueError si no llega ni task ni message.
            raise EmptyResponseError(
                "El servidor A2A devolvió una respuesta vacía."
            ) from error

        if not responses:
            raise EmptyResponseError("El servidor A2A no devolvió ninguna respuesta.")
        # En modo no streaming el SDK entrega un único StreamResponse.
        response = responses[-1]
        context_id = response_context_id(response)
        if context_id:
            self.context_id = context_id
        return extract_reply(response)

    async def close(self) -> None:
        """Libera la conexión HTTP (el cliente A2A cierra la que recibe)."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        else:
            await self._http_client.aclose()


def describe_agent_card(card: AgentCard) -> str:
    """Resume lo que el Agent Card dice del agente remoto."""
    lineas = [f"Conectado a: {card.name} (versión {card.version})"]
    if card.description:
        lineas.append(card.description)
    if card.skills:
        lineas.append("Habilidades publicadas:")
        lineas.extend(f"  - {skill.name}: {skill.description}" for skill in card.skills)
    return "\n".join(lineas)


def run_terminal(
    session: A2ATerminalSession,
    *,
    input_func: Callable[[str], str] = input,
    output: Callable[[str], None] = print,
) -> int:
    """Ciclo interactivo hasta ``Bye``, Ctrl-C o fin de entrada.

    La lectura de teclado ocurre FUERA del event loop y cada petición corre en
    un ``asyncio.Runner``. Si todo el ciclo estuviera dentro de
    ``asyncio.run``, el primer Ctrl-C mientras se escribe solo cancelaría la
    tarea y ``input()`` seguiría esperando un Enter.
    """
    with asyncio.Runner() as runner:
        try:
            try:
                card = runner.run(session.connect())
            except TerminalClientError as error:
                output(f"Error: {error}")
                return 1

            output(describe_agent_card(card))
            output("Escribe tu mensaje. Para salir escribe 'Bye' o presiona Ctrl-C.")
            output("-" * 70)

            while True:
                try:
                    mensaje = input_func("\nTú: ").strip()
                except EOFError:
                    output("\nAgente: ¡Hasta luego!")
                    return 0
                if not mensaje:
                    continue
                if mensaje.lower() == EXIT_COMMAND:
                    output("Agente: ¡Hasta luego!")
                    return 0

                try:
                    respuesta = runner.run(session.ask(mensaje))
                except TerminalClientError as error:
                    output(f"\nAgente: [Error] {error}")
                    continue
                output(f"\nAgente: {respuesta}")
        except KeyboardInterrupt:
            output("\n\nAgente: ¡Hasta luego!")
            return 0
        finally:
            runner.run(session.close())


def _configure_console() -> None:
    """Evita fallos con tildes y emojis en consolas de Windows.

    Se replica aquí en lugar de importar ``hdt5.shared.console`` porque el
    paquete ``hdt5.shared`` importa el Agents SDK, y la terminal no debe
    depender del sistema multiagente.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    """Lee la configuración y abre la terminal contra el servidor A2A."""
    _configure_console()
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Terminal de Parachute S.A. que actúa como cliente A2A."
    )
    parser.add_argument(
        "--url",
        default=get_a2a_url(),
        help="URL base del servidor A2A (por defecto A2A_PUBLIC_URL o %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=get_timeout(),
        help="Segundos de espera por respuesta (por defecto %(default)s).",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout debe ser mayor que cero.")

    print(SEPARADOR)
    print(" PARACHUTE S.A. — Terminal cliente A2A")
    print(SEPARADOR)
    print(f"Descubriendo el Agent Card en {args.url} ...")
    return run_terminal(A2ATerminalSession(args.url, timeout=args.timeout))


if __name__ == "__main__":
    sys.exit(main())
