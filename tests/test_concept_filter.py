from __future__ import annotations

import unittest

from src.concept_filter import filter_valid_concepts


def _payload(
    *,
    definitions: list[str] | None = None,
    technical_rules: list[str] | None = None,
    procedures: list[str] | None = None,
) -> dict[str, object]:
    return {
        "concept": "placeholder",
        "definitions": definitions or [],
        "technical_rules": technical_rules or [],
        "procedures": procedures or [],
        "terminology": [],
        "examples": [],
        "relationships": [],
        "source_chunks": [1],
    }


class ConceptFilterTests(unittest.TestCase):
    def test_filter_valid_concepts_keeps_nominal_concepts_with_core_content(self) -> None:
        concepts = {
            "whole sign house system": _payload(definitions=["A system."]),
            "angular house": _payload(technical_rules=["Angular houses are strong."]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertEqual(set(filtered), {"whole sign house system", "angular house"})

    def test_filter_valid_concepts_drops_long_and_discursive_concepts(self) -> None:
        concepts = {
            "angularity of house as source of dynamic cosmic energy and stable support": _payload(
                definitions=["d1"]
            ),
            "symbolism of four cardinal point in astrology": _payload(definitions=["d1"]),
            "house oracle and profitability relationship": _payload(definitions=["d1"]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertNotIn("angularity of house as source of dynamic cosmic energy and stable support", filtered)
        self.assertNotIn("symbolism of four cardinal point in astrology", filtered)
        self.assertNotIn("house oracle and profitability relationship", filtered)

    def test_filter_valid_concepts_drops_multiple_of_and_verb_led_names(self) -> None:
        concepts = {
            "relationship of house to oracle of profitability": _payload(definitions=["d1"]),
            "interpret house strength": _payload(definitions=["d1"]),
            "assess planetary strength": _payload(definitions=["d1"]),
            "porphyry house system": _payload(definitions=["d1"]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertNotIn("relationship of house to oracle of profitability", filtered)
        self.assertNotIn("interpret house strength", filtered)
        self.assertNotIn("assess planetary strength", filtered)
        self.assertIn("porphyry house system", filtered)

    def test_filter_valid_concepts_drops_concepts_without_core_content(self) -> None:
        concepts = {
            "ascendant": _payload(),
            "midheaven": _payload(procedures=["Locate the culminating degree."]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertNotIn("ascendant", filtered)
        self.assertIn("midheaven", filtered)


if __name__ == "__main__":
    unittest.main()
