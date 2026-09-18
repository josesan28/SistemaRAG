from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hdt5.descentralizada.main import HandoffData, build_agentes


class DescentralizedAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = object()
        self.faq_agent = SimpleNamespace(
            name="Agente FAQ",
            instructions="Instrucciones FAQ.",
            handoffs=[],
        )
        self.weather_agent = SimpleNamespace(
            name="Agente de Citas y Clima",
            instructions="Instrucciones de citas y clima.",
            handoffs=[],
        )

        faq_builder_patch = patch(
            "hdt5.descentralizada.main.build_faq_agent",
            return_value=self.faq_agent,
        )
        weather_builder_patch = patch(
            "hdt5.descentralizada.main.build_weather_agent",
            return_value=self.weather_agent,
        )
        handoff_builder_patch = patch(
            "hdt5.descentralizada.main.handoff",
            side_effect=lambda *, agent, **_: agent,
        )
        self.faq_builder = faq_builder_patch.start()
        self.weather_builder = weather_builder_patch.start()
        self.handoff_builder = handoff_builder_patch.start()
        self.addCleanup(faq_builder_patch.stop)
        self.addCleanup(weather_builder_patch.stop)
        self.addCleanup(handoff_builder_patch.stop)

    def test_faq_es_el_punto_de_entrada(self) -> None:
        agente_inicial, agentes = build_agentes(self.model)

        self.assertIs(agente_inicial, self.faq_agent)
        self.assertEqual(agentes, [self.faq_agent, self.weather_agent])
        self.faq_builder.assert_called_once_with(self.model)
        self.weather_builder.assert_called_once_with(self.model)

    def test_handoffs_son_bidireccionales(self) -> None:
        build_agentes(self.model)

        self.assertEqual(self.faq_agent.handoffs, [self.weather_agent])
        self.assertEqual(self.weather_agent.handoffs, [self.faq_agent])

    def test_handoffs_tienen_un_esquema_con_propiedades(self) -> None:
        build_agentes(self.model)

        self.assertEqual(self.handoff_builder.call_count, 2)
        for handoff_call in self.handoff_builder.call_args_list:
            with self.subTest(destino=handoff_call.kwargs["agent"].name):
                self.assertIs(handoff_call.kwargs["input_type"], HandoffData)
                self.assertTrue(callable(handoff_call.kwargs["on_handoff"]))

    def test_instrucciones_indican_cuando_transferir(self) -> None:
        build_agentes(self.model)

        self.assertIn("atiende la solicitud directamente", self.weather_agent.instructions)
        self.assertIn("fecha exacta", self.weather_agent.instructions)
        self.assertIn("transfiere la conversación", self.faq_agent.instructions)
        self.assertIn("Agente de Citas y Clima", self.faq_agent.instructions)
        self.assertIn("transfiere la conversación", self.weather_agent.instructions)
        self.assertIn("Agente FAQ", self.weather_agent.instructions)


if __name__ == "__main__":
    unittest.main()
