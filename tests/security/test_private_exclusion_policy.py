"""Exercise the publication gate with synthetic private data."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from handoff.visual import analyze_project
from handoff.visual_export import publish_visual, validate_visual

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/publication_preflight.py"
POLICY = ".handoff-private-exclusions.yml"
ENV = "HANDOFF_PRIVATE_EXCLUSION_POLICY"
NAMES = [".samplevault", "SampleVault", "samplevault"]


@pytest.fixture
def private_tree(tmp_path):
    (tmp_path / ".gitignore").write_text(".handoff/\n" + POLICY + "\n", encoding="utf-8")
    cases = []
    for prefix in ("", "examples/nested/"):
        for name in {*NAMES, *(name.swapcase() for name in NAMES)}:
            for leaf in ("README.md", "data.json", ".handoff/output.md"):
                cases.append(
                    {
                        "path": f"{prefix}{name}/{leaf}",
                        "ignored": name in NAMES or leaf.startswith(".handoff/"),
                        "tracked": True,
                        "legacy_only": name in NAMES and not leaf.startswith(".handoff/"),
                    }
                )
    assert len(cases) == 36
    assert sum(case["legacy_only"] for case in cases) == 12
    policy = {
        "version": 1,
        "nonce": "0" * 64,
        "git_ignore": [name + "/" for name in NAMES],
        "tracked_dirs": [".samplevault", "samplevault"],
        "regression": cases,
    }
    seal = hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/private-exclusion-policy.sha256").write_text(seal, encoding="ascii")
    (tmp_path / POLICY).write_text(json.dumps(policy), encoding="utf-8")
    return tmp_path, policy


def run(root, *args, secret=None):
    env = {key: value for key, value in os.environ.items() if key != ENV}
    if secret is not None:
        env[ENV] = secret
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *map(str, args)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_local_and_secret_validation(private_tree):
    root, policy = private_tree
    assert run(root, "--validate-only").returncode == 0
    assert run(root, "--validate-only", "--policy-env", secret=json.dumps(policy)).returncode == 0
    for secret, expected in [(None, "missing"), ("!", "malformed"), ("{}", "malformed")]:
        result = run(root, "--validate-only", "--policy-env", secret=secret)
        assert result.returncode != 0 and expected in result.stderr
    policy["nonce"] = "1" * 64
    replacement = run(root, "--validate-only", "--policy-env", secret=json.dumps(policy))
    assert replacement.returncode != 0 and "integrity" in replacement.stderr
    (root / POLICY).unlink()
    assert "missing" in run(root, "--validate-only").stderr
    (root / POLICY).mkdir()
    assert "unreadable" in run(root, "--validate-only").stderr


def test_fail_closed_and_redacted(private_tree):
    root, policy = private_tree
    for content in ("", "{", '{"version":1,"version":1}'):
        (root / POLICY).write_text(content, encoding="utf-8")
        result = run(root, "--validate-only")
        assert result.returncode != 0 and "malformed" in result.stderr
    policy["regression"][0]["tracked"] = False
    (root / POLICY).write_text(json.dumps(policy), encoding="utf-8")
    result = run(root, "--validate-only")
    assert result.returncode != 0 and "regression" in result.stderr
    assert "samplevault" not in (result.stdout + result.stderr).casefold()
    policy["regression"][0]["path"] = "../samplevault/data.json"
    (root / POLICY).write_text(json.dumps(policy), encoding="utf-8")
    assert "malformed" in run(root, "--validate-only").stderr


def test_candidate_and_archive_preflight(private_tree):
    root, _ = private_tree
    manifest = root / "candidate.txt"
    candidate = root / "main.py"
    candidate.write_text("pass\n", encoding="utf-8")
    manifest.write_text("main.py\n", encoding="utf-8")
    vsix = root / "test.vsix"
    sdist = root / "test.tar.gz"
    with ZipFile(vsix, "w") as archive:
        archive.writestr("extension/main.py", "pass\n")
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo("package/main.py")
        member.size = 5
        archive.addfile(member, io.BytesIO(b"pass\n"))
    result = run(root, "--manifest", manifest, "--archive", vsix, "--archive", sdist)
    assert result.returncode == 0 and "Archives checked: 2" in result.stdout

    for bad in (POLICY, "nested/saMPLEvault/main.py", "../outside.py"):
        manifest.write_text(f"{bad}\n", encoding="utf-8")
        result = run(root, "--manifest", manifest)
        assert result.returncode != 0 and "samplevault" not in result.stderr.casefold()
    manifest.write_text("main.py\n", encoding="utf-8")
    candidate.write_text("# SampleVault\n", encoding="utf-8")
    result = run(root, "--manifest", manifest)
    assert "Protected content" in result.stderr and "samplevault" not in result.stderr.casefold()
    candidate.write_text("pass\n", encoding="utf-8")

    wheel = io.BytesIO()
    with ZipFile(wheel, "w") as archive:
        archive.writestr(POLICY, "private")
    with ZipFile(vsix, "w") as archive:
        archive.writestr("extension/engine/sample.whl", wheel.getvalue())
    result = run(root, "--manifest", manifest, "--archive", vsix)
    assert result.returncode != 0 and "Protected publication path" in result.stderr
    with tarfile.open(sdist, "w:gz") as archive:
        archive.addfile(tarfile.TarInfo(f"package/{POLICY}"))
    result = run(root, "--manifest", manifest, "--archive", sdist)
    assert result.returncode != 0 and "Protected publication path" in result.stderr


def test_policy_file_stays_out_of_scan(private_tree):
    root, _ = private_tree
    (root / "main.py").write_text("pass\n", encoding="utf-8")
    (root / ".gitignore").write_text("", encoding="utf-8")
    model = analyze_project(root)
    assert POLICY not in json.dumps(model)
    assert "samplevault" not in json.dumps(model).casefold()

    publish_visual(root)
    assert not validate_visual(root, ".handoff")
    for artifact in (root / ".handoff").rglob("*"):
        if artifact.is_file() and artifact.suffix in {".md", ".html", ".json", ".svg"}:
            assert "samplevault" not in artifact.read_text(encoding="utf-8").casefold()
            assert POLICY not in artifact.read_text(encoding="utf-8")
