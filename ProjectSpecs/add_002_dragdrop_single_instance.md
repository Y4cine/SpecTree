
You are extending an existing Python application.

Read:
- spec/spec_v1.md
- spec/addenda/add_002_dragdrop_single_instance.md

Implement ONLY the behavior described in add_002_dragdrop_single_instance.md.
Do NOT refactor unrelated parts.
Keep UI changes minimal.

----------------------------------------
STEP STRATEGY (MANDATORY)
----------------------------------------

Step 1 — Quick plan (5–10 lines)
- Which Qt tree component you will use (QTreeView+model OR QTreeWidget).
- How you will map UI nodes to domain nodes (object reference or index path).
- How you will translate a drop into a single domain MoveNodeCommand call.

Then implement.

----------------------------------------

Step 2 — UI Drag & Drop
Requirements:
- Single node drag only.
- Root cannot be dragged.
- Support:
  - drop-on-node => move as last child
  - drop-above/below => move as sibling with correct insertion index
- Reject invalid drops (into own subtree, root).

All successful drops MUST be executed via CommandManager using MoveNodeCommand.
No direct mutation of domain model from UI except through commands.

----------------------------------------

Step 3 — Undo/Redo
- After each drop, undo must restore previous tree state.
- redo must reapply.

----------------------------------------

Step 4 — Tests
- Add domain-level tests that validate:
  - reorder within siblings
  - move as child
  - reject move into own subtree
  - undo/redo around MoveNodeCommand for the same scenarios

UI event simulation tests are optional; domain tests are required.

----------------------------------------

Step 5 — Checkpoint
Output:
1) Files changed
2) How to run tests
3) Manual test steps for DnD

----------------------------------------

STRICT RULES
- Do not implement cross-instance DnD.
- Do not implement copy/paste.
- Do not implement multi-selection drag.
- Keep code minimal.

Output only changed/new files and the checkpoint.

