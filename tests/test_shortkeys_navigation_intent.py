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

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent

from app.ui_mainwindow import MainWindow
from domain.commands import CreateNodeCommand
from domain.model import Node


_app = QApplication.instance() or QApplication([])


def test_text_fields_keep_tab_for_content() -> None:
    window = MainWindow()
    try:
        assert window.content_edit.tabChangesFocus() is False
        assert window.sensors_edit.tabChangesFocus() is False
        assert window.actuators_edit.tabChangesFocus() is False
    finally:
        window.close()


def test_ctrl_tab_toggles_between_tree_and_editor_panes() -> None:
    window = MainWindow()
    try:
        created_node = Node()
        created = window._execute(
            CreateNodeCommand(parent_path=(), insert_index=0, node=created_node),
            keep_selection_node=created_node,
        )
        assert created is True

        window.tree.setFocus()
        window.toggle_pane_action.trigger()
        assert window._active_pane == "EDITOR"
        assert window.editor_mode == MainWindow.NAVIGATION_MODE

        window.toggle_pane_action.trigger()
        assert window._active_pane == "TREE"
        assert window.tree.hasFocus() is True
    finally:
        window.close()


def test_read_only_disables_mutating_shortcut_actions() -> None:
    window = MainWindow()
    try:
        window._set_read_only_mode(True)

        assert window.save_action.isEnabled() is False
        assert window.move_up_action.isEnabled() is False
        assert window.delete_action.isEnabled() is False
    finally:
        window.close()


def test_tree_enter_and_insert_create_nodes_with_default_title() -> None:
    window = MainWindow()
    try:
        first_child = Node()
        ok = window._execute(
            CreateNodeCommand(parent_path=(), insert_index=0, node=first_child),
            keep_selection_node=first_child,
        )
        assert ok is True

        enter_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        handled_enter = window.eventFilter(window.tree, enter_event)
        assert handled_enter is True
        assert len(window.model.root.children) == 2

        selected_after_enter = window._selected_node()
        assert selected_after_enter is not None
        assert selected_after_enter.title == "New Node"

        insert_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Insert, Qt.NoModifier)
        handled_insert = window.eventFilter(window.tree, insert_event)
        assert handled_insert is True

        selected_after_insert = window._selected_node()
        assert selected_after_insert is not None
        assert selected_after_insert.title == "New Node"
        assert len(window.model.root.children) == 2
        assert len(window.model.root.children[1].children) == 1
        assert window.model.root.children[1].children[0].title == "New Node"
    finally:
        window.close()


def test_editor_mode_navigation_and_edit_transitions() -> None:
    window = MainWindow()
    try:
        window._focus_editor_pane()
        assert window.editor_mode == MainWindow.NAVIGATION_MODE

        enter_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        handled_enter = window.eventFilter(window.title_edit, enter_event)
        assert handled_enter is True
        assert window.editor_mode == MainWindow.EDIT_MODE

        ctrl_enter_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.ControlModifier)
        handled_ctrl_enter = window.eventFilter(window.title_edit, ctrl_enter_event)
        assert handled_ctrl_enter is True
        assert window.editor_mode == MainWindow.NAVIGATION_MODE

        down_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
        handled_down = window.eventFilter(window.title_edit, down_event)
        assert handled_down is True
        assert window._active_editor_widget is window.content_edit
    finally:
        window.close()
