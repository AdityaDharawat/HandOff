import shutil
import subprocess

import pytest
import yaml
from typer.testing import CliRunner

from handoff.cli import app
from handoff.core import capture
from handoff.models import Progress, Source
from handoff.skill import DESTINATIONS, manifest


@pytest.fixture
def git(tmp_path):
    if not shutil.which("git"):
        pytest.skip("Git is required")

    def run(*args):
        return (
            subprocess.check_output(
                [
                    "git",
                    "-c",
                    "user.name=HandOff Test",
                    "-c",
                    "user.email=test@example.invalid",
                    *args,
                ],
                cwd=tmp_path,
            )
            .decode()
            .strip()
        )

    run("init", "-q")
    return run


def test_misleading_commit_and_dirty_state(tmp_path, git):
    source = tmp_path / "auth.py"
    source.write_bytes(b"def refresh_token():\n    ...\n")
    git("add", "auth.py")
    git("commit", "-qm", "Authentication complete and fully verified")
    source.write_bytes(b"def refresh_token():\n    pass\n")
    (tmp_path / "untracked.py").write_bytes(b"answer = 42\n")
    current = capture(tmp_path)
    assert current.git.head == git("rev-parse", "HEAD")
    assert current.git.changes["auth.py"] == "working bytes differ from index"
    assert current.git.changes["untracked.py"] == "untracked"
    assert any(f.status == Progress.PARTIALLY_IMPLEMENTED for f in current.findings)
    assert not any(f.status == Progress.COMPLETED_VERIFIED for f in current.findings)
    assert "fully verified" not in current.model_dump_json()


def test_configured_junit_records_failures_without_copying_logs(tmp_path):
    state = tmp_path / ".handoff"
    state.mkdir()
    (state / "config.yaml").write_text("test_report: junit.xml\n")
    (tmp_path / "junit.xml").write_text(
        "<testsuites><testsuite><testcase><failure>PRIVATE LOG</failure></testcase>"
        "<testcase/><testcase><skipped/></testcase></testsuite></testsuites>"
    )
    result = capture(tmp_path)
    [evidence] = [e for e in result.evidence if e.source_type == Source.RESULT]
    assert evidence.metadata == {
        "role": "recorded-test",
        "failed": "1",
        "passed": "1",
        "skipped": "1",
        "errors": "0",
        "provenance": "external-unverified",
    }
    assert "PRIVATE LOG" not in result.model_dump_json()
    assert any(f.kind == "risk" and evidence.id in f.evidence_ids for f in result.findings)


def test_junit_metadata_remains_a_declaration(tmp_path):
    (tmp_path / ".handoff").mkdir()
    (tmp_path / ".handoff/config.yaml").write_text("test_report: junit.xml\n")
    commit = "a" * 40
    (tmp_path / "junit.xml").write_text(
        '<testsuite timestamp="2026-01-01T00:00:00Z"><properties>'
        f'<property name="git.commit" value="{commit}"/>'
        '<property name="framework" value="pytest"/>'
        '<property name="command" value="private command line"/>'
        "</properties><testcase><error/></testcase></testsuite>"
    )
    snapshot = capture(tmp_path)
    [item] = [e for e in snapshot.evidence if e.source_type == Source.RESULT]
    assert item.metadata["declared_git_commit"] == commit
    assert item.metadata["declared_timestamp"] == "2026-01-01T00:00:00+00:00"
    assert item.metadata["declared_framework"] == "pytest"
    assert item.metadata["errors"] == "1"
    assert item.commit_hash is None
    assert "private command line" not in snapshot.model_dump_json()


def test_install_and_check_project_skills(tmp_path):
    args = ["skill", "--path", str(tmp_path)]
    runner = CliRunner()
    assert runner.invoke(app, [*args, "--check"]).exit_code == 1
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, [*args, "--check"]).exit_code == 0
    metadata = yaml.safe_load(manifest().decode().split("---", 2)[1])
    assert metadata["name"] == "handoff"
    assert metadata["description"]
    for target in DESTINATIONS.values():
        assert (tmp_path / target).read_bytes() == manifest()
    codex = tmp_path / DESTINATIONS["codex"]
    codex.write_bytes(b"local instructions")
    assert runner.invoke(app, args).exit_code == 1
    assert codex.read_bytes() == b"local instructions"
