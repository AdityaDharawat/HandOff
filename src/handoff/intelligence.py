"""Derive narrowly scoped findings from observed evidence."""

from typing import Literal

from .models import Confidence, Evidence, Finding, Progress, Snapshot, Source, stable_id


def analyze(snapshot: Snapshot) -> Snapshot:
    findings: list[Finding] = []

    def emit(
        kind: Literal["progress", "decision", "risk", "action"],
        summary: str,
        items: list[Evidence],
        confidence: Confidence,
        *,
        status: Progress | None = None,
        priority: Literal["high", "medium", "low"] | None = None,
        validation: str | None = None,
    ) -> None:
        ids = [item.id for item in items]
        findings.append(
            Finding(
                id=stable_id(kind, summary, *ids),
                kind=kind,
                summary=summary,
                evidence_ids=ids,
                confidence=confidence,
                status=status,
                priority=priority,
                validation=validation,
            )
        )

    groups: dict[str, list[Evidence]] = {}
    for item in snapshot.evidence:
        if item.source_path:
            groups.setdefault(item.source_path, []).append(item)
    environment_documented = any(
        item.metadata.get("role") == "doc-environment" for item in snapshot.evidence
    )
    tests = [item for item in snapshot.evidence if item.source_type == Source.TEST]
    for items in groups.values():
        for item in items:
            match item.metadata.get("role"):
                case "decision":
                    emit(
                        "decision",
                        "Decision record located. Rationale remains unassessed.",
                        [item],
                        Confidence.VERIFIED,
                    )
                case "script-declaration":
                    emit(
                        "progress",
                        "An exported function declaration was observed. Its behavior is unknown.",
                        [item],
                        Confidence.UNCERTAIN,
                        status=Progress.UNKNOWN,
                    )
                case "stub":
                    emit(
                        "progress",
                        "A function has a placeholder body. Feature scope is uncertain.",
                        [item],
                        Confidence.UNCERTAIN,
                        status=Progress.PARTIALLY_IMPLEMENTED,
                    )
                    emit(
                        "action",
                        "Review the declaration and establish its intended behavior.",
                        [item],
                        Confidence.INFERRED,
                        priority="high",
                        validation="Document its contract and verify a focused behavior test.",
                    )
                case "parse-error":
                    emit(
                        "risk",
                        "Static parsing failed for a Python file or manifest.",
                        [item],
                        Confidence.VERIFIED,
                        priority="medium",
                    )
                    emit(
                        "action",
                        "Inspect the parse failure in the supported Python environment.",
                        [item],
                        Confidence.INFERRED,
                        priority="medium",
                        validation="Record the supported interpreter and a successful syntax check.",
                    )
                case "environment" if not environment_documented:
                    emit(
                        "risk",
                        "Environment requirements may need documentation.",
                        [item],
                        Confidence.INFERRED,
                        priority="medium",
                    )
                case "implementation":
                    emit(
                        "progress",
                        "A function body exists. Its behavior has not been verified.",
                        [item],
                        Confidence.VERIFIED,
                        status=Progress.IMPLEMENTED_UNVERIFIED,
                    )
                case "work-item":
                    emit(
                        "progress",
                        "Operator-declared work state. Review the cited file for scope.",
                        [item],
                        Confidence.INFERRED,
                        status=Progress(item.metadata["state"]),
                    )
                    if item.metadata["state"] == "blocked":
                        emit(
                            "action",
                            "Confirm the declared blocker and identify its resolution criteria.",
                            [item],
                            Confidence.INFERRED,
                            priority="high",
                            validation="Record the dependency or decision needed to proceed.",
                        )
                case "recorded-test" if (
                    item.metadata.get("failed", "0") != "0"
                    or item.metadata.get("errors", "0") != "0"
                ):
                    emit(
                        "risk",
                        "A supplied test artifact records failures. Its baseline is unknown.",
                        [item],
                        Confidence.VERIFIED,
                        priority="high",
                    )
                    emit(
                        "action",
                        "Review the recorded test failures against the current project.",
                        [item],
                        Confidence.INFERRED,
                        priority="high",
                        validation="Identify the tested revision and reproduce results with authorization.",
                    )
            if item.source_type == Source.TODO:
                emit(
                    "action",
                    "Review the marker in context and decide whether work is needed.",
                    [item],
                    Confidence.UNCERTAIN,
                    priority="low",
                    validation="Record the decision against the referenced line.",
                )
        if items[0].source_type == Source.SOURCE and len(items) == 1:
            emit(
                "progress",
                "Source code is present. Feature and implementation status are unknown.",
                items,
                Confidence.UNKNOWN,
                status=Progress.UNKNOWN,
            )
    if tests:
        emit(
            "action",
            "Establish a test baseline after reviewing the project test instructions.",
            tests[:10],
            Confidence.INFERRED,
            priority="medium",
            validation="Record the command, environment, and observed result.",
        )
    elif declarations := [
        item for item in snapshot.evidence if item.metadata.get("role") == "script-declaration"
    ]:
        emit(
            "action",
            "Establish a verification baseline for observed exported behavior.",
            declarations[:3],
            Confidence.INFERRED,
            priority="medium",
            validation="Confirm the intended behavior and record one focused test result.",
        )
    priority = {"high": 0, "medium": 1, "low": 2, None: 3}
    return snapshot.model_copy(
        update={"findings": sorted(findings, key=lambda item: (priority[item.priority], item.id))}
    )
