"""Conservative line landmarks for JavaScript and TypeScript."""

import re
from collections.abc import Iterator

EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
DECLARATION = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\("
)
MARKER = re.compile(r"^\s*//\s*(TODO|FIXME)\b", re.IGNORECASE)


def visible_lines(text: str) -> Iterator[tuple[int, str]]:
    block = False
    template = False
    for number, line in enumerate(text.splitlines(), 1):
        if block or line.lstrip().startswith("/*"):
            block = "*/" not in line
            continue
        was_template = template
        if len(re.findall(r"(?<!\\)`", line)) % 2:
            template = not template
        if not was_template and not template:
            yield number, line
