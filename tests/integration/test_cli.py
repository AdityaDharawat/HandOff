from typer.testing import CliRunner

from handoff.cli import app

runner = CliRunner()


def test_report_lifecycle(tmp_path):
    args = ["--path", str(tmp_path)]
    source = tmp_path / "main.py"
    source.write_text("def api():\n    pass\n")

    def invoke(name, *options):
        return runner.invoke(app, [name, *args, *options])

    assert invoke("init").exit_code == 0
    assert invoke("scan", "--json").exit_code == 0
    assert invoke("generate", "--output-dir", "./reports").exit_code == 0
    assert invoke("check").exit_code == 0
    assert invoke("status").exit_code == 0
    assert invoke("validate").exit_code == 0
    report = tmp_path / "reports" / "HANDOFF.md"
    note = b"\r\nA manually written note.\r\n"
    report.write_bytes(report.read_bytes() + note)
    before = report.read_bytes()
    source.write_text("def api():\n    return 1\n")
    assert invoke("check").exit_code == 2
    assert invoke("update").exit_code == 1
    assert report.read_bytes() == before
    assert invoke("update", "--yes").exit_code == 0
    assert report.read_bytes().endswith(note)
    [backup] = (tmp_path / ".handoff" / "backups").glob("*/HANDOFF.md")
    assert backup.read_bytes() == before
    assert invoke("check").exit_code == 0
    assert invoke("validate").exit_code == 0
    assert invoke("explain", "unknown").exit_code == 1


def test_refuse_unmanaged_report(tmp_path):
    report = tmp_path / "HANDOFF.md"
    report.write_bytes(b"Existing notes")
    result = runner.invoke(app, ["generate", "--path", str(tmp_path), "--force"])
    assert result.exit_code == 1
    assert report.read_bytes() == b"Existing notes"
    assert not (tmp_path / "HANDOFF_AGENT.md").exists()
