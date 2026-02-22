
# `add_005_icons_and_highlighting.md`

## Scope

UI polish only (no domain changes):

1. Toolbar uses icons instead of text.
2. Active pane highlighting: Tree pane vs Editor pane.
3. Editor mode highlighting: Navigation mode vs Edit mode (color-coded).

Framework: PyQt5
Tree: QTreeWidget

Out of scope:

* New actions/features
* Theme system / user-configurable colors
* Large UI refactor

---

## 1) Toolbar Icons (replace text)

### Requirements

* Toolbar buttons must show **icons** (no text on the toolbar).
* Tooltips must show:

  * action name
  * shortcut (if defined), e.g. “Undo (Ctrl+Z)”
* Icons can be:

  * Qt standard icons (`QStyle.standardIcon`)
  * or bundled SVG/PNG (optional)
    MVP preference: **Qt standard icons** (no asset pipeline).

### Notes

* Text labels may remain in menus (if any).
* Actions must remain QActions.

---

## 2) Active Pane Highlighting (Tree vs Editor)

### Goal

Users can see at a glance which pane is active:

* Tree pane active → Tree frame highlighted
* Editor pane active → Editor frame highlighted

### Requirements

* Use a visible frame highlight.
* Minimal acceptable:

  * a QFrame border around each pane
  * thicker border for active pane, thinner for inactive pane
* Colors:

  * active pane border: **blue**
  * inactive pane border: neutral (gray/black)

### Trigger rules

* When focus enters any widget inside Tree pane → Tree becomes active pane.
* When focus enters any widget inside Editor pane → Editor becomes active pane.
* Ctrl+Tab pane switching must also update highlight.

---

## 3) Editor Mode Highlighting (NAV vs EDIT)

### Goal

Users can see whether editor side is in:

* NAVIGATION_MODE
* EDIT_MODE

### Requirements

* The editor pane highlight must also indicate mode:

  * NAVIGATION_MODE border color: **blue**
  * EDIT_MODE border color: **red**
* Mode highlight applies only when editor pane is active.

  * If Tree pane is active, editor border can revert to inactive style.

### Minimal acceptable visual

Border color and thickness is sufficient.

Optional:

* status bar text: “EDITOR: NAV” / “EDITOR: EDIT” (nice-to-have)

---

## Acceptance Tests (Manual)

1. Toolbar shows icons (no text), tooltips show shortcut.
2. Clicking Tree highlights Tree pane; clicking editor field highlights Editor pane.
3. In editor:

   * in NAV mode: editor border is blue
   * in EDIT mode: editor border is red
4. Ctrl+Tab toggling updates the correct pane highlight.
5. No functional behavior changes (only visuals).

