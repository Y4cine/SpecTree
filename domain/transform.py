from __future__ import annotations

import re

from domain.model import DEFAULT_SORT_STEP, Node, iter_subtree_with_depth, sorted_children

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


class TransformError(ValueError):
    pass


def flatten_branch_to_markdown(source: Node) -> str:
    sections: list[str] = []
    for depth, node in iter_subtree_with_depth(source):
        if depth > 5:
            raise TransformError("Flatten aborted: subtree depth exceeds 6 heading levels")
        heading = "#" * (depth + 1)
        body = node.content
        if body:
            sections.append(f"{heading} {node.title}\n{body}")
        else:
            sections.append(f"{heading} {node.title}")
    return "\n\n".join(sections)


def flatten_branch_to_node(source: Node, sort_key: float) -> Node:
    return Node(
        title=source.title,
        content_type=source.content_type,
        content=flatten_branch_to_markdown(source),
        sensors="",
        actuators="",
        image="",
        printable=source.printable,
        sort_key=sort_key,
        children=[],
    )


def expand_markdown_to_branch(source: Node, sort_key: float) -> Node:
    lines = source.content.splitlines()
    root: Node | None = None
    stack: list[tuple[int, Node]] = []
    pending_content: list[str] = []

    def flush_content() -> None:
        if not stack:
            return
        node = stack[-1][1]
        node.content = "\n".join(pending_content).strip("\n")
        pending_content.clear()

    for line in lines:
        match = HEADING_RE.match(line)
        if not match:
            pending_content.append(line)
            continue

        flush_content()
        level = len(match.group(1))
        title = match.group(2).strip()

        if not stack:
            new_node = _new_empty_node(title, source, sort_key)
            root = new_node
            stack.append((level, new_node))
            continue

        prev_level = stack[-1][0]
        if level > prev_level + 1:
            raise TransformError("Expand aborted: heading level jump is greater than +1")

        while stack and stack[-1][0] >= level:
            stack.pop()

        if not stack:
            raise TransformError("Expand aborted: multiple top-level headings are not supported")

        parent = stack[-1][1]
        child_sort_key = float((len(parent.children) + 1) * DEFAULT_SORT_STEP)
        child = _new_empty_node(title, source, child_sort_key)
        parent.children.append(child)
        sorted_children(parent)
        stack.append((level, child))

    flush_content()

    if root is None:
        raise TransformError("Expand aborted: no valid heading found")

    return root


def _new_empty_node(title: str, source: Node, sort_key: float) -> Node:
    return Node(
        title=title,
        content_type=source.content_type,
        content="",
        sensors="",
        actuators="",
        image="",
        printable=source.printable,
        sort_key=sort_key,
        children=[],
    )
