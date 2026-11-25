"""Tests for compiling the protocol specification into a checkable contract."""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from fap.protocol import ProtocolDriftError, compile_protocol

SPEC = Path(__file__).resolve().parents[1] / "Formal Audit Protocol.md"


class CompileRepositorySpec(unittest.TestCase):
    def test_compiles_the_repository_spec(self):
        model = compile_protocol(SPEC)

        self.assertEqual(model.sha256, hashlib.sha256(SPEC.read_bytes()).hexdigest())
        self.assertEqual(
            [slot.id for slot in model.slots],
            ["4.1", "4.2", "4.3", "4.4", "6", "7", "10"],
        )
        self.assertEqual(
            [slot.kind for slot in model.slots],
            [
                "Required Finding",
                "Required Finding",
                "Required Output",
                "Required Finding",
                "Required Finding",
                "Required Determination",
                "Final Determination",
            ],
        )
        for slot in model.slots:
            self.assertTrue(slot.prompt, f"slot {slot.id} has no prompt")
            self.assertGreater(slot.source_line, 0)

    def test_compiles_the_closed_vocabularies(self):
        model = compile_protocol(SPEC)

        self.assertEqual(
            model.enums["documents"],
            [
                "zz_Workflow",
                "00_sdr_sensor_design",
                "zV_AdmittedOutputValidity_SpectrumSensingFM0",
                "zX_CandidateFuture_SpectrumSensingFM0",
            ],
        )
        self.assertEqual(
            model.enums["readiness"],
            ["Defined", "Decidable", "Executable", "Auditable"],
        )
        self.assertEqual(
            model.enums["verdict"],
            [
                "Suitable without reservation",
                "Suitable with minor corrective actions",
                "Suitable with major corrective actions",
                "Not currently suitable",
            ],
        )
        self.assertEqual(
            model.enums["gap_types"],
            ["Missing", "Ambiguous", "Implicit", "Conflicting", "Unowned", "Unverifiable"],
        )

    def test_compiles_sections_and_exclusions(self):
        model = compile_protocol(SPEC)

        numbers = [section.number for section in model.sections]
        for required in ("1", "2", "2.1", "2.2", "3", "4", "4.1", "5", "6", "7", "8", "9", "10"):
            self.assertIn(required, numbers)

        joined = " ".join(model.exclusions)
        self.assertIn("Figures/End2End", joined)
        self.assertIn("notebook", joined)

    def test_slot_prompts_are_the_spec_questions(self):
        model = compile_protocol(SPEC)
        by_id = {slot.id: slot for slot in model.slots}

        self.assertEqual(
            by_id["4.1"].prompt,
            "Is the compliance-relevant measurand set properly specified?",
        )
        self.assertTrue(by_id["4.2"].prompt.startswith("Can the audited document quartet"))
        self.assertTrue(by_id["4.3"].prompt.startswith("Provide recommendations for establishing"))
        self.assertTrue(by_id["4.4"].prompt.startswith("Do the attached files materially"))
        self.assertTrue(by_id["6"].prompt.startswith("Have methodologies comparable"))
        self.assertEqual(by_id["7"].prompt, "Provide an overall readiness rating and justify the rating.")
        self.assertTrue(by_id["10"].prompt.startswith("Provide a final integrated assessment"))

    def test_compilation_is_deterministic(self):
        first = compile_protocol(SPEC).to_dict()
        second = compile_protocol(SPEC).to_dict()
        self.assertEqual(first, second)


class DetectDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.spec = Path(self.tmp) / "spec.md"
        shutil.copy(SPEC, self.spec)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def rewrite(self, old, new):
        self.spec.write_text(self.spec.read_text().replace(old, new, 1))

    def test_missing_required_output_is_detected(self):
        self.rewrite("Required Output", "Suggested Output")
        with self.assertRaises(ProtocolDriftError) as caught:
            compile_protocol(self.spec)
        self.assertIn("4.3", str(caught.exception))

    def test_changed_prompt_is_detected(self):
        self.rewrite(
            "Is the compliance-relevant measurand set properly specified?",
            "Is the measurand set fine?",
        )
        with self.assertRaises(ProtocolDriftError) as caught:
            compile_protocol(self.spec)
        self.assertIn("4.1", str(caught.exception))

    def test_changed_verdict_value_is_detected(self):
        self.rewrite("Not currently suitable", "Not suitable yet")
        with self.assertRaises(ProtocolDriftError) as caught:
            compile_protocol(self.spec)
        self.assertIn("verdict", str(caught.exception))

    def test_removed_document_is_detected(self):
        self.rewrite("4. `zX_CandidateFuture_SpectrumSensingFM0`\n", "")
        with self.assertRaises(ProtocolDriftError) as caught:
            compile_protocol(self.spec)
        self.assertIn("documents", str(caught.exception))

    def test_missing_readiness_level_is_detected(self):
        self.rewrite("\nAuditable\n", "\nAudit ready\n")
        with self.assertRaises(ProtocolDriftError) as caught:
            compile_protocol(self.spec)
        self.assertIn("readiness", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
