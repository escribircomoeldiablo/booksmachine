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
        self.assertEqual(frame["label"], "Aplicar profecciones")
        self.assertEqual(frame["anchor_concepts"], ["profection", "annual lord of year"])
        self.assertGreaterEqual(len(frame["shared_steps"]), 4)
        self.assertIn("Identificar el planeta que rige el signo profectado (el cronocrátor)", [step["text"] for step in frame["shared_steps"]])
        self.assertEqual(frame["procedure_outputs"], [{"text": "El cronocrátor que gobierna el periodo definido por la profección."}])

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
                "Si la luz de la secta está cadente, la predominancia puede pasar a la otra luminaria",
                "Si la Luna asciende por el este, la Luna es el predominador",
                "Si ambas luminarias declinan en casas cadentes, la predominancia pasa al Ascendente",
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

    def test_build_procedure_frames_localizes_ux_fields_to_spanish(self) -> None:
        concepts = {
            "profection": {
                "definitions": [],
                "technical_rules": [],
                "shared_procedure": [
                    {
                        "id": "step-1",
                        "order": 1,
                        "text": "Activate each zodiac sign individually in zodiacal order at a fixed rate (annually, monthly, or daily)",
                    },
                    {
                        "id": "step-2",
                        "order": 2,
                        "text": "Identify the planet that rules the profected sign (the time lord)",
                    },
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [
                    {"text": "Identification of the time lord who governs the native's life during the profection period"}
                ],
                "procedure_evidence": {"procedure_steps": [], "decision_rules": [], "preconditions": [], "exceptions": [], "author_variants": [], "procedure_outputs": []},
                "source_chunks": [1],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["apply_profections"]

        self.assertEqual(frame["label"], "Aplicar profecciones")
        self.assertEqual(
            frame["goal"],
            "Aplicar profecciones para determinar el cronocrátor y los temas activados durante el periodo profectado.",
        )
        self.assertEqual(
            [step["text"] for step in frame["shared_steps"]],
            [
                "Activar cada signo zodiacal individualmente en orden zodiacal a una cadencia fija (anual, mensual o diaria)",
                "Identificar el planeta que rige el signo profectado (el cronocrátor)",
            ],
        )
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "Identificación del cronocrátor que gobierna la vida del nativo durante el periodo profectado"}],
        )

    def test_build_procedure_frames_localizes_decision_rule_outcomes_and_technical_glossary(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [
                    {
                        "condition": "Sun in 1st, 10th, or 11th houses AND witnessed by bound lord within bounds",
                        "outcome": "Sun is Predominator",
                        "related_steps": [],
                    },
                    {
                        "condition": "the Sun or Moon is not suitable to be the predominator",
                        "outcome": "Default to Ascendant or occasionally Midheaven or a derivative light or authoritative planet",
                        "related_steps": [],
                    },
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
            "oikodespotes": {
                "shared_procedure": [],
                "decision_rules": [
                    {
                        "condition": "the bound lord of the Predominator is not witnessed by the Predominator or is located in the Descendant",
                        "outcome": "xiste Oikodespotes for the nativity according to Valens",
                        "related_steps": [],
                    },
                    {
                        "condition": "the domicile lord of the Predominator is used",
                        "outcome": "it becomes the Master of the Nativity",
                        "related_steps": [],
                    },
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
            "planet s own natural signification": {
                "definitions": [],
                "technical_rules": [],
                "shared_procedure": [
                    {"id": "step-3", "order": 1, "text": "Identify the planet's own natural significations"}
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [3],
                "related_concepts": ["planet"],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frames = build_procedure_frames(concepts)

        predominator = frames["determine_predominator"]
        self.assertEqual(
            predominator["decision_rules"][0]["outcome"],
            "El Sol es el predominador",
        )
        self.assertEqual(
            predominator["decision_rules"][1]["outcome"],
            "pasar al Ascendente o, ocasionalmente, al Medio Cielo o a una luminaria derivada o planeta con autoridad",
        )

        oikodespotes = frames["determine_oikodespotes"]
        self.assertEqual(
            oikodespotes["decision_rules"][0]["condition"],
            "el regente de límites del predominador no es testificado por el predominador o está ubicado en el Descendente",
        )
        self.assertEqual(
            oikodespotes["decision_rules"][0]["outcome"],
            "no existe oikodespotes para la natividad según Valente",
        )
        self.assertEqual(
            oikodespotes["decision_rules"][1]["outcome"],
            "se convierte en el oikodespotes",
        )

    def test_build_procedure_frames_localizes_variant_phrases_from_vol2_artifact(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "Both lights in cadent houses", "outcome": "Predomination defaults to Ascendant", "related_steps": []},
                    {"condition": "the sect light is cadent", "outcome": "Disqualify sect light; examine contrary sect light", "related_steps": []},
                    {"condition": "none of these qualify", "outcome": "There is no Predominator", "related_steps": []},
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
            "oikodespotes": {
                "shared_procedure": [],
                "decision_rules": [
                    {
                        "condition": "the oikodespotes is in aversion to the predominador (Valens & Paulus methods)",
                        "outcome": "Reject it as Oikodespotes or continue search for another candidate",
                        "related_steps": [],
                    },
                    {
                        "condition": "the planet is contrary to sect, detrimented, afflicted by malefics, or cadent",
                        "outcome": "Its benefic qualities and power are diminished as Oikodespotes",
                        "related_steps": [],
                    },
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

        frames = build_procedure_frames(concepts)

        predominator = frames["determine_predominator"]
        self.assertEqual(
            predominator["decision_rules"][0],
            {"condition": "Ambas luminarias en casas cadentes", "outcome": "La predominancia pasa al Ascendente", "related_steps": []},
        )
        self.assertEqual(
            predominator["decision_rules"][1]["outcome"],
            "Descartar la luz de la secta; examinar la luminaria contraria a la secta",
        )
        self.assertEqual(
            predominator["decision_rules"][2]["outcome"],
            "No hay predominador",
        )

        oikodespotes = frames["determine_oikodespotes"]
        self.assertEqual(
            oikodespotes["decision_rules"][0]["outcome"],
            "Rechazarlo como oikodespotes o continuar la búsqueda de otro candidato",
        )
        self.assertEqual(
            oikodespotes["decision_rules"][1]["condition"],
            "el planeta es contrario a la secta, está en detrimento, afligido por maléficos o cadente",
        )
        self.assertEqual(
            oikodespotes["decision_rules"][1]["outcome"],
            "Sus cualidades benéficas y su poder se ven disminuidos como oikodespotes",
        )

    def test_build_procedure_frames_creates_kurios_selection_frame(self) -> None:
        concepts = {
            "kurio": {
                "shared_procedure": [
                    {
                        "id": "step-1",
                        "order": 1,
                        "text": "Identify and list all candidates for the role of Kurios by evaluating the seven authoritative offices: Lord of the Ascendant, Planet in domicile and bounds of Ascendant, Lord of the Moon, Lord of the Midheaven, Lord of Fortune, Planet making heliacal rise/set/station within seven days of birth, and Bound lord of the Prenatal Lunation",
                    },
                    {
                        "id": "step-2",
                        "order": 2,
                        "text": "Evaluate each candidate according to: 1) greatest sympathy with the nativity; 2) placement in front; 3) being more eastern; 4) being more in its own familiar places (domicile, exaltation, triplicity, bounds); 5) greatest strength in relation to the figure of the nativity and co-witnessing by other planets",
                    },
                    {
                        "id": "step-3",
                        "order": 3,
                        "text": "Proclaim as Kurios the planet found to be most aligned by these criteria",
                    },
                ],
                "decision_rules": [
                    {
                        "condition": "a candidate planet is in a cadent house",
                        "outcome": "it is disqualified from being Kurios by most authorities",
                        "related_steps": [],
                    },
                    {
                        "condition": "all candidates are problematic",
                        "outcome": "Kurios may be a weak or ineffective leader",
                        "related_steps": [],
                    },
                ],
                "preconditions": [
                    {
                        "text": "Planets must hold one of the authoritative candidate positions (the seven offices) to qualify as potential Kurios.",
                        "scope": "entire Kurios selection procedure",
                        "related_steps": [],
                    }
                ],
                "exceptions": [],
                "author_variant_overrides": [
                    {
                        "author": "Porphyry",
                        "kind": "procedural variant",
                        "text": "Porphyry sets forth two different methods for Kurios determination: first emphasizes the lord or occupant of Midheaven or a planet approaching the Midheaven; second lists seven possible candidates then applies qualitative filters.",
                        "related_steps": [],
                        "operation": "annotate",
                    }
                ],
                "procedure_outputs": [
                    {"text": "Identification of the planetary Kurios, Lord of the Nativity."}
                ],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["midheaven", "lot of fortune"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "almuten": {
                "shared_procedure": [],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [
                    {
                        "author": "Later Medieval",
                        "kind": "criterion variant",
                        "text": "Later medieval astrologers would judge a planet for preeminence (almuten or victor) primarily on the strength of the number of zodiacal signs in which it had rulership (essential dignities).",
                        "related_steps": [],
                        "operation": "annotate",
                    }
                ],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": ["kurio"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["determine_kurios"]

        self.assertEqual(frame["frame_type"], "selection")
        self.assertEqual(frame["label"], "Determinar kurios")
        self.assertEqual(frame["anchor_concepts"], ["kurio"])
        self.assertIn("almuten", frame["supporting_concepts"])
        self.assertEqual(len(frame["candidate_priority_rules"]), 2)
        self.assertEqual(frame["fallback_rules"], [])
        self.assertIn(
            "Identificar y listar todos los candidatos al papel de kurios evaluando los siete cargos de autoridad: regente del Ascendente, planeta en domicilio y límites del Ascendente, regente de la Luna, regente del Medio Cielo, regente de la Fortuna, planeta con salida, puesta o estación helíaca dentro de los siete días del nacimiento, y regente de límites de la lunación prenatal",
            [step["text"] for step in frame["shared_steps"]],
        )
        self.assertEqual(
            frame["decision_rules"][0]["outcome"],
            "queda descalificado como kurios según la mayoría de las autoridades",
        )
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "Identificación del kurios planetario, regente de la natividad."}],
        )

    def test_build_procedure_frames_creates_lot_of_fortune_analysis_frame(self) -> None:
        concepts = {
            "lot of fortune": {
                "shared_procedure": [
                    {
                        "id": "step-1",
                        "order": 1,
                        "text": "Calculate the Lot of Fortune based on whether the chart is diurnal (Sun to Moon) or nocturnal (Moon to Sun)",
                    },
                    {
                        "id": "step-2",
                        "order": 2,
                        "text": "Locate the Lot of Fortune in the zodiac and determine its sign and house",
                    },
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [
                    {
                        "text": "Determination of the condition of the Lot of Fortune regarding material prosperity, bodily well-being, and periods of activity via zodiacal releasing."
                    }
                ],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": ["sect"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "fortune house": {
                "shared_procedure": [
                    {
                        "id": "step-3",
                        "order": 3,
                        "text": "Generate Fortune houses by making the sign/house containing the Lot of Fortune the first house and count the rest accordingly for specific inquiries",
                    }
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [3],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "releasing house": {
                "shared_procedure": [
                    {
                        "id": "step-4",
                        "order": 4,
                        "text": "Apply zodiacal releasing from the Lot of Fortune to analyze periods of life, noting when the releasing arrives at angular, succedent, or cadent Fortune houses",
                    }
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [4],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frame = build_procedure_frames(concepts)["analyze_lot_of_fortune"]

        self.assertEqual(frame["frame_type"], "analysis")
        self.assertEqual(frame["label"], "Analizar lote de la fortuna")
        self.assertEqual(frame["anchor_concepts"], ["lot of fortune"])
        self.assertEqual(set(frame["supporting_concepts"]), {"fortune house", "releasing house"})
        self.assertGreaterEqual(len(frame["shared_steps"]), 4)
        self.assertIn(
            "Calcular el Lote de la Fortuna según si la carta es diurna (del Sol a la Luna) o nocturna (de la Luna al Sol)",
            [step["text"] for step in frame["shared_steps"]],
        )
        self.assertIn(
            "Aplicar liberación zodiacal desde el Lote de la Fortuna para analizar periodos de vida, observando cuándo la liberación llega a casas de Fortuna angulares, sucedentes o cadentes",
            [step["text"] for step in frame["shared_steps"]],
        )
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "Determinación de la condición del Lote de la Fortuna respecto de la prosperidad material, el bienestar corporal y los periodos de actividad mediante liberación zodiacal."}],
        )

    def test_build_procedure_frames_creates_sect_light_selection_frame(self) -> None:
        concepts = {
            "sect light": {
                "shared_procedure": [
                    {"id": "step-1", "order": 1, "text": "Identify the sect light: Sun by day, Moon by night"},
                    {"id": "step-2", "order": 2, "text": "Check if the sect light is located in a valid house (per author: angular/succedent, releasing house, or specific list)"},
                    {"id": "step-3", "order": 3, "text": "If the sect light is not eligible, examine the contrary light"},
                ],
                "decision_rules": [
                    {"condition": "the sect light is located in an authoritative/releasing house", "outcome": "That body is the Predominator", "related_steps": []},
                    {"condition": "the sect light is not eligible, but the other light is in a valid house", "outcome": "The other light is chosen as Predominator", "related_steps": []},
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["predominator"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "sect": {
                "shared_procedure": [],
                "decision_rules": [
                    {"condition": "the sect light is cadent", "outcome": "predomination may go to the other light if it satisfies the criteria", "related_steps": []}
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [{"text": "Identification of the Predominator: Sun, Moon, or Ascendant as qualified by house, sect, and direction."}],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frame = build_procedure_frames(concepts)["assess_sect_light"]

        self.assertEqual(frame["frame_type"], "selection")
        self.assertEqual(frame["label"], "Evaluar luz de la secta")
        self.assertEqual(frame["anchor_concepts"], ["sect light", "sect"])
        self.assertGreaterEqual(len(frame["shared_steps"]), 2)
        self.assertEqual(len(frame["decision_rules"]), 3)
        self.assertIn(
            "Identificar la luz de la secta: Sol de día, Luna de noche",
            [step["text"] for step in frame["shared_steps"]],
        )
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "Identificación del predominador: Sol, Luna o Ascendente según casa, secta y dirección."}],
        )

    def test_build_procedure_frames_creates_derived_houses_analysis_frame(self) -> None:
        concepts = {
            "derived houses": {
                "shared_procedure": [
                    {"id": "step-1", "order": 1, "text": "Count forward (in zodiacal order) from the reference house to reach the derived house"},
                    {"id": "step-2", "order": 2, "text": "Interpret the condition, planets, and aspects in the derived house for the question at hand"},
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [{"text": "Identification of the derived house and its condition pertaining to the person or topic in question."}],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["lot of fortune"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["derive_houses"]

        self.assertEqual(frame["frame_type"], "analysis")
        self.assertEqual(frame["label"], "Derivar casas")
        self.assertEqual(frame["anchor_concepts"], ["derived houses"])
        self.assertEqual(
            [step["text"] for step in frame["shared_steps"]],
            [
                "Contar hacia adelante (en orden zodiacal) desde la casa de referencia hasta llegar a la casa derivada",
                "Interpretar la condición, los planetas y los aspectos en la casa derivada para la cuestión planteada",
            ],
        )
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "Identificación de la casa derivada y de su condición en relación con la persona o asunto consultado."}],
        )

    def test_build_procedure_frames_creates_aversion_analysis_frame(self) -> None:
        concepts = {
            "aversion": {
                "shared_procedure": [
                    {
                        "id": "step-1",
                        "order": 1,
                        "text": "Check if the lord is in a house configured by whole-sign aspect to the Ascendant (houses 3, 4, 5, 7, 9, 10, 11) or in aversion (houses 2, 6, 8, 12)",
                    }
                ],
                "decision_rules": [
                    {
                        "condition": "lord is in house in aversion",
                        "outcome": "Steering is difficult; path moves through challenging topics.",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["ascendant"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["assess_aversion"]

        self.assertEqual(frame["frame_type"], "analysis")
        self.assertEqual(frame["label"], "Evaluar aversión")
        self.assertEqual(frame["anchor_concepts"], ["aversion"])
        self.assertEqual(
            frame["shared_steps"][0]["text"],
            "Verificar si el regente está en una casa configurada por aspecto de signo entero al Ascendente (casas 3, 4, 5, 7, 9, 10, 11) o en aversión (casas 2, 6, 8, 12)",
        )
        self.assertEqual(
            frame["decision_rules"][0]["outcome"],
            "La conducción se dificulta; el camino transcurre por temas desafiantes.",
        )

    def test_build_procedure_frames_creates_domicile_lord_of_ascendant_evaluation_frame(self) -> None:
        concepts = {
            "domicile lord of ascendant": {
                "shared_procedure": [],
                "decision_rules": [
                    {
                        "condition": "domicile lord of Ascendant is in the first house and in good condition",
                        "outcome": "Native is strong, self-steering, with full power to direct life.",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": ["ascendant"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["evaluate_domicile_lord_of_ascendant"]

        self.assertEqual(frame["frame_type"], "evaluation")
        self.assertEqual(frame["label"], "Evaluar regente domiciliario del ascendente")
        self.assertEqual(frame["anchor_concepts"], ["domicile lord of ascendant"])
        self.assertEqual(
            frame["decision_rules"][0]["outcome"],
            "El nativo es fuerte, se gobierna a sí mismo y posee plena capacidad para dirigir su vida.",
        )

    def test_build_procedure_frames_creates_apheta_hyleg_selection_frame(self) -> None:
        concepts = {
            "predominator apheta hyleg": {
                "shared_procedure": [],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [
                    {
                        "text": "The identification of the Predominator (Apheta/Hyleg) for purposes of assigning the Oikodespotes and for further longevity calculation."
                    }
                ],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [3],
                "related_concepts": ["oikodespotes"],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frame = build_procedure_frames(concepts)["identify_apheta_hyleg"]

        self.assertEqual(frame["frame_type"], "selection")
        self.assertEqual(frame["label"], "Identificar apheta hyleg")
        self.assertEqual(frame["anchor_concepts"], ["predominator apheta hyleg"])
        self.assertEqual(
            frame["procedure_outputs"],
            [{"text": "La identificación del predominador (apheta/hyleg) para asignar el oikodespotes y continuar el cálculo de longevidad."}],
        )

    def test_build_procedure_frames_hybrid_mode_autogenerates_uncovered_procedures(self) -> None:
        concepts = {
            "equal house system": {
                "definitions": ["Equal house system: each house spans 30 degrees from the Ascendant degree."],
                "technical_rules": [],
                "shared_procedure": [
                    {
                        "id": "step-1",
                        "order": 1,
                        "text": "For equal house system: Mark the degree of the Ascendant as the start of the first house; from there, each successive house is marked every 30° at the same degree in the following sign",
                    }
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": ["ascendant"],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "profection": {
                "definitions": [],
                "technical_rules": [],
                "shared_procedure": [
                    {"id": "step-2", "order": 1, "text": "Select the type of profection (annual, monthly, daily) according to the timing interval required"}
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [{"text": "The time lord who governs the period defined by the profection."}],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [2],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            },
            "planet s own natural signification": {
                "definitions": [],
                "technical_rules": [],
                "shared_procedure": [
                    {"id": "step-3", "order": 1, "text": "Identify the planet's own natural significations"}
                ],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [3],
                "related_concepts": ["planet"],
                "parent_concepts": [],
                "child_concepts": [],
            },
        }

        frames = build_procedure_frames(concepts)

        self.assertIn("apply_profections", frames)
        self.assertIn("auto_equal_house_system", frames)
        auto_frame = frames["auto_equal_house_system"]
        self.assertEqual(auto_frame["anchor_concepts"], ["equal house system"])
        self.assertEqual(auto_frame["frame_type"], "analysis")
        self.assertEqual(auto_frame["label"], "Sistema de casas iguales")
        self.assertEqual(auto_frame["goal"], "Analizar el procedimiento asociado con sistema de casas iguales.")
        self.assertEqual(
            auto_frame["shared_steps"],
            [
                {
                    "id": "step-1",
                    "order": 1,
                    "text": "Para el sistema de casas iguales: marcar el grado del Ascendente como inicio de la primera casa; desde allí, cada casa sucesiva se marca cada 30° en el mismo grado del signo siguiente",
                }
            ],
        )
        auto_signification = frames["auto_planet_s_own_natural_signification"]
        self.assertEqual(auto_signification["frame_type"], "analysis")
        self.assertEqual(auto_signification["label"], "Significación natural propia del planeta")
        self.assertEqual(
            auto_signification["goal"],
            "Analizar el procedimiento asociado con significación natural propia del planeta.",
        )
        self.assertEqual(
            auto_signification["shared_steps"][0]["text"],
            "Identificar las significaciones naturales propias del planeta",
        )

    def test_build_procedure_frames_hybrid_mode_does_not_duplicate_curated_anchors(self) -> None:
        concepts = {
            "predominator": {
                "shared_procedure": [],
                "decision_rules": [{"condition": "the sect light is cadent", "outcome": "examine the contrary light", "related_steps": []}],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "procedure_evidence": {"decision_rules": []},
                "source_chunks": [1],
                "related_concepts": [],
                "parent_concepts": [],
                "child_concepts": [],
            }
        }

        frames = build_procedure_frames(concepts)

        self.assertIn("determine_predominator", frames)
        self.assertNotIn("auto_predominator", frames)


if __name__ == "__main__":
    unittest.main()
