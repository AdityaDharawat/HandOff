from handoff.config import Settings, WorkItem
from handoff.intelligence import analyze
from handoff.models import Progress
from handoff.scanner.repository import scan


def test_progress_requires_more_than_a_test_filename(tmp_path):
    (tmp_path / "test_api.py").write_text("def test_api():\n    assert False\n")
    (tmp_path / "main.py").write_text("def api():\n    pass\n")
    snapshot = analyze(scan(tmp_path, Settings()))
    statuses = {item.status for item in snapshot.findings}
    assert Progress.PARTIALLY_IMPLEMENTED in statuses
    assert Progress.COMPLETED_VERIFIED not in statuses
    assert any(item.validation for item in snapshot.findings)
    evidence = {item.id for item in snapshot.evidence}
    assert all(set(item.evidence_ids) <= evidence for item in snapshot.findings)


def test_explicit_work_declarations_are_linked_without_exporting_notes(tmp_path):
    (tmp_path / "plan.md").write_text("# Private work plan\n")
    (tmp_path / "blocker.md").write_text("# Private dependency details\n")
    settings = Settings(
        work_items=[
            WorkItem(path="plan.md", state="not_started"),
            WorkItem(path="blocker.md", state="blocked"),
            WorkItem(path="missing.md", state="blocked"),
        ]
    )
    snapshot = analyze(scan(tmp_path, settings))
    assert {item.status for item in snapshot.findings if item.status} == {
        Progress.NOT_STARTED,
        Progress.BLOCKED,
    }
    assert any("outside the visible inventory" in issue for issue in snapshot.limitations)
    assert "Private" not in snapshot.model_dump_json()
