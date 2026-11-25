"""Compile the Formal Audit Protocol specification into a machine-checkable contract.

The specification (``Formal Audit Protocol.md``) is the source of truth. This module does
not guess at its meaning: every slot, closed vocabulary and audited document name is
located by an explicit anchor and then compared against the value the contract expects.
If the specification drifts, compilation fails loudly instead of silently producing a
thinner contract that would let an audit skip an inconvenient question.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(r"^(#{1,3})\s+(\d+(?:\.\d+)?|[A-Z]\.\d+)\.?\s+(.+?)\s*$")
MARKERS = ("Required Finding", "Required Output", "Required Determination")
FINAL_ANCHOR = "Provide a final integrated assessment"

# The contract this tool implements. Any difference between these values and the
# specification is a drift error, never a silent adjustment.
EXPECTED_SLOTS = {
    "4.1": ("Required Finding", "Is the compliance-relevant measurand set properly specified?"),
    "4.2": ("Required Finding", "Can the audited document quartet serve as"),
    "4.3": ("Required Output", "Provide recommendations for establishing a complete"),
    "4.4": ("Required Finding", "Do the attached files materially contribute"),
    "6": ("Required Finding", "Have methodologies comparable to the proposed approach"),
    "7": ("Required Determination", "Provide an overall readiness rating and justify the rating."),
    "10": ("Final Determination", "Provide a final integrated assessment"),
}

EXPECTED_DOCUMENTS = [
    "zz_Workflow",
    "00_sdr_sensor_design",
    "zV_AdmittedOutputValidity_SpectrumSensingFM0",
    "zX_CandidateFuture_SpectrumSensingFM0",
]

EXPECTED_READINESS = ["Defined", "Decidable", "Executable", "Auditable"]

EXPECTED_VERDICT = [
    "Suitable without reservation",
    "Suitable with minor corrective actions",
    "Suitable with major corrective actions",
    "Not currently suitable",
]

EXPECTED_GAP_TYPES = ["Missing", "Ambiguous", "Implicit", "Conflicting", "Unowned", "Unverifiable"]


class ProtocolDriftError(Exception):
    """The specification no longer matches the contract this tool implements."""


@dataclass(frozen=True)
class Section:
    number: str
    title: str
    level: int
    line: int
    end_line: int


@dataclass(frozen=True)
class Slot:
    """One mandatory answer the report must contain."""

    id: str
    kind: str
    section: str
    prompt: str
    source_line: int


@dataclass(frozen=True)
class ProtocolModel:
    source: str
    sha256: str
    line_count: int
    sections: list[Section]
    slots: list[Slot]
    documents: list[str]
    exclusions: list[str]
    enums: dict[str, list[str]]
    text: str = ""

    def slot_ids(self) -> list[str]:
        return [slot.id for slot in self.slots]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "sha256": self.sha256,
            "line_count": self.line_count,
            "sections": [
                {
                    "number": s.number,
                    "title": s.title,
                    "level": s.level,
                    "line": s.line,
                    "end_line": s.end_line,
                }
                for s in self.sections
            ],
            "slots": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "section": s.section,
                    "prompt": s.prompt,
                    "source_line": s.source_line,
                }
                for s in self.slots
            ],
            "documents": list(self.documents),
            "exclusions": list(self.exclusions),
            "enums": {name: list(values) for name, values in self.enums.items()},
        }


def compile_protocol(path: str | Path) -> ProtocolModel:
    """Read the specification and return its contract, or raise ProtocolDriftError."""
    path = Path(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()

    sections = _sections(lines)
    slots = _slots(lines, sections)
    enums = {
        "documents": _documents(lines, sections),
        "readiness": _readiness(lines, sections),
        "verdict": _verdict(lines, sections),
        "gap_types": _gap_types(lines, sections),
    }
    return ProtocolModel(
        source=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        line_count=len(lines),
        sections=sections,
        slots=slots,
        documents=enums["documents"],
        exclusions=_exclusions(lines, sections),
        enums=enums,
        text=text,
    )


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _sections(lines: list[str]) -> list[Section]:
    found: list[tuple[str, str, int, int]] = []
    for index, text in enumerate(lines, start=1):
        match = HEADING.match(text)
        if match:
            found.append((match.group(2), match.group(3), len(match.group(1)), index))

    sections: list[Section] = []
    for position, (number, title, level, line) in enumerate(found):
        end = found[position + 1][3] - 1 if position + 1 < len(found) else len(lines)
        sections.append(Section(number=number, title=title, level=level, line=line, end_line=end))
    return sections


def _body(lines: list[str], sections: list[Section], number: str) -> list[tuple[int, str]]:
    for section in sections:
        if section.number == number:
            return [(n, lines[n - 1]) for n in range(section.line + 1, section.end_line + 1)]
    raise ProtocolDriftError(f"section {number} is missing from the specification")


def _next_content(lines: list[str], after: int) -> tuple[str, int]:
    for number in range(after + 1, len(lines) + 1):
        text = lines[number - 1].strip()
        if text:
            return text, number
    raise ProtocolDriftError(f"a required marker at line {after} is followed by nothing")


def _slots(lines: list[str], sections: list[Section]) -> list[Slot]:
    found: dict[str, Slot] = {}
    for section in sections:
        markers = [
            (number, text.strip())
            for number, text in _body(lines, sections, section.number)
            if text.strip() in MARKERS
        ]
        if len(markers) > 1:
            raise ProtocolDriftError(
                f"section {section.number} declares {len(markers)} required markers; "
                "the contract expects at most one"
            )
        if markers:
            number, kind = markers[0]
            prompt, prompt_line = _next_content(lines, number)
            found[section.number] = Slot(
                id=section.number,
                kind=kind,
                section=section.title,
                prompt=prompt,
                source_line=prompt_line,
            )

    for number, text in _body(lines, sections, "10"):
        if text.strip().startswith(FINAL_ANCHOR) and "10" not in found:
            found["10"] = Slot(
                id="10",
                kind="Final Determination",
                section="Final Audit Determination",
                prompt=text.strip(),
                source_line=number,
            )
            break

    missing = sorted(set(EXPECTED_SLOTS) - set(found))
    if missing:
        raise ProtocolDriftError(
            "required slot missing in section "
            + ", ".join(missing)
            + ": the specification no longer contains the expected "
            "Required Finding/Output/Determination marker"
        )
    unexpected = sorted(set(found) - set(EXPECTED_SLOTS))
    if unexpected:
        raise ProtocolDriftError(
            "unexpected required marker in section " + ", ".join(unexpected)
        )

    for slot_id, (kind, prefix) in EXPECTED_SLOTS.items():
        slot = found[slot_id]
        if slot.kind != kind:
            raise ProtocolDriftError(
                f"slot {slot_id}: expected {kind!r}, found {slot.kind!r}"
            )
        if not _normalise(slot.prompt).startswith(prefix):
            raise ProtocolDriftError(
                f"slot {slot_id}: prompt drifted; expected it to start with {prefix!r}, "
                f"found {slot.prompt!r}"
            )

    return [found[slot_id] for slot_id in EXPECTED_SLOTS]


def _require(name: str, values: list[str], expected: list[str]) -> None:
    if values != expected:
        raise ProtocolDriftError(
            f"enum {name!r} drifted from the specification: expected {expected}, found {values}"
        )


def _documents(lines: list[str], sections: list[Section]) -> list[str]:
    values = []
    for _, text in _body(lines, sections, "2.1"):
        match = re.match(r"^\d+\.\s+`([^`]+)`\s*$", text.strip())
        if match:
            values.append(match.group(1))
    _require("documents", values, EXPECTED_DOCUMENTS)
    return values


def _readiness(lines: list[str], sections: list[Section]) -> list[str]:
    values = [
        text.strip()
        for _, text in _body(lines, sections, "7")
        if re.fullmatch(r"[A-Z][a-z]+", text.strip())
    ]
    _require("readiness", values, EXPECTED_READINESS)
    return values


def _verdict(lines: list[str], sections: list[Section]) -> list[str]:
    body = _body(lines, sections, "10")
    start = None
    for position, (_, text) in enumerate(body):
        if text.strip() == "Select one of the following:":
            start = position
            break
    if start is None:
        raise ProtocolDriftError(
            "enum 'verdict' drifted from the specification: 'Select one of the following:' "
            "is missing from section 10"
        )

    # The options are written as a bare block of unpunctuated label lines; the first
    # punctuated line after them is the next instruction, not an option.
    values: list[str] = []
    for _, text in body[start + 1:]:
        stripped = text.strip()
        if not stripped:
            continue
        if stripped.endswith("."):
            break
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        values.append(stripped)
    _require("verdict", values, EXPECTED_VERDICT)
    return values


def _gap_types(lines: list[str], sections: list[Section]) -> list[str]:
    values = []
    for _, text in _body(lines, sections, "4.3"):
        match = re.fullmatch(r"(\w+) measurands\.", text.strip())
        if match:
            values.append(match.group(1))
    _require("gap_types", values, EXPECTED_GAP_TYPES)
    return values


def _exclusions(lines: list[str], sections: list[Section]) -> list[str]:
    values = []
    for _, text in _body(lines, sections, "2.2"):
        match = re.match(r"^\s*-\s+(.+?)\s*$", text)
        if match:
            values.append(match.group(1).replace("**", "").replace("`", "").strip())
    return values
