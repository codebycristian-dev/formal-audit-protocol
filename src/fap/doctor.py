"""Diagnose whether the frozen set can carry the audit the protocol demands.

This is the tool's first job and its most useful one: refusing to audit a set that cannot
be audited. Every refusal names the document and the reason, because an audit that starts
from an unverifiable premise produces a report that is worse than no report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .protocol import ProtocolModel


class Finding(NamedTuple):
    level: str  # PASS | WARN | FAIL
    code: str
    message: str


@dataclass
class Report:
    findings: list[Finding]
    documents: int

    @property
    def failures(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.level == "FAIL"]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def render(self) -> str:
        lines = []
        for finding in self.findings:
            lines.append(f"[{finding.level}] {finding.code}: {finding.message}")
        if self.ok:
            lines.append(f"RESULT: ready ({self.documents} documents, citations resolvable)")
        else:
            lines.append(f"RESULT: not ready ({len(self.failures)} blocking finding(s))")
        return "\n".join(lines)


def diagnose(manifest: dict, model: ProtocolModel) -> Report:
    findings: list[Finding] = []
    entries = manifest["documents"]
    resolved = [entry for entry in entries if entry["status"] == "resolved"]

    for entry in entries:
        name = entry["canonical"]
        status = entry["status"]
        if status == "missing":
            findings.append(
                Finding(
                    "FAIL",
                    "document-missing",
                    f"{name} was not found under {manifest['root']}; "
                    "the protocol requires the full document set",
                )
            )
        elif status == "ambiguous":
            candidates = ", ".join(entry.get("candidates", []))
            findings.append(
                Finding(
                    "FAIL",
                    "document-ambiguous",
                    f"{name} matches more than one file ({candidates}); "
                    "identity must be decided before the audit runs",
                )
            )
        elif entry["format"] == "pdf":
            findings.append(
                Finding(
                    "FAIL",
                    "document-unreadable",
                    f"{name} is only available as PDF ({entry['path']}); "
                    "line-anchored citations cannot be resolved, so extract it to "
                    "readable LaTeX or Markdown first",
                )
            )
        elif not entry["lines"]:
            findings.append(
                Finding(
                    "FAIL",
                    "document-empty",
                    f"{name} ({entry['path']}) has no lines to cite",
                )
            )

        for rendering in entry.get("renderings", []):
            findings.append(
                Finding(
                    "WARN",
                    "document-rendering",
                    f"{name} is also present as {rendering}; citations resolve against "
                    f"{entry['path']}, the readable source",
                )
            )

    by_hash: dict[str, list[str]] = {}
    for entry in resolved:
        by_hash.setdefault(entry["sha256"], []).append(entry["canonical"])
    for digest, names in by_hash.items():
        if len(names) > 1:
            findings.append(
                Finding(
                    "FAIL",
                    "document-duplicate-content",
                    "two audited documents have identical content "
                    f"({', '.join(sorted(names))}, sha256 {digest[:12]}); "
                    "one of them is not what the protocol names",
                )
            )

    expected = set(model.documents)
    declared = {entry["canonical"] for entry in entries}
    if expected != declared:
        findings.append(
            Finding(
                "FAIL",
                "protocol-manifest-mismatch",
                "the manifest was frozen against a different document list: "
                f"missing {sorted(expected - declared)}, unexpected {sorted(declared - expected)}",
            )
        )

    for extra in manifest.get("extra_files", []):
        findings.append(
            Finding(
                "WARN",
                "document-extra",
                f"{extra} is not part of the audited set; §2.1 does not authorize it",
            )
        )

    if not findings:
        findings.append(
            Finding("PASS", "set-complete", "every required document is resolved and readable")
        )

    return Report(findings=findings, documents=len(resolved))
