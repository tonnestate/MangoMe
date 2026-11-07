"""Test fixture guard: a scratch database name may be claimed by one live process at a time (H1: concurrent test processes sharing one scratch database)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

LOCK_DIR = Path(tempfile.gettempdir()) / "mangome-test-db-locks"


class DatabaseInUse(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def claim_database(name: str, lock_dir: Path = LOCK_DIR) -> Path:
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{name}.lock"
    if path.exists():
        try:
            pid = int(path.read_text().strip())
        except ValueError:
            pid = 0
        if pid and pid != os.getpid() and _alive(pid):
            raise DatabaseInUse(f"DATABASE_IN_USE: {name} is claimed by live process {pid}")
    path.write_text(str(os.getpid()))
    return path


def release_database(path: Path) -> None:
    path.unlink(missing_ok=True)
