
# `add_001_multi_instance_locking.md`

## Scope

Add file locking to prevent concurrent write access to the same document file.

This addendum extends `spec_v1.md`.

No other behavior changes.

---

## Goal

If a document file is already opened in one app instance, a second instance must:

* Either open it in read-only mode
* Or refuse to open it with a clear error

MVP Decision:
Second instance opens in **read-only mode**.

---

## Functional Requirements

### 1. Locking Mechanism

When opening a file:

* Attempt to acquire an exclusive lock.
* If lock acquisition succeeds:

  * File is opened in read-write mode.
* If lock acquisition fails:

  * File is opened in read-only mode.
  * UI must indicate read-only state.

Lock must be released:

* On application close.
* On file close.
* On crash (OS cleanup).

Implementation may use:

* OS-level file locking (e.g., `portalocker`)
* Or platform-specific file descriptor locking

Must work on Windows and Linux.

---

### 2. Read-Only Mode Behavior

In read-only mode:

* Save is disabled.
* Commands that modify the model are disabled.
* Toolbar buttons for modification are disabled.
* UI clearly indicates:
  “Read-only (locked by another instance)”

Undo/Redo may remain active for local temporary changes,
but Save must remain disabled.

---

### 3. Saving Behavior

Only instances that own the lock may save.

Attempting to save without lock:

* Must raise error
* Must show message box
* Must not corrupt file

---

### 4. UI Indication

When file is locked:

* Status bar shows:
  “READ-ONLY – File locked by another instance”
* Window title may append:
  “[Read-only]”

---

## Non-Goals

* No lock timeouts
* No distributed/network locking guarantees
* No merge functionality
* No collaborative editing

---

## Acceptance Tests

1. Open file in instance A → writable.
2. Open same file in instance B → read-only.
3. Close A → B can reopen writable.
4. Save attempt in B while locked → error shown.
5. App crash in A → lock released automatically.
6. Lock does not persist after process exit.

---

## Technical Constraints

* Lock must be tied to the file path.
* Lock must not require a database.
* Lock must not require a background service.
* Lock must be deterministic.

---

## Open Questions (Optional)

* Should read-only allow local edits (temporary) or disable editing entirely?
  Recommendation: disable editing to avoid confusion.

---

