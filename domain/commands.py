from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from domain.model import (
    Node,
    SpecModel,
    assign_sort_key_for_insert,
    maybe_reindex_siblings,
    sort_key_after_source,
    sorted_children,
    validate_not_moving_into_subtree,
)
from domain.transform import expand_markdown_to_branch, flatten_branch_to_node


class Command(Protocol):
    description: str

    def apply(self, model: SpecModel) -> None:
        raise NotImplementedError

    def rollback(self, model: SpecModel) -> None:
        raise NotImplementedError


@dataclass
class CreateNodeCommand:
    parent_path: tuple[int, ...]
    insert_index: int
    node: Node = field(default_factory=Node)
    description: str = "Create node"
    _created_path: tuple[int, ...] | None = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        parent = model.get_node(self.parent_path)
        siblings = sorted_children(parent)
        index = max(0, min(self.insert_index, len(siblings)))
        self.node.sort_key = assign_sort_key_for_insert(siblings, index)
        siblings.insert(index, self.node)
        maybe_reindex_siblings(siblings)
        sorted_children(parent)
        self._created_path = self.parent_path + (siblings.index(self.node),)

    def rollback(self, model: SpecModel) -> None:
        if self._created_path is None:
            return
        parent, _ = model.get_parent_and_index(self._created_path)
        siblings = sorted_children(parent)
        siblings.remove(self.node)
        sorted_children(parent)


@dataclass
class DeleteNodeCommand:
    path: tuple[int, ...]
    description: str = "Delete node"
    _deleted_node: Node | None = field(default=None, init=False)
    _parent_path: tuple[int, ...] | None = field(default=None, init=False)
    _index: int | None = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        if not self.path:
            raise ValueError("Root cannot be deleted")
        parent, index = model.get_parent_and_index(self.path)
        siblings = sorted_children(parent)
        self._deleted_node = siblings.pop(index)
        self._parent_path = self.path[:-1]
        self._index = index
        sorted_children(parent)

    def rollback(self, model: SpecModel) -> None:
        if self._deleted_node is None or self._parent_path is None or self._index is None:
            return
        parent = model.get_node(self._parent_path)
        siblings = sorted_children(parent)
        siblings.insert(self._index, self._deleted_node)
        maybe_reindex_siblings(siblings)
        sorted_children(parent)


@dataclass
class UpdateFieldCommand:
    path: tuple[int, ...]
    field_name: str
    new_value: Any
    description: str = "Update field"
    _old_value: Any = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        node = model.get_node(self.path)
        if self.field_name not in {"title", "content", "sensors", "actuators", "image", "printable"}:
            raise ValueError(f"Unsupported field for update: {self.field_name}")
        self._old_value = getattr(node, self.field_name)
        setattr(node, self.field_name, self.new_value)

    def rollback(self, model: SpecModel) -> None:
        node = model.get_node(self.path)
        setattr(node, self.field_name, self._old_value)


@dataclass
class MoveNodeCommand:
    path: tuple[int, ...]
    new_parent_path: tuple[int, ...]
    new_index: int
    description: str = "Move node"
    _node: Node | None = field(default=None, init=False)
    _old_parent_path: tuple[int, ...] | None = field(default=None, init=False)
    _old_index: int | None = field(default=None, init=False)
    _new_path: tuple[int, ...] | None = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        current_path = self._new_path if self._new_path is not None else self.path
        if not current_path:
            raise ValueError("Root cannot be moved")

        validate_not_moving_into_subtree(current_path, self.new_parent_path)
        old_parent, old_index = model.get_parent_and_index(current_path)
        old_siblings = sorted_children(old_parent)
        node = old_siblings.pop(old_index)

        new_parent = model.get_node(self.new_parent_path)
        new_siblings = sorted_children(new_parent)
        insert_index = max(0, min(self.new_index, len(new_siblings)))

        node.sort_key = assign_sort_key_for_insert(new_siblings, insert_index)
        new_siblings.insert(insert_index, node)
        maybe_reindex_siblings(new_siblings)
        sorted_children(new_parent)

        self._node = node
        self._old_parent_path = current_path[:-1]
        self._old_index = old_index
        self._new_path = self.new_parent_path + (new_siblings.index(node),)

    def rollback(self, model: SpecModel) -> None:
        if self._node is None or self._old_parent_path is None or self._old_index is None or self._new_path is None:
            return

        current_parent, current_index = model.get_parent_and_index(self._new_path)
        current_siblings = sorted_children(current_parent)
        node = current_siblings.pop(current_index)

        old_parent = model.get_node(self._old_parent_path)
        old_siblings = sorted_children(old_parent)
        insert_index = max(0, min(self._old_index, len(old_siblings)))
        node.sort_key = assign_sort_key_for_insert(old_siblings, insert_index)
        old_siblings.insert(insert_index, node)
        maybe_reindex_siblings(old_siblings)
        sorted_children(old_parent)
        self._new_path = self._old_parent_path + (old_siblings.index(node),)


@dataclass
class FlattenBranchToNodeCommand:
    path: tuple[int, ...]
    description: str = "Flatten branch to node"
    _inserted_path: tuple[int, ...] | None = field(default=None, init=False)
    _created_node: Node | None = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        if not self.path:
            raise ValueError("Root cannot be flattened as sibling result requires a parent")
        source = model.get_node(self.path)
        parent, source_index = model.get_parent_and_index(self.path)
        siblings = sorted_children(parent)
        new_key = sort_key_after_source(siblings, source_index)
        created = flatten_branch_to_node(source, new_key)
        siblings.insert(source_index + 1, created)
        maybe_reindex_siblings(siblings)
        sorted_children(parent)
        self._created_node = created
        self._inserted_path = self.path[:-1] + (siblings.index(created),)

    def rollback(self, model: SpecModel) -> None:
        if self._inserted_path is None or self._created_node is None:
            return
        parent, _ = model.get_parent_and_index(self._inserted_path)
        siblings = sorted_children(parent)
        siblings.remove(self._created_node)
        sorted_children(parent)


@dataclass
class ExpandNodeToBranchCommand:
    path: tuple[int, ...]
    description: str = "Expand node to branch"
    _inserted_path: tuple[int, ...] | None = field(default=None, init=False)
    _created_node: Node | None = field(default=None, init=False)

    def apply(self, model: SpecModel) -> None:
        if not self.path:
            raise ValueError("Root cannot be expanded as sibling result requires a parent")
        source = model.get_node(self.path)
        parent, source_index = model.get_parent_and_index(self.path)
        siblings = sorted_children(parent)
        new_key = sort_key_after_source(siblings, source_index)
        created = expand_markdown_to_branch(source, new_key)
        siblings.insert(source_index + 1, created)
        maybe_reindex_siblings(siblings)
        sorted_children(parent)
        self._created_node = created
        self._inserted_path = self.path[:-1] + (siblings.index(created),)

    def rollback(self, model: SpecModel) -> None:
        if self._inserted_path is None or self._created_node is None:
            return
        parent, _ = model.get_parent_and_index(self._inserted_path)
        siblings = sorted_children(parent)
        siblings.remove(self._created_node)
        sorted_children(parent)
