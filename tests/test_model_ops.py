from __future__ import annotations

from domain.command_manager import CommandManager
from domain.commands import CreateNodeCommand, DeleteNodeCommand, MoveNodeCommand, UpdateFieldCommand
from domain.model import Node, SpecModel, sorted_children
from domain.persistence import load_spec, save_spec


def _base_model() -> SpecModel:
    return SpecModel(schema_version="1.0", root=Node(title="Root", sort_key=10.0, children=[]))


def test_root_cannot_be_deleted() -> None:
    model = _base_model()
    manager = CommandManager(model)

    try:
        manager.execute(DeleteNodeCommand(path=tuple()))
    except ValueError as exc:
        assert "Root cannot be deleted" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_cannot_move_node_into_own_subtree() -> None:
    model = _base_model()
    manager = CommandManager(model)

    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=Node(title="A")))
    manager.execute(CreateNodeCommand(parent_path=(0,), insert_index=0, node=Node(title="A1")))

    try:
        manager.execute(MoveNodeCommand(path=(0,), new_parent_path=(0, 0), new_index=0))
    except ValueError as exc:
        assert "own subtree" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_create_edit_save_reopen_roundtrip(tmp_path) -> None:
    model = _base_model()
    manager = CommandManager(model)
    manager.execute(CreateNodeCommand(parent_path=tuple(), insert_index=0, node=Node(title="Pump")))
    manager.execute(UpdateFieldCommand(path=(0,), field_name="content", new_value="Purpose"))
    manager.execute(UpdateFieldCommand(path=(0,), field_name="sensors", new_value="PT-101"))
    manager.execute(UpdateFieldCommand(path=(0,), field_name="actuators", new_value="V-201"))
    manager.execute(UpdateFieldCommand(path=(0,), field_name="image", new_value="pump-area"))
    manager.execute(UpdateFieldCommand(path=(0,), field_name="printable", new_value=False))

    path = tmp_path / "spec.json"
    save_spec(path, model)
    loaded = load_spec(path)

    node = sorted_children(loaded.root)[0]
    assert node.title == "Pump"
    assert node.content == "Purpose"
    assert node.sensors == "PT-101"
    assert node.actuators == "V-201"
    assert node.image == "pump-area"
    assert node.printable is False
