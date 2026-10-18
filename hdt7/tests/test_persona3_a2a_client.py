"""Pruebas del cliente A2A de terminal implementado por Persona 3.

Ninguna prueba llama a Groq ni abre puertos: el servidor A2A real de Persona 2
corre en memoria (httpx.ASGITransport) con el MAS simulado, y los casos de
error usan servidores HTTP simulados (httpx.MockTransport).
"""

from __future__ import annotations

import ast
import logging
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from a2a.helpers import new_text_message
from a2a.types import (
    AgentCard,
    Artifact,
    Part,
    StreamResponse,
    Task,
    TaskState,
    TaskStatus,
)
from google.protobuf.json_format import MessageToDict

from hdt7.a2a_executor import ParachuteAgentExecutor
from hdt7.a2a_server import create_app
from hdt7.agent_card import build_agent_card
from hdt7.terminal_client import (
    A2ATerminalSession,
    EmptyResponseError,
    InvalidAgentCardError,
    ServerUnavailableError,
    TaskFailedError,
    TerminalClientError,
    build_request,
    extract_reply,
    run_terminal,
)

SERVER_URL = "http://testserver"
CARD_PATH = "/.well-known/agent-card.json"


class FakeMcpClient:
    """Sustituye la conexión MCP durante el ciclo de vida del servidor."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_: Any) -> None:
        return None


def _card_json(card: AgentCard | None = None) -> dict[str, Any]:
    return MessageToDict(card or build_agent_card(SERVER_URL))


def _mock_session(handler) -> A2ATerminalSession:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return A2ATerminalSession(SERVER_URL, timeout=7, http_client=http_client)


def _task_response(
    state: TaskState,
    *,
    artifacts: list[Artifact] | None = None,
    status_text: str | None = None,
) -> StreamResponse:
    status = TaskStatus(state=state)
    if status_text:
        status.message.CopyFrom(new_text_message(status_text))
    task = Task(
        id="tarea-1",
        context_id="contexto-1",
        status=status,
        artifacts=artifacts or [],
    )
    response = StreamResponse()
    response.task.CopyFrom(task)
    return response


class ServidorA2AEnMemoriaTests(unittest.IsolatedAsyncioTestCase):
    """Cliente oficial contra el servidor A2A de Persona 2 con el MAS simulado."""

    async def asyncSetUp(self) -> None:
        self.run_mock = AsyncMock()
        patches = [
            patch("hdt7.a2a_server.create_mcp_client", return_value=FakeMcpClient()),
            patch("hdt7.a2a_server.get_model", return_value=object()),
            patch("hdt7.a2a_server.build_manager", return_value=object()),
            patch("hdt7.a2a_executor.run_multi_agent", new=self.run_mock),
        ]
        for parche in patches:
            parche.start()
            self.addCleanup(parche.stop)

        app = create_app(
            agent_card=build_agent_card(SERVER_URL),
            executor=ParachuteAgentExecutor(),
        )
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        self.addAsyncCleanup(lifespan.__aexit__, None, None, None)

        http_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
        self.session = A2ATerminalSession(SERVER_URL, http_client=http_client)
        self.addAsyncCleanup(self.session.close)

    async def test_descubre_el_agent_card_con_sus_skills(self) -> None:
        card = await self.session.connect()

        self.assertEqual(card.name, "Parachute S.A.")
        self.assertEqual(
            {skill.id for skill in card.skills},
            {"preguntas_frecuentes", "evaluacion_climatica"},
        )
        self.assertIs(self.session.agent_card, card)

    async def test_muestra_la_respuesta_del_artefacto(self) -> None:
        self.run_mock.return_value = ("El peso máximo es de 100 kg.", [])
        await self.session.connect()

        respuesta = await self.session.ask("¿Cuál es el peso máximo?")

        self.assertEqual(respuesta, "El peso máximo es de 100 kg.")
        self.assertEqual(self.run_mock.await_args.args[1], "¿Cuál es el peso máximo?")

    async def test_conserva_el_context_id_entre_turnos(self) -> None:
        primer_historial = [{"role": "user", "content": "primera"}]
        self.run_mock.side_effect = [
            ("Primera respuesta", primer_historial),
            ("Segunda respuesta", [*primer_historial, {"role": "user"}]),
        ]
        await self.session.connect()

        await self.session.ask("primera")
        primer_contexto = self.session.context_id
        await self.session.ask("segunda")

        self.assertTrue(primer_contexto)
        self.assertEqual(self.session.context_id, primer_contexto)
        # El servidor reconoció el contexto y entregó el historial anterior.
        self.assertEqual(self.run_mock.await_args_list[1].args[2], primer_historial)

    async def test_reporta_una_tarea_failed(self) -> None:
        self.run_mock.side_effect = RuntimeError("fallo simulado del MAS")
        await self.session.connect()

        with (
            self.assertLogs("hdt7.a2a", level="ERROR"),
            self.assertRaises(TaskFailedError) as contexto,
        ):
            await self.session.ask("pregunta")

        self.assertIn("No se pudo procesar la solicitud.", str(contexto.exception))


class DescubrimientoTests(unittest.IsolatedAsyncioTestCase):
    async def test_servidor_no_disponible(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexión rechazada", request=request)

        session = _mock_session(handler)
        self.addAsyncCleanup(session.close)

        with self.assertRaises(ServerUnavailableError) as contexto:
            await session.connect()
        self.assertIn("python -m hdt7.a2a_server", str(contexto.exception))

    async def test_agent_card_no_disponible(self) -> None:
        session = _mock_session(lambda request: httpx.Response(404))
        self.addAsyncCleanup(session.close)

        with self.assertRaises(InvalidAgentCardError) as contexto:
            await session.connect()
        self.assertIn("404", str(contexto.exception))

    async def test_agent_card_que_no_es_json(self) -> None:
        session = _mock_session(lambda request: httpx.Response(200, text="<html>"))
        self.addAsyncCleanup(session.close)

        with self.assertRaises(InvalidAgentCardError):
            await session.connect()

    async def test_agent_card_que_no_es_un_objeto(self) -> None:
        session = _mock_session(lambda request: httpx.Response(200, json=[1, 2]))
        self.addAsyncCleanup(session.close)

        with self.assertRaises(InvalidAgentCardError):
            await session.connect()

    async def test_agent_card_sin_interfaz_jsonrpc(self) -> None:
        card = _card_json()
        card["supportedInterfaces"] = []
        session = _mock_session(lambda request: httpx.Response(200, json=card))
        self.addAsyncCleanup(session.close)

        with self.assertRaises(InvalidAgentCardError) as contexto:
            await session.connect()
        self.assertIn("JSON-RPC", str(contexto.exception))

    async def test_descubre_en_la_ruta_well_known(self) -> None:
        rutas: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            rutas.append(request.url.path)
            return httpx.Response(200, json=_card_json())

        session = _mock_session(handler)
        self.addAsyncCleanup(session.close)

        await session.connect()
        self.assertEqual(rutas, [CARD_PATH])


class EnvioTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_del_servidor(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=_card_json())
            raise httpx.ReadTimeout("sin respuesta", request=request)

        session = _mock_session(handler)
        self.addAsyncCleanup(session.close)
        await session.connect()

        with self.assertRaises(TerminalClientError) as contexto:
            await session.ask("hola")
        self.assertIn("7 s", str(contexto.exception))

    async def test_servidor_cae_durante_la_conversacion(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=_card_json())
            raise httpx.ConnectError("conexión rechazada", request=request)

        session = _mock_session(handler)
        self.addAsyncCleanup(session.close)
        await session.connect()

        with self.assertRaises(ServerUnavailableError):
            await session.ask("hola")

    async def test_ask_sin_connect(self) -> None:
        session = A2ATerminalSession(SERVER_URL)
        self.addAsyncCleanup(session.close)

        with self.assertRaises(RuntimeError):
            await session.ask("hola")


class ExtraccionTests(unittest.TestCase):
    def test_solicitud_lleva_rol_usuario_y_contexto(self) -> None:
        request = build_request("hola", "contexto-1")

        self.assertEqual(request.message.parts[0].text, "hola")
        self.assertEqual(request.message.context_id, "contexto-1")
        self.assertEqual(request.message.task_id, "")
        self.assertTrue(request.message.message_id)

    def test_une_varios_artefactos_de_texto(self) -> None:
        response = _task_response(
            TaskState.TASK_STATE_COMPLETED,
            artifacts=[
                Artifact(artifact_id="a", parts=[Part(text="Uno")]),
                Artifact(artifact_id="b", parts=[Part(text="Dos")]),
            ],
        )

        self.assertEqual(extract_reply(response), "Uno\n\nDos")

    def test_tarea_completada_sin_artefactos(self) -> None:
        response = _task_response(TaskState.TASK_STATE_COMPLETED)

        with self.assertRaises(EmptyResponseError):
            extract_reply(response)

    def test_artefacto_sin_partes_de_texto(self) -> None:
        artefacto = Artifact(artifact_id="a", parts=[Part(url="https://x.y/z.png")])
        response = _task_response(
            TaskState.TASK_STATE_COMPLETED, artifacts=[artefacto]
        )

        with self.assertRaises(EmptyResponseError):
            extract_reply(response)

    def test_tarea_failed_incluye_el_motivo(self) -> None:
        response = _task_response(
            TaskState.TASK_STATE_FAILED, status_text="Groq no disponible"
        )

        with self.assertRaises(TaskFailedError) as contexto:
            extract_reply(response)
        self.assertIn("Groq no disponible", str(contexto.exception))

    def test_estado_no_terminal_se_reporta(self) -> None:
        response = _task_response(TaskState.TASK_STATE_WORKING)

        with self.assertRaises(TaskFailedError) as contexto:
            extract_reply(response)
        self.assertIn("TASK_STATE_WORKING", str(contexto.exception))

    def test_acepta_respuesta_de_tipo_mensaje(self) -> None:
        response = StreamResponse()
        response.message.CopyFrom(new_text_message("Hola desde el agente"))

        self.assertEqual(extract_reply(response), "Hola desde el agente")


class FakeSession:
    """Sesión controlada para probar el ciclo interactivo sin red."""

    def __init__(self, *, connect_error: Exception | None = None) -> None:
        self.connect_error = connect_error
        self.preguntas: list[str] = []
        self.respuestas: list[Any] = []
        self.cerrada = False

    async def connect(self) -> AgentCard:
        if self.connect_error:
            raise self.connect_error
        return build_agent_card(SERVER_URL)

    async def ask(self, text: str) -> str:
        self.preguntas.append(text)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    async def close(self) -> None:
        self.cerrada = True


def _scripted_input(*entradas: Any):
    pendientes = list(entradas)

    def leer(_prompt: str) -> str:
        entrada = pendientes.pop(0)
        if isinstance(entrada, BaseException):
            raise entrada
        return entrada

    return leer


class CicloInteractivoTests(unittest.TestCase):
    def _run(self, session: FakeSession, *entradas: Any) -> tuple[int, str]:
        salida: list[str] = []
        codigo = run_terminal(
            session, input_func=_scripted_input(*entradas), output=salida.append
        )
        return codigo, "\n".join(salida)

    def test_conversa_hasta_bye(self) -> None:
        session = FakeSession()
        session.respuestas = ["El peso máximo es de 100 kg."]

        codigo, salida = self._run(session, "", "¿Peso máximo?", "BYE")

        self.assertEqual(codigo, 0)
        self.assertEqual(session.preguntas, ["¿Peso máximo?"])
        self.assertIn("Conectado a: Parachute S.A.", salida)
        self.assertIn("Agente: El peso máximo es de 100 kg.", salida)
        self.assertIn("¡Hasta luego!", salida)
        self.assertTrue(session.cerrada)

    def test_ctrl_c_cierra_la_terminal(self) -> None:
        session = FakeSession()

        codigo, salida = self._run(session, KeyboardInterrupt())

        self.assertEqual(codigo, 0)
        self.assertIn("¡Hasta luego!", salida)
        self.assertTrue(session.cerrada)

    def test_fin_de_entrada_cierra_la_terminal(self) -> None:
        session = FakeSession()

        codigo, salida = self._run(session, EOFError())

        self.assertEqual(codigo, 0)
        self.assertTrue(session.cerrada)

    def test_un_error_no_termina_la_conversacion(self) -> None:
        session = FakeSession()
        session.respuestas = [TaskFailedError("tarea fallida"), "Ahora sí"]

        codigo, salida = self._run(session, "uno", "dos", "Bye")

        self.assertEqual(codigo, 0)
        self.assertIn("[Error] tarea fallida", salida)
        self.assertIn("Agente: Ahora sí", salida)

    def test_servidor_no_disponible_al_iniciar(self) -> None:
        session = FakeSession(connect_error=ServerUnavailableError("sin servidor"))

        codigo, salida = self._run(session)

        self.assertEqual(codigo, 1)
        self.assertIn("Error: sin servidor", salida)
        self.assertTrue(session.cerrada)


class DesacoplamientoTests(unittest.TestCase):
    """La terminal solo puede hablar A2A: no conoce el MAS ni el Agents SDK."""

    def test_no_importa_el_sistema_multiagente(self) -> None:
        ruta = Path(__file__).resolve().parents[1] / "terminal_client.py"
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        modulos: set[str] = set()
        nombres: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos.update(alias.name for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                modulos.add(nodo.module or "")
                nombres.update(alias.name for alias in nodo.names)
            elif isinstance(nodo, ast.Name):
                nombres.add(nodo.id)

        prohibidos = ("agents", "hdt5", "hdt7.multi_agent", "hdt7.a2a_executor")
        for modulo in modulos:
            self.assertFalse(
                any(modulo == p or modulo.startswith(f"{p}.") for p in prohibidos),
                f"La terminal no debe importar {modulo}",
            )
        for nombre in ("Runner", "build_manager", "run_multi_agent"):
            self.assertNotIn(nombre, nombres)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
