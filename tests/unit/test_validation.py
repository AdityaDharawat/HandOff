import pytest

from handoff.config import HandoffError
from handoff.core import capture
from handoff.freshness import differences
from handoff.models import Confidence, Finding, Progress, stable_id
from handoff.storage import writing
from handoff.validation import check_evidence


def test_reject_unsupported_completion(tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    return 42\n")
    snapshot = capture(tmp_path)
    snapshot.findings.append(
        Finding(
            id=stable_id("progress", "unsupported"),
            kind="progress",
            summary="Feature completes",
            status=Progress.COMPLETED_VERIFIED,
            confidence=Confidence.VERIFIED,
            evidence_ids=[snapshot.evidence[0].id],
        )
    )
    assert check_evidence(tmp_path, snapshot) == ["Verified completion lacks test-result evidence."]


def test_freshness_explains_new_removed_and_configured_files(tmp_path):
    (tmp_path / "requirements.txt").write_text("rich>=13\n")
    initial = capture(tmp_path)
    (tmp_path / "requirements.txt").unlink()
    (tmp_path / "pyproject.toml").write_text("[project.scripts]\na = 'module:main'\n")
    state = tmp_path / ".handoff"
    state.mkdir()
    (state / "config.yaml").write_text("max_depth: 1\n")
    updated = capture(tmp_path)
    assert differences(initial, updated) == [
        "Changed scan settings",
        "Added pyproject.toml",
        "Removed requirements.txt",
    ]
    assert any(e.metadata.get("role") == "entry" for e in updated.evidence)


def test_writer_lock_preserves_current_owner(tmp_path):
    lock = tmp_path / ".handoff" / "write.lock"
    with writing(tmp_path):
        assert lock.exists()
        with pytest.raises(HandoffError, match="Another writer"), writing(tmp_path):
            pytest.fail("Concurrent writer entered the critical section")
        assert lock.exists()
    assert not lock.exists()
