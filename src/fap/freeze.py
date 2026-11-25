"""Freeze an audited document set: resolve it, hash it, record what it really is.

An audit that cannot prove which bytes it read is not an audit. Freezing records, for
every document the protocol demands, the resolved path, the SHA-256 of the content, the
size, the line count and the real format (the audited files are LaTeX even when they are
named ``.md``). Nothing is repaired, converted or invented here: a missing document stays
missing and is recorded as such.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .protocol import ProtocolModel

DOC_SUFFIXES = ("", ".md", ".markdown", ".tex", ".txt", ".pdf")
EXCLUDED_SEGMENTS = ("Figures",)
SCHEMA = 1


def detect_format(path: str | Path) -> str:
    """Return ``pdf``, ``latex``, ``markdown`` or ``text`` for a document."""
    path = Path(path)
    with path.open("rb") as handle:
        head = handle.read(65536)
    if head.startswith(b"%PDF"):
        return "pdf"
    text = head.decode("utf-8", "replace")
    if "\\documentclass" in text or "\\begin{document}" in text:
        return "latex"
    if path.suffix.lower() in {".md", ".markdown"}:
        return "markdown"
    return "text"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_document(root: str | Path, canonical: str) -> list[Path]:
    """Find every file in the tree that claims to be the document ``canonical``."""
    root = Path(root)
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {suffix for suffix in DOC_SUFFIXES if suffix}:
            continue
        if path.stem != canonical:
            continue
        if any(part.startswith(".") or part in EXCLUDED_SEGMENTS for part in path.relative_to(root).parts):
            continue
        found.append(path)
    return sorted(found)


def freeze(root: str | Path, model: ProtocolModel, exclude: list[str | Path] | None = None) -> dict:
    """Build the manifest of the audited set described by the protocol.

    ``exclude`` names directories the caller owns (typically the output directory holding
    the manifest itself), so the tool's own artefacts are never mistaken for audited
    documents.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")
    excluded_dirs = [Path(path).resolve() for path in (exclude or [])]

    def owned(path: Path) -> bool:
        return any(directory == path or directory in path.parents for directory in excluded_dirs)

    documents = []
    used: set[Path] = set()
    for canonical in model.documents:
        matches = resolve_document(root, canonical)
        used.update(matches)
        entry: dict = {"canonical": canonical}
        if not matches:
            entry.update(
                status="missing", path=None, sha256=None, bytes=None, lines=None, format=None
            )
        elif len([path for path in matches if detect_format(path) != "pdf"]) > 1:
            entry.update(
                status="ambiguous",
                path=None,
                sha256=None,
                bytes=None,
                lines=None,
                format=None,
                candidates=[str(path.relative_to(root)) for path in matches],
            )
        else:
            # A PDF rendering of a readable source is not a second document: the readable
            # source is authoritative for citations, the rendering is recorded as such.
            readable = [path for path in matches if detect_format(path) != "pdf"]
            path = readable[0] if readable else matches[0]
            fmt = detect_format(path)
            entry.update(
                status="resolved",
                path=str(path.relative_to(root)),
                sha256=file_sha256(path),
                bytes=path.stat().st_size,
                lines=None if fmt == "pdf" else len(path.read_text(errors="replace").splitlines()),
                format=fmt,
                renderings=[
                    str(other.relative_to(root)) for other in matches if other != path
                ],
            )
        documents.append(entry)

    extras = [
        str(path.relative_to(root))
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in {suffix for suffix in DOC_SUFFIXES if suffix}
        and path not in used
        and not owned(path)
        and not any(
            part.startswith(".") or part in EXCLUDED_SEGMENTS
            for part in path.relative_to(root).parts
        )
    ]

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "protocol": {
            "source": str(Path(model.source).resolve()),
            "sha256": model.sha256,
            "slots": model.slot_ids(),
        },
        "documents": documents,
        "extra_files": extras,
    }
