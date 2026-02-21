from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QKeySequence
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
from domain.model import Node, sorted_children
from domain.persistence import load_spec, new_default_model, save_spec
from domain.transform import TransformError


class FocusOutTextEdit(QPlainTextEdit):
    def __init__(self, on_focus_out, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_focus_out = on_focus_out

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._on_focus_out()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SpecTree MVP")

        self.current_path: Path | None = None
        self.model = new_default_model()
        self.command_manager = CommandManager(self.model)
        self._loading_fields = False

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Title"])
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

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
        add_sibling_button = QPushButton("Add Sibling")
        add_sibling_button.clicked.connect(self.add_sibling)
        add_child_button = QPushButton("Add Child")
        add_child_button.clicked.connect(self.add_child)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_selected)
        button_row.addWidget(add_sibling_button)
        button_row.addWidget(add_child_button)
        button_row.addWidget(delete_button)

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
        self._refresh_tree()

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

        add_action("New", self.new_file)
        add_action("Open", self.open_file)
        add_action("Save", self.save_file, "Ctrl+S")
        add_action("Export", self.export_markdown)
        toolbar.addSeparator()
        add_action("Move Up", self.move_up)
        add_action("Move Down", self.move_down)
        add_action("Flatten", self.flatten_selected)
        add_action("Expand", self.expand_selected)
        toolbar.addSeparator()
        add_action("Undo", self.undo, "Ctrl+Z")
        add_action("Redo", self.redo, "Ctrl+Y")

        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence(Qt.Key_Delete))
        delete_action.triggered.connect(self.delete_selected)
        self.addAction(delete_action)

    def _selected_path(self) -> tuple[int, ...] | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return tuple(items[0].data(0, Qt.UserRole))

    def _refresh_tree(self, selected_path: tuple[int, ...] | None = None) -> None:
        self.tree.clear()

        def build(node: Node, parent_item: QTreeWidgetItem | None, path: tuple[int, ...]) -> None:
            item = QTreeWidgetItem([node.title])
            item.setData(0, Qt.UserRole, path)
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            for idx, child in enumerate(sorted(node.children, key=lambda n: n.sort_key)):
                build(child, item, path + (idx,))

        build(self.model.root, None, tuple())
        self.tree.expandAll()

        if selected_path is None:
            selected_path = tuple()

        item = self._find_item_by_path(selected_path)
        if item is None:
            item = self._find_item_by_path(tuple())
        if item is not None:
            self.tree.setCurrentItem(item)

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
        path = self._selected_path()
        if path is None:
            return
        node = self.model.get_node(path)
        self._loading_fields = True
        self.title_edit.setText(node.title)
        self.content_edit.setPlainText(node.content)
        self.sensors_edit.setPlainText(node.sensors)
        self.actuators_edit.setPlainText(node.actuators)
        self.image_edit.setText(node.image)
        self.printable_check.setChecked(node.printable)
        self._loading_fields = False

    def _execute(self, command, keep_selection: tuple[int, ...] | None = None) -> None:
        try:
            self.command_manager.execute(command)
            self._refresh_tree(selected_path=keep_selection or self._selected_path())
        except (ValueError, IndexError, TransformError) as exc:
            QMessageBox.critical(self, "Operation failed", str(exc))

    def _commit_field(self, field_name: str, value) -> None:
        if self._loading_fields:
            return
        path = self._selected_path()
        if path is None:
            return
        node = self.model.get_node(path)
        if getattr(node, field_name) == value:
            return
        self._execute(UpdateFieldCommand(path=path, field_name=field_name, new_value=value), keep_selection=path)

    def add_sibling(self) -> None:
        path = self._selected_path()
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Root has no sibling.")
            return
        parent_path = path[:-1]
        insert_index = path[-1] + 1
        self._execute(CreateNodeCommand(parent_path=parent_path, insert_index=insert_index), keep_selection=parent_path + (insert_index,))

    def add_child(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        parent = self.model.get_node(path)
        insert_index = len(sorted_children(parent))
        self._execute(CreateNodeCommand(parent_path=path, insert_index=insert_index), keep_selection=path + (insert_index,))

    def delete_selected(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        if not path:
            QMessageBox.information(self, "Not allowed", "Root cannot be deleted.")
            return
        self._execute(DeleteNodeCommand(path=path), keep_selection=path[:-1])

    def move_up(self) -> None:
        path = self._selected_path()
        if path is None or not path:
            return
        idx = path[-1]
        if idx == 0:
            return
        parent_path = path[:-1]
        self._execute(MoveNodeCommand(path=path, new_parent_path=parent_path, new_index=idx - 1), keep_selection=parent_path + (idx - 1,))

    def move_down(self) -> None:
        path = self._selected_path()
        if path is None or not path:
            return
        parent = self.model.get_node(path[:-1])
        siblings = sorted_children(parent)
        idx = path[-1]
        if idx >= len(siblings) - 1:
            return
        parent_path = path[:-1]
        self._execute(MoveNodeCommand(path=path, new_parent_path=parent_path, new_index=idx + 1), keep_selection=parent_path + (idx + 1,))

    def flatten_selected(self) -> None:
        path = self._selected_path()
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Select a non-root node to flatten.")
            return
        self._execute(FlattenBranchToNodeCommand(path=path), keep_selection=path)

    def expand_selected(self) -> None:
        path = self._selected_path()
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Select a non-root node to expand.")
            return
        self._execute(ExpandNodeToBranchCommand(path=path), keep_selection=path)

    def undo(self) -> None:
        if self.command_manager.undo():
            self._refresh_tree(selected_path=self._selected_path())

    def redo(self) -> None:
        if self.command_manager.redo():
            self._refresh_tree(selected_path=self._selected_path())

    def new_file(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self.model = new_default_model()
        self.command_manager = CommandManager(self.model)
        self.current_path = None
        self._refresh_tree(tuple())

    def open_file(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open spec", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.model = load_spec(path)
            self.command_manager = CommandManager(self.model)
            self.current_path = Path(path)
            self._refresh_tree(tuple())
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_file(self) -> None:
        if self.current_path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save spec", "spec.json", "JSON (*.json)")
            if not path:
                return
            self.current_path = Path(path)
        try:
            save_spec(self.current_path, self.model)
            self.command_manager.is_dirty = False
        except OSError as exc:
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
            event.accept()
        else:
            event.ignore()
