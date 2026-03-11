from __future__ import annotations

import unittest

from src.argument_render import render_argument_block_input, render_argument_chunk_summary
from src.argument_schema import ArgumentChunkV1


def _chunk(**kwargs: object) -> ArgumentChunkV1:
    return ArgumentChunkV1(
        schema_version="1.0.0",
        chunk_id="c1",
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


class ArgumentRenderTests(unittest.TestCase):
    def test_render_keeps_fixed_section_order(self) -> None:
        rendered = render_argument_chunk_summary(
            _chunk(
                theses=["T1"],
                evidence=["E1"],
                authors_or_schools=["A1"],
                key_terms=["K1"],
            )
        )
        self.assertIn("TESIS\n- T1", rendered)
        self.assertLess(rendered.index("TESIS"), rendered.index("EVIDENCIA"))
        self.assertLess(rendered.index("EVIDENCIA"), rendered.index("AUTORES O ESCUELAS"))

    def test_render_omits_empty_sections(self) -> None:
        rendered = render_argument_chunk_summary(_chunk())
        self.assertEqual(rendered, "SIN ESTRUCTURA ARGUMENTAL CLARA")

    def test_block_input_renders_all_chunks(self) -> None:
        rendered = render_argument_block_input([_chunk(theses=["T1"]), _chunk(claims=["C1"])])
        self.assertEqual(len(rendered), 2)
        self.assertIn("TESIS", rendered[0])


if __name__ == "__main__":
    unittest.main()
