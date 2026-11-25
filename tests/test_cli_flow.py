"""End-to-end CLI flow: the audit is refused until it can be defended.

These tests drive the public command line only, against a small frozen set in a temporary
directory. They never read the repository's real audited documents and never inspect git.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fap.cli import main
from fap.phases import PHASE_PLAN, phase_by_id

from .fixtures import DOCUMENTS, SPEC, VERDICT, answer_for, build_audit, write_documents


def run(*argv: str) -> tuple[int, str, str]:
    """Run ``main`` with captured streams and return ``(exit code, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class FlowCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name: str) -> Path:
        return self.root / name


class Init(FlowCase):
    def test_init_freezes_a_complete_set_and_refuses_an_incomplete_one(self):
        documents = self.path("documents")
        audit = self.path("audit")
        write_documents(documents)

        code, out, _ = run(
            "init", str(documents), "--out", str(audit), "--protocol", str(SPEC)
        )

        self.assertEqual(code, 0, out)
        self.assertTrue((audit / "audit.json").is_file())
        self.assertTrue((audit / "manifest.json").is_file())
        manifest = json.loads((audit / "manifest.json").read_text())
        self.assertEqual(
            [entry["status"] for entry in manifest["documents"]], ["resolved"] * len(DOCUMENTS)
        )

        partial = self.path("partial")
        partial_audit = self.path("partial-audit")
        write_documents(partial, ["zz_Workflow", "00_sdr_sensor_design"])

        code, out, _ = run(
            "init", str(partial), "--out", str(partial_audit), "--protocol", str(SPEC)
        )

        self.assertEqual(code, 1)
        self.assertIn("zV_AdmittedOutputValidity_SpectrumSensingFM0", out)
        self.assertIn("zX_CandidateFuture_SpectrumSensingFM0", out)


class Status(FlowCase):
    def test_status_fails_while_phases_are_pending_and_passes_once_answered(self):
        pending = build_audit(self.path("pending"), answers=False)
        code, out, _ = run("status", "--state", str(pending["state_path"]))
        self.assertEqual(code, 1)
        self.assertIn(f"phases answered: 0/{len(PHASE_PLAN)}", out)

        complete = build_audit(self.path("complete"))
        code, out, _ = run("status", "--state", str(complete["state_path"]))
        self.assertEqual(code, 0)
        self.assertIn(f"phases answered: {len(PHASE_PLAN)}/{len(PHASE_PLAN)}", out)
        self.assertIn(VERDICT, out)


class PhasePrompt(FlowCase):
    def test_phase_prompt_numbers_the_document_lines_and_lists_the_headings(self):
        audit = build_audit(self.path("audit"))

        code, out, _ = run(
            "phase", "prompt", "--phase", "A.1", "--state", str(audit["state_path"])
        )

        self.assertEqual(code, 0)
        self.assertIn(
            "    4 | The workflow defines five artefacts and three approval gates.", out
        )
        self.assertIn("    1 | \\documentclass[12pt]{report}", out)
        self.assertIn("## Required structure", out)
        for requirement in phase_by_id("A.1").requirements:
            self.assertIn(requirement.label, out)


class PhaseIngest(FlowCase):
    def test_ingest_stores_a_valid_answer_and_refuses_invalid_ones_untouched(self):
        audit = build_audit(self.path("audit"), answers=False)
        state_path = audit["state_path"]
        phase = phase_by_id("A.1")
        answer = answer_for(phase)

        good = self.path("answer-a1.md")
        good.write_text(answer)
        code, out, err = run(
            "phase", "ingest", "--phase", "A.1", "--in", str(good), "--state", str(state_path)
        )
        self.assertEqual(code, 0, err)
        stored = json.loads(state_path.read_text())
        self.assertEqual(stored["phases"]["A.1"]["status"], "complete")
        self.assertEqual(stored["phases"]["A.1"]["answer"], answer)

        snapshot = state_path.read_bytes()

        missing_heading = self.path("missing-heading.md")
        missing_heading.write_text(answer.replace("### Scope\n", ""))
        code, _, err = run(
            "phase",
            "ingest",
            "--phase",
            "A.1",
            "--in",
            str(missing_heading),
            "--state",
            str(state_path),
        )
        self.assertEqual(code, 1)
        self.assertIn("Scope", err)
        self.assertEqual(state_path.read_bytes(), snapshot)

        beyond_length = self.path("beyond-length.md")
        beyond_length.write_text(answer.replace("líneas 1–2", "líneas 900–950"))
        code, _, err = run(
            "phase",
            "ingest",
            "--phase",
            "A.1",
            "--in",
            str(beyond_length),
            "--state",
            str(state_path),
        )
        self.assertEqual(code, 1)
        self.assertIn("900", err)
        self.assertEqual(state_path.read_bytes(), snapshot)


class ReportBuild(FlowCase):
    def test_report_build_refuses_pending_phases_and_builds_a_complete_audit(self):
        audit = build_audit(self.path("audit"), answers=False)
        state_path = audit["state_path"]
        out_path = self.path("report.md")
        ledger = state_path.parent / "ledger.jsonl"

        code, out, _ = run(
            "report", "build", "--state", str(state_path), "--out", str(out_path)
        )
        self.assertEqual(code, 1)
        self.assertIn("phase-pending", out)
        self.assertFalse(out_path.exists())
        self.assertFalse(ledger.exists())

        for phase in PHASE_PLAN:
            answer_path = self.path(f"answer-{phase.id}.md")
            answer_path.write_text(answer_for(phase))
            code, _, err = run(
                "phase",
                "ingest",
                "--phase",
                phase.id,
                "--in",
                str(answer_path),
                "--state",
                str(state_path),
            )
            self.assertEqual(code, 0, f"{phase.id}: {err}")

        state = json.loads(state_path.read_text())
        state["verdict"] = {
            "value": VERDICT,
            "justification": "The frozen set and its citations support this determination.",
        }
        state_path.write_text(json.dumps(state, indent=2))

        code, out, _ = run(
            "report", "build", "--state", str(state_path), "--out", str(out_path)
        )
        self.assertEqual(code, 0, out)
        self.assertTrue(out_path.is_file())
        self.assertIn(VERDICT, out_path.read_text())
        entries = ledger.read_text().splitlines()
        self.assertEqual(len(entries), 1)
        self.assertEqual(json.loads(entries[0])["event"], "report-built")


class CiteCheck(FlowCase):
    def test_cite_check_accepts_resolved_citations_and_rejects_a_missing_line(self):
        audit = build_audit(self.path("audit"))

        resolved = self.path("resolved.md")
        resolved.write_text("The gate is normative (zz, líneas 2–3).\n")
        code, out, _ = run(
            "cite", "check", "--report", str(resolved), "--state", str(audit["state_path"])
        )
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: citations resolve", out)

        nonexistent = self.path("nonexistent.md")
        nonexistent.write_text("The gate is normative (zz, líneas 900–950).\n")
        code, out, _ = run(
            "cite",
            "check",
            "--report",
            str(nonexistent),
            "--state",
            str(audit["state_path"]),
        )
        self.assertEqual(code, 1)
        self.assertIn("unresolved", out)


if __name__ == "__main__":
    unittest.main()
