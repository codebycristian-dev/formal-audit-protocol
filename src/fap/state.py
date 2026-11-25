"""The audit state: one JSON file that records what has been answered and by whom.

The state is the ledger of the audit in progress. It is deliberately boring and readable:
every phase either has an answer or it does not, and the verdict is a value from the
protocol's closed vocabulary.
"""

from __future__ import annotations

import json
from pathlib import Path

from .phases import PHASE_PLAN, citation_code
from .protocol import ProtocolModel

SCHEMA = 1


def skeleton(model: ProtocolModel, manifest_path: str = "manifest.json") -> dict:
    return {
        "schema": SCHEMA,
        "protocol": {
            "source": str(Path(model.source).resolve()),
            "sha256": model.sha256,
        },
        "manifest": manifest_path,
        "phases": {
            phase.id: {"status": "pending", "answer": None} for phase in PHASE_PLAN
        },
        "verdict": {"value": None, "justification": None},
        "aliases": {},
    }


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def save(state: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def state_dir(path: str | Path) -> Path:
    return Path(path).resolve().parent


def manifest_for(state: dict, state_path: str | Path) -> dict:
    path = state_dir(state_path) / state["manifest"]
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text())


def aliases(state: dict, model: ProtocolModel) -> dict[str, str]:
    """Map citation codes to canonical document names.

    The convention used by the protocol's own reports is the part before the first
    underscore (``00``, ``zz``, ``zV``, ``zX``); the full canonical name also resolves.
    """
    mapping = {canonical: canonical for canonical in model.documents}
    for canonical in model.documents:
        mapping.setdefault(citation_code(canonical), canonical)
    for code, canonical in state.get("aliases", {}).items():
        mapping[code] = canonical
    return mapping


def documents_text(manifest: dict, root: Path, canonicals: list[str]) -> dict[str, str]:
    """Read the frozen text of the given documents, refusing unreadable ones."""
    by_name = {entry["canonical"]: entry for entry in manifest["documents"]}
    texts: dict[str, str] = {}
    for canonical in canonicals:
        entry = by_name.get(canonical)
        if entry is None:
            raise KeyError(f"{canonical} is not part of the audited set")
        if entry["status"] != "resolved":
            raise ValueError(f"{canonical} is {entry['status']} in the frozen set")
        if entry["format"] == "pdf":
            raise ValueError(f"{canonical} is PDF only; citations cannot be anchored")
        texts[canonical] = (Path(root) / entry["path"]).read_text(errors="replace")
    return texts


def hashes(manifest: dict) -> dict[str, str]:
    return {
        entry["canonical"]: entry["sha256"]
        for entry in manifest["documents"]
        if entry["sha256"]
    }
