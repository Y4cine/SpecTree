from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QEvent, QMimeData, QSignalBlocker, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QDrag, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QFrame,
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
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QStyle,
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
    NAVIGATION_MODE = "NAVIGATION_MODE"
    EDIT_MODE = "EDIT_MODE"

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
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self.tree.move_requested.connect(self._on_tree_move_requested)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)

        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(lambda: self._commit_field("title", self.title_edit.text()))

        self.content_edit = FocusOutTextEdit(lambda: self._commit_field("content", self.content_edit.toPlainText()))
        self.sensors_edit = FocusOutTextEdit(lambda: self._commit_field("sensors", self.sensors_edit.toPlainText()))
        self.actuators_edit = FocusOutTextEdit(lambda: self._commit_field("actuators", self.actuators_edit.toPlainText()))
        self.content_edit.setTabChangesFocus(False)
        self.sensors_edit.setTabChangesFocus(False)
        self.actuators_edit.setTabChangesFocus(False)

        self.image_edit = QLineEdit()
        self.image_edit.editingFinished.connect(lambda: self._commit_field("image", self.image_edit.text()))

        self.printable_check = QCheckBox("Printable")
        self.printable_check.toggled.connect(lambda value: self._commit_field("printable", bool(value)))

        self._editor_field_frames: dict[QWidget, QFrame] = {}

        editor_layout = QFormLayout()
        editor_layout.addRow("Title", self._wrap_editor_field(self.title_edit))
        editor_layout.addRow("Content", self._wrap_editor_field(self.content_edit))
        editor_layout.addRow("Sensors", self._wrap_editor_field(self.sensors_edit))
        editor_layout.addRow("Actuators", self._wrap_editor_field(self.actuators_edit))
        editor_layout.addRow("Image", self._wrap_editor_field(self.image_edit))
        editor_layout.addRow("", self._wrap_editor_field(self.printable_check))

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

        self.tree_pane_frame = QFrame()
        self.tree_pane_frame.setObjectName("treePaneFrame")
        tree_pane_layout = QVBoxLayout(self.tree_pane_frame)
        tree_pane_layout.setContentsMargins(4, 4, 4, 4)
        tree_pane_layout.addWidget(self.tree)

        self.editor_pane_frame = QFrame()
        self.editor_pane_frame.setObjectName("editorPaneFrame")
        editor_pane_layout = QVBoxLayout(self.editor_pane_frame)
        editor_pane_layout.setContentsMargins(4, 4, 4, 4)
        editor_pane_layout.addWidget(right)

        splitter = QSplitter()
        splitter.addWidget(self.tree_pane_frame)
        splitter.addWidget(self.editor_pane_frame)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._editor_fields = [
            self.title_edit,
            self.content_edit,
            self.sensors_edit,
            self.actuators_edit,
            self.image_edit,
            self.printable_check,
        ]
        self._editor_pane_focus_widgets = [
            *self._editor_fields,
            self.add_sibling_button,
            self.add_child_button,
            self.delete_button,
        ]
        self._active_editor_widget = self.title_edit
        self._active_pane = "TREE"
        self.editor_mode = self.NAVIGATION_MODE

        for widget in [self.tree, *self._editor_pane_focus_widgets]:
            widget.installEventFilter(self)
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
        self._update_status_indicator()

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
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(toolbar)

        def add_action(text: str, callback, shortcut: str | list[str] | None = None) -> QAction:
            action = QAction(text, self)
            action.triggered.connect(callback)
            if isinstance(shortcut, str):
                action.setShortcut(QKeySequence(shortcut))
            elif shortcut:
                action.setShortcuts([QKeySequence(value) for value in shortcut])
            self._set_action_tooltip(action)
            toolbar.addAction(action)
            return action

        self.new_action = add_action("New", self.new_file)
        self.open_action = add_action("Open", self.open_file)
        self.save_action = add_action("Save", self.save_file, "Ctrl+S")
        self.export_action = add_action("Export", self.export_markdown)
        self.new_action.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.open_action.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.save_action.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_action.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        toolbar.addSeparator()
        self.move_up_action = add_action("Move Up", self.move_up, "Ctrl+Shift+Up")
        self.move_down_action = add_action("Move Down", self.move_down, "Ctrl+Shift+Down")
        self.flatten_action = add_action("Flatten", self.flatten_selected)
        self.expand_action = add_action("Expand", self.expand_selected)
        self.move_up_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.move_down_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.flatten_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.expand_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        toolbar.addSeparator()
        self.undo_action = add_action("Undo", self.undo, "Ctrl+Z")
        self.redo_action = add_action("Redo", self.redo, ["Ctrl+Y", "Ctrl+Shift+Z"])
        self.undo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.redo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))

        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence(Qt.Key_Delete))
        delete_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        delete_action.triggered.connect(self.delete_selected)
        self._set_action_tooltip(delete_action)
        self.tree.addAction(delete_action)
        self.delete_action = delete_action

        self.toggle_pane_action = QAction("Toggle Pane", self)
        self.toggle_pane_action.setShortcut(QKeySequence("Ctrl+Tab"))
        self.toggle_pane_action.setShortcutContext(Qt.ApplicationShortcut)
        self.toggle_pane_action.triggered.connect(self._toggle_pane_focus)
        self.addAction(self.toggle_pane_action)

        self._mutating_actions = [
            self.save_action,
            self.move_up_action,
            self.move_down_action,
            self.flatten_action,
            self.expand_action,
            self.delete_action,
        ]

    def _set_action_tooltip(self, action: QAction) -> None:
        shortcut = action.shortcut().toString(QKeySequence.NativeText).strip()
        if shortcut:
            action.setToolTip(f"{action.text()} ({shortcut})")
        else:
            action.setToolTip(action.text())

    def _wrap_editor_field(self, widget: QWidget) -> QFrame:
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(2, 2, 2, 2)
        frame_layout.addWidget(widget)
        self._editor_field_frames[widget] = frame
        return frame

    def _is_editor_input_widget(self, widget) -> bool:
        return widget in self._editor_fields

    def _is_editor_pane_widget(self, widget) -> bool:
        return widget in self._editor_pane_focus_widgets

    def _set_editor_mode(self, mode: str) -> None:
        if mode not in (self.NAVIGATION_MODE, self.EDIT_MODE):
            return
        self.editor_mode = mode
        self._update_status_indicator()

    def _set_active_pane(self, pane: str) -> None:
        self._active_pane = pane
        self._update_status_indicator()

    def _update_status_indicator(self) -> None:
        pane_text = "TREE" if self._active_pane == "TREE" else f"EDITOR ({self.editor_mode})"
        if self.read_only_mode:
            self.statusBar().showMessage(f"READ-ONLY – File locked by another instance | {pane_text}")
        else:
            self.statusBar().showMessage(pane_text)
        self._update_pane_highlights()
        self._update_editor_field_highlights()

    def _update_pane_highlights(self) -> None:
        inactive_style = "border: 1px solid #666666;"
        tree_active_style = "border: 3px solid #2563eb;"
        editor_inactive_style = "border: 1px solid #666666;"

        if self._active_pane == "TREE":
            self.tree_pane_frame.setStyleSheet(tree_active_style)
            self.editor_pane_frame.setStyleSheet(inactive_style)
            return

        self.tree_pane_frame.setStyleSheet(inactive_style)
        self.editor_pane_frame.setStyleSheet(editor_inactive_style)

    def _update_editor_field_highlights(self) -> None:
        neutral_style = "border: 1px solid transparent;"
        nav_style = "border: 2px solid #2563eb;"
        edit_style = "border: 2px solid #dc2626;"

        for frame in self._editor_field_frames.values():
            frame.setStyleSheet(neutral_style)

        if self._active_pane != "EDITOR":
            return
        if self._active_editor_widget not in self._editor_field_frames:
            return

        active_frame = self._editor_field_frames[self._active_editor_widget]
        if self.editor_mode == self.EDIT_MODE:
            active_frame.setStyleSheet(edit_style)
        else:
            active_frame.setStyleSheet(nav_style)

    def _focus_tree(self) -> None:
        self.tree.setFocus()
        self._set_active_pane("TREE")

    def _focus_editor_pane(self) -> None:
        if self._active_editor_widget not in self._editor_fields:
            self._active_editor_widget = self.title_edit
        self._active_editor_widget.setFocus()
        self._set_active_pane("EDITOR")
        self._set_editor_mode(self.NAVIGATION_MODE)

    def _toggle_pane_focus(self) -> None:
        focused_widget = self.focusWidget()
        if focused_widget is self.tree or (focused_widget is not None and self.tree.isAncestorOf(focused_widget)):
            self._focus_editor_pane()
            return
        self._focus_tree()

    def _focus_prev_editor_field(self) -> None:
        if self._active_editor_widget not in self._editor_fields:
            self._active_editor_widget = self.title_edit
        index = self._editor_fields.index(self._active_editor_widget)
        self._active_editor_widget = self._editor_fields[(index - 1) % len(self._editor_fields)]
        self._active_editor_widget.setFocus()

    def _focus_next_editor_field(self) -> None:
        if self._active_editor_widget not in self._editor_fields:
            self._active_editor_widget = self.title_edit
        index = self._editor_fields.index(self._active_editor_widget)
        self._active_editor_widget = self._editor_fields[(index + 1) % len(self._editor_fields)]
        self._active_editor_widget.setFocus()

    def _start_inline_tree_rename(self, node: Node) -> None:
        item = self._find_item_by_node(node)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        self.tree.editItem(item, 0)
        QTimer.singleShot(0, self._select_inline_tree_editor_text)

    def _select_inline_tree_editor_text(self) -> None:
        focused_widget = self.focusWidget()
        if isinstance(focused_widget, QLineEdit) and self.tree.isAncestorOf(focused_widget):
            focused_widget.selectAll()

    def _add_tree_sibling_below_and_rename(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None or not path:
            QMessageBox.information(self, "Not allowed", "Root has no sibling.")
            return
        created_node = Node()
        parent_path = path[:-1]
        insert_index = path[-1] + 1
        success = self._execute(
            CreateNodeCommand(parent_path=parent_path, insert_index=insert_index, node=created_node),
            keep_selection_node=created_node,
        )
        if success:
            self._start_inline_tree_rename(created_node)

    def _add_tree_child_and_rename(self) -> None:
        selected_node = self._selected_node()
        path = self._path_for_node(selected_node)
        if path is None:
            return
        created_node = Node()
        parent = selected_node
        insert_index = len(sorted_children(parent))
        success = self._execute(
            CreateNodeCommand(parent_path=path, insert_index=insert_index, node=created_node),
            keep_selection_node=created_node,
        )
        if success:
            self._start_inline_tree_rename(created_node)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.FocusIn:
            if watched is self.tree:
                self._set_active_pane("TREE")
            elif self._is_editor_pane_widget(watched):
                if self._is_editor_input_widget(watched):
                    self._active_editor_widget = watched
                else:
                    self._active_editor_widget = None
                if self._active_pane != "EDITOR":
                    self._set_editor_mode(self.NAVIGATION_MODE)
                self._set_active_pane("EDITOR")

        if event.type() != QEvent.KeyPress:
            return super().eventFilter(watched, event)

        modifiers = event.modifiers()
        key = event.key()

        if modifiers & Qt.ControlModifier and key in (Qt.Key_Tab, Qt.Key_Backtab):
            self._toggle_pane_focus()
            return True

        if watched is self.tree:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._add_tree_sibling_below_and_rename()
                return True
            if event.key() == Qt.Key_Insert:
                self._add_tree_child_and_rename()
                return True
            if event.key() == Qt.Key_F2:
                selected_node = self._selected_node()
                if selected_node is not None:
                    self._start_inline_tree_rename(selected_node)
                return True

        if self._is_editor_input_widget(watched):
            if self.editor_mode == self.NAVIGATION_MODE:
                if key == Qt.Key_Up:
                    self._focus_prev_editor_field()
                    return True
                if key == Qt.Key_Down:
                    self._focus_next_editor_field()
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self._set_editor_mode(self.EDIT_MODE)
                    return True
            else:
                if key == Qt.Key_Escape:
                    self._set_editor_mode(self.NAVIGATION_MODE)
                    return True
                if (modifiers & Qt.ControlModifier) and key in (Qt.Key_Return, Qt.Key_Enter):
                    self._set_editor_mode(self.NAVIGATION_MODE)
                    return True

        return super().eventFilter(watched, event)

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        node = item.data(0, Qt.UserRole)
        if not isinstance(node, Node):
            return
        new_title = item.text(0)
        if node.title == new_title:
            return
        path = self._path_for_node(node)
        if path is None:
            return
        self._execute(
            UpdateFieldCommand(path=path, field_name="title", new_value=new_title),
            keep_selection_node=node,
        )

    def _update_window_title(self) -> None:
        suffix = " [Read-only]" if self.read_only_mode else ""
        self.setWindowTitle(f"{self.base_title}{suffix}")

    def _set_read_only_mode(self, read_only: bool) -> None:
        self.read_only_mode = read_only
        for action in self._mutating_actions:
            action.setEnabled(not read_only)
        for widget in self._mutating_widgets:
            widget.setEnabled(not read_only)

        self._update_status_indicator()

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
                    item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsEditable)
                else:
                    item.setFlags(((item.flags() | Qt.ItemIsDropEnabled | Qt.ItemIsEditable) & ~Qt.ItemIsDragEnabled))
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

    def _show_tree_context_menu(self, pos) -> None:
        target_item = self.tree.itemAt(pos)
        if target_item is None:
            return

        self.tree.setCurrentItem(target_item)
        target_node = target_item.data(0, Qt.UserRole)
        if not isinstance(target_node, Node):
            return

        target_path = self._path_for_node(target_node)
        if target_path is None:
            return

        is_root = len(target_path) == 0
        sibling_index = target_path[-1] if not is_root else -1

        if is_root:
            move_up_enabled = False
            move_down_enabled = False
            sibling_ops_enabled = False
        else:
            parent = self.model.get_node(target_path[:-1])
            sibling_count = len(sorted_children(parent))
            move_up_enabled = sibling_index > 0
            move_down_enabled = sibling_index < sibling_count - 1
            sibling_ops_enabled = True

        has_children = len(sorted_children(target_node)) > 0

        menu = QMenu(self)
        insert_menu = menu.addMenu("Insert")
        edit_menu = menu.addMenu("Edit")
        move_menu = menu.addMenu("Move")
        tools_menu = menu.addMenu("Tools")

        add_child_first_action = insert_menu.addAction("Add Child (as first child)")
        add_child_last_action = insert_menu.addAction("Add Child (as last child)")
        add_sibling_above_action = insert_menu.addAction("Add Sibling Above")
        add_sibling_below_action = insert_menu.addAction("Add Sibling Below")

        delete_action = edit_menu.addAction("Delete Node")

        move_up_action = move_menu.addAction("Move Up")
        move_down_action = move_menu.addAction("Move Down")

        flatten_action = tools_menu.addAction("Flatten Branch → Node")
        expand_action = tools_menu.addAction("Expand Node → Branch")

        add_sibling_above_action.setEnabled(sibling_ops_enabled)
        add_sibling_below_action.setEnabled(sibling_ops_enabled)
        delete_action.setEnabled(not is_root)
        move_up_action.setEnabled(move_up_enabled)
        move_down_action.setEnabled(move_down_enabled)
        flatten_action.setEnabled((not is_root) and has_children)
        expand_action.setEnabled(not is_root)

        selected_action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if selected_action is None:
            return

        if selected_action == add_child_first_action:
            created_node = Node()
            success = self._execute(
                CreateNodeCommand(parent_path=target_path, insert_index=0, node=created_node),
                keep_selection_node=created_node,
            )
            if success:
                self.title_edit.setFocus()
            return

        if selected_action == add_child_last_action:
            created_node = Node()
            success = self._execute(
                CreateNodeCommand(
                    parent_path=target_path,
                    insert_index=len(sorted_children(target_node)),
                    node=created_node,
                ),
                keep_selection_node=created_node,
            )
            if success:
                self.title_edit.setFocus()
            return

        if selected_action == add_sibling_above_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Root has no siblings.")
                return
            created_node = Node()
            success = self._execute(
                CreateNodeCommand(parent_path=target_path[:-1], insert_index=sibling_index, node=created_node),
                keep_selection_node=created_node,
            )
            if success:
                self.title_edit.setFocus()
            return

        if selected_action == add_sibling_below_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Root has no siblings.")
                return
            created_node = Node()
            success = self._execute(
                CreateNodeCommand(parent_path=target_path[:-1], insert_index=sibling_index + 1, node=created_node),
                keep_selection_node=created_node,
            )
            if success:
                self.title_edit.setFocus()
            return

        if selected_action == delete_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Root cannot be deleted.")
                return
            self._execute(DeleteNodeCommand(path=target_path))
            return

        if selected_action == move_up_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Root cannot be moved.")
                return
            self._execute(
                MoveNodeCommand(path=target_path, new_parent_path=target_path[:-1], new_index=sibling_index - 1),
                keep_selection_node=target_node,
            )
            return

        if selected_action == move_down_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Root cannot be moved.")
                return
            self._execute(
                MoveNodeCommand(path=target_path, new_parent_path=target_path[:-1], new_index=sibling_index + 1),
                keep_selection_node=target_node,
            )
            return

        if selected_action == flatten_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Select a non-root node to flatten.")
                return
            self._execute(FlattenBranchToNodeCommand(path=target_path), keep_selection_node=target_node)
            return

        if selected_action == expand_action:
            if is_root:
                QMessageBox.information(self, "Not allowed", "Select a non-root node to expand.")
                return
            self._execute(ExpandNodeToBranchCommand(path=target_path), keep_selection_node=target_node)
            return

    def _execute(self, command, keep_selection_node: Node | None = None) -> bool:
        if self.read_only_mode:
            QMessageBox.critical(self, "Read-only", "Cannot modify while file is locked by another instance.")
            return False
        try:
            logger.debug(
                "Executing command: %s",
                command.__class__.__name__,
            )
            selected_before = self._selected_node()
            self.command_manager.execute(command)
            logger.debug("Executed command: %s", command.__class__.__name__)
            self._refresh_tree(selected_node=keep_selection_node or selected_before)
            return True
        except (ValueError, IndexError, TransformError) as exc:
            logger.debug("Command failed: %s error=%s", command.__class__.__name__, exc)
            QMessageBox.critical(self, "Operation failed", str(exc))
            return False

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
