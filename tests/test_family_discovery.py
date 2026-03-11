from __future__ import annotations

import unittest

from src.family_discovery import (
    build_family_discovery_prompt,
    discover_family_candidates,
    parse_family_discovery_response,
)


class FamilyDiscoveryTests(unittest.TestCase):
    def test_parse_family_discovery_response_accepts_json_fenced_block(self) -> None:
        raw = """```json
        {
          "candidate_families": [
            {
              "family_label": "time lord techniques",
              "members": ["profection", "decennial", "annual lord of year"],
              "rationale": "Timing doctrines."
            }
          ],
          "left_unclustered": ["angle"]
        }
        ```"""

        payload = parse_family_discovery_response(raw)

        self.assertEqual(payload["candidate_families"][0]["family_label"], "time lord techniques")
        self.assertEqual(
            payload["candidate_families"][0]["members"],
            ["profection", "decennial", "annual lord of year"],
        )
        self.assertEqual(payload["left_unclustered"], ["angle"])

    def test_build_family_discovery_prompt_includes_only_requested_unassigned_context(self) -> None:
        concepts = {
            "profection": {
                "concept": "profection",
                "definitions": ["A timing technique."],
                "terminology": ["Profection"],
                "relationships": [],
                "source_chunks": [1],
            },
            "angle": {
                "concept": "angle",
                "definitions": ["A basic concept."],
                "terminology": ["Angle"],
                "relationships": [],
                "source_chunks": [2],
            },
        }

        prompt = build_family_discovery_prompt(
            concepts=concepts,
            unassigned_concepts=["profection"],
            prompt_template='Input:\n{{INPUT_JSON}}',
        )

        self.assertIn("profection", prompt)
        self.assertNotIn('"angle"', prompt)

    def test_discover_family_candidates_returns_raw_llm_clusters_without_losing_members(self) -> None:
        concepts = {
            "profection": {"concept": "profection", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "decennial": {"concept": "decennial", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "annual lord of year": {"concept": "annual lord of year", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
        }
        family_payload = {"unassigned_concepts": ["profection", "decennial", "annual lord of year"]}

        def _fake_llm(_: str) -> str:
            return """
            {
              "candidate_families": [
                {
                  "family_label": "time lord techniques",
                  "members": ["profection", "decennial", "annual lord of year"],
                  "rationale": "Timing techniques."
                }
              ],
              "left_unclustered": []
            }
            """

        payload = discover_family_candidates(concepts=concepts, family_payload=family_payload, llm_callable=_fake_llm)

        self.assertIsNone(payload["discovery_error"])
        self.assertEqual(
            payload["candidate_families"][0]["members"],
            ["profection", "decennial", "annual lord of year"],
        )

    def test_discover_family_candidates_falls_back_to_deterministic_clusters_when_llm_fails(self) -> None:
        concepts = {
            "aries": {"concept": "aries", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "cancer": {"concept": "cancer", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "aquarius": {"concept": "aquarius", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "ascensional time": {"concept": "ascensional time", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "pre ascension": {"concept": "pre ascension", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "post ascension": {"concept": "post ascension", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "house place": {"concept": "house place", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "topic of house": {"concept": "topic of house", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
            "favorability": {"concept": "favorability", "definitions": [], "terminology": [], "relationships": [], "source_chunks": []},
        }
        family_payload = {
            "unassigned_concepts": [
                "aries",
                "cancer",
                "aquarius",
                "ascensional time",
                "pre ascension",
                "post ascension",
                "house place",
                "topic of house",
                "favorability",
            ]
        }

        def _failing_llm(_: str) -> str:
            raise RuntimeError("OpenAI SDK is not installed.")

        payload = discover_family_candidates(concepts=concepts, family_payload=family_payload, llm_callable=_failing_llm)

        self.assertEqual(
            payload["candidate_families"],
            [
                {
                    "family_label": "zodiac signs",
                    "members": ["aries", "cancer", "aquarius"],
                    "rationale": "Canonical zodiac sign concepts left outside the current family catalog.",
                },
                {
                    "family_label": "ascensional measures",
                    "members": ["ascensional time", "pre ascension", "post ascension"],
                    "rationale": "Ascensional calculations and measures that belong to the same technical cluster.",
                },
                {
                    "family_label": "house interpretive criteria",
                    "members": ["house place", "topic of house", "favorability"],
                    "rationale": "Interpretive criteria used to determine what a house signifies and how strongly it functions.",
                },
            ],
        )
        self.assertEqual(payload["left_unclustered"], [])
        self.assertEqual(payload["discovery_error"], "OpenAI SDK is not installed.")

    def test_parse_family_discovery_response_escapes_raw_control_characters_inside_strings(self) -> None:
        raw = '{\n  "candidate_families": [\n    {\n      "family_label": "time lord techniques",\n      "members": ["profection", "decennial"],\n      "rationale": "Line one\nLine two"\n    }\n  ],\n  "left_unclustered": []\n}'

        payload = parse_family_discovery_response(raw)

        self.assertEqual(payload["candidate_families"][0]["family_label"], "time lord techniques")
        self.assertEqual(payload["candidate_families"][0]["members"], ["profection", "decennial"])
        self.assertEqual(payload["candidate_families"][0]["rationale"], "Line one\nLine two")


if __name__ == "__main__":
    unittest.main()
