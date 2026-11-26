"""Explain repository changes relative to the published snapshot."""

from .models import Snapshot


def differences(previous: Snapshot, current: Snapshot) -> list[str]:
    reasons = []
    for field, label in (
        ("head", "Git HEAD"),
        ("branch", "Git branch"),
        ("state", "Git availability"),
        ("changes", "Visible working-tree state"),
    ):
        if getattr(previous.git, field) != getattr(current.git, field):
            reasons.append(f"Changed {label}")
    if previous.config_digest != current.config_digest:
        reasons.append("Changed scan settings")
    if previous.limitations != current.limitations:
        reasons.append("Changed scan limitations")
    before = {file.path: file.digest for file in previous.files}
    after = {file.path: file.digest for file in current.files}
    reasons.extend(f"Added {name}" for name in sorted(after.keys() - before.keys()))
    reasons.extend(f"Removed {name}" for name in sorted(before.keys() - after.keys()))
    reasons.extend(
        f"Changed {name}"
        for name in sorted(before.keys() & after.keys())
        if before[name] != after[name]
    )
    return reasons
