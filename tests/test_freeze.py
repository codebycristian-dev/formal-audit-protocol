"""Tests for freezing an audited document set: format detection, hashes, resolution."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from fap.freeze import detect_format, file_sha256, freeze, resolve_document
from fap.protocol import compile_protocol

SPEC = Path(__file__).resolve().parents[1] / "Formal Audit Protocol.md"

LATEX_BODY = """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Workflow}
The workflow defines five artefacts and three approval gates.
\\end{document}
"""

MARKDOWN_BODY = """# Design

The design document states its own scope.

It has several paragraphs.
"""


class TempTree(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

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


class DetectFormat(TempTree):
    def test_latex_with_markdown_extension_is_latex(self):
        path = self.write("a.md", LATEX_BODY)
        self.assertEqual(detect_format(path), "latex")

    def test_plain_markdown(self):
        path = self.write("b.md", MARKDOWN_BODY)
        self.assertEqual(detect_format(path), "markdown")

    def test_pdf_magic(self):
        path = self.write("c.pdf", b"%PDF-1.7\n\x00\x01trailer\n")
        self.assertEqual(detect_format(path), "pdf")

    def test_plain_text(self):
        path = self.write("d.txt", "no markup at all\nsecond line\n")
        self.assertEqual(detect_format(path), "text")


class Hashes(TempTree):
    def test_sha256_matches_hashlib(self):
        path = self.write("x.md", MARKDOWN_BODY)
        self.assertEqual(file_sha256(path), hashlib.sha256(MARKDOWN_BODY.encode()).hexdigest())

    def test_hash_is_stable_across_calls(self):
        path = self.write("x.md", MARKDOWN_BODY)
        self.assertEqual(file_sha256(path), file_sha256(path))


class Resolution(TempTree):
    def test_resolves_flat_file(self):
        path = self.write("zz_Workflow.md", LATEX_BODY)
        self.assertEqual(resolve_document(self.root, "zz_Workflow"), [path])

    def test_resolves_pdf_side_by_side(self):
        self.write("00_sdr.md", MARKDOWN_BODY)
        pdf = self.write("00_sdr.pdf", b"%PDF-1.4\n")
        found = resolve_document(self.root, "00_sdr")
        self.assertEqual(sorted(found), sorted([self.root / "00_sdr.md", pdf]))

    def test_resolves_document_directory(self):
        path = self.write("00_sdr_sensor_design/00_sdr_sensor_design.md", MARKDOWN_BODY)
        self.assertEqual(resolve_document(self.root, "00_sdr_sensor_design"), [path])

    def test_absent_document_resolves_to_nothing(self):
        self.assertEqual(resolve_document(self.root, "zV_AdmittedOutputValidity"), [])


class Freeze(TempTree):
    def test_manifest_records_every_document_with_hash_and_format(self):
        model = compile_protocol(SPEC)
        for name in model.enums["documents"]:
            self.write(f"{name}/{name}.md", LATEX_BODY)

        manifest = freeze(self.root, model)

        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["protocol"]["sha256"], model.sha256)
        self.assertEqual(len(manifest["documents"]), 4)
        for entry in manifest["documents"]:
            self.assertEqual(entry["status"], "resolved")
            self.assertEqual(entry["format"], "latex")
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertGreater(entry["lines"], 0)

    def test_missing_document_is_recorded_not_invented(self):
        model = compile_protocol(SPEC)
        self.write("zz_Workflow/zz_Workflow.md", LATEX_BODY)

        manifest = freeze(self.root, model)

        statuses = {entry["canonical"]: entry["status"] for entry in manifest["documents"]}
        self.assertEqual(statuses["zz_Workflow"], "resolved")
        self.assertEqual(statuses["zX_CandidateFuture_SpectrumSensingFM0"], "missing")
        entry = next(e for e in manifest["documents"] if e["status"] == "missing")
        self.assertIsNone(entry["sha256"])

    def test_readable_source_wins_over_its_pdf_rendering(self):
        model = compile_protocol(SPEC)
        self.write("zz_Workflow/zz_Workflow.md", LATEX_BODY)
        self.write("zz_Workflow/zz_Workflow.pdf", b"%PDF-1.5\n")

        manifest = freeze(self.root, model)

        entry = next(e for e in manifest["documents"] if e["canonical"] == "zz_Workflow")
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["path"], "zz_Workflow/zz_Workflow.md")
        self.assertEqual(entry["format"], "latex")
        self.assertEqual(entry["renderings"], ["zz_Workflow/zz_Workflow.pdf"])

    def test_pdf_document_has_no_line_count(self):
        model = compile_protocol(SPEC)
        self.write("zz_Workflow/zz_Workflow.pdf", b"%PDF-1.5\n")

        manifest = freeze(self.root, model)

        entry = next(e for e in manifest["documents"] if e["canonical"] == "zz_Workflow")
        self.assertEqual(entry["format"], "pdf")
        self.assertIsNone(entry["lines"])

    def test_excluded_figures_are_not_reported_as_extra(self):
        model = compile_protocol(SPEC)
        for name in model.enums["documents"]:
            self.write(f"{name}/{name}.md", LATEX_BODY)
        self.write("zz_Workflow/Figures/End2End/plot.jpeg", b"\xff\xd8\xff")

        manifest = freeze(self.root, model)

        self.assertEqual(manifest["extra_files"], [])

    def test_figure_files_are_not_documents(self):
        model = compile_protocol(SPEC)
        for name in model.enums["documents"]:
            self.write(f"{name}/{name}.md", LATEX_BODY)
        self.write("zz_Workflow/_page_3_Diagram_0.jpeg", b"\xff\xd8\xff")

        manifest = freeze(self.root, model)

        self.assertEqual(manifest["extra_files"], [])

    def test_output_directory_inside_root_is_not_reported_as_extra(self):
        model = compile_protocol(SPEC)
        for name in model.enums["documents"]:
            self.write(f"{name}/{name}.md", LATEX_BODY)
        out = self.root / "freeze"
        out.mkdir()
        (out / "manifest.json").write_text("{}")

        manifest = freeze(self.root, model, exclude=[out])

        self.assertEqual(manifest["extra_files"], [])

    def test_unexpected_file_is_reported_as_extra(self):
        model = compile_protocol(SPEC)
        for name in model.enums["documents"]:
            self.write(f"{name}/{name}.md", LATEX_BODY)
        self.write("zz_AgentSkills/zz_AgentSkills.md", MARKDOWN_BODY)

        manifest = freeze(self.root, model)

        self.assertEqual(manifest["extra_files"], ["zz_AgentSkills/zz_AgentSkills.md"])


if __name__ == "__main__":
    unittest.main()
