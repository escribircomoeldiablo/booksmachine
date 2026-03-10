from __future__ import annotations

import unittest

from src.procedure_frame_builder import build_procedure_frames


class ProcedureFrameBuilderTests(unittest.TestCase):
    def test_build_procedure_frames_creates_timing_frame_for_profections(self) -> None:
        concepts = {
            "profection": {
                "definitions": [
                    "profections: A symbolic timing procedure in which each sign is individually activated, in zodiacal order, at a fixed rate. The matters of the house occupied by the profected sign are emphasized for that period of time, and the planet that rules the profected sign (the time lord) influences the outcome of the house's matters."
                ],
                "technical_rules": [
                    "In profections, the time lord governs the life for the duration of the profection.",
                    "During the period of a profection, the time lord has the opportunity to bring about its significations as indicated in the natal chart.",
                ],
                "shared_procedure": [
                    {
                        "id": "step-001-select-profection-type",
                        "order": 1,
                        "text": "Select the type of profection (annual, monthly, daily) according to the timing interval required",
                    }
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [{"text": "The time lord who governs the period defined by the profection."}],
                "procedure_evidence": {"procedure_steps": [], "decision_rules": [], "preconditions": [], "exceptions": [], "author_variants": [], "procedure_outputs": []},
                "source_chunks": [6],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "annual lord of year": {
                "definitions": ["annual lord of the year: A planet that assumes governance of the chart for the duration of one year based upon a time-lord procedure."],
                "shared_procedure": [],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"procedure_steps": [], "decision_rules": [], "preconditions": [], "exceptions": [], "author_variants": [], "procedure_outputs": []},
                "source_chunks": [1],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frame = build_procedure_frames(concepts)["apply_profections"]

        self.assertEqual(frame["frame_type"], "timing")
        self.assertEqual(frame["anchor_concepts"], ["profection", "annual lord of year"])
        self.assertGreaterEqual(len(frame["shared_steps"]), 4)
        self.assertIn("Identify the planet that rules the profected sign (the time lord)", [step["text"] for step in frame["shared_steps"]])
        self.assertEqual(frame["procedure_outputs"], [{"text": "The time lord who governs the period defined by the profection."}])

    def test_build_procedure_frames_clusters_predominator_supporting_concepts(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [{"condition": "the sect light is cadent", "outcome": "examine the contrary light", "related_steps": []}],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": [{"chunk_index": 1, "value": "r1"}]},
                "source_chunks": [1],
                "related_concepts": ["house system"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "predomination of sect light": {
                "shared_procedure": [{"id": "step-1", "order": 1, "text": "Evaluate the sect light first"}],
                "decision_rules": [{"condition": "the sect light is cadent", "outcome": "turn to the contrary light", "related_steps": []}],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"procedure_steps": [{"chunk_index": 2, "value": "s1"}], "decision_rules": []},
                "source_chunks": [2],
                "related_concepts": ["sect"],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frames = build_procedure_frames(concepts)

        self.assertIn("determine_predominator", frames)
        frame = frames["determine_predominator"]
        self.assertEqual(frame["frame_type"], "selection")
        self.assertEqual(frame["anchor_concepts"], ["predominator"])
        self.assertIn("predomination of sect light", frame["supporting_concepts"])
        self.assertGreaterEqual(len(frame["shared_steps"]), 2)
        self.assertEqual(len(frame["decision_rules"]), 2)
        self.assertEqual(len(frame["candidate_priority_rules"]), 0)
        self.assertEqual(len(frame["fallback_rules"]), 2)

    def test_build_procedure_frames_unifies_master_of_nativity_with_oikodespotes_selection(self) -> None:
        concepts = {
            "oikodespotes": {
                "shared_procedure": [],
                "decision_rules": [{"condition": "the bound lord witnesses the Predominator", "outcome": "it qualifies as Oikodespotes", "related_steps": []}],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [
                    {"author": "Valens", "kind": "method", "text": "Valens assigns the Oikodespotes from the bound lord of the Predominator.", "related_steps": [], "operation": "annotate"}
                ],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["predominator"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "master of the nativity": {
                "shared_procedure": [],
                "decision_rules": [{"condition": "the domicile lord of the Predominator is used", "outcome": "it becomes the Master of the Nativity", "related_steps": []}],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [
                    {"author": "Porphyry", "kind": "assignment of master", "text": "Porphyry assigns the domicile lord of the Predominator as Master of the Nativity.", "related_steps": [], "operation": "annotate"}
                ],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": ["predominator"],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frames = build_procedure_frames(concepts)

        self.assertIn("determine_oikodespotes", frames)
        self.assertNotIn("determine_master_of_the_nativity", frames)
        frame = frames["determine_oikodespotes"]
        self.assertEqual(frame["frame_type"], "selection")
        self.assertEqual(frame["anchor_concepts"], ["oikodespotes", "master of the nativity"])
        self.assertEqual(len(frame["author_method_variants"]), 2)
        self.assertGreaterEqual(len(frame["decision_rules"]), 2)
        self.assertGreaterEqual(len(frame["candidate_priority_rules"]), 2)

    def test_build_procedure_frames_splits_oikodespotes_selection_from_evaluation(self) -> None:
        concepts = {
            "oikodespotes": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "the Oikodespotes is the domicile lord of the Predominator", "outcome": "it is selected as master", "related_steps": []},
                    {"condition": "Oikodespotes meets these conditions", "outcome": "it gives good character in accordance with its nature", "related_steps": []},
                ],
                "technical_rules": [
                    "In delineation, consider if the Oikodespotes belongs to the sect of the chart, is in its own domiciles or exaltation, is in angular or succedent houses, or is rising.",
                    "When Saturn is the Master of the Nativity and is effective by day in its own domiciles, it produces good effects.",
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [
                    {"author": "Porphyry", "kind": "method", "text": "Porphyry assigns the domicile lord of the Predominator as Oikodespotes.", "related_steps": [], "operation": "annotate"},
                    {"author": "Petosiris", "kind": "interpretive", "text": "The Oikodespotes reveals character and bodily constitution.", "related_steps": [], "operation": "annotate"},
                ],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["predominator"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frames = build_procedure_frames(concepts)

        selection = frames["determine_oikodespotes"]
        evaluation = frames["evaluate_oikodespotes"]
        self.assertEqual(len(selection["decision_rules"]), 1)
        self.assertIn("selected as master", selection["decision_rules"][0]["outcome"])
        self.assertEqual(len(selection["author_method_variants"]), 1)
        self.assertEqual(len(selection["candidate_priority_rules"]), 1)
        self.assertGreaterEqual(len(evaluation["decision_rules"]), 2)
        self.assertIn("good character", evaluation["decision_rules"][0]["outcome"])
        self.assertGreaterEqual(len(evaluation["preconditions"]), 1)
        self.assertEqual(len(evaluation["author_variant_overrides"]), 1)

    def test_build_procedure_frames_dedupes_and_filters_broken_rules(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "If the Moon is ascending in the east", "outcome": "the Moon will be the Predominator", "related_steps": []},
                    {"condition": "the Moon is ascending in the east", "outcome": "the Moon is the Predominator", "related_steps": []},
                    {"condition": "both the Sun and Moon are declining westward (e.g.", "outcome": "in the cadent ninth house), the Ascendant will have the predomination", "related_steps": []},
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "predomination": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "the light of the sect is cadent", "outcome": "predomination might go to the other light", "related_steps": []},
                    {"condition": "both lights are declining in cadent houses", "outcome": "predomination goes to the Ascendant", "related_steps": []},
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frame = build_procedure_frames(concepts)["determine_predominator"]

        self.assertEqual(len(frame["decision_rules"]), 3)
        self.assertEqual(len(frame["candidate_priority_rules"]), 1)
        self.assertEqual(len(frame["fallback_rules"]), 2)
        self.assertEqual(
            [step["text"] for step in frame["shared_steps"]],
            [
                "If the light of the sect is cadent, then predomination might go to the other light",
                "If the Moon is ascending in the east, then the Moon will be the Predominator",
                "If both lights are declining in cadent houses, then predomination goes to the Ascendant",
            ],
        )

    def test_build_procedure_frames_moves_selection_notes_out_of_core(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "the Moon is ascending in the east", "outcome": "the Moon is the Predominator", "related_steps": []},
                    {"condition": "both lights are declining in cadent houses", "outcome": "predomination goes to the Ascendant", "related_steps": []},
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [
                    {"author": "Porphyry", "kind": "house system usage", "text": "does not specify any particular house system, so may have used whole signs for determining the Predominator", "related_steps": [], "operation": "annotate"}
                ],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["house system"],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frame = build_procedure_frames(concepts)["determine_predominator"]

        self.assertEqual(len(frame["methodological_notes"]), 1)
        self.assertEqual(len(frame["author_variant_overrides"]), 0)


if __name__ == "__main__":
    unittest.main()
