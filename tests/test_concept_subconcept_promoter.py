from __future__ import annotations

import unittest

from src.concept_subconcept_promoter import promote_taxonomy_subconcepts, restore_promoted_subconcepts
from src.concept_filter import filter_valid_concepts


def _payload(
    *,
    concept: str,
    definitions: list[str] | None = None,
    technical_rules: list[str] | None = None,
    procedures: list[str] | None = None,
    terminology: list[str] | None = None,
    examples: list[str] | None = None,
    relationships: list[str] | None = None,
    source_chunks: list[int] | None = None,
) -> dict[str, object]:
    return {
        "concept": concept,
        "definitions": definitions or [],
        "technical_rules": technical_rules or [],
        "procedures": procedures or [],
        "terminology": terminology or [],
        "examples": examples or [],
        "relationships": relationships or [],
        "source_chunks": source_chunks or [],
    }


class ConceptSubconceptPromoterTests(unittest.TestCase):
    def test_promotes_house_angularity_from_definition_head_and_child_family(self) -> None:
        concepts = {
            "planetary condition": _payload(
                concept="planetary condition",
                definitions=[
                    "House Angularity: angular houses provide strength and cadent houses weaken planets.",
                    "Angular houses: the strongest houses.",
                    "Cadent houses: the weakest houses.",
                ],
                terminology=["Succedent Houses"],
                technical_rules=["Angular houses, succedent houses, and cadent houses form a strength hierarchy."],
                source_chunks=[51],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)
        restored = restore_promoted_subconcepts(filter_valid_concepts(promoted), promoted)

        self.assertIn("house angularity", restored)
        self.assertEqual(restored["house angularity"]["source_chunks"], [51])
        self.assertEqual(restored["house angularity"]["_promotion_reason"], "definition_head_parent")
        self.assertTrue(restored["house angularity"]["definitions"])

    def test_promotes_house_angularity_from_family_support_when_parent_only_in_concept_name(self) -> None:
        concepts = {
            "angularity and favorability of house": _payload(
                concept="angularity and favorability of house",
                terminology=["Angular houses", "Succedent houses", "Cadent houses", "Ascendant"],
                source_chunks=[34],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)
        restored = restore_promoted_subconcepts(filter_valid_concepts(promoted), promoted)

        self.assertIn("house angularity", restored)
        self.assertEqual(restored["house angularity"]["source_chunks"], [34])
        self.assertEqual(restored["house angularity"]["_promotion_reason"], "family_child_support_parent")
        self.assertEqual(
            restored["house angularity"]["terminology"],
            ["Angular houses", "Succedent houses", "Cadent houses"],
        )

    def test_promotes_succedent_houses_from_exact_definition_head(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=["Succedent houses: houses following angular houses with moderate energy."],
                technical_rules=["Succedent houses provide moderate support."],
                source_chunks=[8],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)

        self.assertIn("succedent houses", promoted)
        self.assertEqual(
            promoted["succedent houses"]["definitions"],
            ["Succedent houses: houses following angular houses with moderate energy."],
        )
        self.assertEqual(
            promoted["succedent houses"]["technical_rules"],
            ["Succedent houses provide moderate support."],
        )
        self.assertEqual(promoted["succedent houses"]["source_chunks"], [8])

    def test_promotes_cadent_houses_from_exact_definition_head(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=["Cadent houses: houses following succedent houses and declining from power."],
                source_chunks=[8],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)

        self.assertIn("cadent houses", promoted)
        self.assertEqual(
            promoted["cadent houses"]["definitions"],
            ["Cadent houses: houses following succedent houses and declining from power."],
        )

    def test_promotes_epanaphora_and_apoklino_from_terminology(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                terminology=["Epanaphora", "Apoklino", "Epanaphora (post-ascension)"],
                technical_rules=[
                    "The Greek epanaphora means to rise toward the angular house.",
                    "The Greek apoklino means to slope down from the angular house.",
                ],
                source_chunks=[7],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)
        restored = restore_promoted_subconcepts(filter_valid_concepts(promoted), promoted)

        self.assertIn("epanaphora", restored)
        self.assertIn("apoklino", restored)
        self.assertEqual(restored["epanaphora"]["terminology"], ["Epanaphora", "Epanaphora (post-ascension)"])
        self.assertEqual(restored["apoklino"]["terminology"], ["Apoklino"])
        self.assertTrue(restored["epanaphora"]["technical_rules"])
        self.assertTrue(restored["apoklino"]["technical_rules"])

    def test_promotes_benefic_houses_from_exact_definition_head(self) -> None:
        concepts = {
            "favorability of house": _payload(
                concept="favorability of house",
                definitions=["Benefic houses: houses favorable to the life of the individual."],
                relationships=["Benefic houses include angular, 11th, 9th, and 5th; malefic houses include 2nd, 6th, 8th, and 12th."],
                source_chunks=[9],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)

        self.assertIn("benefic houses", promoted)
        self.assertEqual(
            promoted["benefic houses"]["definitions"],
            ["Benefic houses: houses favorable to the life of the individual."],
        )

    def test_promotes_favorability_parent_and_children_from_closed_house_fortune_family(self) -> None:
        concepts = {
            "fortunate and unfortunate houses": _payload(
                concept="fortunate and unfortunate houses",
                source_chunks=[42],
            ),
            "good condition and bad condition of planets in houses": _payload(
                concept="good condition and bad condition of planets in houses",
                technical_rules=[
                    "Benefic planets in good condition in fortunate houses produce best outcomes.",
                    "Malefic planets in poor condition in unfavorable houses produce destructive outcomes.",
                ],
                source_chunks=[42],
            ),
            "good houses": _payload(
                concept="good houses",
                definitions=["good houses or places: Houses configured by whole-sign aspects to the Ascendant."],
                source_chunks=[42, 85],
            ),
            "bad houses or places": _payload(
                concept="bad houses or places",
                definitions=["bad houses or places: Houses in aversion to the Ascendant."],
                source_chunks=[42, 83],
            ),
        }

        promoted = promote_taxonomy_subconcepts(concepts)
        restored = restore_promoted_subconcepts(filter_valid_concepts(promoted), promoted)

        self.assertIn("favorability of house", restored)
        self.assertEqual(restored["favorability of house"]["_promotion_reason"], "family_child_support_parent")
        self.assertEqual(
            restored["favorability of house"]["terminology"],
            ["Benefic houses", "Malefic houses"],
        )
        self.assertIn("benefic houses", promoted)
        self.assertIn("malefic houses", promoted)
        self.assertEqual(promoted["benefic houses"]["source_chunks"], [42, 85])
        self.assertEqual(promoted["malefic houses"]["source_chunks"], [42, 83])

    def test_does_not_promote_terms_outside_allowlist(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=["Profitable houses: a category not allowlisted."],
                terminology=["Kentron"],
                source_chunks=[7],
            )
        }

        promoted = promote_taxonomy_subconcepts(concepts)

        self.assertNotIn("profitable houses", promoted)
        self.assertEqual(set(promoted), {"angularity of house"})


if __name__ == "__main__":
    unittest.main()
