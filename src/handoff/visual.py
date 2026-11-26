"""Versioned, read-only visual projection of existing scan evidence."""

import ast
import json
import posixpath
import re
import tomllib
from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from .config import HandoffError, read_limited, safe_path
from .core import capture
from .models import Snapshot
from .scanner.script import EXTENSIONS as SCRIPT_EXTENSIONS
from .scanner.script import visible_lines

LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".css": "CSS",
    ".html": "HTML",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
}
PACKAGE = re.compile(r"^(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_.-]+")
VERSION = re.compile(r"^[a-zA-Z0-9 .,^~<>=!*|+_-]{1,50}$")
STATIC_IMPORT = re.compile(
    r"""^\s*import\s+(?:[\w$*{},\s]+\s+from\s+)?["']([@.][\w./-]+)["']\s*;?\s*$"""
)


def script_relationships(
    raw: bytes, name: str, available: set[str], alias: str | None = None
) -> list[dict[str, str | int]]:
    links: list[dict[str, str | int]] = []
    for line_number, line in visible_lines(raw.decode("utf-8")):
        if not (match := STATIC_IMPORT.fullmatch(line)):
            continue
        target = match[1]
        configured = target.startswith("@/")
        if configured and alias is not None:
            base = posixpath.normpath(posixpath.join(alias, target[2:]))
        elif target.startswith(("./", "../")):
            base = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        else:
            continue
        if base.startswith("../") or base.startswith("/"):
            continue
        paths = [base]
        if not PurePosixPath(base).suffix:
            paths.extend(base + extension for extension in SCRIPT_EXTENSIONS)
            paths.extend(base + "/index" + extension for extension in SCRIPT_EXTENSIONS)
        targets = [target for target in paths if target in available and target != name]
        if len(targets) == 1:
            edge: dict[str, str | int] = {
                "source": name,
                "target": targets[0],
                "line": line_number,
                "kind": "static import",
            }
            if configured:
                edge["configuration"] = "tsconfig.json"
            links.append(edge)
    return links


def configured_alias(raw: bytes) -> str | None:
    try:
        config = json.loads(raw)
        options = config.get("compilerOptions", {})
        values = options.get("paths", {}).get("@/*", [])
        base_url = options.get("baseUrl", ".")
        if (
            isinstance(base_url, str)
            and re.fullmatch(r"[.\w/-]{1,120}", base_url)
            and isinstance(values, list)
            and len(values) == 1
            and isinstance(values[0], str)
            and re.fullmatch(r"[.\w/-]{1,120}/\*", values[0])
        ):
            base = posixpath.normpath(posixpath.join(base_url, values[0][:-2]))
            if not base.startswith("/") and base != ".." and not base.startswith("../"):
                return base
    except (ValueError, TypeError, AttributeError, RecursionError):
        return None
    return None


def read_observed(root: Path, name: str, size: int, digest: str) -> bytes:
    raw = read_limited(safe_path(root, name), size)
    if sha256(raw).hexdigest() != digest:
        raise HandoffError("An analysis input changed in flight.")
    return raw


def source_relationships(
    raw: bytes,
    name: str,
    modules: dict[str, str],
) -> list[dict[str, str | int]]:
    tree = ast.parse(raw.decode("utf-8"))
    owner = name.removeprefix("src/").removesuffix(".py").replace("/", ".")
    package = owner.rpartition(".")[0].split(".") if "." in owner else []
    links: list[dict[str, str | int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        targets = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level > len(package):
                continue
            base = ".".join([*package[: len(package) - node.level + 1], node.module or ""])
            if not node.level:
                base = node.module or ""
            base = base.strip(".")
            targets = [f"{base}.{alias.name}".strip(".") for alias in node.names]
            if not any(target in modules for target in targets):
                targets = [base]
        for target in targets:
            if target in modules and modules[target] != name:
                links.append(
                    {
                        "source": name,
                        "target": modules[target],
                        "line": node.lineno,
                        "kind": "static import",
                    }
                )
    return links


def dependencies(raw: bytes, name: str) -> list[dict[str, str]]:
    if name.endswith("pyproject.toml"):
        parsed = tomllib.loads(raw.decode())
        project = parsed.get("project", {})
        if not isinstance(project, dict):
            return []
        groups = [(project.get("dependencies", []), "runtime")]
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            groups.extend((items, "optional") for items in optional.values())
        entries = [
            (match[0], item[match.end() :].strip(), role)
            for items, role in groups
            if isinstance(items, list)
            for item in items
            if isinstance(item, str) and (match := PACKAGE.match(item))
        ]
    else:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return []
        entries = [
            (package, version, role)
            for field, role in (("dependencies", "runtime"), ("devDependencies", "development"))
            if isinstance(group := parsed.get(field), dict)
            for package, version in group.items()
            if PACKAGE.fullmatch(package) and isinstance(version, str)
        ]
    return [
        {
            "name": package,
            "version": version if VERSION.fullmatch(version) else "",
            "scope": role,
            "source": name,
        }
        for package, version, role in entries
    ]


def project_model(root: Path, snapshot: Snapshot) -> dict[str, Any]:
    files = snapshot.files
    module_names: dict[str, str] = {}
    ambiguous = set()
    for file in files:
        if file.path.endswith(".py"):
            module = file.path.removeprefix("src/").removesuffix(".py").replace("/", ".")
            module = module.removesuffix(".__init__")
            if module in module_names:
                ambiguous.add(module)
            module_names[module] = file.path
    modules = {module: path for module, path in module_names.items() if module not in ambiguous}
    edges: list[dict[str, str | int]] = []
    packages: list[dict[str, str]] = []
    stale_inputs = False
    available = {file.path for file in files}
    alias = None
    for file in files:
        if file.path == "tsconfig.json":
            try:
                alias = configured_alias(read_observed(root, file.path, file.size, file.digest))
            except (OSError, HandoffError):
                stale_inputs = True
            break
    for file in files:
        name = file.path
        is_manifest = PurePosixPath(name).name in {"package.json", "pyproject.toml"}
        if not is_manifest and (
            not name.endswith((".py", *SCRIPT_EXTENSIONS)) or len(edges) >= 800
        ):
            continue
        try:
            raw = read_observed(root, name, file.size, file.digest)
            if is_manifest and len(packages) < 2000:
                packages.extend(dependencies(raw, name)[: 2000 - len(packages)])
            elif not is_manifest and name.endswith(".py"):
                edges.extend(source_relationships(raw, name, modules)[: 800 - len(edges)])
            elif not is_manifest:
                edges.extend(script_relationships(raw, name, available, alias)[: 800 - len(edges)])
        except (OSError, HandoffError):
            stale_inputs = True
        except (ValueError, SyntaxError, RecursionError):
            continue
    status = Counter(str(item.status) for item in snapshot.findings if item.status)
    languages = Counter(
        LANGUAGES[suffix]
        for file in files
        if (suffix := PurePosixPath(file.path).suffix.lower()) in LANGUAGES
    )
    return {
        "schema_version": 1,
        "snapshot": snapshot.model_dump(mode="json"),
        "counts": {
            "files": len(files),
            "bytes": sum(file.size for file in files),
            "evidence": len(snapshot.evidence),
            "status": dict(status),
        },
        "languages": dict(languages.most_common()),
        "packages": packages,
        "edges": edges,
        "analysis_notes": [
            *snapshot.limitations,
            *(
                ["Some source changed during visual analysis. Refresh to retry."]
                if stale_inputs
                else []
            ),
            *(["The graph reached its 800 relationship limit."] if len(edges) >= 800 else []),
            *(
                ["The dependency view reached its 2,000 package limit."]
                if len(packages) >= 2000
                else []
            ),
        ],
    }


def analyze_project(root: Path) -> dict[str, Any]:
    return project_model(root, capture(root))
