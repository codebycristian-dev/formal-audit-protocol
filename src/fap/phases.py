"""The phase plan: what every phase must produce, as a prompt and as a validation rule.

The protocol is a procedure with twenty mandatory sections. Each phase here declares the
headings its answer must contain, and literal anchors that must still exist in the
specification. Compilation fails if an anchor disappears, so the plan cannot quietly become
thinner than the document it claims to execute.

A phase answer satisfies a sub-requirement group by answering ``none`` only when the
protocol's per-item questions have nothing to apply to; that is recorded, not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import ProtocolDriftError, ProtocolModel


@dataclass(frozen=True)
class Requirement:
    label: str
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class Phase:
    id: str
    title: str
    section: str
    document: str | None
    requirements: tuple[Requirement, ...]
    anchors: tuple[str, ...]


def _reqs(*labels: str) -> tuple[Requirement, ...]:
    return tuple(Requirement(label) for label in labels)


def _grouped(parents: tuple[str, ...], children: tuple[str, ...]) -> tuple[Requirement, ...]:
    return tuple(Requirement(parent, children) for parent in parents)


MEASURAND_CHECKS = (
    "Compliance-relevant measurands are explicitly defined",
    "Definitions are unique and non-conflicting",
    "Measurands are traceable to project objectives",
    "Measurands have authoritative ownership",
    "Measurands possess clear acceptance criteria",
    "Measurands are operationally measurable",
)

SUFFICIENCY_CHECKS = (
    "Complete lifecycle coverage",
    "Governance coverage",
    "Verification coverage",
    "Validation coverage",
    "Evidence-generation coverage",
    "Change-control coverage",
    "Configuration-management coverage",
)

GAP_TYPES = ("Missing", "Ambiguous", "Implicit", "Conflicting", "Unowned", "Unverifiable")
GAP_CHILDREN = (
    "Describe the deficiency",
    "Assess its impact",
    "Identify affected artefacts",
    "Recommend remediation",
)

CONTRIBUTION_CHECKS = (
    "Extend the methodology",
    "Clarify project governance",
    "Strengthen traceability",
    "Introduce new compliance requirements",
    "Modify previous audit conclusions",
    "Improve verification or validation coverage",
)

READINESS_LEVELS = ("Defined", "Decidable", "Executable", "Auditable")
READINESS_CHILDREN = (
    "Compliance",
    "Supporting evidence",
    "Deficiencies",
    "Prerequisites for advancement",
)

DEFICIENCY_AREAS = (
    "Governance",
    "Technical execution",
    "Verification",
    "Validation",
    "Traceability",
    "Compliance",
    "Auditability",
    "Configuration management",
    "Change management",
    "Evidence production",
)
DEFICIENCY_CHILDREN = (
    "Describe the issue",
    "Assess severity",
    "Assess impact",
    "Identify affected artefacts",
    "Recommend corrective actions",
    "Estimate implementation priority",
)

PHASE_PLAN: tuple[Phase, ...] = (
    Phase(
        id="A.1",
        title="Workflow Characterization",
        section="A.1",
        document="zz_Workflow",
        requirements=_reqs(
            "Primary purpose",
            "Scope",
            "Governance role",
            "Key normative statements",
            "Relationship to the overall project methodology",
        ),
        anchors=("Primary purpose.", "Governance role.", "Key normative statements."),
    ),
    Phase(
        id="A.2",
        title="Project Design Characterization",
        section="A.2",
        document="00_sdr_sensor_design",
        requirements=_reqs(
            "Technical purpose",
            "Design responsibilities",
            "Engineering scope",
            "Relationship to zz_Workflow",
            "Mechanisms by which workflow requirements are instantiated",
        ),
        anchors=("Technical purpose.", "Engineering scope.", "workflow requirements are instantiated"),
    ),
    Phase(
        id="A.3",
        title="Project Boundary Characterization",
        section="A.3",
        document="zV_AdmittedOutputValidity_SpectrumSensingFM0",
        requirements=_reqs(
            "Authoritative function",
            "Boundary-setting role",
            "Admitted outputs",
            "Validity constraints",
            "Relationship to zz_Workflow",
            "Relationship to 00_sdr_sensor_design",
        ),
        anchors=("Authoritative function.", "Admitted outputs.", "Validity constraints.", "Relationship to:"),
    ),
    Phase(
        id="A.4",
        title="Research and Future Development Characterization",
        section="A.4",
        document="zX_CandidateFuture_SpectrumSensingFM0",
        requirements=_reqs(
            "Research and development role",
            "Technical archive function",
            "Future roadmap function",
            "Separation from authoritative project artefacts",
            "Relationship to the previously audited documents",
        ),
        anchors=(
            "Research and development role.",
            "Future roadmap function.",
            "Separation from authoritative project artefacts.",
        ),
    ),
    Phase(
        id="4.1",
        title="Compliance-Relevant Measurands",
        section="4.1",
        document=None,
        requirements=_reqs(*MEASURAND_CHECKS, "Required Finding"),
        anchors=(
            "Compliance-relevant measurands are explicitly defined.",
            "Measurands are operationally measurable.",
            "Is the compliance-relevant measurand set properly specified?",
        ),
    ),
    Phase(
        id="4.2",
        title="Methodological Sufficiency",
        section="4.2",
        document=None,
        requirements=_reqs(*SUFFICIENCY_CHECKS, "Required Finding"),
        anchors=(
            "Complete lifecycle coverage.",
            "Configuration-management coverage.",
            "Can the audited document quartet serve",
        ),
    ),
    Phase(
        id="4.3",
        title="Gap Analysis of Measurands",
        section="4.3",
        document=None,
        requirements=_grouped(GAP_TYPES, GAP_CHILDREN) + _reqs("Required Output"),
        anchors=("Missing measurands.", "Unverifiable measurands.", "Recommend remediation."),
    ),
    Phase(
        id="4.4",
        title="Contribution Analysis of Additional Files",
        section="4.4",
        document=None,
        requirements=_reqs(*CONTRIBUTION_CHECKS, "Required Finding"),
        anchors=(
            "Extend the methodology.",
            "Improve verification or validation coverage.",
            "Do the attached files materially contribute",
        ),
    ),
    Phase(
        id="5.1",
        title="Methodology Inputs",
        section="5.1",
        document=None,
        requirements=_reqs(
            "Governing contractual assumptions",
            "The general methodology contract",
            "Authoritative requirements",
            "Compliance-relevant measurands",
            "Constraints",
            "Assumptions",
            "Design drivers",
            "Boundary conditions",
        ),
        anchors=("Governing contractual assumptions.", "Boundary conditions."),
    ),
    Phase(
        id="5.2",
        title="Methodology Outputs",
        section="5.2",
        document=None,
        requirements=_reqs(
            "The complete five-artefact chain",
            "Gate decisions",
            "Approval records",
            "Change-control records",
            "Runtime records",
            "Audit records",
            "Evidence artefacts",
            "Verification artefacts",
            "Validation artefacts",
        ),
        anchors=("The complete five-artefact chain.", "Validation artefacts."),
    ),
    Phase(
        id="5.3",
        title="Roles and Authority",
        section="5.3",
        document=None,
        requirements=_reqs(
            "Responsible roles",
            "Accountable roles",
            "Approving authorities",
            "Governance authorities",
            "Escalation paths",
            "Decision ownership",
            "Change-control authority",
            "Acceptance authority",
        ),
        anchors=("Responsible roles.", "Acceptance authority."),
    ),
    Phase(
        id="5.4",
        title="Stages and Gates",
        section="5.4",
        document=None,
        requirements=_reqs(
            "Lifecycle stages",
            "Entry criteria",
            "Exit criteria",
            "Approval gates",
            "Rejection criteria",
            "Governance checkpoints",
            "Evidence requirements at each gate",
        ),
        anchors=("Lifecycle stages.", "Evidence requirements at each gate."),
    ),
    Phase(
        id="5.5",
        title="Verification, Validation, and Evidence",
        section="5.5",
        document=None,
        requirements=_grouped(
            ("Verification",),
            ("Verification procedures", "Verification artefacts", "Verification acceptance criteria"),
        )
        + _grouped(
            ("Validation",),
            ("Validation procedures", "Validation acceptance criteria", "Validity constraints"),
        )
        + _grouped(
            ("Evidence",),
            (
                "Evidence requirements",
                "Traceability requirements",
                "Auditability mechanisms",
                "Record-retention requirements",
            ),
        ),
        anchors=("Verification procedures.", "Record-retention requirements."),
    ),
    Phase(
        id="6",
        title="Literature Benchmark Assessment",
        section="6",
        document=None,
        requirements=_reqs(
            "Required Finding",
            "Comparable approaches",
            "Key similarities",
            "Key differences",
            "Novelty assessment",
        ),
        anchors=(
            "Have methodologies comparable",
            "Summarize comparable approaches.",
            "Assess the novelty of the audited methodology.",
        ),
    ),
    Phase(
        id="7",
        title="Methodology Readiness Assessment",
        section="7",
        document=None,
        requirements=_grouped(READINESS_LEVELS, READINESS_CHILDREN) + _reqs("Overall readiness rating"),
        anchors=(
            "Assess compliance with the level.",
            "Identify prerequisites for advancement.",
            "Provide an overall readiness rating and justify the rating.",
        ),
    ),
    Phase(
        id="8",
        title="Structural Blockers and Deficiencies",
        section="8",
        document=None,
        requirements=_grouped(DEFICIENCY_AREAS, DEFICIENCY_CHILDREN),
        anchors=("Identify all deficiencies affecting:", "Estimate implementation priority."),
    ),
    Phase(
        id="9.1",
        title="Short-Term Actions",
        section="9.1",
        document=None,
        requirements=_reqs("Methodological completeness", "Decision readiness", "Execution readiness"),
        anchors=("Methodological completeness.", "Execution readiness."),
    ),
    Phase(
        id="9.2",
        title="Medium-Term Actions",
        section="9.2",
        document=None,
        requirements=_reqs("Full traceability", "Governance maturity", "Comprehensive evidence generation"),
        anchors=("Full traceability.", "Comprehensive evidence generation."),
    ),
    Phase(
        id="9.3",
        title="Long-Term Actions",
        section="9.3",
        document=None,
        requirements=_reqs(
            "Sustained auditability",
            "Robust change management",
            "Compliance assurance",
            "Lifecycle maintainability",
        ),
        anchors=("Sustained auditability.", "Lifecycle maintainability."),
    ),
    Phase(
        id="10",
        title="Final Audit Determination",
        section="10",
        document=None,
        requirements=_reqs(
            "Strengths",
            "Weaknesses",
            "Residual Risks",
            "Corrective Actions",
            "Final Verdict",
            "Justification",
        ),
        anchors=(
            "Residual Risks",
            "Corrective Actions",
            "Final Verdict",
            "Provide a concise justification for the selected verdict.",
        ),
    ),
)

PHASES = {phase.id: phase for phase in PHASE_PLAN}

NONE_ANSWERS = {"none", "none identified", "none found", "n/a", "not applicable", "ninguno", "ninguna"}


def phase_by_id(phase_id: str) -> Phase:
    try:
        return PHASES[phase_id]
    except KeyError:
        raise KeyError(
            f"unknown phase {phase_id!r}; available: {', '.join(PHASES)}"
        ) from None


def section_text(model: ProtocolModel, number: str) -> str:
    for section in model.sections:
        if section.number == number:
            lines = model.text.splitlines()
            return "\n".join(lines[section.line - 1:section.end_line])
    raise ProtocolDriftError(f"section {number} is missing from the specification")


def verify_phase_plan(model: ProtocolModel) -> None:
    """Fail if any declared phase no longer matches the specification."""
    seen: set[str] = set()
    for phase in PHASE_PLAN:
        if phase.id in seen:
            raise ProtocolDriftError(f"phase {phase.id} is declared twice")
        seen.add(phase.id)
        text = section_text(model, phase.section)
        for anchor in phase.anchors:
            if anchor not in text:
                raise ProtocolDriftError(
                    f"phase {phase.id}: anchor {anchor!r} is missing from section {phase.section}"
                )
        title = next(
            (section.title for section in model.sections if section.number == phase.section),
            None,
        )
        if title is None or not _same_subject(phase.title, title):
            raise ProtocolDriftError(
                f"phase {phase.id}: section {phase.section} is now titled {title!r}; "
                f"the plan describes it as {phase.title!r}"
            )
        if phase.document is not None and phase.document not in model.documents:
            raise ProtocolDriftError(
                f"phase {phase.id}: document {phase.document!r} is not in the audited set"
            )


def _same_subject(planned: str, specified: str) -> bool:
    """Whether the specification's title still names the subject the plan describes.

    Short specifications name a group title (``Inputs``) where the plan adds its context
    (``Methodology Inputs``); containment in either direction is the equality that matters.
    A renamed section shares no such title and is drift.
    """
    planned = _normalise(planned)
    specified = _normalise(specified)
    return bool(specified) and (specified in planned or planned in specified)


def _label(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    while text.startswith("#"):
        text = text[1:]
    text = text.strip()
    if text.startswith("**") and text.endswith("**") and len(text) > 4:
        text = text[2:-2].strip()
    text = text.rstrip(":").strip().rstrip(".").strip()
    return text


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def _blocks(lines: list[str], known: set[str]) -> list[tuple[str, int, int]]:
    """Split the answer into blocks that start at a label the phase actually asked for.

    Only known labels bound a block: a content line is never mistaken for a heading, so a
    one-line answer under a heading stays a valid answer.
    """
    marks = [
        (_normalise(_label(line)), index)
        for index, line in enumerate(lines)
        if _normalise(_label(line)) in known
    ]
    blocks = []
    for position, (label, index) in enumerate(marks):
        end = marks[position + 1][1] if position + 1 < len(marks) else len(lines)
        blocks.append((label, index, end))
    return blocks


def _content(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start + 1:end]).strip()


def _is_none(content: str) -> bool:
    return _normalise(content).strip(" .:") in NONE_ANSWERS


def validate_answer(phase: Phase, answer: str) -> list[str]:
    """Return every requirement the answer fails to satisfy, as human-readable problems."""
    lines = answer.splitlines()
    known = {_normalise(requirement.label) for requirement in phase.requirements}
    for requirement in phase.requirements:
        known.update(_normalise(child) for child in requirement.children)
    marks = [
        (_normalise(_label(line)), index)
        for index, line in enumerate(lines)
        if _normalise(_label(line)) in known
    ]
    problems: list[str] = []

    for requirement in phase.requirements:
        key = _normalise(requirement.label)
        match = next((mark for mark in marks if mark[0] == key), None)
        if match is None:
            problems.append(f"missing heading: {requirement.label}")
            continue
        start = match[1]
        # A grouped requirement owns the blocks of its own children: its region ends at
        # the next label that is not one of them, so the group is neither empty nor
        # allowed to swallow the following requirement's answer.
        child_keys = {_normalise(child) for child in requirement.children}
        end = next(
            (index for label, index in marks if index > start and label not in child_keys),
            len(lines),
        )
        content = _content(lines, start, end)
        if not content:
            problems.append(f"empty answer under: {requirement.label}")
            continue
        if not requirement.children or _is_none(content):
            continue
        inner = lines[start + 1:end]
        inner_blocks = _blocks(inner, child_keys)
        for child in requirement.children:
            child_key = _normalise(child)
            child_match = next((block for block in inner_blocks if block[0] == child_key), None)
            if child_match is None:
                problems.append(f"missing under {requirement.label}: {child}")
            elif not _content(inner, child_match[1], child_match[2]):
                problems.append(f"empty under {requirement.label}: {child}")

    return problems


def _numbered(text: str) -> str:
    return "\n".join(f"{number:>5} | {line}" for number, line in enumerate(text.splitlines(), start=1))


def citation_code(canonical: str) -> str:
    return canonical.split("_")[0]


def render_prompt(
    phase: Phase,
    model: ProtocolModel,
    documents: dict[str, str] | None = None,
    hashes: dict[str, str] | None = None,
) -> str:
    """Render the prompt for one phase, with frozen line numbers so citations can be anchored."""
    documents = documents or {}
    hashes = hashes or {}
    parts = [f"# Phase {phase.id} — {phase.title}", ""]

    parts += ["## Protocol requirement (verbatim)", "", "```markdown", section_text(model, phase.section).strip(), "```", ""]

    if phase.document:
        if phase.document not in documents:
            raise KeyError(f"phase {phase.id} needs the frozen text of {phase.document}")
        parts += [
            f"## Document under audit: {phase.document}",
            f"sha256: {hashes.get(phase.document, 'unknown')}",
            "",
            "```text",
            _numbered(documents[phase.document]),
            "```",
            "",
        ]
    elif documents:
        for canonical, text in documents.items():
            parts += [
                f"## Document under audit: {canonical}",
                f"sha256: {hashes.get(canonical, 'unknown')}",
                "",
                "```text",
                _numbered(text),
                "```",
                "",
            ]

    parts += ["## Required structure", "", "Answer with exactly these headings, in this order, each followed by its content:", ""]
    for requirement in phase.requirements:
        parts.append(f"- {requirement.label}")
        for child in requirement.children:
            parts.append(f"  - {child}")
    parts.append("")

    code = citation_code(phase.document) if phase.document else "<document>"
    parts += [
        "## Citation rule",
        "",
        f"Every claim about a document must cite it as `({code}, líneas X–Y)` using the frozen "
        "line numbers above. A citation that does not resolve to real lines invalidates the "
        "answer, so cite only what you can locate.",
        "",
        "If a required item has nothing to report, answer `none` under that heading. Do not "
        "invent material to fill it.",
        "",
    ]
    return "\n".join(parts)
