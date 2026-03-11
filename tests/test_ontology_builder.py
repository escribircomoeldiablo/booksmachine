from __future__ import annotations

import unittest

from src.ontology_builder import (
    apply_taxonomy_links,
    build_ontology,
    build_ontology_output_path,
    apply_family_memberships,
    resolve_equivalence_families,
)


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


class OntologyBuilderTests(unittest.TestCase):
    def test_resolve_equivalence_families_merges_house_system_variants(self) -> None:
        concepts = {
            "whole sign house system": _payload(
                concept="whole sign house system",
                definitions=["Canonical definition."],
                source_chunks=[6],
            ),
            "whole sign houses": _payload(
                concept="whole sign houses",
                technical_rules=["Signs and houses coincide."],
                source_chunks=[7],
            ),
            "whole-sign houses": _payload(
                concept="whole-sign houses",
                procedures=["Assign one sign per house."],
                source_chunks=[8],
            ),
        }

        merged, canonical_map = resolve_equivalence_families(concepts)

        self.assertEqual(list(merged), ["whole sign house system"])
        self.assertEqual(
            merged["whole sign house system"]["aliases"],
            ["whole sign houses", "whole-sign houses"],
        )
        self.assertEqual(
            merged["whole sign house system"]["definitions"],
            ["Canonical definition."],
        )
        self.assertEqual(
            merged["whole sign house system"]["technical_rules"],
            ["Signs and houses coincide."],
        )
        self.assertEqual(
            merged["whole sign house system"]["procedures"],
            ["Assign one sign per house."],
        )
        self.assertEqual(merged["whole sign house system"]["source_chunks"], [6, 7, 8])
        self.assertEqual(canonical_map["whole sign houses"], "whole sign house system")
        self.assertEqual(canonical_map["whole-sign houses"], "whole sign house system")

    def test_apply_taxonomy_links_creates_house_angularity_and_preserves_chrematistikos(self) -> None:
        concepts = {
            "angularity of house": _payload(concept="angularity of house", source_chunks=[6]),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[8]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[9]),
            "chrematistikos": _payload(concept="chrematistikos", source_chunks=[7]),
            "favorability of house": _payload(concept="favorability of house", source_chunks=[10]),
            "angularity of planet in house": _payload(concept="angularity of planet in house", source_chunks=[11]),
        }

        merged, canonical_map = resolve_equivalence_families(concepts)
        linked = apply_taxonomy_links(
            merged,
            canonical_map,
            taxonomy_links=[
                {"parent": "angularity of house", "child": "angular houses"},
                {"parent": "angularity of house", "child": "succedent houses"},
            ],
        )

        self.assertIn("house angularity", linked)
        self.assertEqual(linked["house angularity"]["node_kind"], "classification")
        self.assertEqual(
            linked["house angularity"]["child_concepts"],
            ["angular houses", "succedent houses", "cadent houses"],
        )
        self.assertEqual(linked["house angularity"]["related_concepts"], ["chrematistikos"])
        self.assertEqual(linked["house angularity"]["source_chunks"], [6, 7, 8, 9])
        self.assertEqual(linked["angular houses"]["parent_concepts"], ["house angularity"])
        self.assertEqual(linked["succedent houses"]["parent_concepts"], ["house angularity"])
        self.assertEqual(linked["cadent houses"]["parent_concepts"], ["house angularity"])
        self.assertEqual(linked["angular houses"]["node_kind"], "subconcept")
        self.assertEqual(linked["chrematistikos"]["related_concepts"], ["house angularity"])
        self.assertEqual(linked["chrematistikos"]["node_kind"], "topic")
        self.assertEqual(linked["favorability of house"]["parent_concepts"], [])
        self.assertEqual(linked["angularity of planet in house"]["parent_concepts"], [])

    def test_build_ontology_applies_equivalence_merge_before_taxonomy_linking(self) -> None:
        concepts = {
            "whole sign house system": _payload(concept="whole sign house system", source_chunks=[6]),
            "whole sign houses": _payload(concept="whole sign houses", source_chunks=[7]),
            "angularity of house": _payload(concept="angularity of house", source_chunks=[8]),
            "angular houses": _payload(concept="angular houses", source_chunks=[9]),
            "chrematistikos": _payload(concept="chrematistikos", source_chunks=[9]),
        }

        ontology = build_ontology(
            concepts,
            taxonomy_links=[{"parent": "angularity of house", "child": "angular houses"}],
        )

        self.assertIn("whole sign house system", ontology)
        self.assertNotIn("whole sign houses", ontology)
        self.assertEqual(ontology["whole sign house system"]["aliases"], ["whole sign houses"])
        self.assertIn("house angularity", ontology)
        self.assertEqual(ontology["house angularity"]["related_concepts"], ["chrematistikos"])
        self.assertEqual(ontology["house angularity"]["aliases"], ["angularity of house"])
        self.assertEqual(ontology["angular houses"]["parent_concepts"], ["house angularity"])

    def test_apply_taxonomy_links_deduplicates_after_canonical_remap(self) -> None:
        concepts = {
            "house angularity": _payload(concept="house angularity", source_chunks=[6]),
            "whole sign house system": _payload(concept="whole sign house system", source_chunks=[7]),
            "whole sign houses": _payload(concept="whole sign houses", source_chunks=[8]),
        }

        merged, canonical_map = resolve_equivalence_families(concepts)
        linked = apply_taxonomy_links(
            merged,
            canonical_map,
            taxonomy_links=[
                {"parent": "house angularity", "child": "whole sign houses"},
                {"parent": "house angularity", "child": "whole sign house system"},
            ],
        )

        self.assertEqual(linked["house angularity"]["child_concepts"], ["whole sign house system"])
        self.assertEqual(linked["whole sign house system"]["parent_concepts"], ["house angularity"])

    def test_build_ontology_output_path_uses_stable_naming(self) -> None:
        self.assertTrue(
            build_ontology_output_path("outputs/Book_knowledge_chunks.jsonl").endswith(
                "Book_knowledge_ontology.json"
            )
        )

    def test_build_ontology_can_disable_legacy_fallback_for_internal_comparison(self) -> None:
        concepts = {
            "angular houses": _payload(concept="angular houses", source_chunks=[8]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[9]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[10]),
        }

        inferred_only = build_ontology(concepts, enable_legacy_fallback=False)
        inferred_plus_legacy = build_ontology(concepts, enable_legacy_fallback=True)

        self.assertNotIn("house angularity", inferred_only)
        self.assertIn("house angularity", inferred_plus_legacy)
        self.assertEqual(
            inferred_plus_legacy["house angularity"]["child_concepts"],
            ["angular houses", "succedent houses", "cadent houses"],
        )

    def test_apply_family_memberships_adds_family_nodes_and_concept_links(self) -> None:
        ontology = {
            "void in course moon": _payload(concept="void in course moon", source_chunks=[4]),
            "lunar application": _payload(concept="lunar application", source_chunks=[5]),
        }
        family_payload = {
            "families": [
                {
                    "family_id": "lunar_motion",
                    "label": "lunar motion",
                    "members": ["void in course moon", "lunar application"],
                }
            ]
        }

        linked = apply_family_memberships(ontology, family_memberships=family_payload)

        self.assertIn("lunar motion", linked)
        self.assertEqual(linked["lunar motion"]["node_kind"], "family")
        self.assertEqual(linked["lunar motion"]["family_id"], "lunar_motion")
        self.assertEqual(linked["lunar motion"]["family_members"], ["void in course moon", "lunar application"])
        self.assertEqual(linked["lunar motion"]["child_concepts"], ["void in course moon", "lunar application"])
        self.assertEqual(linked["lunar motion"]["source_chunks"], [4, 5])
        self.assertEqual(linked["void in course moon"]["family_id"], ["lunar_motion"])
        self.assertEqual(linked["void in course moon"]["belongs_to_families"], ["lunar motion"])
        self.assertEqual(linked["void in course moon"]["parent_concepts"], ["lunar motion"])

    def test_apply_taxonomy_links_preserves_scalar_family_id_for_family_nodes(self) -> None:
        concepts = {
            "lunar motion": {
                **_payload(concept="lunar motion", source_chunks=[4]),
                "family_id": "lunar_motion",
                "node_kind": "family",
            }
        }

        linked = apply_taxonomy_links(concepts, canonical_map={"lunar motion": "lunar motion"})

        self.assertEqual(linked["lunar motion"]["family_id"], "lunar_motion")

    def test_build_ontology_supports_family_memberships_when_taxonomy_is_empty(self) -> None:
        concepts = {
            "void in course moon": _payload(concept="void in course moon", source_chunks=[4]),
        }

        ontology = build_ontology(
            concepts,
            taxonomy_links=[],
            family_memberships={
                "families": [
                    {
                        "family_id": "lunar_motion",
                        "label": "lunar motion",
                        "members": ["void in course moon"],
                    }
                ]
            },
            enable_legacy_fallback=False,
        )

        self.assertIn("lunar motion", ontology)
        self.assertEqual(ontology["lunar motion"]["child_concepts"], ["void in course moon"])
        self.assertEqual(ontology["void in course moon"]["belongs_to_families"], ["lunar motion"])
        self.assertEqual(ontology["void in course moon"]["parent_concepts"], ["lunar motion"])


if __name__ == "__main__":
    unittest.main()
