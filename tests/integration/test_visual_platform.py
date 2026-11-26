import json
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from handoff.config import HandoffError
from handoff.visual import analyze_project
from handoff.visual_export import publish_visual, validate_visual


def test_visual_export_lifecycle(tmp_path):
    (tmp_path / "first.py").write_text("import second\n\ndef unfinished():\n    ...\n")
    (tmp_path / "second.py").write_text("def respond():\n    return True\n")
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"public":"^1.2.3","internal":"https://fixture-secret.invalid/url"}}'
    )
    model = analyze_project(tmp_path)
    assert model["counts"]["files"] == 3
    assert model["edges"] == [
        {"source": "first.py", "target": "second.py", "line": 1, "kind": "static import"}
    ]
    assert "fixture-secret" not in json.dumps(model)
    assert not (tmp_path / ".handoff").exists()
    publication = publish_visual(tmp_path)
    assert validate_visual(tmp_path, ".handoff") == []
    output = tmp_path / ".handoff"
    human = output / "reports/HANDOFF.md"
    notes = b"\r\nManual note.\r\n"
    human.write_bytes(human.read_bytes() + notes)
    assert "Executive summary" in human.read_text(encoding="utf-8")
    for name in publication["files"]:
        if name.endswith(".svg"):
            assert ElementTree.parse(output / name).getroot().tag.endswith("svg")
    publish_visual(tmp_path)
    with ZipFile(output / "handover.zip") as archive:
        assert archive.read("reports/HANDOFF.md").endswith(notes)
        assert sorted(archive.namelist()) == sorted(set(publication["files"]) - {"handover.zip"})
    files = {name: (output / name).stat().st_mtime_ns for name in publication["files"]}
    publish_visual(tmp_path)
    assert files == {name: (output / name).stat().st_mtime_ns for name in files}
    assert validate_visual(tmp_path, ".handoff") == []


def test_export_preserves_unmanaged_files_and_rejects_outside_destination(tmp_path):
    root = tmp_path / ".handoff"
    root.mkdir()
    unmanaged = root / "index.html"
    unmanaged.write_text("My HTML")
    with pytest.raises(HandoffError, match="unmanaged edits"):
        publish_visual(tmp_path)
    assert unmanaged.read_text() == "My HTML"
    assert not (root / "reports/HANDOFF.md").exists()
    with pytest.raises(HandoffError):
        publish_visual(tmp_path, ".handoff/../../outside")


def test_export_escapes_untrusted_project_text(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("# TODO </script><script>untrusted()</script>\n")
    publish_visual(root, ".handoff/exports")
    html = (root / ".handoff/exports/index.html").read_text(encoding="utf-8")
    assert "untrusted()" not in html
    assert "Content-Security-Policy" in html
    assert "analysis-data" in html


def test_typescript_alias_links_to_its_configuration(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions":{"paths":{"@/*":["./src/*"]}}}')
    (src / "index.ts").write_text(
        'import { value } from "@/module";\nexport function read() { return value; }\n'
    )
    (src / "module.ts").write_text("export const value = 3;")
    model = analyze_project(tmp_path)
    assert model["edges"] == [
        {
            "source": "src/index.ts",
            "target": "src/module.ts",
            "line": 1,
            "kind": "static import",
            "configuration": "tsconfig.json",
        }
    ]
    assert "completed_verified" not in model["counts"]["status"]
