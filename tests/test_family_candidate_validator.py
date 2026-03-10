from __future__ import annotations

import unittest

from src.family_candidate_validator import validate_candidate_families


class FamilyCandidateValidatorTests(unittest.TestCase):
    def test_validate_rejects_unknown_members(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "time lord techniques",
                    "members": ["profection", "decennial", "invented concept"],
                    "rationale": "Timing",
                }
            ]
        }

        validated = validate_candidate_families(payload, unassigned_concepts=["profection", "decennial"])

        self.assertEqual(validated["candidate_families"], [])
        self.assertIn("contains_unknown_members", validated["rejected_candidates"][0]["reasons"])

    def test_validate_rejects_generic_labels_and_small_families(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "conditions",
                    "members": ["benefic", "malefic"],
                    "rationale": "Too vague",
                }
            ]
        }

        validated = validate_candidate_families(payload, unassigned_concepts=["benefic", "malefic"])

        self.assertEqual(validated["candidate_families"], [])
        self.assertIn("label_too_generic", validated["rejected_candidates"][0]["reasons"])
        self.assertIn("family_too_small", validated["rejected_candidates"][0]["reasons"])

    def test_validate_rejects_vague_composite_labels(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "lights and related terms",
                    "members": ["light luminarie", "luminary light", "evening star"],
                    "rationale": "Too broad",
                }
            ]
        }

        validated = validate_candidate_families(
            payload,
            unassigned_concepts=["light luminarie", "luminary light", "evening star"],
        )

        self.assertEqual(validated["candidate_families"], [])
        self.assertIn("label_too_generic", validated["rejected_candidates"][0]["reasons"])

    def test_validate_dedupes_internal_members_and_accepts_unique_valid_family(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "time lord techniques",
                    "members": ["profection", "decennial", "profection", "annual lord of year"],
                    "rationale": "Timing",
                }
            ]
        }

        validated = validate_candidate_families(
            payload,
            unassigned_concepts=["profection", "decennial", "annual lord of year"],
        )

        self.assertEqual(len(validated["candidate_families"]), 1)
        self.assertEqual(
            validated["candidate_families"][0]["members"],
            ["profection", "decennial", "annual lord of year"],
        )

    def test_validate_detects_possible_merge_with_existing_family(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "planetary phases",
                    "members": ["phase", "combust", "phasis"],
                    "rationale": "Already covered",
                }
            ]
        }
        existing_catalog = [{"id": "planetary_phases", "label": "planetary phases", "aliases": ["phase"]}]

        validated = validate_candidate_families(
            payload,
            unassigned_concepts=["phase", "combust", "phasis"],
            existing_catalog=existing_catalog,
        )

        self.assertEqual(validated["candidate_families"], [])
        self.assertIn("possible_merge_with_existing_family", validated["rejected_candidates"][0]["reasons"])

    def test_validate_limits_one_candidate_family_per_member(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "time lord techniques",
                    "members": ["profection", "decennial", "annual lord of year"],
                    "rationale": "Timing",
                },
                {
                    "family_label": "predictive systems",
                    "members": ["profection", "decennial", "progression"],
                    "rationale": "Overlap",
                },
            ]
        }

        validated = validate_candidate_families(
            payload,
            unassigned_concepts=["profection", "decennial", "annual lord of year", "progression"],
        )

        self.assertEqual(len(validated["candidate_families"]), 1)
        self.assertEqual(len(validated["rejected_candidates"]), 1)
        self.assertIn("member_collision_across_candidates", validated["rejected_candidates"][0]["reasons"])

    def test_validate_rejects_candidates_built_from_protected_base_concepts(self) -> None:
        payload = {
            "candidate_families": [
                {
                    "family_label": "angularity and direction",
                    "members": ["angle", "angularity", "easterly direction"],
                    "rationale": "Too foundational",
                }
            ]
        }

        validated = validate_candidate_families(
            payload,
            unassigned_concepts=["angle", "angularity", "easterly direction"],
        )

        self.assertEqual(validated["candidate_families"], [])
        self.assertIn("contains_protected_base_concepts", validated["rejected_candidates"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
