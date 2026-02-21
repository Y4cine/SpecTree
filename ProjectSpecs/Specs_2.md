
# spec.md — Hierarchical Text Tree Editor (MVP)

## 0. Purpose
A desktop application to edit a hierarchical tree of text nodes, stored as a nested JSON file.
It supports:
- Tree editing (create, delete, move, reorder)
- Editing per-node text fields (content + sensors/actuators/image)
- A lossy text transformation operator:
  - Branch → Linear Node (Flatten)
  - Linear Node → Branch (Expand)
- Undo/Redo via command pattern (domain-layer)
- Export to Markdown (deterministic), optionally filtered by printable

Non-goals (MVP):
- Collaboration
- Git integration
- SQLite
- COM integration
- Lossless roundtrip / ID-based sync
- Asset embedding / base64 image storage
- Full Typst/AsciiDoc parsing

---

## 1. Storage Format (Single Source of Truth)
### 1.1 File
- The project is stored in a single JSON file: `spec.json`

### 1.2 Top-level structure
```json
{
  "schema_version": "1.0",
  "root": { /* Node */ }
}
````

### 1.3 Node schema (nested, no IDs)

Each node MUST contain the following keys:

* `title: string`
* `content_type: string` — enum: `"md" | "typ" | "adoc"` (default `"md"`)
* `content: string`
* `sensors: string` (default `""`)
* `actuators: string` (default `""`)
* `image: string` (default `""`)  // free text in MVP (path, note, reference)
* `printable: boolean` (default `true`)
* `sort_key: number`
* `children: array<Node>` — MUST exist (may be empty)

Example node:

```json
{
  "title": "Pump",
  "content_type": "md",
  "content": "Purpose...",
  "sensors": "PT-101; TT-102",
  "actuators": "V-201; P-301",
  "image": "screenshot: pump-area",
  "printable": true,
  "sort_key": 20,
  "children": []
}
```

### 1.4 Deterministic write rules

When saving JSON:

* Always write keys in a stable, fixed order (as listed in 1.3).
* Always sort children by ascending `sort_key` before writing.
* Use stable JSON formatting (indent=2) and newline at EOF.

---

## 2. Tree Ordering and sort_key

### 2.1 sort_key conventions

* Default spacing is 10: 10, 20, 30, ...
* Insert result nodes *immediately after* the source node (same parent).

### 2.2 Insertion sort_key

Given sibling list sorted by `sort_key`:

* If inserting after node `src` and there is a next sibling `next`:

  * `new.sort_key = (src.sort_key + next.sort_key) / 2`
* Else:

  * `new.sort_key = src.sort_key + 10`

### 2.3 Reindexing

If gaps become too small (e.g., repeated inserts cause precision issues), reindex siblings:

* Reassign sort_keys as 10,20,30,... in current sibling order.

---

## 3. Domain API (Model Operations)

All model mutations MUST be performed via Commands (see §4).

Minimal operations:

1. CreateNode(parent, after_sibling | as_first_child | as_last_child)
2. DeleteNode(node)  // cannot delete root
3. UpdateTitle(node, new_title)
4. UpdateContent(node, new_content)
5. UpdateSensors(node, new_sensors)
6. UpdateActuators(node, new_actuators)
7. UpdateImage(node, new_image)
8. UpdatePrintable(node, new_printable)
9. MoveNode(node, new_parent, new_index)  // also handles reordering
10. ReorderNodeWithinSiblings(node, new_index)

Invariants:

* Root cannot be deleted.
* A node cannot be moved into its own subtree.
* `children` always exists (array).
* Sibling ordering is defined by `sort_key`.

---

## 4. Undo/Redo (Command Pattern, UI-agnostic)

### 4.1 Command interface

Each Command MUST implement:

* `apply(model)`
* `rollback(model)`
* `description: str`

### 4.2 Command manager

* `undo_stack`
* `redo_stack`
* `execute(command)` clears redo stack
* `undo()` rolls back latest command
* `redo()` reapplies latest undone command
* `is_dirty` set to true after any execute/undo/redo

### 4.3 MVP command set

Commands (minimum):

* CreateNodeCommand
* DeleteNodeCommand
* UpdateFieldCommand (title/content/sensors/actuators/image/printable)
* MoveNodeCommand (reparent + reorder)
* FlattenBranchToNodeCommand
* ExpandNodeToBranchCommand

---

## 5. Lossy Transformations (Text-only Operators)

Transformations are **lossy by design**:

* Only `title` and `content` are transformed.
* `sensors`, `actuators`, `image` are NOT transformed and are ignored.
* `printable` is copied from source to newly created nodes/branch root (MVP convenience).
* Source nodes remain unchanged and are NOT automatically deleted.

Results are always inserted as a new sibling directly after the source node (same parent, adjust sort_key accordingly).

### 5.1 Flatten (Branch → Linear Node)

Input: node `N` with subtree
Output: new node `M` (sibling after N)

Rules:

* `M.title = N.title`
* `M.content_type = N.content_type`
* `M.printable = N.printable`
* `M.sensors/actuators/image = ""`
* `M.children = []`
* `M.content` becomes a hierarchical markup representation of titles+content ONLY.

Encoding grammar (MVP):

* Markdown heading subset only:

  * depth 0 → `# Title`
  * depth 1 → `## Title`
  * ...
  * max depth allowed = 6 (`######`)
* After a heading, place that node’s `content` verbatim.
* Child order follows sibling order (ascending sort_key).
* If subtree depth exceeds 6 → abort with a clear error.

Example encoding:

```md
# Machine A
Purpose...

## Components
List...

### Pump
Pump text...
```

### 5.2 Expand (Linear Node → Branch)

Input: node `M` whose `content` contains Markdown heading subset
Output: new branch root `B` (sibling after M), constructed from the markup

Decoding rules:

* Only headings `^#{1,6}\s+` define structure.
* Text between headings is assigned to the latest node’s `content`.
* Heading level may only increase by +1 (e.g., `##` to `####` is invalid) → abort.
* If no valid first heading exists → abort.

Creation rules:

* All nodes are newly created (no IDs).
* `content_type` inherited from source node M for all created nodes.
* `printable` inherited from source node M for all created nodes.
* `sensors/actuators/image = ""` for all created nodes.

---

## 6. Export (Deterministic Markdown)

The app provides an export function to a `.md` file.

Rules:

* Traverse the tree in sibling order (sort_key).
* Convert hierarchy to Markdown headings (`#..######`) + node `content`.
* Optionally export only nodes with `printable=true` (when enabled).
* Deterministic output: same model → byte-identical export.

---

## 7. UI (Minimal Functional Requirements)

The UI is not fully specified; it must be minimal but usable.

Required elements:

* Left: Tree view (select node)
* Right: Editor fields for selected node:

  * title
  * content (multiline)
  * sensors (multiline or singleline)
  * actuators (multiline or singleline)
  * image (singleline)
  * printable (checkbox)
* Buttons (or toolbar) for:

  * Add sibling
  * Add child
  * Delete
  * Move up/down within siblings (or drag/drop)
  * Flatten
  * Expand
  * Undo
  * Redo
  * Save / Open / New
  * Export Markdown

Shortcuts (MVP minimum):

* Ctrl+Z undo
* Ctrl+Y redo (or Ctrl+Shift+Z)
* Ctrl+S save
* Del delete selected node

Domain layer MUST NOT import any UI framework.

---

## 8. Acceptance Tests (MVP)

1. Create/edit node fields, save, reopen → values preserved.
2. Move/reorder nodes → correct order after save/load.
3. Flatten creates sibling after source with correct encoded markdown.
4. Expand creates sibling-after-source branch from valid markdown.
5. Expand aborts on invalid heading jumps (> +1).
6. Undo/redo works for create/delete/update/move/flatten/expand.
7. Export Markdown is deterministic (stable output).
8. Printable filter excludes non-printable nodes during export.
9. Root cannot be deleted.
10. Node cannot be moved into its own subtree.

````

---

