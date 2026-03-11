from __future__ import annotations

import unittest

from src.concept_filter import filter_valid_concepts


def _payload(
    *,
    definitions: list[str] | None = None,
    technical_rules: list[str] | None = None,
    procedures: list[str] | None = None,
    terminology: list[str] | None = None,
) -> dict[str, object]:
    return {
        "concept": "placeholder",
        "definitions": definitions or [],
        "technical_rules": technical_rules or [],
        "procedures": procedures or [],
        "terminology": terminology or [],
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

    def test_filter_valid_concepts_drops_common_narrative_concept_shapes(self) -> None:
        concepts = {
            "relationship between first and fifth house": _payload(definitions=["d1"]),
            "template for planetary and house delineation": _payload(definitions=["d1"]),
            "planet in house 8 12 interpretation": _payload(definitions=["d1"]),
            "fifth house signification in traditional astrology": _payload(definitions=["d1"]),
            "whole sign house system": _payload(definitions=["d1"]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertNotIn("relationship between first and fifth house", filtered)
        self.assertNotIn("template for planetary and house delineation", filtered)
        self.assertNotIn("planet in house 8 12 interpretation", filtered)
        self.assertNotIn("fifth house signification in traditional astrology", filtered)
        self.assertIn("whole sign house system", filtered)

    def test_filter_valid_concepts_drops_concepts_without_core_content(self) -> None:
        concepts = {
            "ascendant": _payload(),
            "midheaven": _payload(procedures=["Locate the culminating degree."]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertNotIn("ascendant", filtered)
        self.assertIn("midheaven", filtered)

    def test_filter_valid_concepts_keeps_exact_terminology_anchor_without_formal_definition(self) -> None:
        concepts = {
            "lot of fortune": _payload(terminology=["Lot of Fortune", "Fortuna"]),
            "lord of nativity": _payload(terminology=["Lord of the Nativity"]),
            "malefic": _payload(terminology=["Lot of Fortune", "Master of the Nativity"]),
        }
        concepts["lot of fortune"]["concept"] = "lot of fortune"
        concepts["lord of nativity"]["concept"] = "lord of nativity"
        concepts["malefic"]["concept"] = "malefic"

        filtered = filter_valid_concepts(concepts)

        self.assertIn("lot of fortune", filtered)
        self.assertIn("lord of nativity", filtered)
        self.assertNotIn("malefic", filtered)

    def test_filter_valid_concepts_allows_nominal_head_before_as_narrative_suffix(self) -> None:
        concepts = {
            "equal house system as starting at ascendant degree with 30 each house": _payload(definitions=["d1"]),
            "hyleg as releaser in longevity determination": _payload(definitions=["d1"]),
        }

        filtered = filter_valid_concepts(concepts)

        self.assertIn("equal house system as starting at ascendant degree with 30 each house", filtered)
        self.assertIn("hyleg as releaser in longevity determination", filtered)


if __name__ == "__main__":
    unittest.main()
