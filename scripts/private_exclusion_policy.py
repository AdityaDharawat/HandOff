"""Load an owner's private directory exclusions without disclosing their values."""

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec

POLICY_FILE = ".handoff-private-exclusions.yml"
IGNORE_FILE = ".handoff-private-exclusions.gitignore"
SEAL_FILE = "scripts/private-exclusion-policy.sha256"
POLICY_ENV = "HANDOFF_PRIVATE_EXCLUSION_POLICY"
POLICY_NAMES = {POLICY_FILE, IGNORE_FILE}
LIMIT = 64 * 1024
DIRECTORY = re.compile(r"\.?[A-Za-z0-9][A-Za-z0-9._-]{0,95}")


class PolicyError(Exception):
    """An error with a public-safe message."""


def safe_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not re.search(r"[\x00-\x1f\\:]", value)
        and all(
            part not in {"", ".", ".."} and not part.endswith((" ", "."))
            for part in value.split("/")
        )
    )


def require(condition: bool) -> None:
    if not condition:
        raise PolicyError("Private policy malformed or unsupported.")


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


@dataclass(frozen=True)
class PrivatePolicy:
    git_ignore: tuple[str, ...]
    tracked_dirs: frozenset[str]

    def protects(self, path: PurePosixPath) -> bool:
        return bool(self.tracked_dirs.intersection(part.casefold() for part in path.parts[:-1]))

    def discloses(self, data: bytes) -> bool:
        decoded = data.decode("utf-8", errors="replace").casefold()
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            decoded += data.decode("utf-16", errors="replace").casefold()
        return any(directory.lstrip(".") in decoded for directory in self.tracked_dirs)


def load_policy(root: Path, from_env: bool = False) -> PrivatePolicy:
    if from_env:
        raw = os.environ.pop(POLICY_ENV, "").encode("utf-8")
        if not raw:
            raise PolicyError("Private policy missing.")
    else:
        path = root / POLICY_FILE
        try:
            if path.is_symlink() or not path.is_file():
                if not path.exists() and not path.is_symlink():
                    raise PolicyError("Private policy missing.")
                raise PolicyError("Private policy unreadable.")
            with path.open("rb") as stream:
                raw = stream.read(LIMIT + 1)
        except OSError:
            raise PolicyError("Private policy unreadable.") from None
    require(0 < len(raw) <= LIMIT)
    try:
        data = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise PolicyError("Private policy malformed or unsupported.") from None
    require(
        isinstance(data, dict)
        and set(data) == {"version", "nonce", "git_ignore", "tracked_dirs", "regression"}
    )
    require(type(data["version"]) is int and data["version"] == 1)
    require(
        isinstance(data["nonce"], str) and re.fullmatch(r"[0-9a-f]{64}", data["nonce"]) is not None
    )
    rules, dirs, cases = data["git_ignore"], data["tracked_dirs"], data["regression"]
    require(isinstance(rules, list) and 0 < len(rules) <= 128)
    require(isinstance(dirs, list) and 0 < len(dirs) <= 128)
    require(isinstance(cases, list) and 0 < len(cases) <= 512)
    require(
        all(
            isinstance(rule, str) and rule.endswith("/") and DIRECTORY.fullmatch(rule[:-1])
            for rule in rules
        )
    )
    require(
        all(
            isinstance(name, str) and DIRECTORY.fullmatch(name) and name == name.casefold()
            for name in dirs
        )
    )
    require(len(set(rules)) == len(rules) and len(set(dirs)) == len(dirs))
    require(set(dirs) == {rule[:-1].casefold() for rule in rules})
    policy = PrivatePolicy(tuple(rules), frozenset(dirs))

    try:
        generic = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise PolicyError("Private policy regression unavailable.") from None
    baseline = GitIgnoreSpec.from_lines(generic)
    combined = GitIgnoreSpec.from_lines([*generic, *rules])
    seen: set[str] = set()
    covered: set[tuple[str, bool]] = set()
    for case in cases:
        require(
            isinstance(case, dict) and set(case) == {"path", "ignored", "tracked", "legacy_only"}
        )
        path = case["path"]
        require(safe_path(path) and path not in seen)
        require(all(type(case[key]) is bool for key in ("ignored", "tracked", "legacy_only")))
        seen.add(path)
        ignored = combined.match_file(path)
        legacy_only = ignored and not baseline.match_file(path)
        parsed = PurePosixPath(path)
        if (ignored, policy.protects(parsed), legacy_only) != (
            case["ignored"],
            case["tracked"],
            case["legacy_only"],
        ):
            raise PolicyError("Private policy regression detected.")
        if legacy_only:
            for i, part in enumerate(parsed.parts[:-1]):
                if part + "/" in rules:
                    covered.add((part + "/", i > 0))
    if covered != {(rule, nested) for rule in rules for nested in (False, True)}:
        raise PolicyError("Private policy regression coverage incomplete.")
    try:
        seal = (root / SEAL_FILE).read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        raise PolicyError("Private policy integrity seal unavailable.") from None
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("ascii")
    if not hmac.compare_digest(hashlib.sha256(canonical).hexdigest(), seal):
        raise PolicyError("Private policy integrity check failed.")
    return policy
