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

    def test_assign_families_hybrid_rules_assign_uncovered_authorities_lots_and_angles(self) -> None:
        concepts = {
            "kurio": _payload(concept="kurio"),
            "al kadkhudah alcochoden": _payload(concept="al kadkhudah alcochoden"),
            "lot of fortune": _payload(concept="lot of fortune"),
            "derived houses": _payload(concept="derived houses"),
            "ascendant": _payload(concept="ascendant"),
            "bound lord": _payload(concept="bound lord"),
            "aspect": _payload(concept="aspect"),
            "witnessing": _payload(concept="witnessing"),
        }
        catalog = [
            {"id": "chart_authorities", "label": "chart authorities", "aliases": ["predominator", "lord of nativity"]},
            {"id": "lots", "label": "lots", "aliases": ["lot of spirit daimon"]},
            {"id": "chart_angles", "label": "chart angles and axes", "aliases": ["angle", "line of horizon"]},
            {"id": "dignities", "label": "dignities", "aliases": ["dignity", "domicile lord"]},
            {"id": "house_systems", "label": "house systems", "aliases": ["equal house system", "quadrant house"]},
            {"id": "configuration", "label": "configuration", "aliases": ["bodily conjunction", "aversion"]},
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertEqual(assignments["kurio"][0]["family_id"], "chart_authorities")
        self.assertEqual(assignments["kurio"][0]["source"], "hybrid_rule")
        self.assertEqual(assignments["al kadkhudah alcochoden"][0]["family_id"], "chart_authorities")
        self.assertEqual(assignments["lot of fortune"][0]["family_id"], "lots")
        self.assertEqual(assignments["derived houses"][0]["family_id"], "house_systems")
        self.assertEqual(assignments["ascendant"][0]["family_id"], "chart_angles")
        self.assertEqual(assignments["bound lord"][0]["family_id"], "dignities")
        self.assertEqual(assignments["aspect"][0]["family_id"], "configuration")
        self.assertEqual(assignments["witnessing"][0]["family_id"], "configuration")

    def test_assign_families_hybrid_rules_can_add_secondary_family_without_overriding_exact_match(self) -> None:
        concepts = {
            "almuten": _payload(concept="almuten"),
        }
        catalog = [
            {"id": "chart_authorities", "label": "chart authorities", "aliases": ["predominator", "lord of nativity"]},
            {"id": "dignities", "label": "dignities", "aliases": ["almuten", "dignity"]},
        ]

        payload = assign_families(concepts, catalog)
        families = payload["concept_assignments"][0]["families"]

        self.assertEqual(families[0]["family_id"], "dignities")
        self.assertEqual(families[0]["source"], "alias_match")
        self.assertEqual(families[1]["family_id"], "chart_authorities")
        self.assertEqual(families[1]["source"], "hybrid_rule")

    def test_assign_families_supports_promoted_candidate_families_from_catalog_aliases(self) -> None:
        concepts = {
            "ascensional time": _payload(concept="ascensional time"),
            "pre ascension": _payload(concept="pre ascension"),
            "post ascension": _payload(concept="post ascension"),
            "casting ray": _payload(concept="casting ray"),
            "aporrhoia": _payload(concept="aporrhoia"),
            "passing by": _payload(concept="passing by"),
            "house place": _payload(concept="house place"),
            "topic of house": _payload(concept="topic of house"),
            "favorability": _payload(concept="favorability"),
            "solar phase": _payload(concept="solar phase"),
            "morning star": _payload(concept="morning star"),
        }
        catalog = [
            {"id": "ascensional_measures", "label": "ascensional measures", "aliases": ["ascensional time", "pre ascension", "post ascension"]},
            {"id": "ray_motion_doctrines", "label": "ray motion doctrines", "aliases": ["casting ray", "aporrhoia", "passing by"]},
            {"id": "house_interpretive_criteria", "label": "house interpretive criteria", "aliases": ["house place", "topic of house", "favorability"]},
            {"id": "planetary_phases", "label": "planetary phases", "aliases": ["solar phase", "morning star"]},
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertEqual(assignments["ascensional time"][0]["family_id"], "ascensional_measures")
        self.assertEqual(assignments["casting ray"][0]["family_id"], "ray_motion_doctrines")
        self.assertEqual(assignments["house place"][0]["family_id"], "house_interpretive_criteria")
        self.assertEqual(assignments["solar phase"][0]["family_id"], "planetary_phases")

    def test_assign_families_supports_expanded_zodiac_and_dignity_aliases(self) -> None:
        concepts = {
            "aries": _payload(concept="aries"),
            "aquarius": _payload(concept="aquarius"),
            "exaltation lord": _payload(concept="exaltation lord"),
            "face": _payload(concept="face"),
        }
        catalog = [
            {"id": "zodiac_signs", "label": "zodiac signs", "aliases": ["aries", "aquarius"]},
            {"id": "dignities", "label": "dignities", "aliases": ["exaltation lord", "face"]},
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertEqual(assignments["aries"][0]["family_id"], "zodiac_signs")
        self.assertEqual(assignments["aquarius"][0]["family_id"], "zodiac_signs")
        self.assertEqual(assignments["exaltation lord"][0]["family_id"], "dignities")
        self.assertEqual(assignments["face"][0]["family_id"], "dignities")

    def test_assign_families_supports_last_pass_residual_value_concepts(self) -> None:
        concepts = {
            "ascending node": _payload(concept="ascending node"),
            "lunation phase": _payload(concept="lunation phase"),
            "killing planet anairetes": _payload(concept="killing planet anairetes"),
            "neighboring": _payload(concept="neighboring"),
            "fixed sign": _payload(concept="fixed sign"),
            "planet s own natural signification": _payload(concept="planet s own natural signification"),
            "monomoira": _payload(concept="monomoira"),
        }
        catalog = [
            {"id": "celestial_coordinates", "label": "celestial coordinate system", "aliases": ["ascending node"]},
            {"id": "planetary_phases", "label": "planetary phases", "aliases": ["lunation phase"]},
            {"id": "chart_authorities", "label": "chart authorities", "aliases": ["killing planet anairetes"]},
            {"id": "configuration", "label": "configuration", "aliases": ["neighboring"]},
            {"id": "sign_qualities", "label": "sign qualities", "aliases": ["fixed sign"]},
            {"id": "planetary_significations", "label": "planetary significations", "aliases": ["planet s own natural signification"]},
            {"id": "dignities", "label": "dignities", "aliases": ["monomoira"]},
        ]

        payload = assign_families(concepts, catalog)
        assignments = {item["concept"]: item["families"] for item in payload["concept_assignments"]}

        self.assertEqual(assignments["ascending node"][0]["family_id"], "celestial_coordinates")
        self.assertEqual(assignments["lunation phase"][0]["family_id"], "planetary_phases")
        self.assertEqual(assignments["killing planet anairetes"][0]["family_id"], "chart_authorities")
        self.assertEqual(assignments["neighboring"][0]["family_id"], "configuration")
        self.assertEqual(assignments["fixed sign"][0]["family_id"], "sign_qualities")
        self.assertEqual(assignments["planet s own natural signification"][0]["family_id"], "planetary_significations")
        self.assertEqual(assignments["monomoira"][0]["family_id"], "dignities")


if __name__ == "__main__":
    unittest.main()
