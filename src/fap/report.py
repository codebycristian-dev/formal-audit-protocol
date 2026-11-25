"""The coverage gate and the report assembler.

The gate is the point of the whole tool: a report is emitted only when every phase of the
protocol has an answer that satisfies its required structure, the verdict comes from the
closed vocabulary, and every citation resolves against the frozen set. Anything else is a
refusal with a reason, not a weaker report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from . import citations as citations_module
from .phases import PHASE_PLAN, section_text, validate_answer
from .protocol import ProtocolModel


@dataclass(frozen=True)
class Problem:
    code: str
    message: str


@dataclass
class Coverage:
    problems: list[Problem]
    warnings: list[Problem]
    citations: list

    @property
    def ok(self) -> bool:
        return not self.problems

    def render(self) -> str:
        lines = []
        for problem in self.problems:
            lines.append(f"[FAIL] {problem.code}: {problem.message}")
        for warning in self.warnings:
            lines.append(f"[WARN] {warning.code}: {warning.message}")
        if self.ok:
            lines.append("RESULT: report can be emitted")
        else:
            lines.append(f"RESULT: refused ({len(self.problems)} blocking problem(s))")
        return "\n".join(lines)


def body_of(state: dict) -> str:
    """The audited answers, concatenated in protocol order."""
    parts = []
    for phase in PHASE_PLAN:
        entry = state["phases"].get(phase.id) or {}
        if entry.get("answer"):
            parts.append(entry["answer"])
    return "\n\n".join(parts)


def check_coverage(
    state: dict, model: ProtocolModel, manifest: dict, aliases: dict[str, str]
) -> Coverage:
    problems: list[Problem] = []
    warnings: list[Problem] = []

    for phase in PHASE_PLAN:
        entry = state["phases"].get(phase.id) or {}
        answer = entry.get("answer")
        if entry.get("status") != "complete" or not answer:
            problems.append(
                Problem("phase-pending", f"phase {phase.id} ({phase.title}) has no answer")
            )
            continue
        for problem in validate_answer(phase, answer):
            problems.append(Problem("phase-incomplete", f"phase {phase.id}: {problem}"))

    verdict = state.get("verdict") or {}
    value = verdict.get("value")
    if value not in model.enums["verdict"]:
        problems.append(
            Problem(
                "verdict-invalid",
                f"verdict {value!r} is not one of: " + ", ".join(model.enums["verdict"]),
            )
        )
    if not (verdict.get("justification") or "").strip():
        problems.append(
            Problem("verdict-justification-missing", "the verdict needs a justification")
        )
    if value:
        final = (state["phases"].get("10") or {}).get("answer") or ""
        if value not in final:
            problems.append(
                Problem(
                    "verdict-not-in-report",
                    f"the final determination does not state the verdict {value!r}",
                )
            )

    found = citations_module.check(body_of(state), manifest, aliases)
    for citation in citations_module.failures(found):
        problems.append(
            Problem("citation-unresolved", f"{citation.text}: {citation.detail}")
        )
    for citation in found:
        if citation.status == citations_module.RELATIVE_STATUS:
            warnings.append(
                Problem(
                    "citation-relative",
                    f"{citation.text} inherits the previous document and was not resolved",
                )
            )

    for phase in PHASE_PLAN:
        entry = state["phases"].get(phase.id) or {}
        answer = entry.get("answer") or ""
        if answer and not citations_module.extract(answer):
            warnings.append(
                Problem(
                    "phase-uncited",
                    f"phase {phase.id} ({phase.title}) makes claims without citing a document",
                )
            )

    return Coverage(problems=problems, warnings=warnings, citations=found)


def assemble(state: dict, model: ProtocolModel, manifest: dict) -> str:
    """Render the audited answers into the report, following the protocol's own numbering."""
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Formal Audit Report",
        "",
        f"- Protocol: `{model.source}`",
        f"- Protocol SHA-256: `{model.sha256}`",
        f"- Frozen set: `{manifest['root']}`",
        f"- Generated: {generated}",
        "",
        "## Frozen documents",
        "",
        "| Document | Path | Format | Lines | SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in manifest["documents"]:
        if entry["status"] != "resolved":
            lines.append(f"| {entry['canonical']} | {entry['status']} | — | — | — |")
            continue
        lines.append(
            f"| {entry['canonical']} | {entry['path']} | {entry['format']} | "
            f"{entry['lines']} | `{(entry['sha256'] or '')[:16]}` |"
        )
    lines.append("")

    verdict = state.get("verdict") or {}
    lines += [
        "## Determination",
        "",
        f"**Verdict:** {verdict.get('value')}",
        "",
        f"{verdict.get('justification') or ''}",
        "",
    ]

    for phase in PHASE_PLAN:
        entry = state["phases"].get(phase.id) or {}
        answer = entry.get("answer")
        if not answer:
            continue
        title = _section_title(model, phase.section)
        lines += [f"## {phase.section}. {title}", "", answer.strip(), "", "---", ""]

    return "\n".join(lines)


def _section_title(model: ProtocolModel, number: str) -> str:
    header = section_text(model, number).splitlines()[0]
    return header.lstrip("#").strip()
