"""Install or compare project-local skills against the packaged manifest."""

from importlib.resources import files
from pathlib import Path

from .config import HandoffError, read_limited, safe_path
from .storage import atomic_write

DESTINATIONS = {
    "codex": ".agents/skills/handoff/SKILL.md",
    "claude": ".claude/skills/handoff/SKILL.md",
}


def manifest() -> bytes:
    return files("handoff").joinpath("skill_manifest.md").read_bytes()


def synchronize(root: Path, provider: str, check: bool) -> None:
    if provider not in {*DESTINATIONS, "both"}:
        raise HandoffError("Provider must be codex, claude, or both.")
    targets = DESTINATIONS.values() if provider == "both" else [DESTINATIONS[provider]]
    data = manifest()
    pending = []
    for target in targets:
        path = safe_path(root, target)
        if path.exists():
            existing = read_limited(path, 65536).replace(b"\r\n", b"\n")
            if existing == data.replace(b"\r\n", b"\n"):
                continue
            raise HandoffError(f"{target} differs. Reconcile local changes before syncing.")
        if check:
            raise HandoffError(f"{target} is missing.")
        pending.append(path)
    for path in pending:
        atomic_write(path, data)
