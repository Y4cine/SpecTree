from __future__ import annotations

from domain.command_manager import CommandManager
from domain.commands import (
    CreateNodeCommand,
    DeleteNodeCommand,
    ExpandNodeToBranchCommand,
    FlattenBranchToNodeCommand,
    MoveNodeCommand,
    UpdateFieldCommand,
)
from domain.model import Node, SpecModel, sorted_children


def _setup_model() -> tuple[SpecModel, CommandManager]:
    model = SpecModel(schema_version="1.0", root=Node(title="Root", sort_key=10.0, children=[]))
    return model, CommandManager(model)


def test_undo_redo_create_delete_update_move() -> None:
    model, manager = _setup_model()

    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=Node(title="A")))
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=1, node=Node(title="B")))
    assert [n.title for n in sorted_children(model.root)] == ["A", "B"]

    manager.execute(UpdateFieldCommand(path=(0,), field_name="title", new_value="A*") )
    assert sorted_children(model.root)[0].title == "A*"

    manager.execute(MoveNodeCommand(path=(0,), new_parent_path=tuple(), new_index=1))
    assert [n.title for n in sorted_children(model.root)] == ["B", "A*"]

    manager.execute(DeleteNodeCommand(path=(0,)))
    assert [n.title for n in sorted_children(model.root)] == ["A*"]

    assert manager.undo() is True
    assert [n.title for n in sorted_children(model.root)] == ["B", "A*"]

    assert manager.undo() is True
    assert [n.title for n in sorted_children(model.root)] == ["A*", "B"]

    assert manager.undo() is True
    assert [n.title for n in sorted_children(model.root)] == ["A", "B"]

    assert manager.redo() is True
    assert manager.redo() is True
    assert manager.redo() is True
    assert [n.title for n in sorted_children(model.root)] == ["A*"]


def test_undo_redo_flatten_expand() -> None:
    model, manager = _setup_model()
    src = Node(title="Machine", content="Purpose", sort_key=10.0)
    src.children.append(Node(title="Pump", content="Pump text", sort_key=10.0))
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=src))

    manager.execute(FlattenBranchToNodeCommand(path=(0,)))
    root_children = sorted_children(model.root)
    assert len(root_children) == 2
    assert root_children[1].children == []

    assert manager.undo() is True
    assert len(sorted_children(model.root)) == 1

    linear = Node(title="Linear", content="# Linear\nBody\n\n## Child\nChild body", sort_key=20.0)
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=1, node=linear))
    manager.execute(ExpandNodeToBranchCommand(path=(1,)))
    assert len(sorted_children(model.root)) == 3

    assert manager.undo() is True
    assert len(sorted_children(model.root)) == 2
