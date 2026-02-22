
## Change request (override part of add_005)
Editor highlighting must be field-based, not pane-based.

### Requirements
- Only the currently focused editor field is highlighted.
- In NAVIGATION_MODE: active field border is BLUE.
- In EDIT_MODE: active field border is RED.
- Non-active fields must have neutral border (or none).
- When focus changes between editor fields, highlight follows.
- When switching NAV/EDIT mode, the active field border color updates immediately.
- When Tree pane is active, editor field highlight may be removed or shown neutral.

---

## Debug-Prompt (falls du es “reparieren lassen” willst)

Fix UI highlighting:
Currently the editor pane highlight applies to the whole pane, which is wrong.
Change to field-level highlighting: only the focused editor field gets a colored border.
Use BLUE for NAV mode and RED for EDIT mode.
Implement with per-field wrapper QFrames and a central update function triggered by focusChanged and mode changes.
Do not change domain logic. Output only modified UI files.
