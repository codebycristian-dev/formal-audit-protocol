"""Shared fixtures: a small but real audited set, and answers that satisfy the phase plan."""

from __future__ import annotations

import json
from pathlib import Path

from fap.freeze import freeze
from fap.phases import PHASE_PLAN, citation_code
from fap.protocol import compile_protocol
from fap.state import skeleton

SPEC = Path(__file__).resolve().parents[1] / "Formal Audit Protocol.md"

VERDICT = "Suitable with major corrective actions"

DOCUMENTS = {
    "zz_Workflow": """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Workflow}
The workflow defines five artefacts and three approval gates.
Every stage has an entry criterion and an exit criterion.
\\end{document}
""",
    "00_sdr_sensor_design": """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Design}
The design document instantiates the workflow requirements.
It names the measurands it expects the workflow to govern.
\\end{document}
""",
    "zV_AdmittedOutputValidity_SpectrumSensingFM0": """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Validity}
Admitted outputs are governed by the validity boundary.
The precedence order is stated for control purposes.
\\end{document}
""",
    "zX_CandidateFuture_SpectrumSensingFM0": """\\documentclass[12pt]{report}
\\begin{document}
\\chapter{Future}
Research archive and roadmap live here, apart from authority.
Nothing here is normative for the project.
\\end{document}
""",
}


def code_for(phase) -> str:
    return citation_code(phase.document) if phase.document else "zz"


def answer_for(phase, verdict: str = VERDICT) -> str:
    """An answer that satisfies the phase's required structure and cites frozen lines."""
    code = code_for(phase)
    lines: list[str] = []
    for requirement in phase.requirements:
        lines.append(f"### {requirement.label}")
        if phase.id == "10" and requirement.label == "Final Verdict":
            lines.append(f"{verdict} ({code}, líneas 1–2).")
        else:
            lines.append(f"Evidence for {requirement.label} ({code}, líneas 1–2).")
        for child in requirement.children:
            lines.append(f"#### {child}")
            lines.append(f"Detail for {child} ({code}, líneas 1–2).")
    return "\n".join(lines) + "\n"


def write_documents(root: Path, names: list[str] | None = None) -> None:
    for canonical in names or list(DOCUMENTS):
        path = root / canonical / f"{canonical}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DOCUMENTS[canonical])


def build_audit(root: Path, answers: bool = True, verdict: str = VERDICT) -> dict:
    """Create documents, a frozen manifest and an audit state inside ``root``."""
    model = compile_protocol(SPEC)
    write_documents(root)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    manifest = freeze(root, model, exclude=[audit_dir])
    (audit_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    state = skeleton(model)
    if answers:
        for phase in PHASE_PLAN:
            state["phases"][phase.id] = {
                "status": "complete",
                "answer": answer_for(phase, verdict),
                "citations": [],
            }
        state["verdict"] = {
            "value": verdict,
            "justification": "The frozen set and its citations support this determination.",
        }
    state_path = audit_dir / "audit.json"
    state_path.write_text(json.dumps(state, indent=2))
    return {
        "model": model,
        "manifest": manifest,
        "state": state,
        "state_path": state_path,
        "root": root,
        "audit_dir": audit_dir,
    }
