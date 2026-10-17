"""Pruebas del Agent Card y servidor A2A implementados por Persona 2."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, call, patch

from a2a.helpers import new_text_message
from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.types import (
    Role,
    SendMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from hdt7.agent_card import DEFAULT_A2A_URL, TEXT_MODE, build_agent_card
from hdt7.a2a_executor import ParachuteAgentExecutor


class CapturingEventQueue(EventQueue):
    """Cola mínima para inspeccionar los eventos publicados por el executor."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def enqueue_event(self, event: Any) -> None:
        self.events.append(event)


class AgentCardTests(unittest.TestCase):
    def test_identifica_al_agente_y_sus_modos_de_texto(self) -> None:
        card = build_agent_card()

        self.assertEqual(card.name, "Parachute S.A.")
        self.assertEqual(card.version, "1.0.0")
        self.assertEqual(list(card.default_input_modes), [TEXT_MODE])
        self.assertEqual(list(card.default_output_modes), [TEXT_MODE])

    def test_publica_las_dos_skills_requeridas(self) -> None:
        card = build_agent_card()

        self.assertEqual(
            {skill.id for skill in card.skills},
            {"preguntas_frecuentes", "evaluacion_climatica"},
        )
        for skill in card.skills:
            self.assertEqual(list(skill.input_modes), [TEXT_MODE])
            self.assertEqual(list(skill.output_modes), [TEXT_MODE])
            self.assertTrue(skill.description)
            self.assertTrue(skill.examples)

    def test_declara_una_interfaz_jsonrpc_a2a_1_0(self) -> None:
        card = build_agent_card()

        self.assertEqual(len(card.supported_interfaces), 1)
        interface = card.supported_interfaces[0]
        self.assertEqual(interface.url, DEFAULT_A2A_URL)
        self.assertEqual(interface.protocol_binding, "JSONRPC")
        self.assertEqual(interface.protocol_version, "1.0")
        self.assertFalse(card.capabilities.streaming)
        self.assertFalse(card.capabilities.push_notifications)
        self.assertFalse(card.capabilities.extended_agent_card)

    def test_permite_configurar_la_url_publica(self) -> None:
        card = build_agent_card("http://a2a.example:9000/")

        self.assertEqual(
            card.supported_interfaces[0].url, "http://a2a.example:9000"
        )


class AgentExecutorTests(unittest.IsolatedAsyncioTestCase):
    def _context(
        self,
        text: str,
        *,
        context_id: str = "contexto-1",
        task_id: str = "tarea-1",
    ) -> RequestContext:
        message = new_text_message(
            text,
            role=Role.ROLE_USER,
            context_id=context_id,
            task_id=task_id,
        )
        return RequestContext(
            ServerCallContext(),
            request=SendMessageRequest(message=message),
        )

    async def test_publica_respuesta_y_estados_de_tarea(self) -> None:
        manager = object()
        executor = ParachuteAgentExecutor(manager)
        event_queue = CapturingEventQueue()
        history = [{"role": "user", "content": "pregunta"}]

        with (
            patch(
                "hdt7.a2a_executor.run_multi_agent",
                new=AsyncMock(return_value=("Respuesta final", history)),
            ) as run_mock,
            self.assertLogs("hdt7.a2a", level="INFO") as logs,
        ):
            await executor.execute(self._context("  pregunta  "), event_queue)

        run_mock.assert_awaited_once_with(manager, "pregunta", None)
        self.assertEqual(len(event_queue.events), 4)
        self.assertIsInstance(event_queue.events[0], Task)

        working = event_queue.events[1]
        self.assertIsInstance(working, TaskStatusUpdateEvent)
        self.assertEqual(working.status.state, TaskState.TASK_STATE_WORKING)

        artifact = event_queue.events[2]
        self.assertIsInstance(artifact, TaskArtifactUpdateEvent)
        self.assertEqual(artifact.artifact.name, "respuesta")
        self.assertEqual(artifact.artifact.parts[0].text, "Respuesta final")
        self.assertEqual(artifact.artifact.parts[0].media_type, "text/plain")

        completed = event_queue.events[3]
        self.assertIsInstance(completed, TaskStatusUpdateEvent)
        self.assertEqual(completed.status.state, TaskState.TASK_STATE_COMPLETED)
        self.assertTrue(any("task.received" in line for line in logs.output))
        self.assertTrue(any("task.completed" in line for line in logs.output))

    async def test_publica_estado_fallido_si_el_mas_falla(self) -> None:
        executor = ParachuteAgentExecutor(object())
        event_queue = CapturingEventQueue()

        with (
            patch(
                "hdt7.a2a_executor.run_multi_agent",
                new=AsyncMock(side_effect=RuntimeError("fallo simulado")),
            ),
            self.assertLogs("hdt7.a2a", level="ERROR") as logs,
        ):
            await executor.execute(self._context("pregunta"), event_queue)

        self.assertEqual(len(event_queue.events), 3)
        failed = event_queue.events[-1]
        self.assertIsInstance(failed, TaskStatusUpdateEvent)
        self.assertEqual(failed.status.state, TaskState.TASK_STATE_FAILED)
        self.assertEqual(
            failed.status.message.parts[0].text,
            "No se pudo procesar la solicitud.",
        )
        self.assertTrue(any("task.failed" in line for line in logs.output))

    async def test_reutiliza_historial_dentro_del_mismo_contexto(self) -> None:
        manager = object()
        executor = ParachuteAgentExecutor(manager)
        first_history = [{"role": "user", "content": "primera"}]
        second_history = [*first_history, {"role": "user", "content": "segunda"}]

        with patch(
            "hdt7.a2a_executor.run_multi_agent",
            new=AsyncMock(
                side_effect=[
                    ("Primera respuesta", first_history),
                    ("Segunda respuesta", second_history),
                ]
            ),
        ) as run_mock:
            await executor.execute(
                self._context("primera", task_id="tarea-1"),
                CapturingEventQueue(),
            )
            await executor.execute(
                self._context("segunda", task_id="tarea-2"),
                CapturingEventQueue(),
            )

        self.assertEqual(
            run_mock.await_args_list,
            [
                call(manager, "primera", None),
                call(manager, "segunda", first_history),
            ],
        )


if __name__ == "__main__":
    unittest.main()
