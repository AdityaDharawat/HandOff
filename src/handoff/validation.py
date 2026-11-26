"""Check provenance, portable references, and exact managed report integrity."""

import re
from hashlib import sha256
from pathlib import Path

from .config import HandoffError, read_limited, safe_path
from .models import Confidence, Evidence, Finding, Progress, Snapshot, Source
from .reports import FILES, MAX_REPORT, render, report_path, split_managed

IDENTIFIER = re.compile(r"(?:ev|progress|decision|risk|action)-[a-f0-9]{20}")


def check_evidence(root: Path, snapshot: Snapshot, *, verify_content: bool = False) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    files = {file.path: file for file in snapshot.files}
    if len(files) != len(snapshot.files):
        issues.append("Duplicate inventory paths.")
    records: list[Evidence | Finding] = [*snapshot.evidence, *snapshot.findings]
    for entry in records:
        if entry.id in seen or not IDENTIFIER.fullmatch(entry.id):
            issues.append("Invalid or duplicate record identifier.")
        seen.add(entry.id)
    if snapshot.git.head and not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", snapshot.git.head):
        issues.append("Invalid Git HEAD identifier.")
    sources = {item.id: item for item in snapshot.evidence}
    for file in snapshot.files:
        try:
            path = safe_path(root, file.path)
            if not path.is_file():
                issues.append("An inventory reference is missing.")
            elif not 0 <= file.size <= 2097152 or not re.fullmatch(r"[a-f0-9]{64}", file.digest):
                issues.append("Invalid inventory size or digest.")
            elif verify_content and (
                path.stat().st_size != file.size
                or sha256(read_limited(path, file.size)).hexdigest() != file.digest
            ):
                issues.append("Evidence is stale because inventory content changed.")
        except HandoffError:
            issues.append("An inventory path is unsafe or changed during validation.")
        except OSError:
            issues.append("An inventory reference could not be read.")
    for item in snapshot.evidence:
        if item.line_end is not None and item.line_start is None:
            issues.append("Evidence line range has no start.")
        if item.source_path:
            referenced = files.get(item.source_path)
            if not referenced or item.content_hash != referenced.digest:
                issues.append("Evidence references an unknown file or mismatched digest.")
            elif item.line_start and not (
                item.line_start <= (item.line_end or item.line_start) <= referenced.lines
            ):
                issues.append("Evidence line range is outside the recorded file.")
    for finding in snapshot.findings:
        refs = [sources.get(ref) for ref in finding.evidence_ids]
        if not refs or not all(refs):
            issues.append("Finding lacks resolvable supporting evidence.")
        if finding.status == Progress.COMPLETED_VERIFIED and (
            finding.confidence != Confidence.VERIFIED
            or not any(ref and ref.source_type == Source.RESULT for ref in refs)
        ):
            issues.append("Verified completion lacks test-result evidence.")
        elif finding.status == Progress.COMPLETED_VERIFIED:
            issues.append("Verified completion lacks independently verified feature provenance.")
        if finding.kind == "action" and not finding.validation:
            issues.append("Action lacks a validation criterion.")
    return sorted(set(issues))


def validate_reports(root: Path, directory: str, snapshot: Snapshot) -> list[str]:
    issues = check_evidence(root, snapshot, verify_content=True)
    return issues or report_issues(root, directory, snapshot)


def report_issues(root: Path, directory: str, snapshot: Snapshot) -> list[str]:
    issues = []
    for index, name in enumerate(FILES):
        try:
            data = read_limited(report_path(root, directory, name), MAX_REPORT)
            if split_managed(data)[1] != render(snapshot, bool(index)):
                issues.append(f"{name} differs from its published evidence.")
        except (OSError, HandoffError):
            issues.append(f"{name} is missing, unreadable or has invalid markers.")
    return issues
