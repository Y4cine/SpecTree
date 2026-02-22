# Addendum 004: Shortkeys & Navigation (Entwurf als Markdown)

## `add_004_shortkeys_navigation.md`

### Scope

Add global navigation shortcuts (tree + editor focus) and shortcut hints in tooltips.
Add a consistent strategy to leave long-text fields where Tab must be inserted as content (not focus navigation).

### Non-goals

* No vim/emacs mode
* No configurable keymap in MVP
* No macro recording

---

## A) Navigation Shortcuts (Global)

### A1. Focus switching (works from anywhere)

* `F6` → Focus Tree (left pane)
* `Shift+F6` → Focus Editor (right pane, last focused field)
* `Ctrl+1` → Focus Tree
* `Ctrl+2` → Focus Content (main text)
* `Ctrl+3` → Focus Sensors
* `Ctrl+4` → Focus Actuators
* `Ctrl+5` → Focus Image

(Die Ctrl+Nummern sind optional, aber sehr lernbar.)

### A2. Tree navigation (when Tree has focus)

* `Up/Down` → select previous/next node (default Qt)
* `Left` → collapse node (or go to parent if already collapsed) *(Qt Standard)*
* `Right` → expand node (or go to first child if already expanded) *(Qt Standard)*
* `Enter` → Focus Content editor (start writing)
* `F2` → Focus Title field (rename/edit title)

### A3. Node navigation while editing (from editor fields)

* `Alt+Up` → Select previous visible node in tree (and keep editor focus OR jump editor with it; MVP: jump selection + keep editor focus)
* `Alt+Down` → Select next visible node
* `Alt+Left` → Select parent node
* `Alt+Right` → Select first child (if exists)

(Alt + Arrows ist in vielen Tree-Tools eine “Power-User”-Navigation.)

---

## B) Editing / Structure (Global)

### B1. Core editing (already exists partly)

* `Ctrl+Z` Undo
* `Ctrl+Y` Redo (or `Ctrl+Shift+Z`)
* `Ctrl+S` Save (only if not read-only)
* `Del` Delete node (tree-focused only; disabled for root)

### B2. Insert nodes (Navigation-first)

* `Ctrl+Enter` → Add Sibling Below **and focus Content** (fast writing flow)
* `Ctrl+Shift+Enter` → Add Child (last) **and focus Content**
* `Ctrl+Backspace` (optional) → Delete node (with confirm if you like; MVP: no confirm)

(Die “Add+jump into writing” Kombi macht Tree-Editoren schnell.)

### B3. Move nodes (already present via buttons + DnD)

* `Ctrl+Shift+Up` → Move node up among siblings
* `Ctrl+Shift+Down` → Move node down among siblings

---

## C) Leaving long-text fields (Tab must insert)

### Requirement

In Content/Sensors/Actuators fields, Tab inserts a tab/indent.
So we need alternative ways to leave the field.

### Rules

* `Esc` → leave current editor field and focus Tree (no save implied)
* `Ctrl+Enter` → “commit intent” and focus Tree (or perform “add sibling below” if you pick the flow shortcut above)
* `Ctrl+Tab` / `Ctrl+Shift+Tab` → cycle focus between editor fields (content → sensors → actuators → image → title → tree)

### Implementation guidance (PyQt5)

* Ensure text widgets have `setTabChangesFocus(False)` so Tab stays content.
* Install an eventFilter on the editor widgets:

  * if `Esc`: focus tree
  * if `Ctrl+Tab`: focus next editor widget
  * if `Ctrl+Shift+Tab`: focus previous editor widget
  * if `Ctrl+Enter`: execute configured action (either focus tree or add sibling then focus content)

---

## D) Shortcut hints on UI

* Every toolbar action must have a tooltip containing:

  * Action name
  * Shortcut (e.g., “Undo (Ctrl+Z)”)
* Use QAction shortcuts so Qt automatically shows shortcut in tooltip/menu where applicable.

---

## Acceptance tests (manual)

1. From any editor field, `F6` focuses tree.
2. From tree, `Enter` focuses content.
3. In content field, pressing Tab inserts tab (does NOT change focus).
4. In content field, `Esc` returns to tree selection without crash.
5. `Alt+Up/Down` changes selected node even while editing.
6. Tooltips show shortcuts.
7. Read-only mode disables save-related shortcuts.
