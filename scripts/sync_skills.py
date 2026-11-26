"""Synchronize this source checkout's skill copies from the packaged manifest."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    canonical = (root / "src/handoff/skill_manifest.md").read_text(encoding="utf-8")
    targets = [
        "SKILL.md",
        ".agents/skills/handoff/SKILL.md",
        ".claude/skills/handoff/SKILL.md",
    ]
    for target in targets:
        path = root / target
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != canonical:
                parser.exit(1, f"Skill copy differs or is missing: {target}\n")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(canonical, encoding="utf-8")


if __name__ == "__main__":
    main()
