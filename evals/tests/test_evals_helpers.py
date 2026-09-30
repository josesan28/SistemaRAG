from __future__ import annotations

import importlib.util
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
    def test_expande_fechas_relativas(self) -> None:
        texto = _expand_dates("Entre [HOY-1], [HOY] y [HOY+5]")

        self.assertIn((date.today() - timedelta(days=1)).isoformat(), texto)
        self.assertIn(date.today().isoformat(), texto)
        self.assertIn((date.today() + timedelta(days=5)).isoformat(), texto)

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


if __name__ == "__main__":
    unittest.main()
