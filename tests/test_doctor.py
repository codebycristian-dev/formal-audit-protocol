"""Tests for the readiness diagnosis: the tool refuses to audit a bad document set."""

import tempfile
import unittest
from pathlib import Path

from fap.cli import main
from fap.doctor import diagnose
from fap.freeze import freeze
from fap.protocol import compile_protocol

SPEC = Path(__file__).resolve().parents[1] / "Formal Audit Protocol.md"

LATEX_A = """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Workflow}
The workflow defines five artefacts and three approval gates.
\\end{document}
"""

LATEX_B = """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Design}
The design document instantiates the workflow requirements.
\\end{document}
"""

LATEX_C = """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Validity}
Admitted outputs are governed by the validity boundary.
\\end{document}
"""

LATEX_D = """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Future}
Research archive and roadmap live here, apart from authority.
\\end{document}
"""

BODIES = {
    "zz_Workflow": LATEX_A,
    "00_sdr_sensor_design": LATEX_B,
    "zV_AdmittedOutputValidity_SpectrumSensingFM0": LATEX_C,
    "zX_CandidateFuture_SpectrumSensingFM0": LATEX_D,
}


class DoctorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.model = compile_protocol(SPEC)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path

    def complete_set(self):
        for name, body in BODIES.items():
            self.write(f"{name}/{name}.md", body)
        return freeze(self.root, self.model)

    def codes(self, report):
        return [finding.code for finding in report.findings]

    def failures(self, report):
        return [finding for finding in report.findings if finding.level == "FAIL"]


class CompleteSet(DoctorCase):
    def test_complete_readable_set_passes(self):
        report = diagnose(self.complete_set(), self.model)

        self.assertEqual(self.failures(report), [])
        self.assertTrue(report.ok)
        self.assertEqual(report.exit_code, 0)
        self.assertIn("RESULT: ready", report.render())


class IncompleteSet(DoctorCase):
    def test_absent_document_blocks_the_audit(self):
        for name, body in BODIES.items():
            if name.startswith("zV_"):
                continue
            self.write(f"{name}/{name}.md", body)

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertFalse(report.ok)
        self.assertEqual(report.exit_code, 1)
        self.assertIn("document-missing", self.codes(report))
        message = " ".join(f.message for f in self.failures(report))
        self.assertIn("zV_AdmittedOutputValidity_SpectrumSensingFM0", message)
        self.assertIn("RESULT: not ready", report.render())

    def test_single_document_cannot_cover_the_quartet(self):
        self.write("zz_Workflow/zz_Workflow.md", LATEX_A)

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertFalse(report.ok)
        self.assertEqual(len([c for c in self.codes(report) if c == "document-missing"]), 3)


class UnreadableOrAmbiguous(DoctorCase):
    def test_pdf_only_document_cannot_anchor_citations(self):
        for name, body in BODIES.items():
            if name == "zz_Workflow":
                self.write(f"{name}/{name}.pdf", b"%PDF-1.5\nworkflow\n")
            else:
                self.write(f"{name}/{name}.md", body)

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertFalse(report.ok)
        self.assertIn("document-unreadable", self.codes(report))
        message = " ".join(f.message for f in self.failures(report))
        self.assertIn("zz_Workflow", message)

    def test_duplicate_copies_of_one_document_are_ambiguous(self):
        for name, body in BODIES.items():
            self.write(f"{name}/{name}.md", body)
        self.write("mirror/zz_Workflow.md", LATEX_A)

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertFalse(report.ok)
        self.assertIn("document-ambiguous", self.codes(report))

    def test_identical_content_under_two_names_is_a_contradiction(self):
        for name, body in BODIES.items():
            self.write(f"{name}/{name}.md", body)
        self.write(
            "zX_CandidateFuture_SpectrumSensingFM0/zX_CandidateFuture_SpectrumSensingFM0.md",
            LATEX_C,
        )

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertFalse(report.ok)
        self.assertIn("document-duplicate-content", self.codes(report))


class Extras(DoctorCase):
    def test_pdf_rendering_of_a_readable_document_is_only_a_warning(self):
        self.complete_set()
        self.write("zz_Workflow/zz_Workflow.pdf", b"%PDF-1.5\n")

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertTrue(report.ok)
        self.assertEqual(
            [f.level for f in report.findings if f.code == "document-rendering"], ["WARN"]
        )

    def test_unexpected_document_is_a_warning_not_a_blocker(self):
        self.complete_set()
        self.write("zz_AgentSkills/zz_AgentSkills.md", "# Agent skills\n\ntext\n")

        report = diagnose(freeze(self.root, self.model), self.model)

        self.assertTrue(report.ok)
        self.assertIn("document-extra", self.codes(report))
        self.assertEqual([f.level for f in report.findings if f.code == "document-extra"], ["WARN"])


class CommandLine(DoctorCase):
    def test_freeze_then_doctor_exit_codes(self):
        out = self.root / "freeze"
        for name, body in BODIES.items():
            self.write(f"{name}/{name}.md", body)

        self.assertEqual(
            main(["freeze", str(self.root), "--protocol", str(SPEC), "--out", str(out)]), 0)
        self.assertEqual(main(["doctor", "--manifest", str(out / "manifest.json")]), 0)

        (self.root / "zV_AdmittedOutputValidity_SpectrumSensingFM0"
         / "zV_AdmittedOutputValidity_SpectrumSensingFM0.md").unlink()

        self.assertEqual(
            main(["freeze", str(self.root), "--protocol", str(SPEC), "--out", str(out)]), 0)
        self.assertEqual(main(["doctor", "--manifest", str(out / "manifest.json")]), 1)

    def test_protocol_check_reports_the_compiled_contract(self):
        self.assertEqual(main(["protocol", "check", "--protocol", str(SPEC)]), 0)

    def test_protocol_check_fails_on_a_drifted_spec(self):
        drifted = self.root / "drifted.md"
        drifted.write_text(SPEC.read_text().replace("Required Finding", "Suggested Finding"))
        self.assertEqual(main(["protocol", "check", "--protocol", str(drifted)]), 1)


if __name__ == "__main__":
    unittest.main()
