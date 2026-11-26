from os import utime

from typer.testing import CliRunner

from handoff.cli import app
from handoff.core import capture
from handoff.models import Confidence, Finding, Progress, Source, stable_id
from handoff.validation import check_evidence

runner = CliRunner()


def test_check_rejects_edited_managed_report(tmp_path):
    args = ["--path", str(tmp_path)]
    assert runner.invoke(app, ["generate", *args]).exit_code == 0
    report = tmp_path / "HANDOFF.md"
    report.write_bytes(report.read_bytes().replace(b"# Project handover", b"# Edited"))
    result = runner.invoke(app, ["check", *args])
    assert result.exit_code == 3
    assert "differs from its published evidence" in result.output


def test_validation_checks_content_even_with_unchanged_timestamp(tmp_path):
    args = ["--path", str(tmp_path)]
    source = tmp_path / "main.py"
    source.write_bytes(b"def run():\n    return 1\n")
    assert runner.invoke(app, ["generate", *args]).exit_code == 0
    original = source.stat()
    source.write_bytes(b"def run():\n    return 2\n")
    utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert source.stat().st_mtime_ns == original.st_mtime_ns
    result = runner.invoke(app, ["validate", *args])
    assert result.exit_code == 3
    assert "Evidence is stale" in result.output


def test_repeated_publication_preserves_reports_and_snapshot(tmp_path):
    args = ["--path", str(tmp_path)]
    assert runner.invoke(app, ["generate", *args]).exit_code == 0
    report = tmp_path / "HANDOFF.md"
    report.write_bytes(b"Before\r\n" + report.read_bytes() + b"After\r\n")
    snapshot = tmp_path / ".handoff/snapshots/published.json"
    before = (report.read_bytes(), snapshot.read_bytes())
    assert runner.invoke(app, ["update", *args]).exit_code == 0
    assert runner.invoke(app, ["generate", *args]).exit_code == 0
    assert (report.read_bytes(), snapshot.read_bytes()) == before
    assert not (tmp_path / ".handoff/backups").exists()


def test_passing_external_artifact_cannot_support_verified_completion(tmp_path):
    (tmp_path / ".handoff").mkdir()
    (tmp_path / ".handoff/config.yaml").write_text("test_report: junit.xml\n")
    (tmp_path / "junit.xml").write_text("<testsuite><testcase/></testsuite>")
    snapshot = capture(tmp_path)
    [result] = [item for item in snapshot.evidence if item.source_type == Source.RESULT]
    snapshot.findings.append(
        Finding(
            id=stable_id("progress", "external"),
            kind="progress",
            summary="Completed",
            status=Progress.COMPLETED_VERIFIED,
            confidence=Confidence.VERIFIED,
            evidence_ids=[result.id],
        )
    )
    assert result.metadata["provenance"] == "external-unverified"
    assert check_evidence(tmp_path, snapshot) == [
        "Verified completion lacks independently verified feature provenance."
    ]
