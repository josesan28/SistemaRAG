"""Adaptador entre solicitudes A2A y el sistema multiagente de Parachute S.A."""

from __future__ import annotations

import logging
from typing import Any

from a2a.helpers import new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from hdt7.multi_agent import run_multi_agent

LOGGER = logging.getLogger("hdt7.a2a")


class ParachuteAgentExecutor(AgentExecutor):
    """Ejecuta el MAS y traduce su resultado al ciclo de vida de una tarea A2A."""

    def __init__(self, manager: Any | None = None) -> None:
        self._manager = manager
        self._histories: dict[str, list[Any]] = {}

    def set_manager(self, manager: Any) -> None:
        """Asocia el manager creado durante el ciclo de vida del servidor."""
        self._manager = manager

    def clear_manager(self) -> None:
        """Descarta el manager cuando se cierra su conexión MCP compartida."""
        self._manager = None
        self._histories.clear()

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Procesa un mensaje y publica estados y respuesta mediante A2A."""
        if context.message is None:
            raise ValueError("La solicitud A2A no contiene un mensaje.")

        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        LOGGER.info(
            "task.received task_id=%s context_id=%s", task.id, task.context_id
        )

        try:
            await updater.update_status(
                state=TaskState.TASK_STATE_WORKING,
                message=new_text_message(
                    "Procesando solicitud.",
                    context_id=task.context_id,
                    task_id=task.id,
                ),
            )

            message = context.get_user_input().strip()
            if not message:
                raise ValueError("El mensaje no puede estar vacío.")
            if self._manager is None:
                raise RuntimeError("El sistema multiagente no está disponible.")

            answer, history = await run_multi_agent(
                self._manager,
                message,
                self._histories.get(task.context_id),
            )
            self._histories[task.context_id] = history

            await updater.add_artifact(
                name="respuesta",
                parts=[new_text_part(answer, media_type="text/plain")],
            )
            await updater.update_status(
                state=TaskState.TASK_STATE_COMPLETED,
                message=new_text_message(
                    "Solicitud completada.",
                    context_id=task.context_id,
                    task_id=task.id,
                ),
            )
            LOGGER.info(
                "task.completed task_id=%s context_id=%s", task.id, task.context_id
            )
        except Exception:  # noqa: BLE001 - el fallo debe convertirse a estado A2A
            LOGGER.exception(
                "task.failed task_id=%s context_id=%s", task.id, task.context_id
            )
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(
                    "No se pudo procesar la solicitud.",
                    context_id=task.context_id,
                    task_id=task.id,
                ),
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Informa que este agente no admite cancelación de tareas."""
        raise NotImplementedError("La cancelación de tareas no está soportada.")
