
## Scope

Add a context menu (right-click) to the tree (QTreeWidget) to execute common node operations.

This addendum extends `spec_v1.md`.
No changes to domain storage format.

Out of scope:

* Multi-selection actions
* Copy/Paste (we may add later)
* Advanced menu customization

---

## Goal

Right-clicking a node in the tree opens a context menu with common operations:

* Insert (child/sibling above/below)
* Delete
* Move up/down
* Flatten / Expand

All actions MUST:

* Use CommandManager + domain Commands (no direct model mutation)
* Respect invariants (root not deletable, no invalid moves)
* Update the UI immediately (rebuild from domain as in DnD solution)

---

## UI Behavior (QTreeWidget)

### 1) Context menu trigger

* Right-click on a node opens the menu for that node.
* If right-click occurs on empty area:

  * Show a minimal menu with: “Add Child to Root” (optional) or do nothing (MVP acceptable).
* The right-clicked node becomes selected before executing actions.

### 2) Menu structure (MVP)

**Insert**

* Add Child (as first child)
* Add Child (as last child)
* Add Sibling Above
* Add Sibling Below

**Edit**

* Delete Node

**Move**

* Move Up
* Move Down

**Tools**

* Flatten Branch → Node
* Expand Node → Branch

### 3) Enable/disable rules

* Root:

  * Delete disabled
  * Sibling Above/Below disabled (unless you explicitly support root siblings; default: disabled)
* “Move Up” disabled if node is first sibling.
* “Move Down” disabled if node is last sibling.
* Flatten/Expand enabled whenever applicable:

  * Flatten enabled when node has children (or always allowed but produces trivial result—MVP: enable only if has children).
  * Expand enabled when node.content contains valid heading markup (optional check; MVP may allow and show error if invalid).

---

## Domain operations mapping

All operations execute via commands:

* Add Child (first/last):

  * CreateNodeCommand(parent=target_node, position=first/last)

* Add Sibling Above/Below:

  * CreateNodeCommand(parent=target_parent, position=target_index or target_index+1)

* Delete Node:

  * DeleteNodeCommand(node=target_node)

* Move Up/Down:

  * MoveNodeCommand(node=target_node, new_parent=same_parent, new_index=index±1)

* Flatten:

  * FlattenBranchToNodeCommand(source=target_node)

* Expand:

  * ExpandNodeToBranchCommand(source=target_node)

After each command:

* Rebuild tree from domain (SSOT)
* Best-effort reselect affected node (new node or moved node)

---

## Acceptance Tests

Domain-level tests are not required for menu itself (operations already tested), but add at least:

1. Manual test: menu appears on right-click and selects the correct node.
2. Manual test: “Add Sibling Below” creates a new node after target and it appears immediately.
3. Manual test: Delete is disabled for root and works for non-root.
4. Manual test: Move Up/Down enable/disable works at boundaries.
5. Manual test: Flatten/Expand trigger commands and update tree.

Optional automated UI test is allowed but not required (Qt UI tests can be fragile).

---

## Notes (MVP)

* New nodes created by context menu are blank:

  * title empty
  * content empty
  * sensors/actuators/image empty
  * printable true
* Focus behavior: after creating a node, focus the title editor (optional but recommended).
* Errors (e.g., invalid Expand markup) must show a message box and do nothing else.
