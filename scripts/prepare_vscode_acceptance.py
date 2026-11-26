"""Prepare a standalone synthetic repository and clean VS Code profile."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from tempfile import mkdtemp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsix", type=Path)
    parser.add_argument("sha256sums", type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.vsix.read_bytes()).hexdigest()
    expected = f"{digest}  {args.vsix.name}"
    if args.sha256sums.read_text(encoding="utf-8").strip() != expected:
        raise SystemExit("VSIX checksum or asset name did not match SHA256SUMS.")
    root = Path(mkdtemp(prefix="handoff-acceptance-"))
    shutil.copyfile(args.vsix, root / args.vsix.name)
    sample = root / "Sample Repository"
    sample.mkdir()
    (sample / "main.py").write_text(
        "from helper import total\n\nprint(total(1, 2))\n", encoding="utf-8"
    )
    (sample / "helper.py").write_text(
        "def total(left, right):\n    return left + right\n", encoding="utf-8"
    )
    (sample / "README.md").write_text("# Sample Repository\n", encoding="utf-8")
    (root / "profile").mkdir()
    (root / "extensions").mkdir()
    print(json.dumps({"directory": str(root), "asset": args.vsix.name, "sha256": digest}))


if __name__ == "__main__":
    main()
