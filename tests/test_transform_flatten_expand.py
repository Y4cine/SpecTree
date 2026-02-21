from __future__ import annotations

import pytest

from domain.model import Node
from domain.transform import TransformError, expand_markdown_to_branch, flatten_branch_to_markdown


def test_flatten_branch_to_markdown_valid() -> None:
    root = Node(title="Machine A", content="Purpose")
    child = Node(title="Components", content="List", sort_key=10.0)
    grand = Node(title="Pump", content="Pump text", sort_key=10.0)
    child.children.append(grand)
    root.children.append(child)

    text = flatten_branch_to_markdown(root)
    assert "# Machine A" in text
    assert "## Components" in text
    assert "### Pump" in text


def test_flatten_aborts_when_depth_exceeds_6() -> None:
    node = Node(title="L1")
    cursor = node
    for i in range(2, 8):
        child = Node(title=f"L{i}")
        cursor.children.append(child)
        cursor = child

    with pytest.raises(TransformError):
        flatten_branch_to_markdown(node)


def test_expand_markdown_valid() -> None:
    source = Node(
        title="Linear",
        content_type="md",
        printable=False,
        content="# Root\nroot body\n\n## Child\nchild body\n\n### Leaf\nleaf body",
    )

    branch = expand_markdown_to_branch(source, sort_key=20.0)
    assert branch.title == "Root"
    assert branch.content == "root body"
    assert branch.printable is False
    assert branch.children[0].title == "Child"
    assert branch.children[0].children[0].title == "Leaf"


def test_expand_aborts_on_invalid_jump() -> None:
    source = Node(title="Linear", content="# Root\n\n### Skip")
    with pytest.raises(TransformError):
        expand_markdown_to_branch(source, sort_key=20.0)
