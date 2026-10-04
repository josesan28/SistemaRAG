from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALS_DIR))

from provider import VALID_WEATHER_SCENARIOS, _expand_dates  # noqa: E402


def _load_tool_assertions():
    path = EVALS_DIR / "assertions" / "tool_calls.py"
    spec = importlib.util.spec_from_file_location("eval_tool_calls", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


tool_assertions = _load_tool_assertions()


class ProviderHelperTests(unittest.TestCase):
    def test_provider_fuerza_corpus_local_para_evals(self) -> None:
        self.assertEqual(os.environ.get("FAQ_BACKEND"), "file")

    def test_expande_fechas_relativas(self) -> None:
        texto = _expand_dates("Entre [HOY-1], [HOY] y [HOY+5]")

        self.assertIn((date.today() - timedelta(days=1)).isoformat(), texto)
        self.assertIn(date.today().isoformat(), texto)
        self.assertIn((date.today() + timedelta(days=5)).isoformat(), texto)

    def test_expande_fecha_relativa_en_formato_dia_mes_anio(self) -> None:
        texto = _expand_dates("Quiero saltar el [HOY+5:DMY]")

        esperada = (date.today() + timedelta(days=5)).strftime("%d/%m/%Y")
        self.assertEqual(texto, f"Quiero saltar el {esperada}")

    def test_escenarios_documentados_son_validos(self) -> None:
        self.assertEqual(
            VALID_WEATHER_SCENARIOS,
            {"seguro", "marginal", "no_seguro", "real"},
        )


class ToolAssertionTests(unittest.TestCase):
    def test_valida_manager_inner_fecha_y_veredicto(self) -> None:
        fecha = (date.today() + timedelta(days=3)).isoformat()
        context = {
            "config": {
                "manager_called": ["calendarizar_cita"],
                "called": ["weather_tool"],
                "not_called": ["faq_tool"],
                "weather_date_offset": 3,
                "weather_verdict": "seguro",
                "weather_valido": True,
            },
            "providerResponse": {
                "metadata": {
                    "manager_tool_calls": [{"tool": "calendarizar_cita"}],
                    "inner_tool_calls": [
                        {
                            "tool": "weather_tool",
                            "input": fecha,
                            "result": {"valido": True, "veredicto": "seguro"},
                        }
                    ],
                }
            },
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertTrue(resultado["pass"], resultado["reason"])
        self.assertEqual(resultado["score"], 1.0)

    def test_falla_si_no_se_llama_la_tool_requerida(self) -> None:
        context = {
            "config": {"called": ["faq_tool"]},
            "metadata": {"manager_tool_calls": [], "inner_tool_calls": []},
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertFalse(resultado["pass"])
        self.assertIn("faq_tool", resultado["reason"])

    def test_valida_cantidad_exacta_de_llamadas(self) -> None:
        context = {
            "config": {"call_counts": {"weather_tool": 1}},
            "metadata": {
                "manager_tool_calls": [],
                "inner_tool_calls": [
                    {"tool": "weather_tool", "input": date.today().isoformat(), "result": {}}
                ],
            },
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertTrue(resultado["pass"], resultado["reason"])

    def test_falla_si_la_tool_se_llama_mas_de_una_vez(self) -> None:
        llamada = {"tool": "weather_tool", "input": date.today().isoformat(), "result": {}}
        context = {
            "config": {"call_counts": {"weather_tool": 1}},
            "metadata": {
                "manager_tool_calls": [],
                "inner_tool_calls": [llamada, llamada],
            },
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertFalse(resultado["pass"])
        self.assertIn("2 veces", resultado["reason"])

    def test_valida_el_proximo_sabado(self) -> None:
        dias = (5 - date.today().weekday()) % 7 or 7
        proximo_sabado = (date.today() + timedelta(days=dias)).isoformat()
        context = {
            "config": {"weather_next_weekday": 5},
            "metadata": {
                "manager_tool_calls": [],
                "inner_tool_calls": [
                    {"tool": "weather_tool", "input": proximo_sabado, "result": {}}
                ],
            },
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertTrue(resultado["pass"], resultado["reason"])

    def test_rechaza_numero_de_dia_invalido(self) -> None:
        context = {
            "config": {"weather_next_weekday": 7},
            "metadata": {
                "manager_tool_calls": [],
                "inner_tool_calls": [],
            },
        }

        resultado = tool_assertions.check_tools("respuesta", context)

        self.assertFalse(resultado["pass"])
        self.assertIn("entre 0 y 6", resultado["reason"])


if __name__ == "__main__":
    unittest.main()
