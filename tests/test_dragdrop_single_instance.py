from __future__ import annotations

import pytest

from domain.command_manager import CommandManager
from domain.commands import CreateNodeCommand, MoveNodeCommand
from domain.model import Node, SpecModel, sorted_children


def _setup_model() -> tuple[SpecModel, CommandManager]:
    model = SpecModel(schema_version="1.0", root=Node(title="Root", sort_key=10.0, children=[]))
    manager = CommandManager(model)
    return model, manager


def test_reorder_within_siblings_and_undo_redo() -> None:
    model, manager = _setup_model()
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=Node(title="A")))
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=1, node=Node(title="B")))
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=2, node=Node(title="C")))

    manager.execute(MoveNodeCommand(path=(0,), new_parent_path=tuple(), new_index=2))
    assert [node.title for node in sorted_children(model.root)] == ["B", "C", "A"]

    assert manager.undo() is True
    assert [node.title for node in sorted_children(model.root)] == ["A", "B", "C"]

    assert manager.redo() is True
    assert [node.title for node in sorted_children(model.root)] == ["B", "C", "A"]


def test_move_as_child_and_undo_redo() -> None:
    model, manager = _setup_model()
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=Node(title="Parent")))
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=1, node=Node(title="Child")))

    manager.execute(MoveNodeCommand(path=(1,), new_parent_path=(0,), new_index=0))
    root_children = sorted_children(model.root)
    assert [node.title for node in root_children] == ["Parent"]
    assert [node.title for node in sorted_children(root_children[0])] == ["Child"]

    assert manager.undo() is True
    assert [node.title for node in sorted_children(model.root)] == ["Parent", "Child"]

    assert manager.redo() is True
    root_children = sorted_children(model.root)
    assert [node.title for node in root_children] == ["Parent"]
    assert [node.title for node in sorted_children(root_children[0])] == ["Child"]


def test_reject_move_into_own_subtree() -> None:
    model, manager = _setup_model()
    parent = Node(title="Parent")
    child = Node(title="Child")
    parent.children.append(child)
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=parent))

    with pytest.raises(ValueError):
        manager.execute(MoveNodeCommand(path=(0,), new_parent_path=(0, 0), new_index=0))
