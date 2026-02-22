from __future__ import annotations

from pathlib import Path

import portalocker


class DocumentLock:
    def __init__(self) -> None:
        self._lock: portalocker.Lock | None = None
        self._lock_path: Path | None = None

    @property
    def owns_lock(self) -> bool:
        return self._lock is not None

    @property
    def lock_path(self) -> Path | None:
        return self._lock_path

    def acquire_for_path(self, path: str | Path) -> bool:
        self.release()
        target_path = Path(path)
        lock = portalocker.Lock(
            str(target_path),
            mode="a+",
            timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        )
        try:
            lock.acquire()
        except portalocker.exceptions.LockException:
            return False

        self._lock = lock
        self._lock_path = target_path
        return True

    def release(self) -> None:
        if self._lock is None:
            return
        try:
            self._lock.release()
        finally:
            self._lock = None
            self._lock_path = None
