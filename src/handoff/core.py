"""Application operations shared by CLI and library callers."""

from pathlib import Path

from .config import HandoffError, load_settings, safe_path
from .intelligence import analyze
from .models import Snapshot
from .scanner.repository import scan
from .storage import atomic_write, load_snapshot


def initialize(root: Path) -> None:
    settings = safe_path(root, ".handoff/config.yaml")
    for name in ("snapshots", "reports"):
        safe_path(root, f".handoff/{name}").mkdir(parents=True, exist_ok=True)
    if not settings.exists():
        atomic_write(settings, b"max_depth: 12\nmax_files: 3000\nmax_bytes: 262144\nexcludes: []\n")


def capture(root: Path, output: str = ".") -> Snapshot:
    if output != ".":
        safe_path(root, output)
        parts = output.lower().split("/")
        if (
            {".git", ".agents", ".claude"} & set(parts)
            or ".handoff" in parts
            and parts[:2] != [".handoff", "reports"]
        ):
            raise HandoffError("Output directory overlaps reserved project metadata.")
    return analyze(scan(root, load_settings(root), output))


def published(root: Path, *, optional: bool = False) -> Snapshot | None:
    if optional and not safe_path(root, ".handoff/snapshots/published.json").exists():
        return None
    return load_snapshot(root, "published")


def resolve_root(path: Path) -> Path:
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise HandoffError("Project path must be a directory")
    return root
