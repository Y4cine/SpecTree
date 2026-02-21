from __future__ import annotations

from pathlib import Path

from domain.model import Node


def export_markdown(root: Node, printable_only: bool = False) -> str:
    lines: list[str] = []

    def walk(node: Node, depth: int) -> None:
        include = (not printable_only) or node.printable
        if include:
            heading_depth = min(depth + 1, 6)
            lines.append(f"{'#' * heading_depth} {node.title}")
            if node.content:
                lines.append(node.content)
            lines.append("")

        for child in sorted(node.children, key=lambda n: n.sort_key):
            walk(child, depth + 1)

    walk(root, 0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def export_markdown_file(path: str | Path, root: Node, printable_only: bool = False) -> None:
    Path(path).write_text(export_markdown(root, printable_only=printable_only), encoding="utf-8")
