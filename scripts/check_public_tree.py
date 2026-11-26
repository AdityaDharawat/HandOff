"""Reject local-only paths in the Git index before preparing a release."""

import subprocess
from pathlib import Path, PurePosixPath

LOCAL_DIRS = {
    ".venv",
    "venv",
    "node_modules",
    ".handoff",
    ".aws",
    ".ssh",
    ".audit-cache",
    ".uv-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "private-projects",
    "local-analysis",
    ".vscode",
    ".idea",
    "htmlcov",
    "__pycache__",
}
LOCAL_SUFFIXES = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".kdbx",
    ".log",
    ".tmp",
    ".bak",
    ".swp",
    ".pyc",
    ".pyo",
    ".pyd",
    ".vsix",
}


def blocked_path(path: PurePosixPath) -> bool:
    return (
        bool(LOCAL_DIRS.intersection(path.parts[:-1]))
        or any(part.startswith(".verification") for part in path.parts)
        or path.name
        in {".env", ".coverage", ".netrc", "_netrc", ".npmrc", ".pypirc", "credentials"}
        or (path.name.startswith(".env.") and path.name != ".env.example")
        or path.name.startswith(".coverage.")
        or path.name
        in {
            ".ds_store",
            "thumbs.db",
            ".handoff-private-exclusions.yml",
            ".handoff-private-exclusions.gitignore",
        }
        or path.suffix in LOCAL_SUFFIXES
    )


def index_entries(root: Path):
    entries = subprocess.check_output(
        ["git", "ls-files", "-z", "--stage"], cwd=root, stderr=subprocess.DEVNULL
    )
    for entry in entries.split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            yield (*metadata.decode("ascii").split(), name.decode("utf-8"))


def main() -> None:
    try:
        rejected = sum(
            mode == "160000" or blocked_path(PurePosixPath(name.casefold()))
            for mode, _, _, name in index_entries(Path.cwd())
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Git index unreadable.") from None
    if rejected:
        raise SystemExit(
            f"Public tree check rejected {rejected} tracked entries. Inspect the index privately."
        )
    print(
        "Generic tracked-path checks passed. Run the publication preflight for release authorization."
    )


if __name__ == "__main__":
    main()
