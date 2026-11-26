"""Safely publish a complete offline handover with versioned data."""

import base64
import json
from collections import Counter
from hashlib import sha256
from html import escape
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .config import HandoffError, read_limited, safe_path
from .core import capture
from .models import Source
from .reports import MAX_REPORT, file_reference, literal, plan_reports, write_reports
from .storage import load_snapshot, save_snapshot, writing
from .validation import check_evidence, validate_reports
from .visual import project_model


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"


def offline_dashboard(model: dict[str, Any]) -> bytes:
    directory = files("handoff").joinpath("dashboard")
    layout = directory.joinpath("index.html").read_text(encoding="utf-8")
    css = directory.joinpath("style.css").read_text(encoding="utf-8")
    js = directory.joinpath("app.js").read_text(encoding="utf-8")

    def csp_hash(value: str) -> str:
        return "'sha256-" + base64.b64encode(sha256(value.encode()).digest()).decode() + "'"

    data = json_bytes(model).decode().replace("<", "\\u003c").replace(">", "\\u003e")
    policy = f"default-src 'none'; script-src {csp_hash(js)}; style-src {csp_hash(css)}"
    return (
        layout.replace("{{POLICY}}", policy)
        .replace("{{STYLE}}", f"<style>{css}</style>")
        .replace("{{SCRIPT}}", f"<script>{js}</script>")
        .replace("{{DATA}}", f'<script type="application/json" id="analysis-data">{data}</script>')
    ).encode()


def chart(title: str, values: list[tuple[str, int]]) -> bytes:
    height = max(145, 82 + 34 * len(values))
    high = max([n for _, n in values] or [1]) or 1
    rows = []
    for index, (label, count) in enumerate(values):
        y = 66 + index * 34
        rows.append(
            f'<text x="25" y="{y + 13}">{escape(label)}</text>'
            f'<rect x="255" y="{y}" width="{395 * count / high:.1f}" height="16" rx="3" fill="#006c55"/>'
            f'<text x="675" y="{y + 13}">{count}</text>'
        )
    if not rows:
        rows.append('<text x="25" y="86">No matching evidence</text>')
    return svg_document(title, height, "".join(rows))


def svg_document(title: str, height: int, body: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 750 {height}" role="img">'
        f'<title>{escape(title)}</title><rect width="750" height="{height}" fill="#f0f5ee"/>'
        f'<g fill="#19251f" font-family="system-ui, sans-serif" font-size="13">'
        f'<text x="25" y="34" font-size="21" font-weight="700">{escape(title)}</text>'
        f"{body}</g></svg>"
    ).encode()


def map_svg(title: str, all_edges: list[dict[str, Any]]) -> bytes:
    edges = all_edges[:45]
    paths = list(dict.fromkeys(path for e in edges for path in (e["source"], e["target"])))[:30]
    if not paths:
        return svg_document(
            title, 135, '<text x="25" y="84">No static import edges observed</text>'
        )
    positions = {path: (22 + (i % 3) * 238, 57 + (i // 3) * 52) for i, path in enumerate(paths)}
    links = [
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#527b69"/></marker></defs>'
    ]
    for edge in edges:
        if edge["source"] in positions and edge["target"] in positions:
            x1, y1 = positions[edge["source"]]
            x2, y2 = positions[edge["target"]]
            dx, dy = x2 - x1, y2 - y1
            inset = min(99 / max(1, abs(dx)), 18 / max(1, abs(dy)))
            links.append(
                f'<line x1="{x1 + 97 + dx * inset:.1f}" y1="{y1 + 15 + dy * inset:.1f}" '
                f'x2="{x2 + 97 - dx * inset:.1f}" y2="{y2 + 15 - dy * inset:.1f}" stroke="#527b69" '
                f'marker-end="url(#arrow)"><title>{escape(edge["source"])}:{edge["line"]} imports '
                f"{escape(edge['target'])}</title></line>"
            )
    for path, (x, y) in positions.items():
        links.append(
            f'<g><title>{escape(path)}</title><rect x="{x}" y="{y}" width="195" height="30" rx="5" '
            f'fill="#fff" stroke="#7b9a89"/><text x="{x + 8}" y="{y + 19}">'
            f"{escape(path if len(path) < 26 else '…' + path[-25:])}</text></g>"
        )
    return svg_document(title, 80 + ((len(paths) + 2) // 3) * 52, "".join(links))


def artifacts(model: dict[str, Any], snapshot: Any) -> dict[str, bytes]:
    work = [entry for entry in snapshot.findings if entry.status]
    debt = [
        entry
        for entry in snapshot.evidence
        if entry.source_type == Source.TODO or entry.metadata.get("role") in {"stub", "parse-error"}
    ]
    actions = [entry for entry in snapshot.findings if entry.kind in {"action", "risk"}]
    refs = {entry.id: entry for entry in snapshot.evidence}

    def report(title: str, lines: list[str]) -> bytes:
        return (
            f"# {title}\n\n".encode()
            + ("\n".join(lines or ["No matching evidence."]) + "\n").encode()
        )

    def finding_lines(items: list[Any]) -> list[str]:
        lines = []
        for item in items[:250]:
            sources = [
                file_reference(snapshot, ref.source_path, ref.line_start)
                for identifier in item.evidence_ids
                if (ref := refs.get(identifier)) and ref.source_path
            ]
            lines.append(
                f"- {literal(item.summary)} ({item.status or item.confidence}) {' · '.join(sources)}"
            )
            if item.validation:
                lines.append(f"  - Verify by {literal(item.validation)}")
        if len(items) > 250:
            lines.append("See project-analysis.json for the full set.")
        return lines

    result = {
        "index.html": offline_dashboard(model),
        "data/project-analysis.json": json_bytes(model),
        "data/features.json": json_bytes(
            {"schema_version": 1, "features": [f.model_dump(mode="json") for f in work]}
        ),
        "data/dependencies.json": json_bytes(
            {"schema_version": 1, "packages": model["packages"], "edges": model["edges"]}
        ),
        "data/findings.json": json_bytes(
            {"schema_version": 1, "findings": model["snapshot"]["findings"]}
        ),
        "reports/PROJECT_SUMMARY.md": report(
            "Project summary",
            [
                f"**{literal(snapshot.project)}**. Purpose requires confirmation from project docs.",
                f"- Files inspected: {model['counts']['files']}",
                f"- Languages: {literal(', '.join(model['languages']) or 'Unknown')}",
                f"- Visible working-tree changes: {len(snapshot.git.changes)}",
                "- [Developer handover](HANDOFF.md)",
            ],
        ),
        "reports/ARCHITECTURE.md": report(
            "Architecture",
            [
                "[Static import diagram](../visualizations/architecture.svg)",
                "",
                *[
                    f"- {file_reference(snapshot, edge['source'], edge['line'])} imports "
                    f"{file_reference(snapshot, edge['target'])}"
                    for edge in model["edges"][:200]
                ],
            ],
        ),
        "reports/IMPLEMENTATION_STATUS.md": report("Implementation status", finding_lines(work)),
        "reports/TECHNICAL_DEBT.md": report(
            "Technical debt",
            [
                f"- {literal(item.description)} {file_reference(snapshot, item.source_path, item.line_start)}"
                for item in debt[:250]
                if item.source_path
            ],
        ),
        "reports/NEXT_STEPS.md": report("Next steps", finding_lines(actions)),
        "visualizations/architecture.svg": map_svg(
            "Repository architecture · static imports", model["edges"]
        ),
        "visualizations/dependency-graph.svg": map_svg("Internal dependency graph", model["edges"]),
        "visualizations/feature-status.svg": chart(
            "Implementation status",
            [
                (name.replace("_", " ").capitalize(), count)
                for name, count in model["counts"]["status"].items()
            ],
        ),
        "visualizations/technical-debt.svg": chart(
            "Technical debt evidence", list(Counter(e.description for e in debt).items())
        ),
    }
    tests = [item for item in snapshot.evidence if item.source_type == Source.RESULT]
    result["visualizations/test-summary.svg"] = chart(
        "External test outcomes · unverified",
        [
            (name.capitalize(), sum(int(e.metadata.get(name, "0")) for e in tests))
            for name in ("passed", "failed", "skipped", "errors")
        ]
        if tests
        else [],
    )
    return result


def output_directory(root: Path, output: str) -> Path:
    if output != ".handoff" and not output.startswith(".handoff/"):
        raise HandoffError("Visual output must stay beneath .handoff.")
    return safe_path(root, output)


def zip_bytes(data: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for filename, body in sorted(data.items()):
            from zipfile import ZipInfo

            archive.writestr(ZipInfo(filename), body, compress_type=ZIP_DEFLATED)
    return buffer.getvalue()


def publish_visual(root: Path, output: str = ".handoff") -> dict[str, Any]:
    directory = output_directory(root, output)
    report_dir = f"{output}/reports"
    internal_key = sha256(output.encode()).hexdigest()[:16]
    snapshot_key = f"visual-{internal_key}"
    manifest = safe_path(root, f"{output}/data/publication.json")
    limit = 65536
    with writing(root):
        previous = None
        previous_hashes = {}
        old_manifest = read_limited(manifest, limit) if manifest.exists() else None
        if old_manifest is not None:
            previous_hashes = json.loads(old_manifest)["files"]
            previous = load_snapshot(root, snapshot_key)
        snapshot = capture(root).model_copy(
            update={"output_dir": report_dir, "report_style": "visual"}
        )
        if issues := check_evidence(root, snapshot):
            raise HandoffError(" ".join(issues))
        if previous is not None:
            comparable = snapshot.model_copy(
                update={
                    "observed_at": previous.observed_at,
                    "evidence": [
                        item.model_copy(update={"observed_at": previous.observed_at})
                        for item in snapshot.evidence
                    ],
                }
            )
            if comparable == previous:
                snapshot = previous
        model = project_model(root, snapshot)
        data = artifacts(model, snapshot)
        plans = plan_reports(root, report_dir, snapshot, previous, False)
        for destination, _, body in plans:
            data["reports/" + destination.name] = body
        data["handover.zip"] = zip_bytes(data)
        for filename, body in data.items():
            if filename in {"reports/HANDOFF.md", "reports/HANDOFF_AGENT.md"}:
                continue
            target = safe_path(root, f"{output}/{filename}")
            old = read_limited(target, MAX_REPORT) if target.exists() else None
            if (
                old is not None
                and old != body
                and sha256(old).hexdigest() != previous_hashes.get(filename)
            ):
                raise HandoffError("An existing visual artifact has unmanaged edits.")
            plans.append((target, old, body))
        record = json_bytes(
            {
                "schema_version": 1,
                "files": {
                    filename: sha256(body).hexdigest()
                    for filename, body in data.items()
                    if filename not in {"reports/HANDOFF.md", "reports/HANDOFF_AGENT.md"}
                },
            }
        )
        plans.append((manifest, old_manifest, record))
        if snapshot is not previous or any(old != body for _, old, body in plans):
            with write_reports(root, plans):
                save_snapshot(root, snapshot_key, snapshot)
    return {"directory": directory.relative_to(root).as_posix(), "files": sorted(data)}


def validate_visual(root: Path, output: str) -> list[str]:
    output_directory(root, output)
    key = sha256(output.encode()).hexdigest()[:16]
    report_dir = f"{output}/reports"
    snapshot = load_snapshot(root, f"visual-{key}")
    manifest = safe_path(root, f"{output}/data/publication.json")
    record = json.loads(read_limited(manifest, 65536))
    issues = validate_reports(root, report_dir, snapshot)
    for name, digest in record["files"].items():
        target = safe_path(root, f"{output}/{name}")
        if not target.exists() or sha256(read_limited(target, MAX_REPORT)).hexdigest() != digest:
            issues.append(f"Artifact missing or changed: {name}")
    return issues
