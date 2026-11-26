"""Generate synthetic continuation fixtures and measure bounded local scans."""

import argparse
import json
import tracemalloc
from pathlib import Path
from time import perf_counter

from handoff.config import Settings
from handoff.intelligence import analyze
from handoff.reports import render
from handoff.scanner.repository import scan

CASES = {
    "queue": (
        "An in-memory queue. Items leave in insertion order. Empty dequeue returns None.",
        "def enqueue(queue, item):\n    queue.append(item)\n\n\ndef dequeue(queue):\n    ...\n",
        "def test_continuation():\n    queue = []\n"
        "    enqueue(queue, 'one')\n    enqueue(queue, 'two')\n"
        "    assert dequeue(queue) == 'one'\n    assert dequeue(queue) == 'two'\n"
        "    assert dequeue(queue) is None\n",
    ),
    "slug": (
        "Slug normalization and empty-input fallback are complete. Empty slugs should be 'item'.",
        "def normalize(value):\n    # TODO: support lowercase conversion\n"
        "    return '-'.join(value.lower().split())\n\n\ndef slug(value):\n    return normalize(value)\n",
        "def test_continuation():\n    assert slug('Round Trip') == 'round-trip'\n"
        "    assert slug('   ') == 'item'\n",
    ),
    "port": (
        "Read an optional service port. Default to 8080 when unset.",
        "import os\n\n\ndef port():\n    return int(os.environ['DEMO_PORT'])\n",
        "def test_continuation():\n    from unittest.mock import patch\n"
        "    with patch.dict('os.environ', {}, clear=True):\n        assert port() == 8080\n"
        "    with patch.dict('os.environ', {'DEMO_PORT': '9000'}):\n"
        "        assert port() == 9000\n",
    ),
}


def fixtures(root: Path) -> None:
    for scenario, (readme, source, test) in CASES.items():
        for arm in ("control", "treatment"):
            directory = root / f"{scenario}-{arm}"
            directory.mkdir()
            (directory / "README.md").write_text(readme + "\n", encoding="utf-8")
            (directory / "app.py").write_text(source + "\n" + test, encoding="utf-8")
            if arm == "treatment":
                snapshot = analyze(scan(directory, Settings()))
                for agent in (False, True):
                    name = "HANDOFF_AGENT.md" if agent else "HANDOFF.md"
                    (directory / name).write_bytes(render(snapshot, agent) + b"\n")


def performance(root: Path) -> None:
    for count in (100, 5000, 25000):
        directory = root / str(count)
        directory.mkdir()
        for i in range(count):
            (directory / f"module_{i:05}.py").write_bytes(b"def run():\n    return 1\n")
        tracemalloc.start()
        start = perf_counter()
        snapshot = analyze(scan(directory, Settings(max_files=min(count, 20000))))
        scan_seconds = perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        start = perf_counter()
        report_bytes = sum(len(render(snapshot, agent)) for agent in (False, True))
        print(
            json.dumps(
                {
                    "files": count,
                    "inspected": len(snapshot.files),
                    "skipped": snapshot.skipped_files,
                    "outside_inventory": count - len(snapshot.files),
                    "evidence": len(snapshot.evidence),
                    "scan_seconds": round(scan_seconds, 3),
                    "peak_python_bytes": peak,
                    "snapshot_bytes": len(snapshot.model_dump_json().encode()),
                    "report_seconds": round(perf_counter() - start, 3),
                    "report_bytes": report_bytes,
                    "limitations": snapshot.limitations,
                }
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fixtures", "performance"))
    parser.add_argument("directory", type=Path)
    options = parser.parse_args()
    options.directory.mkdir(parents=True)
    if options.mode == "fixtures":
        fixtures(options.directory.resolve())
    else:
        performance(options.directory.resolve())


if __name__ == "__main__":
    main()
