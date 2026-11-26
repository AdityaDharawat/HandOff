from handoff.config import Settings
from handoff.models import Source
from handoff.scanner.repository import scan


def test_scan_is_bounded_and_does_not_export_source(tmp_path):
    (tmp_path / ".gitignore").write_text("ignored/\n")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "data.txt").write_text("hidden")
    (tmp_path / ".env").write_text("PASSWORD=test-value")
    (tmp_path / "main.py").write_text("def run():\n    pass  # TODO test-value\n")
    result = scan(tmp_path, Settings())
    assert {item.path for item in result.files} == {".gitignore", "main.py"}
    [marker] = [item for item in result.evidence if item.source_type == Source.TODO]
    assert marker.line_start == 2
    assert "test-value" not in result.model_dump_json()
    assert [e.id for e in result.evidence] == [e.id for e in scan(tmp_path, Settings()).evidence]


def test_document_headings_skip_fenced_examples_and_record_locations(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Example\n\n````markdown\n## Environment variables\n```\n````\n## Installation\n"
    )
    result = scan(tmp_path, Settings())
    [heading] = [e for e in result.evidence if e.metadata.get("role", "").startswith("doc-")]
    assert heading.metadata == {"role": "doc-setup"}
    assert heading.line_start == 7
