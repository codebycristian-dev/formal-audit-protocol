"""Tests for citation resolution: a citation that points at nothing must not pass."""

import unittest

from fap.citations import (
    DOCUMENT_UNREADABLE,
    DOCUMENT_UNRESOLVED,
    OK,
    OUT_OF_RANGE,
    RELATIVE_STATUS,
    UNKNOWN_DOCUMENT,
    UNPARSEABLE,
    check,
    extract,
    failures,
    parse_ranges,
    summary,
)

MANIFEST = {
    "root": "/docs",
    "documents": [
        {
            "canonical": "zz_Workflow",
            "status": "resolved",
            "path": "zz_Workflow/zz_Workflow.md",
            "format": "latex",
            "lines": 120,
            "sha256": "a" * 64,
        },
        {
            "canonical": "00_sdr_sensor_design",
            "status": "resolved",
            "path": "00_sdr_sensor_design/00_sdr_sensor_design.md",
            "format": "latex",
            "lines": 40,
            "sha256": "b" * 64,
        },
        {
            "canonical": "zV_AdmittedOutputValidity_SpectrumSensingFM0",
            "status": "missing",
            "path": None,
            "format": None,
            "lines": None,
            "sha256": None,
        },
        {
            "canonical": "zX_CandidateFuture_SpectrumSensingFM0",
            "status": "resolved",
            "path": "zX_CandidateFuture_SpectrumSensingFM0.pdf",
            "format": "pdf",
            "lines": None,
            "sha256": "c" * 64,
        },
    ],
}

ALIASES = {
    "zz_Workflow": "zz_Workflow",
    "zz": "zz_Workflow",
    "00_sdr_sensor_design": "00_sdr_sensor_design",
    "00": "00_sdr_sensor_design",
    "zV": "zV_AdmittedOutputValidity_SpectrumSensingFM0",
    "zX": "zX_CandidateFuture_SpectrumSensingFM0",
}


class Ranges(unittest.TestCase):
    def test_single_line(self):
        self.assertEqual(parse_ranges("881"), ((881, 881),))

    def test_several_ranges_joined_by_y(self):
        self.assertEqual(parse_ranges("881 y 749–752"), ((881, 881), (749, 752)))

    def test_several_ranges_joined_by_comma_and_and(self):
        self.assertEqual(parse_ranges("8–14, 300 and 3152–3154"), ((8, 14), (300, 300), (3152, 3154)))

    def test_unreadable_ranges(self):
        self.assertIsNone(parse_ranges("the first section"))

    def test_zero_is_not_a_line(self):
        self.assertIsNone(parse_ranges("0–4"))

    def test_reversed_range_is_rejected(self):
        self.assertIsNone(parse_ranges("14–8"))


class Resolution(unittest.TestCase):
    def test_valid_citation_resolves(self):
        found = check("The gate is normative (zz, líneas 12–14).", MANIFEST, ALIASES)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].status, OK)
        self.assertEqual(found[0].canonical, "zz_Workflow")
        self.assertEqual(found[0].ranges, ((12, 14),))

    def test_full_canonical_name_resolves(self):
        found = check("(00_sdr_sensor_design, líneas 4)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, OK)

    def test_english_spelling_resolves(self):
        found = check("(zz, lines 3-4)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, OK)

    def test_out_of_range_is_blocking(self):
        found = check("(zz, líneas 100–140)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, OUT_OF_RANGE)
        self.assertTrue(found[0].blocking)
        self.assertIn("120 lines", found[0].detail)

    def test_unknown_document_is_blocking(self):
        found = check("(qq, líneas 1–2)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, UNKNOWN_DOCUMENT)
        self.assertTrue(found[0].blocking)

    def test_missing_document_is_blocking(self):
        found = check("(zV, líneas 1–2)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, DOCUMENT_UNRESOLVED)
        self.assertTrue(found[0].blocking)

    def test_pdf_only_document_is_blocking(self):
        found = check("(zX, líneas 1–2)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, DOCUMENT_UNREADABLE)
        self.assertTrue(found[0].blocking)

    def test_relative_citation_is_not_blocking(self):
        found = check("(líneas 256–282)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, RELATIVE_STATUS)
        self.assertFalse(found[0].blocking)

    def test_unparseable_ranges_are_blocking(self):
        found = check("(zz, líneas the appendix)", MANIFEST, ALIASES)
        self.assertEqual(found[0].status, UNPARSEABLE)
        self.assertTrue(found[0].blocking)

    def test_no_citations_is_not_a_failure(self):
        self.assertEqual(check("A report without citations.", MANIFEST, ALIASES), [])

    def test_citations_are_found_in_document_order(self):
        text = "first (zz, líneas 1) then (00, líneas 2) and (zz, líneas 3)"
        found = extract(text)
        self.assertEqual([item[1] for item in found], ["zz", "00", "zz"])

    def test_failures_and_summary(self):
        found = check("(zz, líneas 1) (zz, líneas 999) (líneas 5)", MANIFEST, ALIASES)
        self.assertEqual(len(failures(found)), 1)
        self.assertIn("ok: 1", summary(found))
        self.assertIn("out-of-range: 1", summary(found))


if __name__ == "__main__":
    unittest.main()
