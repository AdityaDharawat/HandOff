from handoff.core import capture
from handoff.models import Progress
from handoff.scanner import git
from handoff.scanner.git import parse_entries


def test_git_metadata_parser_handles_malformed_records_and_conflicts():
    assert parse_entries(["incomplete"], index=True) is None
    assert parse_entries(["100644 invalid 0\tapp.py"], index=True) is None
    oid = "a" * 40
    assert parse_entries([f"100644 {oid} 2\tapp.py"], index=True) == {"app.py": ""}


def test_numeric_expression_is_not_a_docstring(tmp_path):
    (tmp_path / "main.py").write_text("def run():\n    42\n")
    snapshot = capture(tmp_path)
    assert [item.status for item in snapshot.findings if item.status] == [
        Progress.IMPLEMENTED_UNVERIFIED
    ]


def test_evidence_budget_caps_many_comments(tmp_path):
    path = tmp_path / "main.py"
    path.write_bytes(b"# TODO\n" * 12001)
    snapshot = capture(tmp_path)
    assert len(snapshot.evidence) == 12000
    assert "Scan reached the evidence record budget." in snapshot.limitations


def test_missing_git_produces_inconclusive_freshness(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(git.shutil, "which", lambda name: None)
    snapshot = capture(tmp_path)
    assert snapshot.git.state == "unavailable"
    assert "Git metadata was unavailable." in snapshot.limitations
