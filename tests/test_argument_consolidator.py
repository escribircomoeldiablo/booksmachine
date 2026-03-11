from __future__ import annotations

import unittest

from src.argument_consolidator import build_argument_map
from src.argument_schema import ArgumentChunkV1


def _chunk(**kwargs: object) -> ArgumentChunkV1:
    return ArgumentChunkV1(
        schema_version="1.0.0",
        chunk_id=str(kwargs.get("chunk_id", "c1")),
        source_fingerprint="book",
        section_refs=[],
        theses=list(kwargs.get("theses", [])),
        claims=list(kwargs.get("claims", [])),
        evidence=list(kwargs.get("evidence", [])),
        methods=list(kwargs.get("methods", [])),
        authors_or_schools=list(kwargs.get("authors_or_schools", [])),
        key_terms=list(kwargs.get("key_terms", [])),
        debates=list(kwargs.get("debates", [])),
        limitations=list(kwargs.get("limitations", [])),
    )


class ArgumentConsolidatorTests(unittest.TestCase):
    def test_build_argument_map_dedupes_and_preserves_first_surface(self) -> None:
        payload = build_argument_map(
            [
                _chunk(theses=["State formation"], claims=["Claim A"]),
                _chunk(theses=["  state   formation  "], claims=["claim a"], chunk_id="c2"),
            ],
            source_title="Book",
            audit_rows=[{"decision": "ok"}, {"decision": "empty_legitimate"}],
        )

        self.assertEqual(payload["source_title"], "Book")
        self.assertEqual(payload["map_schema_version"], "1.0.0")
        self.assertEqual(payload["chunk_schema_version"], "1.0.0")
        self.assertEqual(payload["primary_theses"], ["State formation"])
        self.assertEqual(payload["recurring_claims"], ["Claim A"])
        self.assertEqual(payload["source_coverage"]["empty_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
