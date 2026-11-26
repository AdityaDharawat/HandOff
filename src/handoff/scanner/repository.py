"""Inventory and extract structural observations without exporting repository prose."""

import ast
import os
import re
import tokenize
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Protocol

from pathspec import GitIgnoreSpec

from ..config import HandoffError, Settings, read_limited, safe_path
from ..models import Evidence, FileRecord, Snapshot, Source, stable_id
from .git import blob_hashes, inspect_git
from .script import DECLARATION, EXTENSIONS, MARKER, visible_lines

IGNORED_DIRS = {
    ".git",
    ".handoff",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "__pycache__",
    ".cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    "target",
    ".audit-cache",
    ".ssh",
    ".aws",
    ".codex",
    ".terraform",
}
MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "cargo.toml",
    "go.mod",
    "gemfile",
    "pom.xml",
    "composer.json",
    "package-lock.json",
    "uv.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.lock",
    "go.sum",
}
CODE = {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".rb", ".cs", ".sh"}
DOCS = {".md", ".rst", ".adoc"}
SECRET = re.compile(
    r"(?i)(^\.handoff-private-exclusions\.(?:yml|gitignore)$|^\.env(?:\.|$)|credential|secret|^id_(?:rsa|ed25519)|^\.npmrc$|"
    r"^\.netrc$|^\.pypirc$|\.(?:pem|key|p12|pfx|kdbx)$)"
)
TODO = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
OUTPUTS = {"handoff.md", "handoff_agent.md", "handoff.md.bak", "handoff_agent.md.bak"}


class Observer(Protocol):
    def __call__(
        self,
        source: Source,
        description: str,
        file: FileRecord | None = None,
        line: int | None = None,
        metadata: dict[str, str] | None = None,
        commit: str | None = None,
    ) -> None: ...


def classify(path: Path) -> Source:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in MANIFESTS or name.startswith("requirements") and suffix == ".txt":
        return Source.DEPENDENCY
    if name.startswith(("test_", "test-")) or ".test." in name or name.endswith("_test.py"):
        return Source.TEST
    if suffix in DOCS:
        return Source.DOC
    if suffix in CODE:
        return Source.SOURCE
    if suffix in {".yaml", ".yml", ".toml", ".ini", ".json", ".cfg"} or name == "dockerfile":
        return Source.CONFIG
    return Source.FILESYSTEM


def scan(root: Path, settings: Settings, output: str = ".") -> Snapshot:
    now = datetime.now(UTC)
    files: list[FileRecord] = []
    blobs: dict[str, tuple[str, str]] = {}
    evidence: list[Evidence] = []
    limits: set[str] = set()
    custom = GitIgnoreSpec.from_lines(settings.excludes)
    visited = 0
    total = 0
    stopped = False

    def add_issues(_: OSError) -> None:
        limits.add("Some directories could not be read.")

    def observe(
        source: Source,
        description: str,
        file: FileRecord | None = None,
        line: int | None = None,
        metadata: dict[str, str] | None = None,
        commit: str | None = None,
    ) -> None:
        if len(evidence) >= 12000:
            limits.add("Scan reached the evidence record budget.")
            return
        path = file.path if file else None
        evidence.append(
            Evidence(
                id=stable_id("ev", source, path, line, description, commit),
                source_type=source,
                description=description,
                source_path=path,
                observed_at=now,
                line_start=line,
                line_end=line,
                commit_hash=commit,
                content_hash=file.digest if file else None,
                metadata=metadata or {},
            )
        )

    ignores: dict[Path, GitIgnoreSpec] = {}
    for directory, dirs, names in os.walk(root, onerror=add_issues, followlinks=False):
        parent = Path(directory)
        inherited = [(base, ignores[base]) for base in reversed(parent.parents) if base in ignores]
        ignore_file = parent / ".gitignore"
        try:
            if ignore_file.exists() and not ignore_file.is_symlink():
                spec = GitIgnoreSpec.from_lines(
                    read_limited(ignore_file, 65536).decode("utf-8").splitlines()
                )
                ignores[parent] = spec
                inherited.append((parent, spec))
        except (TypeError, ValueError, OSError, HandoffError):
            limits.add("A Git ignore file could not be interpreted.")

        def excluded(name: str, suffix: str = "") -> bool:
            if (
                SECRET.search(name)
                or name.lower() in IGNORED_DIRS
                or name.startswith(".verification-")
            ):
                return True
            candidate = parent / name
            try:
                if candidate.is_symlink() or candidate.resolve() != candidate:
                    return True
            except (OSError, RuntimeError):
                limits.add("An entry could not be resolved during scanning.")
                return True
            rel = candidate.relative_to(root).as_posix() + suffix
            ignored = False
            for base, spec in inherited:
                matches = spec.check_file(candidate.relative_to(base).as_posix() + suffix)
                if matches.include is not None:
                    ignored = matches.include
            return ignored or custom.match_file(rel)

        dirs[:] = sorted(name for name in dirs if not excluded(name, "/"))
        if len(parent.relative_to(root).parts) >= settings.max_depth and dirs:
            dirs.clear()
            limits.add("Scan reached the configured depth limit.")
        for name in sorted(names):
            if name.lower() in OUTPUTS or name.startswith(".handoff-"):
                continue
            visited += 1
            if visited > settings.max_files or total >= 64 * 1024 * 1024:
                limits.add("Scan reached its inventory or byte budget.")
                stopped = True
                break
            if excluded(name):
                continue
            path = parent / name
            relative = path.relative_to(root).as_posix()
            try:
                safe_path(root, relative)
                data = read_limited(path, settings.max_bytes)
                text = data.decode("utf-8")
            except UnicodeError:
                continue
            except (OSError, HandoffError):
                limits.add("Some files were unsafe, unreadable or larger than the scan limit.")
                continue
            if "\x00" in text:
                continue
            total += len(data)
            source = classify(path)
            record = FileRecord(
                path=relative,
                kind=source,
                size=len(data),
                lines=len(text.splitlines()),
                digest=sha256(data).hexdigest(),
            )
            files.append(record)
            blobs[relative] = blob_hashes(data)
            if source != Source.FILESYSTEM:
                observe(source, f"Discovered {source.value.replace('_', ' ')} file.", record)
            if name == "pyproject.toml":
                inspect_pyproject(text, record, observe)
            if path.suffix == ".py":
                inspect_python(text, record, observe)
            elif path.suffix in EXTENSIONS:
                for line, source_line in visible_lines(text):
                    if DECLARATION.match(source_line):
                        observe(
                            Source.SOURCE,
                            "Found an exported function declaration.",
                            record,
                            line,
                            {"role": "script-declaration"},
                        )
                    if marker := MARKER.match(source_line):
                        observe(Source.TODO, f"Observed {marker[1].upper()} comment.", record, line)
            if relative == settings.test_report:
                inspect_test_report(text, record, observe)
            if source == Source.DOC:
                inspect_document(text, record, observe)
        if stopped:
            break

    files_by_path = {file.path: file for file in files}
    for work_path, state in sorted({(item.path, item.state) for item in settings.work_items}):
        if file := files_by_path.get(work_path):
            observe(
                Source.NOTE,
                f"The operator declared a work item {state.replace('_', ' ')}.",
                file,
                metadata={"role": "work-item", "state": state},
            )
        else:
            limits.add("A declared work item refers to a file outside the visible inventory.")
    if settings.test_report and settings.test_report not in files_by_path:
        limits.add("The configured test artifact was outside the visible inventory.")

    git = inspect_git(root, blobs)
    if git.state == "unavailable":
        limits.add("Git metadata was unavailable.")
    if git.changes:
        observe(Source.STATUS, "Git reported visible working-tree changes.")
    for commit in git.commits:
        observe(Source.COMMIT, "Observed a commit identifier.", commit=commit)

    config = sha256(settings.model_dump_json().encode()).hexdigest()
    return Snapshot(
        observed_at=now,
        project=root.name,
        config_digest=config,
        output_dir=output,
        skipped_files=visited - len(files) - int(stopped),
        git=git,
        files=sorted(files, key=lambda file: file.path),
        evidence=evidence,
        limitations=sorted(limits),
    )


def inspect_pyproject(text: str, file: FileRecord, observe: Observer) -> None:
    import tomllib

    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, RecursionError):
        observe(
            Source.DEPENDENCY,
            "Python manifest could not be parsed.",
            file,
            metadata={"role": "parse-error"},
        )
        return
    project = data.get("project")
    if isinstance(project, dict) and isinstance(project.get("scripts"), dict):
        observe(
            Source.CONFIG,
            "Python CLI scripts are declared in the manifest.",
            file,
            metadata={"role": "entry"},
        )
    tool = data.get("tool")
    if isinstance(tool, dict) and "pytest" in tool:
        observe(
            Source.TEST,
            "pytest configuration is declared in the manifest.",
            file,
            metadata={"role": "framework"},
        )


def inspect_document(text: str, file: FileRecord, observe: Observer) -> None:
    parts = file.path.lower().split("/")
    is_decision = any(part in {"adr", "adrs", "decisions"} for part in parts[:-1])
    if is_decision:
        observe(
            Source.DOC,
            "Found a decision record. Read the source for its rationale.",
            file,
            metadata={"role": "decision"},
        )
    headings = {
        "setup": "setup",
        "getting started": "setup",
        "installation": "setup",
        "configuration": "environment",
        "environment variables": "environment",
        "testing": "test-instructions",
        "running tests": "test-instructions",
        "architecture": "architecture",
    }
    # Avoid drawing observations from shell and Markdown examples in fences.
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if marker := re.fullmatch(r"(`{3,}|~{3,})(.*)", stripped):
            if not fence:
                fence = marker[1]
                continue
            if marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
                continue
        if fence:
            continue
        if match := re.fullmatch(r"#{1,6}\s+(.+?)\s*#*\s*", stripped):
            if role := headings.get(match[1].lower()):
                observe(
                    Source.DOC,
                    "Located a recognized documentation heading.",
                    file,
                    number,
                    {"role": f"doc-{role}"},
                )


def inspect_test_report(text: str, file: FileRecord, observe: Observer) -> None:
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.IGNORECASE):
        observe(Source.TEST, "Configured test report has unsupported XML declarations.", file)
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        observe(Source.TEST, "Configured JUnit test report was not valid XML.", file)
        return
    if root.tag not in {"testsuite", "testsuites"}:
        observe(Source.TEST, "Configured test report was not recognized as JUnit XML.", file)
        return
    outcomes = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for case in root.iter("testcase"):
        if case.find("error") is not None:
            outcomes["errors"] += 1
        elif case.find("failure") is not None:
            outcomes["failed"] += 1
        elif case.find("skipped") is not None:
            outcomes["skipped"] += 1
        else:
            outcomes["passed"] += 1
    counts = ", ".join(f"{number} {state}" for state, number in outcomes.items())
    metadata = {
        "role": "recorded-test",
        "provenance": "external-unverified",
        **{key: str(value) for key, value in outcomes.items()},
    }
    timestamps = set()
    for suite in root.iter("testsuite"):
        timestamp = suite.get("timestamp", "")
        if "T" in timestamp and len(timestamp) <= 40:
            try:
                timestamps.add(datetime.fromisoformat(timestamp).isoformat())
            except ValueError:
                continue
    if len(timestamps) == 1:
        metadata["declared_timestamp"] = timestamps.pop()
    for name, pattern in (
        ("git.commit", r"(?:[a-f0-9]{40}|[a-f0-9]{64})"),
        ("framework", r"pytest|unittest|junit|jest"),
    ):
        values = {
            value
            for prop in root.iter("property")
            if prop.get("name") == name
            and (value := prop.get("value", ""))
            and re.fullmatch(pattern, value)
        }
        if len(values) == 1:
            metadata[f"declared_{name.replace('.', '_')}"] = values.pop()
    observe(
        Source.RESULT,
        f"Configured JUnit artifact records {counts} test cases.",
        file,
        metadata=metadata,
    )


def inspect_python(text: str, file: FileRecord, observe: Observer) -> None:
    try:
        for token in tokenize.generate_tokens(StringIO(text).readline):
            if token.type == tokenize.COMMENT and (marker := TODO.search(token.string)):
                observe(Source.TODO, f"Observed {marker.group()} comment.", file, token.start[0])
    except (tokenize.TokenError, SyntaxError):
        pass
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        observe(
            Source.SOURCE,
            "Static Python parsing did not succeed.",
            file,
            metadata={"role": "parse-error"},
        )
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            placeholder = len(body) == 1 and (
                isinstance(body[0], ast.Pass)
                or (
                    isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and body[0].value.value is Ellipsis
                )
            )
            if not body or placeholder:
                observe(
                    Source.SOURCE,
                    "Found a function without executable behavior.",
                    file,
                    node.lineno,
                    {"role": "stub"},
                )
            elif file.kind == Source.SOURCE:
                observe(
                    Source.SOURCE,
                    "Found a Python function with an executable body.",
                    file,
                    node.lineno,
                    {"role": "implementation"},
                )
    roles = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            if node.left.id == "__name__" and any(
                isinstance(item, ast.Constant) and item.value == "__main__"
                for item in node.comparators
            ):
                roles.add("entry")
        if isinstance(node, ast.Attribute) and node.attr in {"getenv", "environ"}:
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                roles.add("environment")
    if file.path.endswith("/__main__.py") or file.path == "__main__.py":
        roles.add("entry")
    for role in sorted(roles):
        description = (
            "Found a possible Python entry point."
            if role == "entry"
            else "Found a reference to process environment configuration."
        )
        observe(Source.SOURCE, description, file, metadata={"role": role})
