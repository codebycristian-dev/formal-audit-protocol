# Feature: fap — an executable Formal Audit Protocol

The tool must make an audit produced under `Formal Audit Protocol.md` **verifiable** rather
than merely persuasive: complete against the protocol's mandatory answers, closed against
its vocabularies, anchored to frozen bytes, and honest about what it could not verify.

## Specs

S1. Verbatim request: "construyelo listo para entregar"
S2. Verbatim request: "cómo podemos construir la herramienta para que haga el propósito"
S3. Every mandatory answer of the protocol is a slot enforced by the compiled contract; the
    prompts are quoted verbatim from the specification:
    - §4.1 "Is the compliance-relevant measurand set properly specified?"
    - §4.2 "Can the audited document quartet serve as the methodological foundation for developing an SDR-based sensing system?"
    - §4.3 "Provide recommendations for establishing a complete, authoritative, and auditable measurand inventory within the existing workflow structure."
    - §4.4 "Do the attached files materially contribute to the previously audited methodology?"
    - §6 "Have methodologies comparable to the proposed approach for the design, implementation, governance, verification, and validation of SDR-based sensing systems been reported in the recent peer-reviewed technical literature?"
    - §7 "Provide an overall readiness rating and justify the rating."
    - §10 "Provide a final integrated assessment addressing the following question:"
S4. Protocol §7: levels `Defined`, `Decidable`, `Executable`, `Auditable`; per level
    "Assess compliance with the level. Cite supporting evidence. Identify deficiencies.
    Identify prerequisites for advancement."
S5. Protocol §10: "Select one of the following:" `Suitable without reservation`,
    `Suitable with minor corrective actions`, `Suitable with major corrective actions`,
    `Not currently suitable`; "Provide a concise justification for the selected verdict."
S6. Protocol §4.3: "Identify: Missing measurands. Ambiguous measurands. Implicit measurands.
    Conflicting measurands. Unowned measurands. Unverifiable measurands." and "For each
    identified gap: Describe the deficiency. Assess its impact. Identify affected artefacts.
    Recommend remediation."
S7. Every claim citing a document resolves against the frozen bytes: document + line range
    must exist in the frozen set, or the report is not emitted.
S8. The report is not emitted when a mandatory answer is missing or empty, a closed
    vocabulary is violated, or a citation does not resolve.
S9. Delivery: tests, README, no runtime dependencies, the specification is never modified.

## Tasks

| ID | Specs | Route | Commit |
| --- | --- | --- | --- |
| T1 | S3, S4, S6 | inline: phase plan, prompt rendering, answer validation | c1 |
| T2 | S7 | inline: citation extraction and resolution | c1 |
| T3 | S5, S8 | inline: coverage gate and report assembly | c1 |
| T4 | S5 | inline: verdict command, closed vocabulary at the door | c1 |
| T5 | S9 | inline: README, delivery | c2 |

## Log

L1: "construyelo listo para entregar"
L2: "cómo podemos construir la herramienta para que haga el propósito"
L3: Existing scaffold (protocol contract, freeze, doctor) predates this feature document and
    is recorded in Engram as `formal-audit-protocol/core`.
L4: Design decision: the phase plan is declared explicitly and each phase carries literal
    anchors from the specification; compilation fails if an anchor disappears. Uniform code
    path over clever parsing, because a silently thinner plan would defeat the purpose.
L5: Design decision: a phase answer may satisfy its sub-requirements by answering `none`,
    because the protocol's per-item questions do not apply when there is nothing to report.
L6: Verification: 96 tests green, re-run by the parent after the worker handoff; the worker's
    own claims were not accepted as evidence.
L7: Defects found while making the suite green: `compile_protocol` passed an undefined `text`
    to the model; a grouped requirement ended its own region at its first child, so every
    grouped answer looked empty; `CITATION` required numeric ranges, so unreadable ranges were
    skipped instead of reported; `detect_format` leaked a file handle.
L8: Rule added (not planned): a renamed phase section is drift. A section can keep all of its
    anchors while ceasing to be the subject the plan describes, so the plan title and the
    specification title must share their subject.
L9: Slice boundary: c1 holds T1-T4, 3497 authored changed lines in one commit. The CLI
    couples the modules, so any smaller split would produce a commit that does not build. The
    delivery shape (single PR or chained PR) is decided when publishing, not here.
L10: Delivery state: `feat/fap-core`, c1 `20c707a`, c2 `d4a50fb`. Pushing and opening a pull
    request remain the owner's decisions.
L11: License: the owner selected Apache-2.0. `LICENSE` is the canonical text from the system
    license directory, not a retyped copy.
