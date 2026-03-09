from __future__ import annotations

import unittest

from src.knowledge_precheck import (
    DECISION_EXTRACT,
    DECISION_EXTRACT_DEGRADED,
    DECISION_SKIP,
    MIXED,
    precheck_chunk_extractability,
)
from src.knowledge_schema import SectionRef


class KnowledgePrecheckTests(unittest.TestCase):
    def test_blank_or_very_short_chunk_is_skip(self) -> None:
        result = precheck_chunk_extractability(
            chunk_text="A",
            section_refs=[SectionRef(label="A", type="unknown", start_char=0, end_char=1)],
        )

        self.assertEqual(result.decision, DECISION_SKIP)
        self.assertIn("very_short", result.reason_codes)

    def test_noisy_chunk_is_extract_degraded(self) -> None:
        noisy = (
            "1 Ptolemy 3.2 source note for comparison\n"
            "2 Valens 2.1 secondary witness and cross reference\n"
            "3 Sahl 1.47 contested locator with edition variance\n"
            "4 Manilius 2.939-48 citation chain with page locator\n"
        )
        result = precheck_chunk_extractability(
            chunk_text=noisy,
            section_refs=[SectionRef(label="225-232.", type="unknown", start_char=0, end_char=50)],
            review_default="extract",
        )

        self.assertEqual(result.decision, DECISION_EXTRACT_DEGRADED)

    def test_hard_contaminated_chunk_is_skip(self) -> None:
        noisy = "^£09 ^£09 ^£09\n1 Ptolemy 3.2\n2 Valens 2.1\n3 Sahl 1.47\n4 Manilius 2.939-48\n"
        result = precheck_chunk_extractability(
            chunk_text=noisy,
            section_refs=[SectionRef(label="225-232.", type="unknown", start_char=0, end_char=50)],
        )

        self.assertEqual(result.decision, DECISION_SKIP)

    def test_clean_doctrinal_chunk_is_extract(self) -> None:
        text = (
            "When the ruler of the Ascendant is angular, prefer that testimony over cadent "
            "placements. Evaluate dignity before accidental factors and then integrate witnesses."
        )
        result = precheck_chunk_extractability(
            chunk_text=text,
            section_refs=[SectionRef(label="Interpretive Criteria", type="section", start_char=0, end_char=170)],
        )

        self.assertEqual(result.decision, DECISION_EXTRACT)

    def test_mixed_requires_two_incompatible_strong_types(self) -> None:
        text = (
            "Exercise 10: Evaluate chart outcomes.\n"
            "Rule: assess the lord first.\n"
            "Interpretive doctrine remains central and paragraph-based explanation follows in detail."
        )
        result = precheck_chunk_extractability(
            chunk_text=text,
            section_refs=[SectionRef(label="Exercise and Commentary", type="section", start_char=0, end_char=140)],
        )
        if result.chunk_type == MIXED:
            self.assertEqual(result.decision, DECISION_EXTRACT_DEGRADED)


if __name__ == "__main__":
    unittest.main()
