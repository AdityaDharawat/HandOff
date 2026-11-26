"""Private JSON command line used by the VS Code extension."""

import argparse
import json
from pathlib import Path
from typing import Any

from .config import HandoffError
from .core import resolve_root
from .visual import analyze_project
from .visual_export import publish_visual, validate_visual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyze", "generate", "validate", "version"])
    parser.add_argument("--path", type=Path, default=Path("."))
    parser.add_argument("--output", default=".handoff")
    options = parser.parse_args()
    result: dict[str, Any]
    try:
        if options.command == "version":
            result = {"protocol": 1}
        else:
            root = resolve_root(options.path)
            if options.command == "analyze":
                result = analyze_project(root)
            elif options.command == "generate":
                result = publish_visual(root, options.output)
            else:
                result = {"issues": validate_visual(root, options.output)}
        print(json.dumps({"protocol": 1, "ok": True, "result": result}, ensure_ascii=True))
    except HandoffError as error:
        print(json.dumps({"protocol": 1, "ok": False, "error": str(error)}, ensure_ascii=True))
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "protocol": 1,
                    "ok": False,
                    "error": "Could not read or write the requested workspace artifacts.",
                }
            )
        )


if __name__ == "__main__":
    main()
