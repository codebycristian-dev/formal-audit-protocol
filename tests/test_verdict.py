"""Tests for setting the verdict: the closed vocabulary is enforced at the door."""

import json
import tempfile
import unittest
from pathlib import Path

from fap.cli import main

from .fixtures import VERDICT, build_audit


class Verdict(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit = build_audit(Path(self._tmp.name))
        self.state_path = self.audit["state_path"]

    def tearDown(self):
        self._tmp.cleanup()

    def stored(self):
        return json.loads(self.state_path.read_text())["verdict"]

    def test_valid_verdict_is_stored(self):
        code = main(
            [
                "verdict",
                "--state",
                str(self.state_path),
                "--value",
                "Not currently suitable",
                "--justification",
                "The measurand inventory is not established.",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.stored()["value"], "Not currently suitable")
        self.assertEqual(
            self.stored()["justification"],
            "The measurand inventory is not established.",
        )

    def test_verdict_outside_the_vocabulary_is_refused(self):
        before = self.stored()
        code = main(
            [
                "verdict",
                "--state",
                str(self.state_path),
                "--value",
                "Suitable with caveats",
                "--justification",
                "Sounds reasonable.",
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.stored(), before)

    def test_verdict_needs_a_justification(self):
        before = self.stored()
        code = main(
            [
                "verdict",
                "--state",
                str(self.state_path),
                "--value",
                VERDICT,
                "--justification",
                "   ",
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.stored(), before)


if __name__ == "__main__":
    unittest.main()
