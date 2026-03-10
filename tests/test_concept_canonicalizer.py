from __future__ import annotations

import unittest

from src.concept_canonicalizer import canonicalize_concept_name, canonicalize_concepts


def _payload(
    *,
    definitions: list[str] | None = None,
    technical_rules: list[str] | None = None,
    procedures: list[str] | None = None,
    terminology: list[str] | None = None,
    examples: list[str] | None = None,
    relationships: list[str] | None = None,
    source_chunks: list[int] | None = None,
) -> dict[str, object]:
    return {
        "concept": "placeholder",
        "definitions": definitions or [],
        "technical_rules": technical_rules or [],
        "procedures": procedures or [],
        "terminology": terminology or [],
        "examples": examples or [],
        "relationships": relationships or [],
        "source_chunks": source_chunks or [],
    }


class ConceptCanonicalizerTests(unittest.TestCase):
    def test_canonicalize_concept_name_strips_narrative_prefixes(self) -> None:
        self.assertEqual(
            canonicalize_concept_name("historical usage and debate on house system"),
            "house system",
        )
        self.assertEqual(
            canonicalize_concept_name("relative angularity of house"),
            "house angularity",
        )
        self.assertEqual(canonicalize_concept_name("angularity of house"), "house angularity")

    def test_canonicalize_concept_name_fixes_chreniatistiko_transliteration(self) -> None:
        self.assertEqual(canonicalize_concept_name("chreniatistiko house"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("chreniatistikos house"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("profitable house"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("advantageous"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("advantageou"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("chrematistiko"), "chrematistikos")
        self.assertEqual(canonicalize_concept_name("oikodespote"), "oikodespotes")
        self.assertEqual(canonicalize_concept_name("phasi"), "phasis")

    def test_canonicalize_concept_name_pluralizes_technical_house_concepts(self) -> None:
        self.assertEqual(canonicalize_concept_name("angular house"), "angular houses")
        self.assertEqual(canonicalize_concept_name("succedent house"), "succedent houses")
        self.assertEqual(canonicalize_concept_name("cadent house"), "cadent houses")
        self.assertEqual(canonicalize_concept_name("derived house"), "derived houses")

    def test_canonicalize_concepts_merges_entries_that_collapse_to_same_key(self) -> None:
        concepts = {
            "historical usage and debate on house system": _payload(
                definitions=["A debated system."],
                source_chunks=[7],
            ),
            "house system": _payload(
                technical_rules=["A house system divides the chart."],
                source_chunks=[8],
            ),
        }

        canonicalized = canonicalize_concepts(concepts)

        self.assertEqual(list(canonicalized), ["house system"])
        self.assertEqual(canonicalized["house system"]["concept"], "house system")
        self.assertEqual(canonicalized["house system"]["definitions"], ["A debated system."])
        self.assertEqual(
            canonicalized["house system"]["technical_rules"],
            ["A house system divides the chart."],
        )
        self.assertEqual(canonicalized["house system"]["source_chunks"], [7, 8])


if __name__ == "__main__":
    unittest.main()
