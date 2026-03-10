from __future__ import annotations

import unittest

from src.concept_normalization import normalize_concept_name, normalize_concepts


class ConceptNormalizationTests(unittest.TestCase):
    def test_normalize_concept_name_applies_surface_rules(self) -> None:
        self.assertEqual(normalize_concept_name("Whole-sign houses"), "whole sign house system")
        self.assertEqual(normalize_concept_name("Whole sign houses"), "whole sign house system")
        self.assertEqual(normalize_concept_name("Whole sign system"), "whole sign house system")
        self.assertEqual(normalize_concept_name("Angular Houses"), "angular house")
        self.assertEqual(normalize_concept_name("The Astrological Houses"), "astrological house")
        self.assertEqual(normalize_concept_name("Advantageous"), "advantageous")
        self.assertEqual(normalize_concept_name("Phasis"), "phasis")
        self.assertEqual(normalize_concept_name("Chrematistikos"), "chrematistikos")
        self.assertEqual(normalize_concept_name("Oikodespotes"), "oikodespotes")

    def test_normalize_concept_name_canonicalizes_discursive_patterns(self) -> None:
        self.assertEqual(normalize_concept_name("classification of house"), "house classification")
        self.assertEqual(normalize_concept_name("classification of the house"), "house classification")
        self.assertEqual(normalize_concept_name("Classifications of the Houses"), "house classification")
        self.assertEqual(normalize_concept_name("classification and valuation of house"), "house classification")
        self.assertEqual(normalize_concept_name("Classification and Topics of the Twelve Houses"), "twelve house classification")
        self.assertEqual(normalize_concept_name("interpretation of house"), "house interpretation")
        self.assertEqual(normalize_concept_name("relationship of house to profitability"), "house profitability relationship")
        self.assertEqual(normalize_concept_name("origin and development of house division"), "house division origin")
        self.assertEqual(normalize_concept_name("topic of house"), "house topic")
        self.assertEqual(normalize_concept_name("condition of house"), "house condition")

    def test_normalize_concepts_dedupes_and_preserves_order(self) -> None:
        concepts = [
            "Whole-sign houses",
            "Whole sign houses",
            "Angular Houses",
            "whole sign house system",
            "Angular house",
            "Succedent houses",
            "classification of house",
            "classification and valuation of the house",
        ]
        self.assertEqual(
            normalize_concepts(concepts),
            ["whole sign house system", "angular house", "succedent house", "house classification"],
        )


if __name__ == "__main__":
    unittest.main()
