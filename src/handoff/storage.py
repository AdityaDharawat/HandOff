"""Versioned snapshots and cooperative single-writer locking."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from .config import HandoffError, read_limited, safe_path
from .models import Snapshot

MAX_SNAPSHOT = 32 * 1024 * 1024


@contextmanager
def writing(root: Path) -> Iterator[None]:
    directory = safe_path(root, ".handoff")
    directory.mkdir(exist_ok=True)
    path = safe_path(root, ".handoff/write.lock")
    try:
        lock = path.open("xb")
    except FileExistsError as exc:
        raise HandoffError(
            "Another writer holds .handoff/write.lock. Check before removing it."
        ) from exc
    try:
        with lock:
            yield
    finally:
        path.unlink()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def save_snapshot(root: Path, name: str, snapshot: Snapshot) -> None:
    data = snapshot.model_dump_json(indent=2).encode() + b"\n"
    if len(data) > MAX_SNAPSHOT:
        raise HandoffError("Snapshot exceeds the storage budget")
    atomic_write(safe_path(root, f".handoff/snapshots/{name}.json"), data)


def load_snapshot(root: Path, name: str) -> Snapshot:
    path = safe_path(root, f".handoff/snapshots/{name}.json")
    if not path.exists():
        raise HandoffError(f"No {name} snapshot. Run handoff scan or handoff generate first.")
    try:
        return Snapshot.model_validate_json(read_limited(path, MAX_SNAPSHOT))
    except ValidationError as exc:
        raise HandoffError("Snapshot is corrupt or uses an unsupported schema version.") from exc
