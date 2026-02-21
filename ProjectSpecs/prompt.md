You are a senior Python engineer. You will build a Windows desktop app that exactly implements the requirements in the attached/above file spec.md.

Absolute rules:
- spec.md is the source of truth. Do not add features not listed there.
- Implement MVP only. Anything marked as non-goal or out-of-scope must not be implemented.
- Use Python 3.11+, PyQt5 for GUI, pytest for tests.
- The domain/model layer MUST be pure Python with ZERO PyQt imports.
- The UI layer must never mutate the model directly. All changes go through domain Commands executed by a CommandManager (undo/redo).
- Provide deterministic JSON save and deterministic Markdown export as specified.
- Prefer clarity and correctness over cleverness.

Work method (agent strategy):
You MUST work in the following steps and fully complete each step before proceeding. After each step output a "Checkpoint" with:
(1) files created/changed
(2) how to run tests / how to run app
(3) what remains

Step 1 — Project skeleton + tooling
- Create repository structure:
  /app
    main.py
    ui_mainwindow.py
  /domain
    model.py
    commands.py
    command_manager.py
    transform.py
    persistence.py
    export_md.py
  /tests
    test_model_ops.py
    test_commands_undo_redo.py
    test_transform_flatten_expand.py
    test_export_deterministic.py
  README.md
  pyproject.toml (or requirements.txt)
- Add minimal dependencies: PyQt5, pytest
- Add a simple README with setup and run instructions.

Step 2 — Domain model + invariants + sort_key
- Implement the nested node structure exactly as in spec.md.
- Enforce invariants (root delete forbidden, move into own subtree forbidden, children always list).
- Implement sort_key insertion and sibling reindexing.

Step 3 — Persistence (load/save deterministic)
- Implement load_spec(path) and save_spec(path) per spec.md deterministic write rules.

Step 4 — Command pattern + CommandManager
- Implement Command interface and CommandManager (undo/redo stacks, dirty flag).
- Implement commands:
  - CreateNodeCommand
  - DeleteNodeCommand
  - UpdateFieldCommand
  - MoveNodeCommand
- Add tests covering execute/undo/redo.

Step 5 — Transformations as Commands (lossy)
- Implement flatten (Branch→Linear Node) and expand (Linear Node→Branch) per spec.md rules.
- Insert results as sibling directly after source (sort_key rules).
- Implement:
  - FlattenBranchToNodeCommand
  - ExpandNodeToBranchCommand
- Add tests for valid cases and error cases.

Step 6 — Markdown export
- Implement deterministic export with printable filter.
- Add tests.

Step 7 — Minimal PyQt5 UI (thin layer)
- Create a minimal usable window with tree on the left and editor fields on the right.
- Buttons/toolbar: add sibling/child, delete, move up/down, flatten, expand, undo, redo, open, save, new, export.
- Shortcuts: Ctrl+Z, Ctrl+Y (or Ctrl+Shift+Z), Ctrl+S, Del.
- UI uses domain commands only.

Step 8 — Integration polish
- Dirty flag prompt on close (minimal).
- Error reporting via message boxes.

Step 9 — Final audit
- Re-check spec.md acceptance tests and confirm each is satisfied.
- List known limitations aligned with out-of-scope.

Output requirements:
- Output the full contents of every file you create or modify.
- Ensure the project can be run with a single command and tests with a single command.
- Keep code simple, readable, and maintainable.
- If any requirement in spec.md is ambiguous, choose the simplest interpretation and document it in README under "Assumptions".