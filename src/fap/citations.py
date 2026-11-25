"""Verify that citations resolve against the frozen bytes.

The protocol's reports cite evidence as ``(00, líneas 881 y 749–752)``. That citation is
only meaningful if those lines exist in the document that was actually audited. This module
resolves every citation to a frozen document and a real line range, and reports the ones it
cannot resolve instead of letting them pass as authority.

It checks resolvability, not truth: a citation that points at real lines still has to be
read by a human. What it eliminates is the citation that points at nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CITATION = re.compile(
    r"\(\s*(?P<doc>[A-Za-z0-9_]+)\s*,\s*(?:l[ií]neas?|lines?)\s+(?P<ranges>[^()\n]+?)\s*\)"
)
RELATIVE = re.compile(r"\(\s*(?:l[ií]neas?|lines?)\s+(?P<ranges>[0-9\s,yand–—\-]+?)\s*\)")
RANGE = re.compile(r"(?P<start>\d+)\s*(?:[–—\-]\s*(?P<end>\d+))?")
SEPARATOR = re.compile(r"\s*(?:,|;|\by\b|\band\b)\s*")

OK = "ok"
UNKNOWN_DOCUMENT = "unknown-document"
DOCUMENT_UNRESOLVED = "document-unresolved"
DOCUMENT_UNREADABLE = "document-unreadable"
OUT_OF_RANGE = "out-of-range"
UNPARSEABLE = "unparseable"
RELATIVE_STATUS = "relative"


@dataclass(frozen=True)
class Citation:
    text: str
    doc_code: str
    canonical: str | None
    ranges: tuple[tuple[int, int], ...]
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == OK

    @property
    def blocking(self) -> bool:
        return self.status not in (OK, RELATIVE_STATUS)


def parse_ranges(spec: str) -> tuple[tuple[int, int], ...] | None:
    ranges = []
    for token in SEPARATOR.split(spec):
        token = token.strip()
        if not token:
            continue
        match = RANGE.fullmatch(token)
        if match is None:
            return None
        start = int(match.group("start"))
        end = int(match.group("end")) if match.group("end") else start
        if start < 1 or end < start:
            return None
        ranges.append((start, end))
    return tuple(ranges) if ranges else None


def _spans(text: str):
    found = []
    for match in CITATION.finditer(text):
        found.append((match.start(), match.end(), match.group("doc"), match.group("ranges")))
    taken = [(start, end) for start, end, _, _ in found]
    for match in RELATIVE.finditer(text):
        if any(start <= match.start() < end for start, end in taken):
            continue
        found.append((match.start(), match.end(), "", match.group("ranges")))
    return sorted(found)


def extract(text: str) -> list[tuple[str, str, str]]:
    """Return ``(citation text, document code, ranges)`` in document order."""
    return [(text[start:end], doc, ranges) for start, end, doc, ranges in _spans(text)]


def check(text: str, manifest: dict, aliases: dict[str, str]) -> list[Citation]:
    """Resolve every citation in ``text`` against the frozen manifest."""
    by_canonical = {entry["canonical"]: entry for entry in manifest["documents"]}
    lower_aliases = {code.casefold(): canonical for code, canonical in aliases.items()}

    results: list[Citation] = []
    for raw, doc_code, ranges in extract(text):
        ranges_parsed = parse_ranges(ranges)
        if not doc_code:
            results.append(
                Citation(raw, "", None, ranges_parsed or (), RELATIVE_STATUS,
                         "relative citation: it inherits the previous document and cannot be resolved on its own")
            )
            continue
        if ranges_parsed is None:
            results.append(
                Citation(raw, doc_code, None, (), UNPARSEABLE, f"cannot read line ranges {ranges!r}")
            )
            continue

        canonical = aliases.get(doc_code) or lower_aliases.get(doc_code.casefold())
        if canonical is None:
            results.append(
                Citation(raw, doc_code, None, ranges_parsed, UNKNOWN_DOCUMENT,
                         f"{doc_code!r} is not one of the audited documents")
            )
            continue

        entry = by_canonical.get(canonical)
        if entry is None or entry["status"] != "resolved":
            status = entry["status"] if entry else "absent"
            results.append(
                Citation(raw, doc_code, canonical, ranges_parsed, DOCUMENT_UNRESOLVED,
                         f"{canonical} is {status} in the frozen set")
            )
            continue

        if entry["format"] == "pdf" or not entry["lines"]:
            results.append(
                Citation(raw, doc_code, canonical, ranges_parsed, DOCUMENT_UNREADABLE,
                         f"{canonical} has no citable lines ({entry['format']})")
            )
            continue

        limit = entry["lines"]
        bad = [(start, end) for start, end in ranges_parsed if end > limit]
        if bad:
            rendered = ", ".join(f"{start}–{end}" for start, end in bad)
            results.append(
                Citation(raw, doc_code, canonical, ranges_parsed, OUT_OF_RANGE,
                         f"{canonical} has {limit} lines; cited {rendered}")
            )
            continue

        results.append(Citation(raw, doc_code, canonical, ranges_parsed, OK, ""))

    return results


def failures(citations: list[Citation]) -> list[Citation]:
    return [citation for citation in citations if citation.blocking]


def summary(citations: list[Citation]) -> str:
    counts: dict[str, int] = {}
    for citation in citations:
        counts[citation.status] = counts.get(citation.status, 0) + 1
    return ", ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
