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

from app.ui_mainwindow import MainWindow


_app = QApplication.instance() or QApplication([])


def test_toolbar_is_icon_only_with_tooltips() -> None:
    window = MainWindow()
    try:
        assert window.new_action.icon().isNull() is False
        assert window.open_action.icon().isNull() is False
        assert window.save_action.icon().isNull() is False
        assert window.undo_action.icon().isNull() is False
        assert "Ctrl+Z" in window.undo_action.toolTip()
    finally:
        window.close()


def test_pane_highlight_changes_with_active_pane() -> None:
    window = MainWindow()
    try:
        window._set_active_pane("TREE")
        assert "3px" in window.tree_pane_frame.styleSheet()
        assert "1px" in window.editor_pane_frame.styleSheet()

        window._set_active_pane("EDITOR")
        window._set_editor_mode(MainWindow.NAVIGATION_MODE)
        assert "3px" in window.editor_pane_frame.styleSheet()
        assert "#2563eb" in window.editor_pane_frame.styleSheet()
    finally:
        window.close()


def test_editor_edit_mode_uses_red_border() -> None:
    window = MainWindow()
    try:
        window._set_active_pane("EDITOR")
        window._set_editor_mode(MainWindow.EDIT_MODE)
        assert "#dc2626" in window.editor_pane_frame.styleSheet()
    finally:
        window.close()
