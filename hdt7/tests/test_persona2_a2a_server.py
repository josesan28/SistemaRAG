"""Pruebas del Agent Card y servidor A2A implementados por Persona 2."""

from __future__ import annotations

import unittest

from hdt7.agent_card import DEFAULT_A2A_URL, TEXT_MODE, build_agent_card


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


if __name__ == "__main__":
    unittest.main()
