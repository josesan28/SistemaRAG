"""Pruebas locales para el parser y las utilidades de la carga."""

from __future__ import annotations

import unittest

from load_faqs import DEFAULT_CORPUS, parse_corpus
from parachute_faq_tool import _validate_search
from parachute_vector_store import to_pgvector_literal


class CorpusTests(unittest.TestCase):
    def test_official_corpus_has_120_unique_faqs(self) -> None:
        faqs = parse_corpus(DEFAULT_CORPUS)

        self.assertEqual(len(faqs), 120)
        self.assertEqual(len({faq.id for faq in faqs}), 120)
        self.assertEqual(faqs[0].id, "FAQ-001")
        self.assertEqual(faqs[-1].id, "FAQ-120")

    def test_pgvector_literal_has_expected_format(self) -> None:
        self.assertEqual(to_pgvector_literal([0.1, -0.2]), "[0.10000000,-0.20000000]")

    def test_search_arguments_are_validated(self) -> None:
        self.assertEqual(_validate_search("  ¿Hay parqueo?  ", 3), ("¿Hay parqueo?", 3))
        with self.assertRaises(ValueError):
            _validate_search("", 3)
        with self.assertRaises(ValueError):
            _validate_search("pregunta", 11)
        with self.assertRaises(ValueError):
            _validate_search("pregunta", True)


if __name__ == "__main__":
    unittest.main()
