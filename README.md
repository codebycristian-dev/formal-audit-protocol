# Formal Audit Protocol

Tooling for executing the **Formal Audit Protocol** defined in
[`Formal Audit Protocol.md`](./Formal%20Audit%20Protocol.md).

The protocol specifies a repeatable audit of a document set that claims to define a
development methodology: it characterizes each document, analyzes the set as a whole,
extracts the methodology (inputs, outputs, roles, gates, verification and validation),
benchmarks it against the literature, rates its readiness, lists structural blockers, and
issues a final determination.

This tool exists so that the resulting report is **verifiable rather than persuasive**:
complete against the protocol's mandatory answers, closed against its vocabularies, anchored
to frozen bytes, and honest about what could not be verified.

## What it guarantees

| Guarantee | How |
| --- | --- |
| **Completeness** | The contract holds 7 mandatory answers and a 20-phase plan; every phase answer is validated against the headings the specification asks for |
| **Closure** | The verdict is one of four values, readiness one of four levels, gap types one of six, enforced at the door and again at the gate |
| **Anchoring** | Every citation `(document, líneas X–Y)` resolves against the frozen set, or the answer is refused and the report is not emitted |
| **Honesty about the unknown** | An item with nothing to report is answered `none`; unverifiable premises block the run instead of being filled with prose |
| **Refusal** | A missing document, two readable sources of one document, a PDF-only document, or two documents with identical content block the audit |

## Status

Complete: the protocol contract, the frozen set, the phase pipeline, citation verification,
the coverage gate and report assembly.

## Repository layout

```
Formal Audit Protocol.md   Protocol specification (source of truth, never modified)
fap                        Source-checkout launcher, no installation needed
src/fap/protocol.py        Compiles the specification into the contract, detects drift
src/fap/phases.py          The 20-phase plan, prompt rendering, answer validation
src/fap/freeze.py          Resolves and hashes the audited set into a manifest
src/fap/doctor.py          Diagnoses whether the frozen set can carry the audit
src/fap/state.py           The audit state: answers, verdict, aliases
src/fap/citations.py       Resolves (document, lines) citations against frozen bytes
src/fap/report.py          Coverage gate and report assembly
src/fap/cli.py             Command line interface
tests/                     Behavioural tests (stdlib unittest, no dependencies)
odd/tasks/fap-core.md      Feature specification, tasks and decisions
```

## Usage

Requires Python 3.11 or newer. No dependencies, no virtualenv, no network.

```bash
./fap protocol check                      # compile the contract, fail on any drift
./fap init <documents-dir> --out <audit-dir>
./fap doctor --manifest <audit-dir>/manifest.json
```

`init` freezes the set and creates `audit.json`. `doctor` exits `0` only when every
document the protocol demands is resolved and citable, and `1` otherwise, naming each
blocking reason.

Then, phase by phase:

```bash
./fap status --state <audit-dir>/audit.json
./fap phase prompt --phase A.1 --state <audit-dir>/audit.json --out a1.md
# answer a1.md with the headings the prompt lists, citing frozen line numbers
./fap phase ingest --phase A.1 --in a1.md --state <audit-dir>/audit.json
```

`ingest` refuses an answer that misses a required heading or cites lines that do not exist,
and it refuses before storing anything. Cross-document phases can embed document text:

```bash
./fap phase prompt --phase 4.1 --state <audit-dir>/audit.json \
  --include-doc zz_Workflow --include-doc 00 --out p41.md
```

Set the verdict from the protocol's own vocabulary, then emit the report:

```bash
./fap verdict --state <audit-dir>/audit.json \
  --value "Suitable with major corrective actions" \
  --justification "The measurand inventory is not established (§4.3)."

./fap cite check --report report.md --state <audit-dir>/audit.json
./fap report build --state <audit-dir>/audit.json --out report.md
```

`report build` runs the gate: it refuses while any phase is pending, when an answer no
longer satisfies its required structure, when the verdict is outside the vocabulary or
absent from the final determination, or when a citation does not resolve. Each emitted
report is recorded in `<audit-dir>/ledger.jsonl`.

Document citation codes are the part before the first underscore (`zz`, `00`, `zV`, `zX`);
the full canonical name also resolves.

## How the contract is enforced

The specification is read, never paraphrased. Every mandatory answer, closed vocabulary,
audited document name and phase anchor is located by an explicit anchor and compared against
the value this tool implements. Any difference is a drift error, so the tool cannot silently
keep auditing against an older reading of the protocol than the one on disk.

Citation checking verifies resolvability, not truth: a citation that points at real lines
still has to be read by a human. What it eliminates is the citation that points at nothing.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -t .
```

## Protocol outline

| Section | Subject |
| --- | --- |
| 1-2 | Objective, scope, exclusions |
| 3, Phase A | Per-document characterization (`A.1`-`A.4`) |
| 4 | Cross-document structural analysis: measurands, methodological sufficiency, gap analysis |
| 5 | Methodology extraction: inputs, outputs, roles, gates, V&V and evidence |
| 6 | Literature benchmark assessment |
| 7 | Readiness assessment: defined, decidable, executable, auditable |
| 8 | Structural blockers and deficiencies |
| 9 | Improvement roadmap: short, medium, long term |
| 10 | Final audit determination and verdict |

## License

Licensed under the Apache License, Version 2.0 — see [`LICENSE`](./LICENSE).

Copyright 2026 Cristian David Dorado Gomez.

The specification `Formal Audit Protocol.md` is the source of truth this tool executes; the
license covers the tooling, not the audited documents.
