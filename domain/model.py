from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Tuple

CONTENT_TYPES = {"md", "typ", "adoc"}
DEFAULT_SORT_STEP = 10.0
MIN_SORT_GAP = 1e-6
NODE_KEY_ORDER = [
    "title",
    "content_type",
    "content",
    "sensors",
    "actuators",
    "image",
    "printable",
    "sort_key",
    "children",
]


@dataclass
class Node:
    title: str = "New Node"
    content_type: str = "md"
    content: str = ""
    sensors: str = ""
    actuators: str = ""
    image: str = ""
    printable: bool = True
    sort_key: float = DEFAULT_SORT_STEP
    children: list[Node] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.content_type not in CONTENT_TYPES:
            raise ValueError(f"Invalid content_type: {self.content_type}")
        if not isinstance(self.children, list):
            self.children = []

    def clone(self) -> Node:
        return Node(
            title=self.title,
            content_type=self.content_type,
            content=self.content,
            sensors=self.sensors,
            actuators=self.actuators,
            image=self.image,
            printable=self.printable,
            sort_key=self.sort_key,
            children=[child.clone() for child in self.children],
        )


@dataclass
class SpecModel:
    schema_version: str
    root: Node

    def get_node(self, path: tuple[int, ...]) -> Node:
        node = self.root
        for idx in path:
            node = sorted_children(node)[idx]
        return node

    def get_parent_and_index(self, path: tuple[int, ...]) -> tuple[Node, int]:
        if not path:
            raise ValueError("Root node has no parent")
        parent = self.get_node(path[:-1])
        index = path[-1]
        siblings = sorted_children(parent)
        if index < 0 or index >= len(siblings):
            raise IndexError("Path index out of range")
        return parent, index


def sorted_children(node: Node) -> list[Node]:
    node.children.sort(key=lambda n: n.sort_key)
    return node.children


def validate_not_moving_into_subtree(source: tuple[int, ...], target_parent: tuple[int, ...]) -> None:
    if target_parent[: len(source)] == source:
        raise ValueError("Cannot move a node into its own subtree")


def maybe_reindex_siblings(siblings: list[Node]) -> None:
    if len(siblings) < 2:
        return
    gaps = [siblings[i + 1].sort_key - siblings[i].sort_key for i in range(len(siblings) - 1)]
    if any(gap <= MIN_SORT_GAP for gap in gaps):
        for i, node in enumerate(siblings, start=1):
            node.sort_key = float(i * DEFAULT_SORT_STEP)


def assign_sort_key_for_insert(siblings: list[Node], insert_index: int) -> float:
    if not siblings:
        return DEFAULT_SORT_STEP
    if insert_index <= 0:
        first_key = siblings[0].sort_key
        return first_key - DEFAULT_SORT_STEP
    if insert_index >= len(siblings):
        return siblings[-1].sort_key + DEFAULT_SORT_STEP
    left = siblings[insert_index - 1].sort_key
    right = siblings[insert_index].sort_key
    return (left + right) / 2.0


def sort_key_after_source(siblings: list[Node], source_index: int) -> float:
    src = siblings[source_index]
    if source_index + 1 < len(siblings):
        nxt = siblings[source_index + 1]
        return (src.sort_key + nxt.sort_key) / 2.0
    return src.sort_key + DEFAULT_SORT_STEP


def node_to_ordered_dict(node: Node) -> dict[str, Any]:
    ordered: dict[str, Any] = {
        "title": node.title,
        "content_type": node.content_type,
        "content": node.content,
        "sensors": node.sensors,
        "actuators": node.actuators,
        "image": node.image,
        "printable": node.printable,
        "sort_key": int(node.sort_key) if float(node.sort_key).is_integer() else node.sort_key,
        "children": [node_to_ordered_dict(child) for child in sorted(node.children, key=lambda n: n.sort_key)],
    }
    return ordered


def node_from_dict(payload: dict[str, Any]) -> Node:
    children_raw = payload.get("children", [])
    if not isinstance(children_raw, list):
        children_raw = []
    node = Node(
        title=str(payload.get("title", "")),
        content_type=str(payload.get("content_type", "md")),
        content=str(payload.get("content", "")),
        sensors=str(payload.get("sensors", "")),
        actuators=str(payload.get("actuators", "")),
        image=str(payload.get("image", "")),
        printable=bool(payload.get("printable", True)),
        sort_key=float(payload.get("sort_key", DEFAULT_SORT_STEP)),
        children=[node_from_dict(child) for child in children_raw],
    )
    sorted_children(node)
    return node


def iter_subtree_with_depth(root: Node) -> Iterable[Tuple[int, Node]]:
    stack: list[tuple[int, Node]] = [(0, root)]
    while stack:
        depth, node = stack.pop()
        yield depth, node
        children = sorted(node.children, key=lambda n: n.sort_key)
        for child in reversed(children):
            stack.append((depth + 1, child))
