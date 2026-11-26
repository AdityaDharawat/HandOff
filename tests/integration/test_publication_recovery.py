from typer.testing import CliRunner

from handoff import cli, reports


def test_snapshot_failure_restores_existing_reports(tmp_path, monkeypatch):
    runner = CliRunner()
    options = ["--path", str(tmp_path)]
    assert runner.invoke(cli.app, ["generate", *options]).exit_code == 0
    names = ("HANDOFF.md", "HANDOFF_AGENT.md")
    original = {name: (tmp_path / name).read_bytes() for name in names}

    def fail(*args):
        raise OSError("simulated storage failure")

    (tmp_path / "main.py").write_text("print(1)\n")
    monkeypatch.setattr(cli, "save_snapshot", fail)
    result = runner.invoke(cli.app, ["update", *options, "--yes"])
    assert result.exit_code == 1
    assert {name: (tmp_path / name).read_bytes() for name in names} == original
    assert runner.invoke(cli.app, ["validate", *options]).exit_code == 0


def test_reserved_report_output_is_rejected(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli.app, ["generate", "--path", str(tmp_path), "--output-dir", ".git"])
    assert result.exit_code == 1
    assert not (tmp_path / ".git").exists()


def test_updater_preserves_external_edit_during_publication(tmp_path, monkeypatch):
    runner = CliRunner()
    args = ["--path", str(tmp_path)]
    assert runner.invoke(cli.app, ["generate", *args]).exit_code == 0
    human = tmp_path / "HANDOFF.md"
    agent = tmp_path / "HANDOFF_AGENT.md"
    original = human.read_bytes()
    external = agent.read_bytes() + b"\nExternal note."
    atomic_write = reports.atomic_write

    def write(path, data):
        atomic_write(path, data)
        if path == human and data != original:
            agent.write_bytes(external)

    monkeypatch.setattr(reports, "atomic_write", write)
    (tmp_path / "new.py").write_text("x = 1")
    assert runner.invoke(cli.app, ["update", *args, "--yes"]).exit_code == 1
    assert agent.read_bytes() == external
    assert human.read_bytes() == original
