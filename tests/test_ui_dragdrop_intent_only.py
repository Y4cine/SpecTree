from __future__ import annotations

import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _PortalockerStubLock:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def acquire(self) -> None:
        return None

    def release(self) -> None:
        return None


_portalocker_stub = types.ModuleType("portalocker")
_portalocker_stub.Lock = _PortalockerStubLock
_portalocker_stub.LOCK_EX = 0
_portalocker_stub.LOCK_NB = 0
_portalocker_stub.exceptions = types.SimpleNamespace(LockException=Exception)
sys.modules.setdefault("portalocker", _portalocker_stub)

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView

from app.ui_mainwindow import DragDropTreeWidget
from domain.model import Node


class _DummyMimeData:
    def __init__(self, has_expected_format: bool) -> None:
        self._has_expected_format = has_expected_format

    def hasFormat(self, _mime_type: str) -> bool:
        return self._has_expected_format


class _DummyDropEvent:
    def __init__(self, has_expected_format: bool = True) -> None:
        self._mime_data = _DummyMimeData(has_expected_format)
        self.ignored = False
        self.accepted = False
        self.drop_action = None

    def mimeData(self):
        return self._mime_data

    def pos(self):
        return None

    def ignore(self) -> None:
        self.ignored = True

    def setDropAction(self, action) -> None:
        self.drop_action = action

    def accept(self) -> None:
        self.accepted = True


class _DummySignal:
    def __init__(self, sink: list[tuple[object, object, int]]) -> None:
        self._sink = sink

    def emit(self, source, target, drop_position: int) -> None:
        self._sink.append((source, target, drop_position))


class _DummyItem:
    def __init__(self, node: Node, parent: object | None) -> None:
        self._node = node
        self._parent = parent

    def parent(self):
        return self._parent

    def data(self, _column: int, _role):
        return self._node


class _DropHost:
    _NODE_MIME_TYPE = DragDropTreeWidget._NODE_MIME_TYPE

    def __init__(self, source: Node, target_item: _DummyItem, emitted: list[tuple[object, object, int]]) -> None:
        self._drag_source_node = source
        self._target_item = target_item
        self.move_requested = _DummySignal(emitted)

    def itemAt(self, _pos):
        return self._target_item

    def dropIndicatorPosition(self):
        return QAbstractItemView.OnItem


def test_drop_event_emits_intent_and_ignores_qt_internal_move() -> None:
    source = Node(title="Source")
    target = Node(title="Target")

    emitted: list[tuple[object, object, int]] = []
    target_item = _DummyItem(node=target, parent=object())
    tree = _DropHost(source=source, target_item=target_item, emitted=emitted)

    event = _DummyDropEvent(has_expected_format=True)
    DragDropTreeWidget.dropEvent(tree, event)

    assert emitted == [(source, target, int(QAbstractItemView.OnItem))]
    assert event.accepted is True
    assert event.ignored is False
    assert event.drop_action == Qt.IgnoreAction
