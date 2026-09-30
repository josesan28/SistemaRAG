"""Pruebas de la topología de la arquitectura jerárquica."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from hdt5.jerarquica.main import build_manager_principal


class FakeAgent:
    """Reemplazo mínimo de Agent para verificar el cableado sin ejecutar LLMs."""

    def __init__(self, *, name, instructions, model, tools):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools = tools
        self.as_tool_calls = []

    def as_tool(self, *, tool_name, tool_description):
        self.as_tool_calls.append(
            {"tool_name": tool_name, "tool_description": tool_description}
        )
        return {"agent": self, "tool_name": tool_name}


class HierarchicalAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = object()
        self.faq_agent = FakeAgent(
            name="Agente FAQ", instructions="FAQ", model=self.model, tools=[]
        )
        self.weather_agent = FakeAgent(
            name="Agente de Citas y Clima",
            instructions="Clima",
            model=self.model,
            tools=[],
        )

        faq_builder_patch = patch(
            "hdt5.jerarquica.main.build_faq_agent", return_value=self.faq_agent
        )
        weather_builder_patch = patch(
            "hdt5.jerarquica.main.build_weather_agent",
            return_value=self.weather_agent,
        )
        agent_patch = patch("hdt5.jerarquica.main.Agent", side_effect=FakeAgent)
        self.faq_builder = faq_builder_patch.start()
        self.weather_builder = weather_builder_patch.start()
        self.agent_builder = agent_patch.start()
        self.addCleanup(faq_builder_patch.stop)
        self.addCleanup(weather_builder_patch.stop)
        self.addCleanup(agent_patch.stop)

    def test_manager_principal_delega_solo_en_sub_managers(self) -> None:
        manager = build_manager_principal(self.model)

        self.assertEqual(manager.name, "Manager Principal Parachute S.A.")
        self.assertEqual(
            [tool["tool_name"] for tool in manager.tools],
            ["gestionar_informacion", "gestionar_operaciones"],
        )
        self.assertEqual(len(self.agent_builder.call_args_list), 3)

    def test_cada_sub_manager_delega_en_su_worker_de_dominio(self) -> None:
        manager = build_manager_principal(self.model)
        sub_manager_informacion = manager.tools[0]["agent"]
        sub_manager_operaciones = manager.tools[1]["agent"]

        self.assertEqual(
            [tool["tool_name"] for tool in sub_manager_informacion.tools],
            ["resolver_faq"],
        )
        self.assertIs(sub_manager_informacion.tools[0]["agent"], self.faq_agent)
        self.assertEqual(
            [tool["tool_name"] for tool in sub_manager_operaciones.tools],
            ["evaluar_cita_y_clima"],
        )
        self.assertIs(sub_manager_operaciones.tools[0]["agent"], self.weather_agent)

    def test_workers_reutilizados_reciben_el_mismo_modelo(self) -> None:
        build_manager_principal(self.model)

        self.faq_builder.assert_called_once_with(self.model)
        self.weather_builder.assert_called_once_with(self.model)


if __name__ == "__main__":
    unittest.main()
