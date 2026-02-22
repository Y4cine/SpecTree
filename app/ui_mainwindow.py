from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QMimeData, QSignalBlocker, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QDrag, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

from domain.command_manager import CommandManager
from domain.commands import (
    CreateNodeCommand,
    DeleteNodeCommand,
    ExpandNodeToBranchCommand,
    FlattenBranchToNodeCommand,
    MoveNodeCommand,
    UpdateFieldCommand,
)
from domain.export_md import export_markdown_file
from domain.file_lock import DocumentLock
from domain.model import Node, sorted_children
from domain.persistence import SaveWithoutLockError, ensure_save_permitted, load_spec, new_default_model, save_spec
from domain.transform import TransformError


logger = logging.getLogger(__name__)


class FocusOutTextEdit(QPlainTextEdit):
    def __init__(self, on_focus_out, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_focus_out = on_focus_out

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._on_focus_out()


class DragDropTreeWidget(QTreeWidget):
    move_requested = pyqtSignal(object, object, int)
    _NODE_MIME_TYPE = "application/x-spectree-node-ref"

    def __init__(self) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self._drag_source_node: object | None = None

    def startDrag(self, supportedActions) -> None:
        items = self.selectedItems()
        if len(items) != 1:
            return
        source_item = items[0]
        source_node = source_item.data(0, Qt.UserRole)
        if source_node is None or source_item.parent() is None:
            return
        self._drag_source_node = source_node
        try:
            drag = QDrag(self)
            mime = self.mimeData(items)
            if mime is None:
                mime = QMimeData()
            mime.setData(self._NODE_MIME_TYPE, b"node")
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)
        finally:
            self._drag_source_node = None

    def dragEnterEvent(self, event) -> None:
        if self._drag_source_node is not None:
            event.setDropAction(Qt.MoveAction)
            super().dragEnterEvent(event)
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._drag_source_node is not None:
            event.setDropAction(Qt.MoveAction)
            super().dragMoveEvent(event)
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        source_node = self._drag_source_node
        if source_node is None:
            event.ignore()
            return

        target_item = self.itemAt(event.pos())
        if target_item is None:
            self._drag_source_node = None
            event.ignore()
            return

        target_node = target_item.data(0, Qt.UserRole)
        if target_node is None:
            self._drag_source_node = None
            event.ignore()
            return
        drop_position = self.dropIndicatorPosition()

        logger.debug(
            "DnD drop received: source=%s target=%s position=%s",
            getattr(source_node, "title", None),
            getattr(target_node, "title", None),
            drop_position,
        )

        if drop_position == QAbstractItemView.OnItem:
            pass
        elif drop_position in (QAbstractItemView.AboveItem, QAbstractItemView.BelowItem):
            if target_item.parent() is None:
                self._drag_source_node = None
                event.ignore()
                return
        else:
            self._drag_source_node = None
            event.ignore()
            return

        logger.debug(
            "DnD accepted: source=%s target=%s drop_position=%s",
            getattr(source_node, "title", None),
            getattr(target_node, "title", None),
            drop_position,
        )

        self.move_requested.emit(source_node, target_node, int(drop_position))
        self._drag_source_node = None
        event.setDropAction(Qt.IgnoreAction)
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.base_title = "SpecTree MVP"
        self.setWindowTitle(self.base_title)

        self.current_path: Path | None = None
        self.model = new_default_model()
        self.command_manager = CommandManager(self.model)
        self.document_lock = DocumentLock()
        self.read_only_mode = False
        self._loading_fields = False

        self.tree = DragDropTreeWidget()
        self.tree.setHeaderLabels(["Title"])
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.move_requested.connect(self._on_tree_move_requested)

        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(lambda: self._commit_field("title", self.title_edit.text()))

        self.content_edit = FocusOutTextEdit(lambda: self._commit_field("content", self.content_edit.toPlainText()))
        self.sensors_edit = FocusOutTextEdit(lambda: self._commit_field("sensors", self.sensors_edit.toPlainText()))
        self.actuators_edit = FocusOutTextEdit(lambda: self._commit_field("actuators", self.actuators_edit.toPlainText()))

        self.image_edit = QLineEdit()
        self.image_edit.editingFinished.connect(lambda: self._commit_field("image", self.image_edit.text()))

        self.printable_check = QCheckBox("Printable")
        self.printable_check.toggled.connect(lambda value: self._commit_field("printable", bool(value)))

        editor_layout = QFormLayout()
        editor_layout.addRow("Title", self.title_edit)
        editor_layout.addRow("Content", self.content_edit)
        editor_layout.addRow("Sensors", self.sensors_edit)
        editor_layout.addRow("Actuators", self.actuators_edit)
        editor_layout.addRow("Image", self.image_edit)
        editor_layout.addRow("", self.printable_check)

        button_row = QHBoxLayout()
        self.add_sibling_button = QPushButton("Add Sibling")
        self.add_sibling_button.clicked.connect(self.add_sibling)
        self.add_child_button = QPushButton("Add Child")
        self.add_child_button.clicked.connect(self.add_child)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected)
        button_row.addWidget(self.add_sibling_button)
        button_row.addWidget(self.add_child_button)
        button_row.addWidget(self.delete_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addLayout(editor_layout)
        right_layout.addLayout(button_row)

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._mutating_widgets = [
            self.title_edit,
            self.content_edit,
            self.sensors_edit,
            self.actuators_edit,
            self.image_edit,
            self.printable_check,
            self.add_sibling_button,
            self.add_child_button,
            self.delete_button,
        ]
        self.statusBar()
        self._set_read_only_mode(False)
        self._refresh_tree()

    def _debug_domain_tree_lines(self) -> list[str]:
        lines: list[str] = []

        def walk(node: Node, depth: int) -> None:
            lines.append(f"{'  ' * depth}- {node.title}")
            for child in sorted_children(node):
                walk(child, depth + 1)

        walk(self.model.root, 0)
        return lines

    def _debug_ui_tree_lines(self) -> list[str]:
        lines: list[str] = []

        def walk(item: QTreeWidgetItem, depth: int) -> None:
            node = item.data(0, Qt.UserRole)
            lines.append(f"{'  ' * depth}- {item.text(0)} node={id(node)}")
            for index in range(item.childCount()):
                walk(item.child(index), depth + 1)

        root_item = self.tree.topLevelItem(0)
        if root_item is not None:
            walk(root_item, 0)
        return lines

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        def add_action(text: str, callback, shortcut: str | None = None) -> QAction:
            action = QAction(text, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            toolbar.addAction(action)
            return action

        self.new_action = add_action("New", self.new_file)
        self.open_action = add_action("Open", self.open_file)
        self.save_action = add_action("Save", self.save_file, "Ctrl+S")
        self.export_action = add_action("Export", self.export_markdown)
        toolbar.addSeparator()
        self.move_up_action = add_action("Move Up", self.move_up)
        self.move_down_action = add_action("Move Down", self.move_down)
        self.flatten_action = add_action("Flatten", self.flatten_selected)
        self.expand_action = add_action("Expand", self.expand_selected)
        toolbar.addSeparator()
        self.undo_action = add_action("Undo", self.undo, "Ctrl+Z")
        self.redo_action = add_action("Redo", self.redo, "Ctrl+Y")

        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence(Qt.Key_Delete))
        delete_action.triggered.connect(self.delete_selected)
        self.addAction(delete_action)
        self.delete_action = delete_action
        self._mutating_actions = [
            self.save_action,
            self.move_up_action,
            self.move_down_action,
            self.flatten_action,
            self.expand_action,
            self.delete_action,
        ]

    def _update_window_title(self) -> None:
        suffix = " [Read-only]" if self.read_only_mode else ""
        self.setWindowTitle(f"{self.base_title}{suffix}")

    def _set_read_only_mode(self, read_only: bool) -> None:
        self.read_only_mode = read_only
        for action in self._mutating_actions:
            action.setEnabled(not read_only)
        for widget in self._mutating_widgets:
            widget.setEnabled(not read_only)

        if read_only:
            self.statusBar().showMessage("READ-ONLY – File locked by another instance")
        else:
            self.statusBar().clearMessage()

        self._update_window_title()

    def _release_document_lock(self) -> None:
        self.document_lock.release()

    def _selected_node(self) -> Node | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        node = items[0].data(0, Qt.UserRole)
        if not isinstance(node, Node):
            return None
        return node

    def _path_for_node(self, target: Node | None) -> tuple[int, ...] | None:
        if target is None:
            return None

        def walk(node: Node, path: tuple[int, ...]) -> tuple[int, ...] | None:
            if node is target:
                return path
            for idx, child in enumerate(sorted_children(node)):
                found = walk(child, path + (idx,))
                if found is not None:
                    return found
            return None

        return walk(self.model.root, tuple())

    def _parent_and_index_for_node(self, target: Node | None) -> tuple[tuple[int, ...], int] | None:
        path = self._path_for_node(target)
        if path is None or not path:
            return None
        return path[:-1], path[-1]

    def _find_item_by_node(self, target: Node) -> QTreeWidgetItem | None:
        root = self.tree.topLevelItem(0)
        if root is None:
            return None

        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            item_node = item.data(0, Qt.UserRole)
            if item_node is target:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        return walk(root)

    def _refresh_tree(self, selected_node: Node | None = None) -> None:
        logger.debug("UI refresh start")
        with QSignalBlocker(self.tree):
            self.tree.clear()

            def build(node: Node, parent_item: QTreeWidgetItem | None, path: tuple[int, ...]) -> None:
                item = QTreeWidgetItem([node.title])
                item.setData(0, Qt.UserRole, node)
                if path:
                    item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
                else:
                    item.setFlags((item.flags() | Qt.ItemIsDropEnabled) & ~Qt.ItemIsDragEnabled)
                if parent_item is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                for idx, child in enumerate(sorted_children(node)):
                    build(child, item, path + (idx,))

            build(self.model.root, None, tuple())
            self.tree.expandAll()

            item = self._find_item_by_node(selected_node) if selected_node is not None else None
            if item is None:
                item = self.tree.topLevelItem(0)
            if item is not None:
                self.tree.setCurrentItem(item)

        logger.debug("Domain tree after refresh:\n%s", "\n".join(self._debug_domain_tree_lines()))
        logger.debug("UI tree after refresh:\n%s", "\n".join(self._debug_ui_tree_lines()))

    def _find_item_by_path(self, path: tuple[int, ...]) -> QTreeWidgetItem | None:
        root = self.tree.topLevelItem(0)
        if root is None:
            return None
        if not path:
            return root
        item = root
        for idx in path:
            if idx < 0 or idx >= item.childCount():
                return None
            item = item.child(idx)
        return item

    def _on_selection_changed(self) -> None:
        try:
            node = self._selected_node()
            if node is None:
                return
            self._loading_fields = True
            self.title_edit.setText(node.title)
            self.content_edit.setPlainText(node.content)
            self.sensors_edit.setPlainText(node.sensors)
            self.actuators_edit.setPlainText(node.actuators)
            self.image_edit.setText(node.image)
            self.printable_check.setChecked(node.printable)
        except (IndexError, ValueError, TypeError) as exc:
            logger.debug("Selection update skipped due to stale selection: %s", exc)
        finally:
            self._loading_fields = False

    def _on_tree_move_requested(self, source_node: Node, target_node: Node, drop_position: int) -> None:
        logger.debug(
            "Move requested: source=%s target=%s drop_position=%s",
            getattr(source_node, "title", None),
            getattr(target_node, "title", None),
            drop_position,
        )

        source_path = self._path_for_node(source_node)
        target_path = self._path_for_node(target_node)
        target_parent_and_index = self._parent_and_index_for_node(target_node)
        if source_path is None or target_path is None:
            return
        if not source_path:
            return

        if drop_position == int(QAbstractItemView.OnItem):
            new_parent_path = target_path
            new_index = len(sorted_children(target_node))
        elif drop_position == int(QAbstractItemView.AboveItem):
            if target_parent_and_index is None:
                return
            new_parent_path, target_index = target_parent_and_index
            new_index = target_index
        elif drop_position == int(QAbstractItemView.BelowItem):
            if target_parent_and_index is None:
                return
            new_parent_path, target_index = target_parent_and_index
            new_index = target_index + 1
        else:
            return

        if new_parent_path[: len(source_path)] == source_path:
            return

        normalized_index = new_index
        source_parent_path = source_path[:-1]
        source_index = source_path[-1]

        if source_parent_path == new_parent_path and source_index < normalized_index:
            normalized_index -= 1

        if source_parent_path == new_parent_path and source_index == normalized_index:
            return

        logger.debug(
            "Move normalized: source=%s new_parent=%s normalized_index=%s",
            source_path,
            new_parent_path,
            normalized_index,
        )

        self._execute(
            MoveNodeCommand(path=source_path, new_parent_path=new_parent_path, new_index=normalized_index),
            keep_selection_node=source_node,
        )

    def _execute(self, command, keep_selection_node: Node | None = None) -> None:
        if self.read_only_mode:
            QMessageBox.critical(self, "Read-only", "Cannot modify while file is locked by another instance.")
            return
        try:
            logger.debug(
                "Executing command: %s",
                command.__class__.__name__,
            )
            selected_before = self._selected_node()
            self.command_manager.execute(command)
            logger.debug("Executed command: %s", command.__class__.__name__)
            self._refresh_tree(selected_node=keep_selection_node or selected_before)
        except (ValueError, IndexError, TransformError) as exc:
            logger.debug("Command failed: %s error=%s", command.__class__.__name__, exc)
            QMessageBox.critical(self, "Operation failed", str(exc))

    def _commit_field(self, field_name: str, value) -> None:
        if self._loading_fields or self.read_only_mode:
            return
        node = self._selected_node()
        path = self._path_for_node(node)
        if path is None:
            return
        selected_node = node
        if getattr(node, field_name) == value:
            return
        self._execute(
            UpdateFieldCommand(path=path, field_name=field_name, new_value=value),
            keep_selection_node=selected_node,
        )

    def add_sibling(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Root has no sibling.")
            return
        parent_path = path[:-1]
        insert_index = path[-1] + 1
        self._execute(CreateNodeCommand(parent_path=parent_path, insert_index=insert_index))

    def add_child(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None:
            return
        parent = selected_node
        insert_index = len(sorted_children(parent))
        self._execute(CreateNodeCommand(parent_path=path, insert_index=insert_index))

    def delete_selected(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None:
            return
        if not path:
            QMessageBox.information(self, "Not allowed", "Root cannot be deleted.")
            return
        self._execute(DeleteNodeCommand(path=path))

    def move_up(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            return
        idx = path[-1]
        if idx == 0:
            return
        parent_path = path[:-1]
        self._execute(
            MoveNodeCommand(path=path, new_parent_path=parent_path, new_index=idx - 1),
            keep_selection_node=selected_node,
        )

    def move_down(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            return
        parent = self.model.get_node(path[:-1])
        siblings = sorted_children(parent)
        idx = path[-1]
        if idx >= len(siblings) - 1:
            return
        parent_path = path[:-1]
        self._execute(
            MoveNodeCommand(path=path, new_parent_path=parent_path, new_index=idx + 1),
            keep_selection_node=selected_node,
        )

    def flatten_selected(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Select a non-root node to flatten.")
            return
        self._execute(FlattenBranchToNodeCommand(path=path))

    def expand_selected(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Select a non-root node to expand.")
            return
        self._execute(ExpandNodeToBranchCommand(path=path))

    def undo(self) -> None:
        selected_node = self._selected_node()
        if self.command_manager.undo():
            logger.debug("Undo executed")
            self._refresh_tree(selected_node=selected_node)

    def redo(self) -> None:
        selected_node = self._selected_node()
        if self.command_manager.redo():
            logger.debug("Redo executed")
            self._refresh_tree(selected_node=selected_node)

    def new_file(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self._release_document_lock()
        self.model = new_default_model()
        self.command_manager = CommandManager(self.model)
        self.current_path = None
        self._set_read_only_mode(False)
        self._refresh_tree()

    def open_file(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open spec", "", "JSON (*.json)")
        if not path:
            return
        try:
            opened_model = load_spec(path)
            opened_path = Path(path)

            self._release_document_lock()
            has_lock = self.document_lock.acquire_for_path(opened_path)

            self.model = opened_model
            self.command_manager = CommandManager(self.model)
            self.current_path = opened_path
            self._set_read_only_mode(not has_lock)
            self._refresh_tree()
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_file(self) -> None:
        if self.current_path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save spec", "spec.json", "JSON (*.json)")
            if not path:
                return
            save_path = Path(path)
            if not self.document_lock.acquire_for_path(save_path):
                self.current_path = save_path
                self._set_read_only_mode(True)
                try:
                    ensure_save_permitted(False)
                except SaveWithoutLockError as exc:
                    QMessageBox.critical(self, "Save failed", str(exc))
                return
            self.current_path = save_path
            self._set_read_only_mode(False)
        try:
            ensure_save_permitted(self.document_lock.owns_lock)
            save_spec(self.current_path, self.model)
            self.command_manager.is_dirty = False
        except (OSError, SaveWithoutLockError) as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def export_markdown(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export markdown", "export.md", "Markdown (*.md)")
        if not path:
            return
        try:
            export_markdown_file(path, self.model.root, printable_only=False)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _confirm_discard_if_dirty(self) -> bool:
        if not self.command_manager.is_dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard_if_dirty():
            self._release_document_lock()
            event.accept()
        else:
            event.ignore()
