"""Read-only Git metadata. Never inspect diff bodies or commit messages."""

import os
import shutil
import subprocess
import tempfile
from hashlib import sha1, sha256
from pathlib import Path
from re import fullmatch

from ..models import GitState


def parse_entries(records: list[str], *, index: bool) -> dict[str, str] | None:
    entries = {}
    for record in filter(None, records):
        header, separator, path = record.partition("\t")
        fields = header.split()
        if not separator or not path or len(fields) != 3:
            return None
        oid = fields[1 if index else 2]
        if not fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", oid):
            return None
        if index and fields[2] != "0":
            # An unmerged path has no ordinary stage-zero index entry.
            entries[path] = ""
        else:
            entries[path] = oid
    return entries


def inspect_git(root: Path, visible: dict[str, tuple[str, str]]) -> GitState:
    marker = root / ".git"
    if marker.is_symlink() or (marker.exists() and marker.resolve() != marker):
        return GitState(state="unavailable")
    if not marker.exists():
        return GitState()
    executable = shutil.which("git")
    if (
        not executable
        or not Path(executable).is_absolute()
        or Path(executable).is_relative_to(root)
    ):
        return GitState(state="unavailable")
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_OPTIONAL_LOCKS="0",
        GIT_NO_LAZY_FETCH="1",
        GIT_ALLOW_PROTOCOL="",
        GIT_NO_REPLACE_OBJECTS="1",
        GIT_TERMINAL_PROMPT="0",
    )

    def run(*args: str) -> list[str] | None:
        try:
            # Bound retained output and command duration. Disable hooks, fsmonitor and pagers.
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    [
                        executable,
                        "--no-pager",
                        "-c",
                        "core.fsmonitor=false",
                        "-c",
                        f"core.hooksPath={os.devnull}",
                        "-c",
                        "core.untrackedCache=false",
                        "-c",
                        "core.quotePath=false",
                        "-c",
                        "status.submoduleSummary=false",
                        *args,
                    ],
                    env=environment,
                    cwd=root,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                )
                if result.returncode or output.tell() > 2097152:
                    return None
                output.seek(0)
                return output.read().decode("utf-8", "replace").split("\0")
        except (OSError, subprocess.TimeoutExpired):
            return None

    index = run("ls-files", "--stage", "-z")
    if index is None:
        return GitState(state="unavailable")
    branch = run("symbolic-ref", "--quiet", "--short", "HEAD")
    name = branch[0].strip() if branch else ""
    history = run("rev-list", "--max-count=20", "HEAD")
    commits = (
        [item for item in history[0].splitlines() if fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", item)]
        if history
        else []
    )
    tree = run("ls-tree", "-r", "-z", "HEAD") if commits else []
    if tree is None:
        return GitState(state="unavailable")
    indexed = parse_entries(index, index=True)
    committed = parse_entries(tree, index=False)
    if indexed is None or committed is None:
        return GitState(state="unavailable")
    changes = {}
    for path, (short_hash, long_hash) in visible.items():
        oid = indexed.get(path)
        if oid == "":
            changes[path] = "unmerged index entries"
        elif oid is None:
            changes[path] = "staged removal" if path in committed else "untracked"
        elif oid != committed.get(path):
            changes[path] = "index differs from HEAD"
        elif oid not in {short_hash, long_hash}:
            changes[path] = "working bytes differ from index"
    return GitState(
        state="available",
        branch=name if fullmatch(r"[A-Za-z0-9._/-]{1,100}", name) else None,
        head=commits[0] if commits else None,
        commits=commits,
        changes=changes,
    )


def blob_hashes(data: bytes) -> tuple[str, str]:
    blob = f"blob {len(data)}\0".encode() + data
    return sha1(blob, usedforsecurity=False).hexdigest(), sha256(blob).hexdigest()
