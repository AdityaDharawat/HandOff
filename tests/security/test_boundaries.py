import json
import os
import subprocess

import pytest
from typer.testing import CliRunner

from handoff.cli import app
from handoff.config import HandoffError, Settings, load_settings, safe_path
from handoff.scanner.repository import scan

runner = CliRunner()


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/outside",
        "C:/outside",
        "a/../b",
        "lpt1",
        "a//b",
        "x:stream",
        "//host/share",
        "C:relative",
        "name\u202e.py",
        "name\udcff.py",
    ],
)
def test_rejects_nonportable_paths(tmp_path, path):
    with pytest.raises(HandoffError):
        safe_path(tmp_path, path)


def test_symlink_output_is_not_followed(tmp_path):
    target = tmp_path / "target.md"
    target.write_bytes(b"keep")
    link = tmp_path / "HANDOFF.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("This runner cannot create symbolic links")
    result = runner.invoke(app, ["generate", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert target.read_bytes() == b"keep"


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions only")
def test_scanner_ignores_directory_junction(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("fixture canary")
    junction = root / "linked"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        pytest.skip("The Windows runner could not create a directory junction")
    assert scan(root, Settings()).files == []
    assert (outside / "private.txt").read_text() == "fixture canary"


@pytest.mark.parametrize(
    "content", ["!!python/object/apply:os.getcwd []", "max_files: [", "max_files: 0"]
)
def test_rejects_invalid_or_unsafe_yaml(tmp_path, content):
    state = tmp_path / ".handoff"
    state.mkdir()
    (state / "config.yaml").write_text(content)
    with pytest.raises(HandoffError):
        load_settings(tmp_path)


def test_payloads_are_not_exported_or_executed(tmp_path):
    payload = "PAYLOAD_SHOULD_NEVER_APPEAR"
    (tmp_path / ".env.production").write_text(payload)
    (tmp_path / "README.md").write_text(f"<script>{payload}</script>\x1b[31m")
    (tmp_path / "main.py").write_text(f"raise Exception('{payload}')\n")
    (tmp_path / "very-big.txt").write_bytes(b"X" * 2048)
    (tmp_path / "binary").write_bytes(b"A\x00B")
    snapshot = scan(tmp_path, Settings(max_bytes=256))
    assert {file.path for file in snapshot.files} == {"README.md", "main.py"}
    assert snapshot.limitations
    assert payload not in snapshot.model_dump_json()
    result = runner.invoke(app, ["generate", "--path", str(tmp_path)])
    assert result.exit_code == 0
    for name in ("HANDOFF.md", "HANDOFF_AGENT.md"):
        data = (tmp_path / name).read_bytes()
        assert payload.encode() not in data
        assert b"<script>" not in data


def test_fake_credentials_stay_out_of_outputs(tmp_path):
    values = (
        "fixture-api-key-431",
        "fixture-access-token-512",
        "fixture-password-313",
        "fixture-private-key-614",
        "fixture-database-credential-715",
        "postgres://fake-fixture:fake@db.invalid/test",
        "fixture-environment-value-916",
        "fixture-cloud-credential-117",
    )
    (tmp_path / ".env").write_text(f"ENV={values[6]}")
    (tmp_path / "private.key").write_text(values[3])
    (tmp_path / "app.py").write_text(f"# TODO {values[0]}\npassword = {values[2]!r}\n")
    (tmp_path / "README.md").write_text(f"# Setup\n\n{values[1]}\n")
    (tmp_path / "app.yaml").write_text(f"database: {values[4]}\nurl: {values[5]}\n")
    (tmp_path / "cloud-credentials.json").write_text(json.dumps({"value": values[7]}))
    args = ["--path", str(tmp_path)]
    scan_result = runner.invoke(app, ["scan", "--json", *args])
    report_result = runner.invoke(app, ["generate", *args])
    assert scan_result.exit_code == report_result.exit_code == 0
    output = scan_result.output + report_result.output
    for path in [*tmp_path.glob("HANDOFF*.md"), *tmp_path.glob(".handoff/snapshots/*.json")]:
        output += path.read_text(encoding="utf-8")
    assert all(value not in output for value in values)


def test_corrupt_and_future_snapshots_report_a_safe_error(tmp_path):
    state = tmp_path / ".handoff" / "snapshots"
    state.mkdir(parents=True)
    published = state / "published.json"
    for data in ("{", json.dumps({"schema_version": 999})):
        published.write_text(data)
        result = runner.invoke(app, ["validate", "--path", str(tmp_path)])
        assert result.exit_code == 1
        assert "corrupt or uses an unsupported schema version" in result.output


def test_report_tampering_is_detected(tmp_path):
    args = ["--path", str(tmp_path)]
    assert runner.invoke(app, ["generate", *args]).exit_code == 0
    report = tmp_path / "HANDOFF.md"
    hostile = report.read_bytes().replace(b"# Project handover", b"# All tests passed")
    report.write_bytes(hostile)
    assert runner.invoke(app, ["validate", *args]).exit_code == 3
    assert runner.invoke(app, ["generate", *args]).exit_code == 1
    assert report.read_bytes() == hostile
