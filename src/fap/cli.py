"""Command line interface: compile the contract, freeze the set, run and assemble the audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import citations as citations_module
from . import state as state_module
from .doctor import diagnose
from .freeze import freeze
from .phases import PHASE_PLAN, phase_by_id, render_prompt, validate_answer, verify_phase_plan
from .protocol import ProtocolDriftError, compile_protocol
from .report import assemble, check_coverage

DEFAULT_PROTOCOL = "Formal Audit Protocol.md"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fap",
        description=(
            "Execute the Formal Audit Protocol: compile the specification into a contract, "
            "freeze the audited document set, render and validate each phase, verify every "
            "citation, and emit the report only when it can be defended."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    protocol = subcommands.add_parser("protocol", help="inspect the compiled protocol contract")
    protocol_sub = protocol.add_subparsers(dest="protocol_command", required=True)
    check = protocol_sub.add_parser("check", help="compile the specification and verify no drift")
    check.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    check.set_defaults(handler=_protocol_check)
    compile_ = protocol_sub.add_parser("compile", help="write the compiled contract as JSON")
    compile_.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    compile_.add_argument("--out", required=True)
    compile_.set_defaults(handler=_protocol_compile)

    init = subcommands.add_parser("init", help="freeze the set and create the audit state")
    init.add_argument("root", help="directory containing the audited documents")
    init.add_argument("--out", required=True, help="audit directory")
    init.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    init.set_defaults(handler=_init)

    freeze_command = subcommands.add_parser("freeze", help="re-freeze the audited document set")
    freeze_command.add_argument("root")
    freeze_command.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    freeze_command.add_argument("--out", required=True)
    freeze_command.set_defaults(handler=_freeze)

    doctor = subcommands.add_parser("doctor", help="report whether the frozen set can be audited")
    doctor.add_argument("--manifest", required=True)
    doctor.set_defaults(handler=_doctor)

    status = subcommands.add_parser("status", help="show which phases are answered")
    status.add_argument("--state", required=True)
    status.set_defaults(handler=_status)

    verdict = subcommands.add_parser("verdict", help="set the audit verdict from the closed vocabulary")
    verdict.add_argument("--state", required=True)
    verdict.add_argument("--value", required=True)
    verdict.add_argument("--justification", required=True)
    verdict.set_defaults(handler=_verdict)

    phase = subcommands.add_parser("phase", help="render a phase prompt or ingest its answer")
    phase_sub = phase.add_subparsers(dest="phase_command", required=True)
    prompt = phase_sub.add_parser("prompt", help="render the prompt for one phase")
    prompt.add_argument("--phase", required=True)
    prompt.add_argument("--state", required=True)
    prompt.add_argument("--include-doc", action="append", default=[])
    prompt.add_argument("--out", default=None)
    prompt.set_defaults(handler=_phase_prompt)
    ingest = phase_sub.add_parser("ingest", help="validate and store one phase answer")
    ingest.add_argument("--phase", required=True)
    ingest.add_argument("--in", dest="input", required=True)
    ingest.add_argument("--state", required=True)
    ingest.set_defaults(handler=_phase_ingest)

    cite = subcommands.add_parser("cite", help="verify citations against the frozen set")
    cite_sub = cite.add_subparsers(dest="cite_command", required=True)
    cite_check = cite_sub.add_parser("check", help="resolve every citation in a report")
    cite_check.add_argument("--report", required=True)
    cite_check.add_argument("--state", required=True)
    cite_check.set_defaults(handler=_cite_check)

    report = subcommands.add_parser("report", help="gate and assemble the audit report")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    build = report_sub.add_parser("build", help="emit the report if it passes the gate")
    build.add_argument("--state", required=True)
    build.add_argument("--out", required=True)
    build.set_defaults(handler=_report_build)

    return parser


def _load_contract(path: str):
    model = compile_protocol(Path(path))
    verify_phase_plan(model)
    return model


def _load_state(path: str):
    state_path = Path(path)
    if not state_path.is_file():
        raise FileNotFoundError(f"audit state not found: {state_path}")
    state = state_module.load(state_path)
    model = _load_contract(state["protocol"]["source"])
    if model.sha256 != state["protocol"]["sha256"]:
        raise ProtocolDriftError(
            "the specification changed after this audit was initialised "
            f"({state['protocol']['sha256'][:12]} -> {model.sha256[:12]}); re-initialise the audit"
        )
    manifest = state_module.manifest_for(state, state_path)
    return state, state_path, model, manifest


def _protocol_check(args) -> int:
    try:
        model = _load_contract(args.protocol)
    except ProtocolDriftError as error:
        print(f"protocol drift: {error}", file=sys.stderr)
        return 1

    print(f"specification: {model.source}")
    print(f"sha256:        {model.sha256}")
    print(f"sections:      {len(model.sections)}")
    print(f"slots:         {len(model.slots)} ({', '.join(model.slot_ids())})")
    for slot in model.slots:
        print(f"  {slot.id:<4} {slot.kind:<24} line {slot.source_line:<4} {slot.prompt}")
    for name in ("documents", "readiness", "verdict", "gap_types"):
        print(f"{name + ':':<15}{', '.join(model.enums[name])}")
    print(f"phases:        {len(PHASE_PLAN)} ({', '.join(phase.id for phase in PHASE_PLAN)})")
    print(f"exclusions:    {len(model.exclusions)}")
    return 0


def _protocol_compile(args) -> int:
    try:
        model = _load_contract(args.protocol)
    except ProtocolDriftError as error:
        print(f"protocol drift: {error}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = model.to_dict()
    payload["phases"] = [
        {
            "id": phase.id,
            "title": phase.title,
            "section": phase.section,
            "document": phase.document,
            "requirements": [
                {"label": requirement.label, "children": list(requirement.children)}
                for requirement in phase.requirements
            ],
        }
        for phase in PHASE_PLAN
    ]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(model.slots)} slots, {len(PHASE_PLAN)} phases)")
    return 0


def _init(args) -> int:
    try:
        model = _load_contract(args.protocol)
    except ProtocolDriftError as error:
        print(f"protocol drift: {error}", file=sys.stderr)
        return 1

    out = Path(args.out)
    try:
        manifest = freeze(args.root, model, exclude=[out])
    except NotADirectoryError as error:
        print(str(error), file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    state = state_module.skeleton(model)
    state_module.save(state, out / "audit.json")

    resolved = sum(1 for entry in manifest["documents"] if entry["status"] == "resolved")
    print(f"audit directory: {out}")
    print(f"frozen {resolved}/{len(manifest['documents'])} documents, "
          f"{len(PHASE_PLAN)} phases pending")
    report = diagnose(manifest, model)
    print(report.render())
    return 0 if report.ok else 1


def _freeze(args) -> int:
    try:
        model = _load_contract(args.protocol)
    except ProtocolDriftError as error:
        print(f"protocol drift: {error}", file=sys.stderr)
        return 1

    try:
        manifest = freeze(args.root, model, exclude=[Path(args.out)])
    except NotADirectoryError as error:
        print(str(error), file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    resolved = sum(1 for entry in manifest["documents"] if entry["status"] == "resolved")
    print(f"wrote {path}")
    print(f"resolved {resolved}/{len(manifest['documents'])} documents, "
          f"{len(manifest['extra_files'])} extra file(s)")
    return 0


def _doctor(args) -> int:
    path = Path(args.manifest)
    if not path.is_file():
        print(f"manifest not found: {path}", file=sys.stderr)
        return 2
    manifest = json.loads(path.read_text())

    try:
        model = _load_contract(manifest["protocol"]["source"])
    except (ProtocolDriftError, OSError) as error:
        print(f"cannot compile the frozen specification: {error}", file=sys.stderr)
        return 1

    if model.sha256 != manifest["protocol"]["sha256"]:
        print(
            "protocol drift: the specification changed after this set was frozen "
            f"({manifest['protocol']['sha256'][:12]} -> {model.sha256[:12]}); re-freeze the set",
            file=sys.stderr,
        )
        return 1

    report = diagnose(manifest, model)
    print(report.render())
    return report.exit_code


def _status(args) -> int:
    try:
        state, _, model, _ = _load_state(args.state)
    except (ProtocolDriftError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1

    complete = 0
    for phase in PHASE_PLAN:
        entry = state["phases"].get(phase.id) or {}
        answered = entry.get("status") == "complete" and entry.get("answer")
        complete += 1 if answered else 0
        print(f"[{'x' if answered else ' '}] {phase.id:<4} {phase.title}")

    verdict = state.get("verdict") or {}
    print()
    print(f"phases answered: {complete}/{len(PHASE_PLAN)}")
    print(f"verdict:         {verdict.get('value') or '(none)'}")
    print(f"protocol:        {model.sha256[:12]}")
    return 0 if complete == len(PHASE_PLAN) and verdict.get("value") else 1


def _verdict(args) -> int:
    try:
        state, state_path, model, _ = _load_state(args.state)
    except (ProtocolDriftError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.value not in model.enums["verdict"]:
        print(
            f"refused: {args.value!r} is not one of: " + ", ".join(model.enums["verdict"]),
            file=sys.stderr,
        )
        return 1
    if not args.justification.strip():
        print("refused: the verdict needs a justification", file=sys.stderr)
        return 1

    state["verdict"] = {
        "value": args.value,
        "justification": args.justification.strip(),
    }
    state_module.save(state, state_path)
    print(f"verdict: {args.value}")
    return 0


def _phase_prompt(args) -> int:
    try:
        state, state_path, model, manifest = _load_state(args.state)
        phase = phase_by_id(args.phase)
    except (ProtocolDriftError, FileNotFoundError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1

    root = Path(manifest["root"])
    wanted: list[str] = []
    if phase.document:
        wanted = [phase.document]
    else:
        mapping = state_module.aliases(state, model)
        for name in args.include_doc:
            canonical = mapping.get(name) or mapping.get(name.casefold())
            if canonical is None:
                print(f"unknown document {name!r}", file=sys.stderr)
                return 2
            wanted.append(canonical)

    try:
        texts = state_module.documents_text(manifest, root, wanted)
    except (KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    prompt = render_prompt(phase, model, texts, state_module.hashes(manifest))
    if args.out:
        Path(args.out).write_text(prompt)
        print(f"wrote {args.out} ({len(prompt.splitlines())} lines)")
    else:
        print(prompt)
    return 0


def _phase_ingest(args) -> int:
    try:
        state, state_path, model, manifest = _load_state(args.state)
        phase = phase_by_id(args.phase)
    except (ProtocolDriftError, FileNotFoundError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1

    answer_path = Path(args.input)
    if not answer_path.is_file():
        print(f"answer not found: {answer_path}", file=sys.stderr)
        return 2
    answer = answer_path.read_text()

    problems = validate_answer(phase, answer)
    if problems:
        for problem in problems:
            print(f"[FAIL] phase-incomplete: phase {phase.id}: {problem}", file=sys.stderr)
        print(f"refused: phase {phase.id} does not satisfy its required structure", file=sys.stderr)
        return 1

    mapping = state_module.aliases(state, model)
    found = citations_module.check(answer, manifest, mapping)
    blocking = citations_module.failures(found)
    for citation in blocking:
        print(f"[FAIL] citation-unresolved: {citation.text}: {citation.detail}", file=sys.stderr)
    if blocking:
        print(f"refused: phase {phase.id} cites lines that do not exist", file=sys.stderr)
        return 1

    state["phases"][phase.id] = {
        "status": "complete",
        "answer": answer,
        "citations": [
            {"text": citation.text, "document": citation.canonical, "status": citation.status}
            for citation in found
        ],
    }
    state_module.save(state, state_path)
    print(f"stored phase {phase.id} ({len(found)} citation(s), {len(answer.splitlines())} lines)")
    if not found:
        print("[WARN] phase-uncited: the answer cites no document", file=sys.stderr)
    return 0


def _cite_check(args) -> int:
    try:
        state, _, model, manifest = _load_state(args.state)
    except (ProtocolDriftError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 2

    found = citations_module.check(
        report_path.read_text(), manifest, state_module.aliases(state, model)
    )
    if not found:
        print("no citations found")
        return 0

    blocking = citations_module.failures(found)
    for citation in found:
        level = "PASS" if citation.ok else ("WARN" if not citation.blocking else "FAIL")
        detail = f" — {citation.detail}" if citation.detail else ""
        print(f"[{level}] {citation.text}{detail}")
    print()
    print(f"citations: {len(found)} ({citations_module.summary(found)})")
    print("RESULT: citations resolve" if not blocking else f"RESULT: {len(blocking)} unresolved")
    return 0 if not blocking else 1


def _report_build(args) -> int:
    try:
        state, state_path, model, manifest = _load_state(args.state)
    except (ProtocolDriftError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1

    coverage = check_coverage(state, model, manifest, state_module.aliases(state, model))
    if not coverage.ok:
        print(coverage.render())
        return 1

    text = assemble(state, model, manifest)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)

    ledger = state_module.state_dir(state_path) / "ledger.jsonl"
    with ledger.open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "event": "report-built",
                    "report": str(out),
                    "protocol_sha256": model.sha256,
                    "citations": len(coverage.citations),
                    "warnings": [warning.code for warning in coverage.warnings],
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    print(coverage.render())
    print(f"wrote {out} ({len(text.splitlines())} lines, "
          f"{len(coverage.citations)} citation(s))")
    return 0
