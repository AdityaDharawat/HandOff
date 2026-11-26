"""Bounded configuration loading and portable path checks."""

from pathlib import Path, PureWindowsPath
from typing import Literal
from unicodedata import category

import yaml
from pydantic import Field, ValidationError, field_validator

from .models import Record


class HandoffError(Exception):
    """An actionable operational error."""


class WorkItem(Record):
    path: str = Field(min_length=1, max_length=512)
    state: Literal["not_started", "blocked"]


class Settings(Record):
    max_depth: int = Field(default=12, ge=0, le=64)
    max_files: int = Field(default=3000, ge=1, le=20000)
    max_bytes: int = Field(default=262144, ge=1, le=2097152)
    excludes: list[str] = Field(default_factory=list, max_length=128)
    test_report: str | None = Field(default=None, max_length=512)
    work_items: list[WorkItem] = Field(default_factory=list, max_length=128)

    @field_validator("work_items")
    @classmethod
    def unique_work_paths(cls, items: list[WorkItem]) -> list[WorkItem]:
        if len({item.path for item in items}) != len(items):
            raise ValueError("Work item paths must be unique")
        return items


def safe_path(root: Path, name: str) -> Path:
    parts = name.split("/")
    if PureWindowsPath(name).drive or any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or PureWindowsPath(part).is_reserved()
        or any(category(c) in {"Cc", "Cf", "Cs"} or c in '\\:<>"|?*' for c in part)
        for part in parts
    ):
        raise HandoffError("Expected a portable repository-relative path")
    result = root
    for part in parts:
        result = result / part
        if result.is_symlink() or (result.exists() and result.resolve() != result):
            raise HandoffError("Path crosses a symbolic link or filesystem redirect")
    return result


def read_limited(path: Path, limit: int) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise HandoffError("Expected an ordinary file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise HandoffError("File exceeds the configured byte limit")
    return data


def load_settings(root: Path) -> Settings:
    path = safe_path(root, ".handoff/config.yaml")
    if not path.exists():
        return Settings()
    try:
        data = yaml.safe_load(read_limited(path, 32768))
        return Settings.model_validate({} if data is None else data)
    except (yaml.YAMLError, ValidationError, UnicodeError, RecursionError) as exc:
        raise HandoffError(
            "Invalid .handoff/config.yaml. Check setting names and value ranges."
        ) from exc
