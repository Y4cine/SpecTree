# Shortkeys

## Pane Switch
- Ctrl+Tab: toggle focus between Tree pane and Editor pane (global; must work even when a text widget has focus).
- The active pane frame is visually highlighted (implementation-defined; minimal acceptable: status bar text "TREE"/"EDITOR").

## Treeview (QTreeWidget)
- Enter: create sibling below current node with default values; immediately start inline rename (in-place edit) of the new node title.
- Ins: create child node (append as last child); immediately start inline rename.
- Arrow keys: keep Qt standard behavior (visible-order navigation, expand/collapse).
- F2: inline rename title of the selected node.

Inline rename requirements:
- The new node gets a default title (e.g. "New Node").
- Inline rename selects the full title text so typing overwrites it.
- No automatic switch to editor pane on creation.

## Editor pane
Editor has two modes: Navigation Mode and Edit Mode.
When the editor pane is activated (via pane switch or click), it enters Navigation Mode.

Ctrl+Tab (pane switch) works in both modes.

### Navigation Mode
- Up/Down: move focus between editor fields/widgets (in a fixed order).
- Enter: switch to Edit Mode of the active widget (focus goes inside the widget).

### Edit Mode
- Tab inserts a tab character / indentation (no focus change).
- Esc OR Ctrl+Enter: switch back to Navigation Mode (leave the widget but keep editor pane active).