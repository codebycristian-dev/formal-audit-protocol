"""Tests for the coverage gate: the report is refused, not weakened."""

import tempfile
import unittest
from pathlib import Path

from fap.report import assemble, check_coverage
from fap.state import aliases

from .fixtures import VERDICT, build_audit


class Gate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit = build_audit(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def coverage(self):
        return check_coverage(
            self.audit["state"],
            self.audit["model"],
            self.audit["manifest"],
            aliases(self.audit["state"], self.audit["model"]),
        )

    def codes(self, coverage):
        return [problem.code for problem in coverage.problems]

    def test_complete_audit_passes(self):
        coverage = self.coverage()
        self.assertEqual(coverage.problems, [], coverage.render())
        self.assertTrue(coverage.ok)

    def test_pending_phase_is_refused(self):
        self.audit["state"]["phases"]["5.3"] = {"status": "pending", "answer": None}
        coverage = self.coverage()
        self.assertFalse(coverage.ok)
        self.assertIn("phase-pending", self.codes(coverage))
        self.assertIn("5.3", coverage.render())

    def test_incomplete_phase_answer_is_refused(self):
        answer = self.audit["state"]["phases"]["4.1"]["answer"]
        self.audit["state"]["phases"]["4.1"]["answer"] = answer.replace(
            "### Required Finding\n", ""
        )
        coverage = self.coverage()
        self.assertIn("phase-incomplete", self.codes(coverage))

    def test_verdict_outside_the_vocabulary_is_refused(self):
        self.audit["state"]["verdict"]["value"] = "Suitable with caveats"
        coverage = self.coverage()
        self.assertIn("verdict-invalid", self.codes(coverage))

    def test_missing_justification_is_refused(self):
        self.audit["state"]["verdict"]["justification"] = "   "
        coverage = self.coverage()
        self.assertIn("verdict-justification-missing", self.codes(coverage))

    def test_verdict_must_be_stated_in_the_final_determination(self):
        self.audit["state"]["verdict"]["value"] = "Not currently suitable"
        coverage = self.coverage()
        self.assertIn("verdict-not-in-report", self.codes(coverage))

    def test_unresolved_citation_is_refused(self):
        phase = self.audit["state"]["phases"]["5.1"]
        phase["answer"] = phase["answer"].replace("líneas 1–2", "líneas 900–950")
        coverage = self.coverage()
        self.assertIn("citation-unresolved", self.codes(coverage))
        self.assertIn("900", coverage.render())

    def test_uncited_phase_is_a_warning_not_a_blocker(self):
        phase = self.audit["state"]["phases"]["4.4"]
        phase["answer"] = phase["answer"].replace(" (zz, líneas 1–2)", "")
        coverage = self.coverage()
        self.assertTrue(coverage.ok, coverage.render())
        self.assertIn("phase-uncited", [warning.code for warning in coverage.warnings])


class Assembly(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit = build_audit(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_report_records_the_frozen_hashes_and_the_verdict(self):
        text = assemble(
            self.audit["state"], self.audit["model"], self.audit["manifest"]
        )
        for entry in self.audit["manifest"]["documents"]:
            self.assertIn(entry["canonical"], text)
            if entry["sha256"]:
                self.assertIn(entry["sha256"][:16], text)
        self.assertIn(VERDICT, text)
        self.assertIn(self.audit["model"].sha256, text)

    def test_report_follows_the_protocol_numbering(self):
        text = assemble(
            self.audit["state"], self.audit["model"], self.audit["manifest"]
        )
        self.assertIn("## A.1.", text)
        self.assertIn("## 4.1.", text)
        self.assertIn("## 10.", text)
        self.assertLess(text.index("## 4.1."), text.index("## 10."))


if __name__ == "__main__":
    unittest.main()
