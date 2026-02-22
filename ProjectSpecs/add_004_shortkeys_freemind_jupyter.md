# `add_004_shortkeys_freemind_jupyter.md`

## Scope

Implement keyboard shortcuts based on:

* FreeMind/FreePlane navigation for the TreeView
* Jupyter-style Navigation/Edit modes for the Editor pane

Tree component: QTreeWidget
Framework: PyQt5

No changes to domain model.

No configurable keymap.

---

## 1. Pane Switch

### Shortcut

* `Ctrl+Tab`: toggle focus between Tree pane and Editor pane.

### Requirements

* Must work globally (even when a text widget has focus).
* Must not conflict with text editing.
* Visual indication of active pane:

  * Minimal acceptable: status bar text (“TREE” / “EDITOR”)
  * Optional: thicker colored frame (e.g., red for active, black for inactive)

---

## 2. TreeView Shortcuts (FreeMind style)

Applies when Tree has focus.

### 2.1 Insert

* `Enter` → Create sibling below current node.
* `Insert` → Create child node (append as last child).

After creation:

* New node receives default title: `"New Node"`.
* Immediately start inline rename using `editItem()`.
* Select all text in the inline editor.
* Do NOT switch to editor pane.

### 2.2 Navigation

* Arrow keys: keep Qt default behavior.

  * Up/Down: visible order navigation.
  * Left/Right: expand/collapse behavior remains default.
* `F2`: inline rename selected node.

### 2.3 Domain Mapping

Creation must use:

* CreateNodeCommand(parent=..., index=...)
  After command execution:
* Rebuild tree from domain (SSOT)
* Select the newly created node
* Start inline rename

---

## 3. Editor Pane: Navigation Mode vs Edit Mode

Editor has two explicit modes:

* NAVIGATION_MODE
* EDIT_MODE

Default when editor pane gains focus: NAVIGATION_MODE

Fields order (fixed):

1. title
2. content
3. sensors
4. actuators
5. image
6. printable (optional)

---

### 3.1 Navigation Mode

* `Up` → Focus previous field
* `Down` → Focus next field
* `Enter` → Switch to EDIT_MODE (focus enters active field)
* `Ctrl+Tab` → Switch pane (Tree)

Navigation Mode must not insert characters.

---

### 3.2 Edit Mode

* Normal text editing behavior.
* `Tab` inserts tab/indent (no focus change).
* `Esc` → Switch to NAVIGATION_MODE (leave widget focus but remain in editor pane).
* `Ctrl+Enter` → Switch to NAVIGATION_MODE.

`Ctrl+Tab` must still switch pane.

---

## 4. Technical Constraints

* Implement editor key behavior using eventFilter.
* Do NOT override default text editing behavior unnecessarily.
* Tree shortcuts implemented via QActions or keyPressEvent override.
* All domain mutations must go through CommandManager.
* No refactor of domain model.

---

## 5. Acceptance Tests (Manual)

1. Ctrl+Tab toggles between Tree and Editor.
2. Enter in Tree creates sibling and starts inline rename.
3. Insert creates child and starts inline rename.
4. F2 edits title in-place.
5. In Editor:

   * Enter enters Edit Mode.
   * Esc leaves Edit Mode.
   * Tab inserts indentation.
   * Ctrl+Tab switches pane.
6. No crashes when rapidly switching modes.

---

# `feature_prompt_add_004.txt`

```text
You are extending an existing PyQt5 application.

Read:
- spec/spec_v1.md
- spec/addenda/add_004_shortkeys_freemind_jupyter.md

Implement ONLY this addendum.
Do NOT refactor unrelated code.
Tree component is QTreeWidget.

----------------------------------------
Step 1 — Plan (5–10 lines)
Explain:
- How global Ctrl+Tab will be implemented.
- How Tree shortcuts will be implemented (QAction vs keyPressEvent override).
- How editor Navigation/Edit mode will be implemented (eventFilter, state variable).

Then proceed.

----------------------------------------
Step 2 — Implement Pane Switch
- Add global QAction for Ctrl+Tab.
- Toggle focus between Tree and Editor.
- Add minimal visual indicator (status bar text acceptable).

----------------------------------------
Step 3 — Implement Tree shortcuts
- Enter → Create sibling below + inline rename.
- Insert → Create child + inline rename.
- F2 → Inline rename.
- Keep Arrow keys default.
- Use CommandManager.
- After command: rebuild tree and reselect node before calling editItem().

----------------------------------------
Step 4 — Implement Editor Mode System
- Introduce NAVIGATION_MODE and EDIT_MODE state.
- Install eventFilter on editor widgets.
- In NAVIGATION_MODE:
    - Up/Down change focused widget.
    - Enter switches to EDIT_MODE.
- In EDIT_MODE:
    - Esc or Ctrl+Enter switches to NAVIGATION_MODE.
    - Tab inserts indentation.
- Ctrl+Tab must switch pane in both modes.

Do NOT break normal QTextEdit behavior.

----------------------------------------
Step 5 — Checkpoint
Output:
1) Modified files
2) How to run app
3) Manual test checklist

STRICT RULES
- No new features beyond shortcuts and mode handling.
- No domain refactor.
- Keep implementation minimal and deterministic.

Output only changed/new files and checkpoint.