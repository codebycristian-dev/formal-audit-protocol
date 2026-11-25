"""Tests for the phase plan: structure, drift detection, answer validation, prompts."""

import shutil
import tempfile
import unittest
from pathlib import Path

from fap.phases import (
    PHASE_PLAN,
    phase_by_id,
    render_prompt,
    section_text,
    validate_answer,
    verify_phase_plan,
)
from fap.protocol import ProtocolDriftError, compile_protocol

from .fixtures import SPEC, answer_for


class PlanMatchesSpecification(unittest.TestCase):
    def setUp(self):
        self.model = compile_protocol(SPEC)

    def test_every_mandatory_slot_has_a_phase(self):
        self.assertTrue(set(self.model.slot_ids()) <= {phase.id for phase in PHASE_PLAN})

    def test_every_phase_section_exists_in_the_specification(self):
        for phase in PHASE_PLAN:
            self.assertTrue(section_text(self.model, phase.section).strip(), phase.id)

    def test_verification_passes_on_the_repository_specification(self):
        verify_phase_plan(self.model)

    def test_phase_documents_are_the_audited_set(self):
        documents = {phase.document for phase in PHASE_PLAN if phase.document}
        self.assertEqual(documents, set(self.model.documents))

    def test_phase_ids_are_unique(self):
        ids = [phase.id for phase in PHASE_PLAN]
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_phase_names_the_alternatives(self):
        with self.assertRaises(KeyError) as caught:
            phase_by_id("Z.9")
        self.assertIn("A.1", str(caught.exception))


class Drift(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.spec = Path(self._tmp.name) / "spec.md"
        shutil.copy(SPEC, self.spec)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_anchor_is_detected(self):
        self.spec.write_text(
            self.spec.read_text().replace("Boundary conditions.", "Boundary cases.", 1)
        )
        with self.assertRaises(ProtocolDriftError) as caught:
            verify_phase_plan(compile_protocol(self.spec))
        self.assertIn("5.1", str(caught.exception))

    def test_renamed_phase_section_is_detected(self):
        # The anchors survive, but the section no longer names the subject the plan describes.
        self.spec.write_text(
            self.spec.read_text().replace(
                "## 4.4 Contribution Analysis of Additional Files",
                "## 4.4 Contribution Analysis of Attached Material",
                1,
            )
        )
        with self.assertRaises(ProtocolDriftError) as caught:
            verify_phase_plan(compile_protocol(self.spec))
        self.assertIn("4.4", str(caught.exception))

    def test_removed_phase_section_is_detected(self):
        # Without its heading the section dissolves into the previous one, so the plan can no
        # longer locate the phase at all.
        self.spec.write_text(
            self.spec.read_text().replace(
                "## 4.4 Contribution Analysis of Additional Files",
                "Contribution Analysis of Additional Files",
                1,
            )
        )
        with self.assertRaises(ProtocolDriftError) as caught:
            verify_phase_plan(compile_protocol(self.spec))
        # §4.4 dissolves into §4.3, so the marker count of the absorbing section is wrong.
        self.assertIn("required markers", str(caught.exception))


class ValidateAnswers(unittest.TestCase):
    def test_complete_answer_is_accepted(self):
        phase = phase_by_id("A.1")
        self.assertEqual(validate_answer(phase, answer_for(phase)), [])

    def test_missing_heading_is_reported(self):
        phase = phase_by_id("A.1")
        answer = answer_for(phase).replace("### Scope\n", "")
        problems = validate_answer(phase, answer)
        self.assertTrue(any("Scope" in problem for problem in problems), problems)

    def test_empty_heading_is_reported(self):
        phase = phase_by_id("A.1")
        answer = "### Primary purpose\n\n### Scope\nreal content\n### Governance role\nx\n" \
                 "### Key normative statements\nx\n### Relationship to the overall project methodology\nx\n"
        problems = validate_answer(phase, answer)
        self.assertTrue(any("empty answer under: Primary purpose" in p for p in problems), problems)

    def test_single_line_answer_is_not_mistaken_for_an_empty_one(self):
        phase = phase_by_id("A.1")
        answer = (
            "Primary purpose\nIt exists to govern the prototype.\n"
            "Scope\nIt covers the five artefacts.\n"
            "Governance role\nIt holds approval authority.\n"
            "Key normative statements\nThree gates are normative.\n"
            "Relationship to the overall project methodology\nIt is the entry point.\n"
        )
        self.assertEqual(validate_answer(phase, answer), [])

    def test_grouped_requirement_accepts_none(self):
        phase = phase_by_id("4.3")
        answer = "".join(
            f"{gap}\nnone\n" for gap in ("Missing", "Ambiguous", "Implicit", "Conflicting", "Unowned", "Unverifiable")
        ) + "Required Output\nEstablish a measurand inventory.\n"
        self.assertEqual(validate_answer(phase, answer), [])

    def test_grouped_requirement_needs_its_children(self):
        phase = phase_by_id("7")
        answer = "Defined\nSubstantive content without the required sub-answers.\n"
        problems = validate_answer(phase, answer)
        self.assertTrue(any("Compliance" in problem for problem in problems), problems)

    def test_grouped_requirement_accepts_children(self):
        phase = phase_by_id("7")
        answer = "".join(
            f"{level}\n"
            "Compliance\npartially\n"
            "Supporting evidence\n(zV, líneas 1–2)\n"
            "Deficiencies\nnone recorded\n"
            "Prerequisites for advancement\nclose the gap\n"
            for level in ("Defined", "Decidable", "Executable", "Auditable")
        ) + "Overall readiness rating\nDefined, not executable.\n"
        self.assertEqual(validate_answer(phase, answer), [])


class Prompts(unittest.TestCase):
    def setUp(self):
        self.model = compile_protocol(SPEC)

    def test_prompt_numbers_the_document_lines(self):
        phase = phase_by_id("A.1")
        prompt = render_prompt(
            phase, self.model, {"zz_Workflow": "alpha\nbeta\n"}, {"zz_Workflow": "abc"}
        )
        self.assertIn("    1 | alpha", prompt)
        self.assertIn("    2 | beta", prompt)
        self.assertIn("sha256: abc", prompt)

    def test_prompt_lists_the_required_structure_and_citation_code(self):
        phase = phase_by_id("A.1")
        prompt = render_prompt(phase, self.model, {"zz_Workflow": "alpha\n"})
        for requirement in phase.requirements:
            self.assertIn(requirement.label, prompt)
        self.assertIn("(zz, líneas", prompt)

    def test_prompt_quotes_the_protocol_section(self):
        phase = phase_by_id("4.1")
        prompt = render_prompt(phase, self.model)
        self.assertIn("Is the compliance-relevant measurand set properly specified?", prompt)

    def test_document_phase_requires_its_document(self):
        phase = phase_by_id("A.2")
        with self.assertRaises(KeyError):
            render_prompt(phase, self.model, {})


if __name__ == "__main__":
    unittest.main()
