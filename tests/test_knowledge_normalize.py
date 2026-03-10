from __future__ import annotations

import unittest

from src.knowledge_normalize import (
    apply_post_extraction_clamp,
    apply_semantic_local_filter,
    normalize_chunk_knowledge,
    merge_chunk_knowledge_records,
)
from src.knowledge_schema import ChunkKnowledgeV1


def _record() -> ChunkKnowledgeV1:
    return ChunkKnowledgeV1(
        schema_version="1.0.0",
        chunk_id="c1",
        source_fingerprint="fp",
        concepts=["c1", "c2", "c3", "c4", "c5"],
        definitions=["d1"],
        technical_rules=["r1"],
        procedures=["p1"],
        terminology=["t1", "t2", "t3", "t4"],
        relationships=["rel1"],
        examples=["e1", "e2", "e3"],
        ambiguities=["amb1", "amb2", "amb3"],
    )


class KnowledgeNormalizeClampTests(unittest.TestCase):
    def test_low_profile_clears_high_risk_core_fields(self) -> None:
        record, actions = apply_post_extraction_clamp(
            _record(),
            confidence_profile="low",
            decision="extract_degraded",
            chunk_type="bibliography",
            chunk_text="References list without doctrinal body.",
        )
        self.assertEqual(record.definitions, [])
        self.assertEqual(record.technical_rules, [])
        self.assertEqual(record.procedures, [])
        self.assertEqual(record.relationships, [])
        self.assertIn("clear_definitions", actions)

    def test_contaminated_keeps_ambiguities_only_with_evidence(self) -> None:
        record = _record()
        record, _ = apply_post_extraction_clamp(
            record,
            confidence_profile="contaminated",
            decision="skip",
            chunk_type="captions_tables_charts",
            chunk_text="Plain caption text without doctrinal claims.",
        )
        self.assertEqual(record.ambiguities, [])

    def test_weak_support_pattern_caps_concepts_and_clears_ambiguities(self) -> None:
        record = _record()
        record.definitions = []
        record.technical_rules = []
        record.procedures = []
        record, actions = apply_post_extraction_clamp(
            record,
            confidence_profile="medium",
            decision="extract_degraded",
            chunk_type="doctrinal_text",
            chunk_text="Heading-style text with loose terms only.",
            weak_support_pattern=True,
            weak_support_concepts_max=2,
            weak_support_terminology_max=1,
        )
        self.assertEqual(record.concepts, ["c1", "c2"])
        self.assertEqual(record.terminology, ["t1"])
        self.assertEqual(record.ambiguities, [])
        self.assertIn("cap_concepts_2_weak_support", actions)
        self.assertTrue(
            "clear_ambiguities_weak_support" in actions or "clear_ambiguities_no_evidence" in actions
        )

    def test_semantic_filter_removes_editorial_rules(self) -> None:
        record = _record()
        record.technical_rules = ["All rights reserved.", "If Mars is angular, it is stronger."]
        record.procedures = ["Permission required to reproduce.", "Evaluate the ruler and condition."]
        record, actions = apply_semantic_local_filter(
            record,
            filter_editorial=True,
            filter_generic_definitions=False,
            filter_modern=False,
        )
        self.assertEqual(record.technical_rules, ["If Mars is angular, it is stronger."])
        self.assertEqual(record.procedures, ["Evaluate the ruler and condition."])
        self.assertIn("clear_editorial_technical_rules", actions)
        self.assertIn("clear_editorial_procedures", actions)

    def test_semantic_filter_drops_generic_definitions(self) -> None:
        record = _record()
        record.definitions = [
            "Ascendant: the rising sign.",
            "House strength: when a planet is angular, its effects are stronger.",
        ]
        record, actions = apply_semantic_local_filter(
            record,
            filter_editorial=False,
            filter_generic_definitions=True,
            filter_modern=False,
        )
        self.assertEqual(
            record.definitions,
            ["House strength: when a planet is angular, its effects are stronger."],
        )
        self.assertIn("drop_generic_definitions", actions)

    def test_semantic_filter_relocates_separable_modern_items(self) -> None:
        record = _record()
        record.concepts = ["Modern psychological self-image and identity development."]
        record, actions = apply_semantic_local_filter(
            record,
            filter_editorial=False,
            filter_generic_definitions=False,
            filter_modern=True,
        )
        self.assertEqual(record.concepts, [])
        self.assertIn("Modern psychological self-image and identity development.", record.ambiguities)
        self.assertIn("relocate_modern_concepts", actions)

    def test_semantic_filter_preserves_embedded_modern_traditional_core(self) -> None:
        record = _record()
        record.concepts = ["Modern reinterpretation of the house while preserving traditional sect doctrine."]
        record, actions = apply_semantic_local_filter(
            record,
            filter_editorial=False,
            filter_generic_definitions=False,
            filter_modern=True,
        )
        self.assertEqual(
            record.concepts,
            ["Modern reinterpretation of the house while preserving traditional sect doctrine."],
        )
        self.assertIn("mark_modern_embedded_preserved_core", actions)

    def test_merge_chunk_knowledge_records_builds_canonical_concept_index(self) -> None:
        r1 = _record()
        r1.concepts = ["Whole-sign houses", "Angular Houses"]
        r2 = _record()
        r2.concepts = ["Whole sign house system", "Succedent houses", "angular house"]

        merged = merge_chunk_knowledge_records([r1, r2])
        self.assertEqual(merged["schema_version"], "merge_v1")
        concept_index = merged["concept_index"]
        self.assertIn("whole sign house system", concept_index)
        self.assertEqual(concept_index["whole sign house system"], [1, 2])
        self.assertEqual(concept_index["angular house"], [1, 2])
        self.assertEqual(concept_index["succedent house"], [2])

    def test_normalize_chunk_knowledge_promotes_conditional_rules_to_decision_rules(self) -> None:
        record = _record()
        record.technical_rules = [
            "If the sect light is cadent, then the Predomination may pass to the other light.",
            "General background rule.",
        ]

        normalized = normalize_chunk_knowledge(record)

        self.assertEqual(
            [(item.condition, item.outcome) for item in normalized.decision_rules],
            [("the sect light is cadent", "the Predomination may pass to the other light")],
        )
        self.assertEqual(normalized.technical_rules, ["General background rule."])

    def test_normalize_chunk_knowledge_promotes_linear_procedure_to_steps(self) -> None:
        record = _record()
        record.procedure_steps = []
        record.procedures = [
            "To use profections: activate each zodiacal sign in order at a fixed rate, identify the time lord as the ruler of the profected sign, and interpret the matters of the house occupied by the profected sign during the period."
        ]

        normalized = normalize_chunk_knowledge(record)

        self.assertEqual(
            [item.text for item in normalized.procedure_steps],
            [
                "activate each zodiacal sign in order at a fixed rate",
                "identify the time lord as the ruler of the profected sign",
                "interpret the matters of the house occupied by the profected sign during the period",
            ],
        )


if __name__ == "__main__":
    unittest.main()
