"""Install the VSIX wheel into a new venv and exercise its offline bridge."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from verify_vsix import ROOT, verify


def smoke(assets: Path) -> None:
    (package,) = assets.glob("*.vsix")
    with TemporaryDirectory(prefix="handoff-vsix-") as location:
        root = Path(location)
        verify(package, False, root)
        (wheel,) = root.glob("*.whl")
        environment = root / "engine"
        subprocess.run([sys.executable, "-I", "-m", "venv", environment], check=True)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [python, "-I", "-m", "pip", "--require-virtualenv", "install", wheel], check=True
        )
        project = root / "external project"
        shutil.copytree(
            ROOT / "examples/sample-project",
            project,
            ignore=shutil.ignore_patterns(".handoff", "HANDOFF*.md", "__pycache__"),
        )

        def bridge(command: str) -> dict:
            result = subprocess.check_output(
                [python, "-I", "-m", "handoff.bridge", command, "--path", project], cwd=root
            )
            payload = json.loads(result)
            if payload["protocol"] != 1 or not payload["ok"]:
                raise RuntimeError(f"Bundled engine failed to {command}")
            return payload["result"]

        bridge("version")
        analysis = bridge("analyze")
        if analysis["snapshot"]["project"] != project.name or not analysis["counts"]["files"]:
            raise RuntimeError("Bundled engine did not analyze the external project")
        bridge("generate")
        if bridge("validate")["issues"]:
            raise RuntimeError("Generated artifacts failed validation")
        print(
            f"Bundled engine passed installation, analysis, report generation and validation on {sys.platform}"
        )


if __name__ == "__main__":
    smoke(Path(sys.argv[1]))
