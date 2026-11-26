"""Check the release asset against the distribution allowlist."""

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "vscode-extension"
REQUIRED = {
    "[Content_Types].xml",
    "extension.vsixmanifest",
    "extension/package.json",
    "extension/readme.md",
    "extension/changelog.md",
    "extension/LICENSE.txt",
    "extension/out/extension.js",
    "extension/media/index.html",
    "extension/media/style.css",
    "extension/media/app.js",
    "extension/media/icon.svg",
}


def verify(package: Path, normalize: bool, extract_engine: Path | None) -> None:
    manifest = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    lock = json.loads((EXTENSION / "package-lock.json").read_text(encoding="utf-8"))
    if lock["version"] != version or lock["packages"][""]["version"] != version:
        raise ValueError("Extension version differs from the npm lockfile")
    wheel_name = f"handoff_continuity-{version}-py3-none-any.whl"
    wheel_path = f"extension/engine/{wheel_name}"
    expected = REQUIRED | {wheel_path}
    with ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(expected) or set(names) != expected:
            raise ValueError(
                f"Unexpected package layout. Missing {expected - set(names)};"
                f" extra {set(names) - expected}"
            )
        files = {name: archive.read(name) for name in names}
    packaged = json.loads(files["extension/package.json"])
    for key in ("version", "name", "publisher", "engines", "license", "main"):
        if packaged[key] != manifest[key]:
            raise ValueError(f"Mismatched extension metadata: {key}")
    if files["extension/LICENSE.txt"] != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Packaged license differs from the source license")
    with ZipFile(io.BytesIO(files[wheel_path])) as wheel:
        source = ROOT / "src"
        allowed = {
            file.relative_to(source).as_posix()
            for file in (source / "handoff").rglob("*")
            if file.is_file() and file.suffix in {".py", ".html", ".css", ".js", ".md"}
        }
        metadata = {
            f"handoff_continuity-{version}.dist-info/{name}"
            for name in ("METADATA", "WHEEL", "entry_points.txt", "licenses/LICENSE", "RECORD")
        }
        if set(wheel.namelist()) != allowed | metadata or len(wheel.namelist()) != len(
            allowed | metadata
        ):
            raise ValueError("Unexpected bundled engine wheel layout")
        wheel_license = f"handoff_continuity-{version}.dist-info/licenses/LICENSE"
        if wheel.read(wheel_license) != files["extension/LICENSE.txt"]:
            raise ValueError("Bundled engine and extension licenses differ")
        for name in allowed:
            if wheel.read(name) != (source / name).read_bytes():
                raise ValueError(f"Bundled engine differs from source: {name}")
        for name in ("index.html", "style.css", "app.js"):
            if files[f"extension/media/{name}"] != wheel.read(f"handoff/dashboard/{name}"):
                raise ValueError(f"Dashboard asset differs from bundled engine: {name}")
    if normalize:
        # Stable ZIP order, metadata and bytes across repeated VSCE runs.
        temporary = package.with_suffix(".tmp")
        with ZipFile(temporary, "w", compression=ZIP_STORED) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(ZipInfo(name), data)
        temporary.replace(package)
    if extract_engine is not None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", wheel_name):
            raise ValueError("Invalid wheel name")
        extract_engine.mkdir(parents=True, exist_ok=True)
        (extract_engine / wheel_name).write_bytes(files[wheel_path])
    print(f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {package.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--normalize", action="store_true")
    parser.add_argument("--extract-engine", type=Path)
    args = parser.parse_args()
    verify(args.package, args.normalize, args.extract_engine)
