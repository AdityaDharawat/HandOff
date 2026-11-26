"""Portable snapshot and intelligence schema."""

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrEnum):
    FILESYSTEM = "filesystem"
    SOURCE = "source_code"
    DOC = "documentation"
    COMMIT = "git_commit"
    STATUS = "git_status"
    TODO = "todo_marker"
    DEPENDENCY = "dependency_manifest"
    CONFIG = "configuration"
    TEST = "test_discovery"
    RESULT = "test_result"
    NOTE = "user_note"


class Confidence(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class Progress(StrEnum):
    COMPLETED_VERIFIED = "completed_verified"
    IMPLEMENTED_UNVERIFIED = "implemented_unverified"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    NOT_STARTED = "not_started"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


def stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{sha256(repr(parts).encode()).hexdigest()[:20]}"


class Evidence(Record):
    id: str
    source_type: Source
    source_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    commit_hash: str | None = None
    observed_at: datetime
    description: str
    evidence_strength: Literal["direct", "indirect"] = "direct"
    confidence: Confidence = Confidence.VERIFIED
    content_hash: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class FileRecord(Record):
    path: str
    kind: str
    size: int = Field(ge=0)
    lines: int = Field(ge=0)
    digest: str


class GitState(Record):
    state: Literal["available", "absent", "unavailable"] = "absent"
    branch: str | None = None
    head: str | None = None
    changes: dict[str, str] = Field(default_factory=dict)
    commits: list[str] = Field(default_factory=list)


class Finding(Record):
    id: str
    kind: Literal["progress", "decision", "risk", "action"]
    summary: str
    confidence: Confidence
    evidence_ids: list[str]
    status: Progress | None = None
    priority: Literal["high", "medium", "low"] | None = None
    validation: str | None = None


class Snapshot(Record):
    schema_version: Literal[1] = 1
    observed_at: datetime
    project: str
    config_digest: str
    output_dir: str = "."
    skipped_files: int = Field(default=0, ge=0)
    report_style: Literal["legacy", "visual"] = "legacy"
    git: GitState
    files: list[FileRecord]
    evidence: list[Evidence]
    findings: list[Finding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
