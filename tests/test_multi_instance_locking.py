from __future__ import annotations

from pathlib import Path

from domain.file_lock import DocumentLock
from domain.persistence import SaveWithoutLockError, ensure_save_permitted


def test_open_file_normally_is_writable(tmp_path: Path) -> None:
    doc_path = tmp_path / "spec.json"
    doc_path.write_text("{}\n", encoding="utf-8")

    lock = DocumentLock()
    try:
        assert lock.acquire_for_path(doc_path) is True
        assert lock.owns_lock is True
    finally:
        lock.release()


def test_second_lock_attempt_triggers_read_only_mode(tmp_path: Path) -> None:
    doc_path = tmp_path / "spec.json"
    doc_path.write_text("{}\n", encoding="utf-8")

    first_instance_lock = DocumentLock()
    second_instance_lock = DocumentLock()
    try:
        assert first_instance_lock.acquire_for_path(doc_path) is True
        second_has_lock = second_instance_lock.acquire_for_path(doc_path)
        assert second_has_lock is False
        read_only_mode = not second_has_lock
        assert read_only_mode is True
    finally:
        second_instance_lock.release()
        first_instance_lock.release()


def test_save_in_read_only_raises_controlled_error() -> None:
    try:
        ensure_save_permitted(False)
    except SaveWithoutLockError:
        return
    assert False, "Expected SaveWithoutLockError when saving without lock"


def test_lock_released_after_closing_instance(tmp_path: Path) -> None:
    doc_path = tmp_path / "spec.json"
    doc_path.write_text("{}\n", encoding="utf-8")

    first_instance_lock = DocumentLock()
    second_instance_lock = DocumentLock()
    try:
        assert first_instance_lock.acquire_for_path(doc_path) is True
        first_instance_lock.release()

        assert second_instance_lock.acquire_for_path(doc_path) is True
    finally:
        second_instance_lock.release()
