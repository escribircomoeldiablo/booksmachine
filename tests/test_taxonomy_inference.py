from __future__ import annotations

import unittest

from src.taxonomy_inference import infer_taxonomy_audit, infer_taxonomy_links


def _payload(
    *,
    concept: str,
    definitions: list[str] | None = None,
    relationships: list[str] | None = None,
    terminology: list[str] | None = None,
    source_chunks: list[int] | None = None,
) -> dict[str, object]:
    return {
        "concept": concept,
        "definitions": definitions or [],
        "technical_rules": [],
        "procedures": [],
        "terminology": terminology or [],
        "examples": [],
        "relationships": relationships or [],
        "source_chunks": source_chunks or [],
    }


class TaxonomyInferenceTests(unittest.TestCase):
    def test_audit_reports_accepted_and_rejected_candidates(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Succedent houses: houses following angular houses.",
                ],
                source_chunks=[8],
            ),
            "house system": _payload(
                concept="house system",
                definitions=[
                    "Predominator: The source of life force.",
                    "Sect: The chart polarity.",
                ],
                source_chunks=[9],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[8]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[8]),
            "predominator": _payload(concept="predominator", source_chunks=[9]),
            "sect": _payload(concept="sect", source_chunks=[9]),
        }

        audit = infer_taxonomy_audit(concepts)

        self.assertEqual(set(audit), {"accepted_links", "rejected_candidates"})
        self.assertEqual(
            [(item["parent"], item["child"]) for item in audit["accepted_links"]],
            [
                ("angularity of house", "angular houses"),
                ("angularity of house", "succedent houses"),
            ],
        )
        rejected = next(item for item in audit["rejected_candidates"] if item["parent"] == "house system")
        self.assertEqual(rejected["decision"], "rejected")
        self.assertEqual(rejected["rejection_reason"], "parent_not_taxonomic")

    def test_audit_marks_explicit_family_pattern_acceptance(self) -> None:
        concepts = {
            "house classification": _payload(
                concept="house classification",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Succedent houses: houses following angular houses.",
                    "Cadent houses: houses declining from angular houses.",
                ],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
        }

        audit = infer_taxonomy_audit(concepts)

        self.assertEqual(len(audit["accepted_links"]), 3)
        self.assertTrue(
            all(item["acceptance_reason"] == "explicit_family_pattern" for item in audit["accepted_links"])
        )

    def test_explicit_family_contamination_falls_back_to_general_selection(self) -> None:
        concepts = {
            "house classification": _payload(
                concept="house classification",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Succedent houses: houses following angular houses.",
                    "Cadent houses: houses declining from angular houses.",
                    "Equal house system: A house division system.",
                ],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
            "equal house system": _payload(concept="equal house system", source_chunks=[7]),
        }

        audit = infer_taxonomy_audit(concepts)

        self.assertEqual(
            [(item["parent"], item["child"]) for item in audit["accepted_links"]],
            [
                ("house classification", "angular houses"),
                ("house classification", "cadent houses"),
                ("house classification", "succedent houses"),
            ],
        )
        self.assertTrue(all("acceptance_reason" not in item for item in audit["accepted_links"]))

    def test_infers_link_from_definition_head(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=[
                    "Angular houses: the strongest houses in the chart.",
                    "Succedent houses: houses following angular houses with moderate energy.",
                ],
                source_chunks=[8],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[8]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[8]),
        }

        taxonomy = infer_taxonomy_links(concepts)
        link = next(link for link in taxonomy["links"] if link["child"] == "succedent houses")

        self.assertEqual(
            link,
            {
                "parent": "angularity of house",
                "child": "succedent houses",
                "signals": ["definition_head"],
                "evidence": ["Succedent houses: houses following angular houses with moderate energy."],
                "source_chunks": [8],
            },
        )

    def test_infers_link_from_closed_relationship_pattern(self) -> None:
        concepts = {
            "favorability of house": _payload(
                concept="favorability of house",
                definitions=[
                    "Benefic houses: houses favorable to the life of the individual.",
                    "Malefic houses: houses contrary to the life of the individual.",
                ],
                relationships=["Benefic houses include angular, 11th, 9th, and 5th houses; malefic houses include 2nd, 6th, 8th, and 12th."],
                source_chunks=[9],
            ),
            "benefic houses": _payload(concept="benefic houses", source_chunks=[9]),
            "malefic houses": _payload(concept="malefic houses", source_chunks=[9]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        benefic = next(link for link in taxonomy["links"] if link["child"] == "benefic houses")
        malefic = next(link for link in taxonomy["links"] if link["child"] == "malefic houses")
        self.assertEqual(benefic["signals"], ["definition_head", "relationship_pattern"])
        self.assertEqual(benefic["parent"], "favorability of house")
        self.assertEqual(benefic["source_chunks"], [9])
        self.assertEqual(malefic["signals"], ["definition_head", "relationship_pattern"])

    def test_does_not_infer_single_definition_head_for_taxonomic_parent_without_supporting_structure(self) -> None:
        concepts = {
            "favorability of house": _payload(
                concept="favorability of house",
                definitions=["Benefic houses: houses favorable to the life of the individual."],
                source_chunks=[9],
            ),
            "benefic houses": _payload(concept="benefic houses", source_chunks=[9]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_does_not_infer_from_weak_isolated_relationship_mention(self) -> None:
        concepts = {
            "house angularity": _payload(
                concept="house angularity",
                relationships=["Angular houses oppose cadent houses."],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_accepts_structural_family_pattern_from_parent_terminology_and_shared_chunks(self) -> None:
        concepts = {
            "house angularity": _payload(
                concept="house angularity",
                terminology=["Angular houses", "Succedent houses", "Cadent houses"],
                source_chunks=[34],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[34, 68]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[34]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[34, 83]),
        }

        taxonomy = infer_taxonomy_links(concepts)
        self.assertEqual(
            taxonomy["links"],
            [
                {
                    "parent": "house angularity",
                    "child": "angular houses",
                    "signals": ["structural_family_pattern"],
                    "evidence": ["Angular houses"],
                    "source_chunks": [34],
                },
                {
                    "parent": "house angularity",
                    "child": "cadent houses",
                    "signals": ["structural_family_pattern"],
                    "evidence": ["Cadent houses"],
                    "source_chunks": [34],
                },
                {
                    "parent": "house angularity",
                    "child": "succedent houses",
                    "signals": ["structural_family_pattern"],
                    "evidence": ["Succedent houses"],
                    "source_chunks": [34],
                },
            ],
        )

        audit = infer_taxonomy_audit(concepts)
        self.assertEqual(len(audit["accepted_links"]), 3)
        self.assertTrue(
            all(item["acceptance_reason"] == "structural_family_pattern" for item in audit["accepted_links"])
        )

    def test_does_not_infer_structural_family_pattern_for_non_allowlisted_parent(self) -> None:
        concepts = {
            "house system": _payload(
                concept="house system",
                terminology=["Predominator", "Sect"],
                source_chunks=[34],
            ),
            "predominator": _payload(concept="predominator", source_chunks=[34]),
            "sect": _payload(concept="sect", source_chunks=[34]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_does_not_infer_definition_head_for_non_taxonomic_parent_with_single_child(self) -> None:
        concepts = {
            "whole sign house system": _payload(
                concept="whole sign house system",
                definitions=[
                    "Equal house system: A house division system where the first house begins at the degree of the Ascendant."
                ],
                source_chunks=[6],
            ),
            "equal house system": _payload(concept="equal house system", source_chunks=[6]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_blocks_coordinated_parent_even_with_multiple_children(self) -> None:
        concepts = {
            "angularity and favorability of first house": _payload(
                concept="angularity and favorability of first house",
                definitions=[
                    "Derived Houses: Each house becomes a new starting point.",
                    "Cadent houses: houses declining from angular houses.",
                ],
                source_chunks=[12],
            ),
            "derived houses": _payload(concept="derived houses", source_chunks=[12]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[12]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_blocks_specific_position_parent(self) -> None:
        concepts = {
            "dynamic energy of midheaven mc degree": _payload(
                concept="dynamic energy of midheaven mc degree",
                definitions=[
                    "Succedent houses: houses following angular houses.",
                    "Cadent houses: houses declining from angular houses.",
                ],
                source_chunks=[9],
            ),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[9]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[9]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_preserves_source_chunks_as_audit_trace_not_extra_signal(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=[
                    "Angular houses: the strongest houses in the chart.",
                    "Cadent houses: houses declining from the angles.",
                ],
                source_chunks=[7, 9],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7, 9]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7, 9]),
        }

        taxonomy = infer_taxonomy_links(concepts)
        link = next(link for link in taxonomy["links"] if link["child"] == "cadent houses")

        self.assertEqual(link["source_chunks"], [7, 9])
        self.assertEqual(link["signals"], ["definition_head"])

    def test_output_is_deterministic_and_deduplicated(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=[
                    "Angular houses: the strongest houses in the chart.",
                    "Cadent houses: houses declining from the angles.",
                    "Cadent houses: houses declining from the angles.",
                ],
                relationships=[
                    "Angular houses are classified as operative places.",
                    "Cadent houses are classified as declining places.",
                ],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
        }

        first = infer_taxonomy_links(concepts)
        second = infer_taxonomy_links(concepts)

        self.assertEqual(first, second)
        self.assertEqual(len(first["links"]), 2)
        cadent = next(link for link in first["links"] if link["child"] == "cadent houses")
        self.assertEqual(cadent["signals"], ["definition_head", "relationship_pattern"])
        self.assertEqual(
            cadent["evidence"],
            [
                "Cadent houses: houses declining from the angles.",
                "Cadent houses are classified as declining places.",
            ],
        )

    def test_allows_non_taxonomic_house_parent_only_when_multiple_children_are_supported(self) -> None:
        concepts = {
            "first house topics": _payload(
                concept="first house topics",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Succedent houses: houses following angular houses.",
                    "Cadent houses: houses declining from angular houses.",
                ],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_blocks_multi_child_fallback_for_system_like_parent(self) -> None:
        concepts = {
            "whole sign house system": _payload(
                concept="whole sign house system",
                definitions=[
                    "Equal house system: A house division system.",
                    "Porphyry house system: A quadrant house system.",
                ],
                source_chunks=[6],
            ),
            "equal house system": _payload(concept="equal house system", source_chunks=[6]),
            "porphyry house system": _payload(concept="porphyry house system", source_chunks=[6]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_allows_definition_head_when_taxonomic_parent_has_multiple_children(self) -> None:
        concepts = {
            "angularity of house": _payload(
                concept="angularity of house",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Succedent houses: houses following angular houses.",
                    "Cadent houses: houses declining from angular houses.",
                ],
                source_chunks=[7],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(
            [(link["parent"], link["child"]) for link in taxonomy["links"]],
            [
                ("angularity of house", "angular houses"),
                ("angularity of house", "cadent houses"),
                ("angularity of house", "succedent houses"),
            ],
        )

    def test_keeps_only_largest_coherent_family_per_parent(self) -> None:
        concepts = {
            "house classification": _payload(
                concept="house classification",
                definitions=[
                    "Equal house system: A house division system.",
                    "Porphyry house system: A quadrant house system.",
                    "Angular houses: the strongest houses.",
                    "Cadent houses: houses declining from angular houses.",
                    "Succedent houses: houses following angular houses.",
                ],
                source_chunks=[6, 7],
            ),
            "equal house system": _payload(concept="equal house system", source_chunks=[6]),
            "porphyry house system": _payload(concept="porphyry house system", source_chunks=[6]),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
            "succedent houses": _payload(concept="succedent houses", source_chunks=[7]),
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(
            [(link["parent"], link["child"]) for link in taxonomy["links"]],
            [
                ("house classification", "angular houses"),
                ("house classification", "cadent houses"),
                ("house classification", "succedent houses"),
            ],
        )

    def test_tie_break_between_same_size_families_is_deterministic(self) -> None:
        concepts = {
            "house classification": _payload(
                concept="house classification",
                definitions=[
                    "Angular houses: the strongest houses.",
                    "Cadent houses: houses declining from angular houses.",
                    "Derived topics: topics derived from another house.",
                    "Primary topics: topics centered on the native.",
                ],
                source_chunks=[7, 12],
            ),
            "angular houses": _payload(concept="angular houses", source_chunks=[7]),
            "cadent houses": _payload(concept="cadent houses", source_chunks=[7]),
            "derived topics": _payload(concept="derived topics", source_chunks=[12]),
            "primary topics": _payload(concept="primary topics", source_chunks=[12]),
        }

        first = infer_taxonomy_links(concepts)
        second = infer_taxonomy_links(concepts)

        self.assertEqual(first, second)
        self.assertEqual(
            [(link["parent"], link["child"]) for link in first["links"]],
            [
                ("house classification", "angular houses"),
                ("house classification", "cadent houses"),
            ],
        )

    def test_never_emits_auto_relations(self) -> None:
        concepts = {
            "angular houses": _payload(
                concept="angular houses",
                definitions=["Angular houses: the strongest houses in the chart."],
                relationships=["Angular houses include the 1st, 10th, 7th, and 4th houses."],
                source_chunks=[7],
            )
        }

        taxonomy = infer_taxonomy_links(concepts)

        self.assertEqual(taxonomy["links"], [])

    def test_audit_explains_when_no_links_are_accepted(self) -> None:
        concepts = {
            "house system": _payload(
                concept="house system",
                definitions=[
                    "Predominator: The source of life force.",
                    "Sect: The chart polarity.",
                ],
                source_chunks=[6],
            ),
            "predominator": _payload(concept="predominator", source_chunks=[6]),
            "sect": _payload(concept="sect", source_chunks=[6]),
        }

        audit = infer_taxonomy_audit(concepts)

        self.assertEqual(audit["accepted_links"], [])
        self.assertEqual(
            [(item["parent"], item["child"], item["rejection_reason"]) for item in audit["rejected_candidates"]],
            [
                ("house system", "predominator", "parent_not_taxonomic"),
                ("house system", "sect", "parent_not_taxonomic"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
