from __future__ import annotations

import json
from pathlib import Path

from domain.model import Node, SpecModel, node_from_dict, node_to_ordered_dict


DEFAULT_FILE_NAME = "spec.json"


class SaveWithoutLockError(PermissionError):
    pass


def new_default_model() -> SpecModel:
    root = Node(title="Root", sort_key=10.0)
    return SpecModel(schema_version="1.0", root=root)


def load_spec(path: str | Path) -> SpecModel:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_version = str(payload.get("schema_version", "1.0"))
    root_payload = payload.get("root")
    if not isinstance(root_payload, dict):
        raise ValueError("Invalid spec file: missing root object")
    root = node_from_dict(root_payload)
    return SpecModel(schema_version=schema_version, root=root)


def ensure_save_permitted(has_lock: bool) -> None:
    if not has_lock:
        raise SaveWithoutLockError("Save denied: file is read-only because it is locked by another instance.")


def save_spec(path: str | Path, model: SpecModel) -> None:
    payload = {
        "schema_version": model.schema_version,
        "root": node_to_ordered_dict(model.root),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text += "\n"
    Path(path).write_text(text, encoding="utf-8")
