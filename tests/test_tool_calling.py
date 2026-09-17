"""Pruebas del flujo de tool calling sin red, Docker ni credenciales."""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
import parachute_faq_tool


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.executed.append((statement, parameters))

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def completion_with(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class VectorToolTests(unittest.TestCase):
    @patch.dict(os.environ, {"FAQ_MAX_COSINE_DISTANCE": "0.65"}, clear=False)
    @patch("parachute_faq_tool._embed_question", return_value="[0.1,0.2]")
    @patch("parachute_faq_tool.connect_to_faq_store")
    def test_tool_filters_vector_neighbors_without_evidence(self, mock_connect, _mock_embed):
        connection = FakeConnection(
            [
                ("FAQ-001", "Logística", "¿Hay parqueo?", "Sí", 0.2),
                ("FAQ-099", "Clima", "¿Habrá lluvia?", "Consulte", 0.9),
            ]
        )
        mock_connect.return_value = connection

        result = parachute_faq_tool.buscar_faq("¿Hay parqueo?", k=2)

        self.assertTrue(result["informacion_suficiente"])
        self.assertEqual(result["cantidad"], 1)
        self.assertEqual(result["resultados"][0]["id"], "FAQ-001")
        self.assertTrue(connection.closed)
        self.assertIn("SET LOCAL ivfflat.probes", connection.cursor_instance.executed[0][0])


class ToolCallingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool_call = SimpleNamespace(
            id="call_123",
            type="function",
            function=SimpleNamespace(
                name="buscar_faq",
                arguments=json.dumps({"pregunta": "¿Cuál es el límite de peso?"}),
            ),
        )
        self.initial_message = SimpleNamespace(content=None, tool_calls=[self.tool_call])
        self.final_message = SimpleNamespace(content="La respuesta respaldada.", tool_calls=[])
        self.completions = MagicMock(
            side_effect=[
                completion_with(self.initial_message),
                completion_with(self.final_message),
            ]
        )
        self.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=self.completions))
        )

    @patch("main.buscar_faq")
    def test_reinserts_tool_result_before_final_response(self, mock_search) -> None:
        mock_search.return_value = {
            "informacion_suficiente": True,
            "cantidad": 1,
            "resultados": [{"id": "FAQ-021", "respuesta": "Máximo 100 kg."}],
        }

        answer = main.answer_question(self.client, "¿Cuál es el límite de peso?")

        self.assertEqual(answer, "La respuesta respaldada.")
        self.assertEqual(self.completions.call_count, 2)
        first_call, final_call = self.completions.call_args_list
        self.assertEqual(first_call.kwargs["tool_choice"], "required")
        self.assertEqual(final_call.kwargs["tool_choice"], "none")
        tool_messages = [
            message
            for message in final_call.kwargs["messages"]
            if message["role"] == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(tool_messages[0]["tool_call_id"], "call_123")
        self.assertIn("FAQ-021", tool_messages[0]["content"])

    @patch("main.buscar_faq")
    def test_rejects_when_tool_has_no_relevant_evidence(self, mock_search) -> None:
        mock_search.return_value = {
            "informacion_suficiente": False,
            "cantidad": 0,
            "resultados": [],
        }

        answer = main.answer_question(self.client, "¿Cuál es la capital de Francia?")

        self.assertEqual(answer, main.UNSUPPORTED_ANSWER)
        self.assertEqual(self.completions.call_count, 2)

    @patch("main.buscar_faq")
    def test_uses_retrieved_answer_if_model_rejects_valid_evidence(self, mock_search) -> None:
        self.final_message.content = main.UNSUPPORTED_ANSWER
        mock_search.return_value = {
            "informacion_suficiente": True,
            "cantidad": 1,
            "resultados": [
                {
                    "id": "FAQ-003",
                    "respuesta": "Hay parqueo disponible en el evento.",
                    "distancia_coseno": 0.1,
                }
            ],
        }

        answer = main.answer_question(self.client, "¿Hay estacionamiento?")

        self.assertEqual(answer, "Hay parqueo disponible en el evento.")


if __name__ == "__main__":
    unittest.main()
