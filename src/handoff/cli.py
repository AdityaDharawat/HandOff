"""HandOff command-line interface."""

import sys
from collections import Counter
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import ParamSpec

import typer
from rich.console import Console
from rich.table import Table

from .config import HandoffError, safe_path
from .core import capture, initialize, published, resolve_root
from .freshness import differences
from .models import Progress, Source
from .reports import plan_reports, show_diff, write_reports
from .skill import synchronize
from .storage import load_snapshot, save_snapshot, writing
from .validation import check_evidence, report_issues, validate_reports

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
PATH = typer.Option(Path("."), "--path", help="Project root directory")
console = Console(highlight=False)


P = ParamSpec("P")


def command(function: Callable[P, None]) -> Callable[P, None]:
    @wraps(function)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            return function(*args, **kwargs)
        except typer.Exit:
            raise
        except HandoffError as exc:
            typer.echo(f"Error: {exc}", err=True)
        except (OSError, ValueError, RuntimeError):
            typer.echo("Error: Unable to access the project or managed state.", err=True)
        raise typer.Exit(1)

    return run


def emit(message: str) -> None:
    # Escape control and format characters while preserving real line separators.
    safe = "\n".join(
        "".join(c if c.isprintable() else ascii(c)[1:-1] for c in line)
        for line in message.split("\n")
    )
    typer.echo(safe)


@app.command("init")
@command
def init(path: Path = PATH) -> None:
    """Create local HandOff configuration and storage."""
    root = resolve_root(path)
    with writing(root):
        initialize(root)
    typer.echo("HandOff initialized.")


@app.command("scan")
@command
def scan_command(
    path: Path = PATH,
    json: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Observe the repository and save the latest snapshot."""
    root = resolve_root(path)
    with writing(root):
        current = capture(root)
        save_snapshot(root, "latest", current)
    if json:
        typer.echo(current.model_dump_json(indent=2))
    elif not quiet:
        table = Table("Observation", "Count or state")
        for label, value in (
            ("Text files", len(current.files)),
            ("Skipped encountered files", current.skipped_files),
            ("Evidence", len(current.evidence)),
            ("Git", current.git.state),
            ("Manifests", sum(e.source_type == Source.DEPENDENCY for e in current.evidence)),
            ("Documentation", sum(e.source_type == Source.DOC for e in current.evidence)),
            ("TODO markers", sum(e.source_type == Source.TODO for e in current.evidence)),
            ("Entry points", sum(e.metadata.get("role") == "entry" for e in current.evidence)),
        ):
            table.add_row(label, str(value))
        console.print(table)
        for issue in current.limitations:
            emit(issue)
        if verbose:
            for item in current.files:
                emit(item.path)


def publish(root: Path, output: str, force: bool, review: bool, yes: bool) -> None:
    with writing(root):
        old = published(root, optional=True)
        current = capture(root, output)
        if issues := check_evidence(root, current):
            raise HandoffError(" ".join(issues))
        baseline = old if old and old.output_dir == output else None
        if baseline is not None:
            comparable = current.model_copy(
                update={
                    "observed_at": baseline.observed_at,
                    "evidence": [
                        item.model_copy(update={"observed_at": baseline.observed_at})
                        for item in current.evidence
                    ],
                }
            )
            if comparable == baseline:
                current = baseline
        plans = plan_reports(root, output, current, baseline, force)
        if current is baseline and all(before == after for _, before, after in plans):
            typer.echo("Reports already match the current scan.")
            return
        if review:
            emit(show_diff(plans, baseline))
            if not yes and (not sys.stdin.isatty() or not typer.confirm("Apply report changes?")):
                raise HandoffError("Update cancelled. Use --yes for an unattended update.")
        with write_reports(root, plans):
            save_snapshot(root, "published", current)
    typer.echo("Published HANDOFF.md and HANDOFF_AGENT.md.")


@app.command()
@command
def generate(path: Path = PATH, output_dir: str = ".", force: bool = False) -> None:
    """Generate human and agent handovers with a local publication baseline."""
    output = output_dir.replace("\\", "/").removeprefix("./").rstrip("/") or "."
    if output_dir.startswith(("/", "\\")):
        raise HandoffError("Output directory must be repository-relative")
    publish(resolve_root(path), output, force, review=False, yes=False)


@app.command()
@command
def status(path: Path = PATH) -> None:
    """Show progress categories from the latest saved observations."""
    root = resolve_root(path)
    snapshot = (
        load_snapshot(root, "latest")
        if safe_path(root, ".handoff/snapshots/latest.json").exists()
        else load_snapshot(root, "published")
    )
    baseline = published(root, optional=True)
    if baseline and baseline.observed_at > snapshot.observed_at:
        snapshot = baseline
    emit(f"Saved snapshot observed {snapshot.observed_at.isoformat()}.")
    counts = Counter(f.status for f in snapshot.findings if f.status)
    for state in Progress:
        emit(f"{state.value} {counts[state]}")
    for item in snapshot.findings:
        if item.status:
            emit(f"{item.id} {item.summary}")


@app.command()
@command
def check(path: Path = PATH) -> None:
    """Compare the current project with the publication baseline."""
    root = resolve_root(path)
    old = load_snapshot(root, "published")
    current = capture(root, old.output_dir)
    reasons = differences(old, current)
    if reasons:
        emit("\n".join(reasons))
        raise typer.Exit(2)
    issues = check_evidence(root, old) or report_issues(root, old.output_dir, old)
    if issues:
        emit("\n".join(issues))
        raise typer.Exit(3)
    if current.limitations:
        emit("Unable to verify freshness for the full scope.")
        emit("\n".join(current.limitations))
        raise typer.Exit(1)
    typer.echo("No changes detected within the scan scope.")


@app.command()
@command
def explain(identifier: str, path: Path = PATH) -> None:
    """Show the provenance and confidence of an evidence or finding ID."""
    root = resolve_root(path)
    for name in ("published", "latest"):
        if not safe_path(root, f".handoff/snapshots/{name}.json").exists():
            continue
        snapshot = load_snapshot(root, name)
        evidence = {item.id: item for item in snapshot.evidence}
        if identifier in evidence:
            typer.echo("Historical observation from a saved snapshot.", err=True)
            typer.echo(evidence[identifier].model_dump_json(indent=2))
            return
        for finding in snapshot.findings:
            if finding.id == identifier:
                typer.echo(f"Saved finding observed {snapshot.observed_at.isoformat()}.", err=True)
                typer.echo(finding.model_dump_json(indent=2))
                for item in finding.evidence_ids:
                    if record := evidence.get(item):
                        typer.echo(record.model_dump_json(indent=2))
                return
    raise HandoffError("Unknown ID. Use an identifier from a current report or scan.")


@app.command()
@command
def validate(path: Path = PATH) -> None:
    """Check managed reports and stored evidence without changing them."""
    root = resolve_root(path)
    snapshot = load_snapshot(root, "published")
    issues = validate_reports(root, snapshot.output_dir, snapshot)
    if issues:
        emit("\n".join(issues))
        raise typer.Exit(3)
    typer.echo("Managed reports and evidence references are consistent.")


@app.command()
@command
def update(path: Path = PATH, yes: bool = False, force: bool = False) -> None:
    """Preview and confirm updated reports while preserving manual notes."""
    root = resolve_root(path)
    previous = load_snapshot(root, "published")
    publish(root, previous.output_dir, force, review=True, yes=yes)


@app.command()
@command
def skill(path: Path = PATH, provider: str = "both", check: bool = False) -> None:
    """Install or check portable Codex and Claude Code project skills."""
    synchronize(resolve_root(path), provider, check)
    typer.echo("Project skill copies match the packaged manifest.")
