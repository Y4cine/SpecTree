from __future__ import annotations

from domain.export_md import export_markdown
from domain.model import Node
from domain.persistence import load_spec, save_spec


def _tree() -> Node:
    root = Node(title="Root", content="R", sort_key=10.0)
    a = Node(title="A", content="A body", sort_key=20.0, printable=True)
    b = Node(title="B", content="B body", sort_key=10.0, printable=False)
    root.children.extend([a, b])
    return root


def test_markdown_export_deterministic() -> None:
    root = _tree()
    out1 = export_markdown(root, printable_only=False)
    out2 = export_markdown(root, printable_only=False)
    assert out1 == out2
    assert out1.index("## B") < out1.index("## A")


def test_markdown_export_printable_filter() -> None:
    root = _tree()
    out = export_markdown(root, printable_only=True)
    assert "## A" in out
    assert "## B" not in out


def test_json_save_deterministic(tmp_path) -> None:
    from domain.model import SpecModel

    model = SpecModel(schema_version="1.0", root=_tree())
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"

    save_spec(p1, model)
    loaded = load_spec(p1)
    save_spec(p2, loaded)

    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")
