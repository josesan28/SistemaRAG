"""Pruebas de assertions/faq_checks.py sin llamar a Groq.

Ejecutar desde evals/: python tests/test_faq_checks.py
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

EVALS_DIR = Path(__file__).resolve().parents[1]


def _load_faq_checks():
    path = EVALS_DIR / "assertions" / "faq_checks.py"
    spec = importlib.util.spec_from_file_location("eval_faq_checks", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


faq_checks = _load_faq_checks()

CONTEXTO = "Q: ¿Cuál es el límite de peso?\nA: El límite de peso máximo es de 100 kg."


def _context(threshold: float = 0.8) -> dict:
    return {
        "vars": {"mensaje": "¿Límite de peso?", "context": CONTEXTO},
        "config": {"threshold": threshold},
    }


class PuntuarTests(unittest.TestCase):
    def test_fraccion_de_afirmaciones_respaldadas(self) -> None:
        veredictos = [{"respaldada": True}, {"respaldada": False}, {"respaldada": True}]
        self.assertAlmostEqual(faq_checks.puntuar(veredictos), 2 / 3)

    def test_sin_afirmaciones_no_hay_nada_infiel(self) -> None:
        self.assertEqual(faq_checks.puntuar([]), 1.0)

    def test_valores_no_booleanos_no_cuentan_como_respaldo(self) -> None:
        self.assertEqual(faq_checks.puntuar([{"respaldada": "sí"}]), 0.0)


class ContextFaithfulnessTests(unittest.TestCase):
    def test_falla_sin_contexto(self) -> None:
        resultado = faq_checks.context_faithfulness("100 kg", {"vars": {"mensaje": "x"}})

        self.assertFalse(resultado["pass"])
        self.assertIn("vars.context", resultado["reason"])

    def test_pasa_si_todo_esta_respaldado(self) -> None:
        veredictos = [{"afirmacion": "El límite es 100 kg.", "respaldada": True}]
        with patch.object(faq_checks, "_pedir_veredictos", return_value=veredictos):
            resultado = faq_checks.context_faithfulness("El límite es 100 kg.", _context())

        self.assertTrue(resultado["pass"], resultado["reason"])
        self.assertEqual(resultado["score"], 1.0)

    def test_falla_y_reporta_afirmaciones_inventadas(self) -> None:
        veredictos = [
            {"afirmacion": "El límite es 100 kg.", "respaldada": True},
            {"afirmacion": "El salto cuesta Q1,500.", "respaldada": False},
        ]
        with patch.object(faq_checks, "_pedir_veredictos", return_value=veredictos) as grader:
            resultado = faq_checks.context_faithfulness("...", _context())

        grader.assert_called_once_with("¿Límite de peso?", "...", CONTEXTO)
        self.assertFalse(resultado["pass"])
        self.assertEqual(resultado["score"], 0.5)
        self.assertIn("Q1,500", resultado["reason"])

    def test_error_del_grader_es_fail(self) -> None:
        with patch.object(faq_checks, "_pedir_veredictos", side_effect=KeyError("afirmaciones")):
            resultado = faq_checks.context_faithfulness("...", _context())

        self.assertFalse(resultado["pass"])
        self.assertIn("grader falló", resultado["reason"])


if __name__ == "__main__":
    unittest.main()
