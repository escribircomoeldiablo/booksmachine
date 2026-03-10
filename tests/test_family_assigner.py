from __future__ import annotations

import unittest

from src.family_assigner import assign_families


def _payload(
    *,
    concept: str,
    definitions: list[str] | None = None,
    terminology: list[str] | None = None,
    relationships: list[str] | None = None,
) -> dict[str, object]:
    return {
        "concept": concept,
        "definitions": definitions or [],
        "technical_rules": [],
        "procedures": [],
        "terminology": terminology or [],
        "examples": [],
        "relationships": relationships or [],
        "source_chunks": [],
    }


class FamilyAssignerTests(unittest.TestCase):
    def test_assign_families_uses_deterministic_alias_match_first(self) -> None:
        concepts = {
            "void in course moon": _payload(concept="void in course moon"),
            "celestial sympathy": _payload(concept="celestial sympathy"),
        }
        catalog = [
            {
                "id": "lunar_motion",
                "label": "lunar motion",
                "aliases": ["void in course moon", "lunar application"],
            }
        ]

        payload = assign_families(concepts, catalog)

        self.assertEqual(
            payload["families"],
            [{"family_id": "lunar_motion", "label": "lunar motion", "members": ["void in course moon"]}],
        )
        self.assertEqual(
            payload["concept_assignments"],
            [
                {
                    "concept": "void in course moon",
                    "families": [{"family_id": "lunar_motion", "source": "alias_match", "confidence": 1.0}],
                }
            ],
        )
        self.assertEqual(payload["unassigned_concepts"], ["celestial sympathy"])

    def test_assign_families_falls_back_to_partial_matching_and_caps_to_two_families(self) -> None:
        concepts = {
            "applying aspect": _payload(
                concept="applying aspect",
                definitions=["Applying aspect describes a configuration moving toward perfection."],
                terminology=["applying aspect"],
            )
        }
        catalog = [
            {
                "id": "aspect_dynamics",
                "label": "aspect dynamics",
                "aliases": ["application", "separation"],
                "controlled_patterns": ["applying aspect", "separating aspect"],
            },
            {
                "id": "lunar_motion",
                "label": "lunar motion",
                "aliases": ["void in course moon", "lunar separation"],
            },
            {
                "id": "planetary_phases",
                "label": "planetary phases",
                "aliases": ["heliacal rising"],
            },
        ]

        payload = assign_families(concepts, catalog)

        self.assertEqual(len(payload["concept_assignments"]), 1)
        self.assertEqual(payload["concept_assignments"][0]["concept"], "applying aspect")
        self.assertEqual(
            [item["family_id"] for item in payload["concept_assignments"][0]["families"]],
            ["aspect_dynamics"],
        )
        self.assertEqual(payload["concept_assignments"][0]["families"][0]["source"], "controlled_pattern_match")

    def test_assign_families_ignores_weak_token_overlap_false_positives(self) -> None:
        concepts = {
            "sect": _payload(concept="sect"),
            "direct motion": _payload(concept="direct motion"),
            "primary motion": _payload(concept="primary motion"),
            "enclosure": _payload(concept="enclosure"),
            "heliacal morning rise": _payload(concept="heliacal morning rise"),
        }
        catalog = [
            {
                "id": "house_classification",
                "label": "house classification",
                "aliases": ["angular houses", "succedent houses", "cadent houses"],
            },
            {
                "id": "lunar_motion",
                "label": "lunar motion",
                "aliases": ["void in course moon", "lunar application", "lunar separation"],
            },
            {
                "id": "maltreatment",
                "label": "maltreatment",
                "aliases": ["striking with ray", "maltreatment by opposition"],
            },
            {
                "id": "aspect_dynamics",
                "label": "aspect dynamics",
                "aliases": ["application", "separation"],
                "controlled_patterns": ["applying aspect", "separating aspect"],
            },
            {
                "id": "planetary_phases",
                "label": "planetary phases",
                "aliases": ["synodic phase", "heliacal rising", "heliacal setting"],
                "controlled_patterns": ["heliacal morning rise", "heliacal evening set"],
            },
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertNotIn("sect", assignments)
        self.assertNotIn("direct motion", assignments)
        self.assertNotIn("primary motion", assignments)
        self.assertNotIn("enclosure", assignments)
        self.assertEqual(assignments["heliacal morning rise"][0]["family_id"], "planetary_phases")
        self.assertEqual(assignments["heliacal morning rise"][0]["source"], "controlled_pattern_match")

    def test_assign_families_supports_catalog_expansion_via_specific_aliases(self) -> None:
        concepts = {
            "sect": _payload(concept="sect"),
            "contrary to sect": _payload(concept="contrary to sect"),
            "configuration": _payload(concept="configuration"),
            "bodily conjunction": _payload(concept="bodily conjunction"),
            "dignity": _payload(concept="dignity"),
            "domicile": _payload(concept="domicile"),
            "hermetic lot": _payload(concept="hermetic lot"),
        }
        catalog = [
            {
                "id": "sect",
                "label": "sect",
                "aliases": ["sect", "sect light", "contrary to sect"],
            },
            {
                "id": "configuration",
                "label": "configuration",
                "aliases": ["configuration", "bodily conjunction"],
            },
            {
                "id": "dignities",
                "label": "dignities",
                "aliases": ["dignity", "domicile"],
            },
            {
                "id": "lots",
                "label": "lots",
                "aliases": ["hermetic lot"],
            },
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertEqual(assignments["sect"][0]["family_id"], "sect")
        self.assertEqual(assignments["contrary to sect"][0]["family_id"], "sect")
        self.assertEqual(assignments["configuration"][0]["family_id"], "configuration")
        self.assertEqual(assignments["bodily conjunction"][0]["family_id"], "configuration")
        self.assertEqual(assignments["dignity"][0]["family_id"], "dignities")
        self.assertEqual(assignments["domicile"][0]["family_id"], "dignities")
        self.assertEqual(assignments["hermetic lot"][0]["family_id"], "lots")


if __name__ == "__main__":
    unittest.main()
