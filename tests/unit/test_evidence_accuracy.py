import re

import pytest

from handoff.core import capture
from handoff.models import Progress
from handoff.reports import render
from handoff.validation import check_evidence


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {"main.py": "def total(items):\n    return sum(items)\n"},
            {Progress.IMPLEMENTED_UNVERIFIED},
        ),
        ({"main.py": "def unfinished():\n    ...\n"}, {Progress.PARTIALLY_IMPLEMENTED}),
        (
            {"main.py": "def done():\n    return 1\n\ndef todo():\n    pass\n"},
            {Progress.PARTIALLY_IMPLEMENTED, Progress.IMPLEMENTED_UNVERIFIED},
        ),
        (
            {"library.py": "def unused():\n    return True\n", "main.py": "print('ready')\n"},
            {Progress.IMPLEMENTED_UNVERIFIED, Progress.UNKNOWN},
        ),
        (
            {"main.py": "def lowercase(s):\n    # TODO lowercase\n    return s.lower()\n"},
            {Progress.IMPLEMENTED_UNVERIFIED},
        ),
        ({"README.md": "# Export completed\n"}, set()),
        (
            {
                "transport.py": "def send():\n    return 42\n",
                "service.py": "from transport import send\ndef run():\n    return send()\n",
            },
            {Progress.IMPLEMENTED_UNVERIFIED},
        ),
        ({"pyproject.toml": "[project.scripts]\nstart = 'service:run'\n"}, set()),
        (
            {
                "main.py": "def divide(a,b):\n    return a/b\n",
                "test_main.py": "def test_zero():\n    assert False\n",
            },
            {Progress.IMPLEMENTED_UNVERIFIED},
        ),
    ],
)
def test_feature_evidence_never_overstates_scope(tmp_path, files, expected):
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    snapshot = capture(tmp_path)
    assert {finding.status for finding in snapshot.findings if finding.status} == expected
    assert all(finding.evidence_ids for finding in snapshot.findings)
    assert check_evidence(tmp_path, snapshot, verify_content=True) == []
    for agent in (False, True):
        report = render(snapshot, agent)
        anchors = set(re.findall(rb'<a id="(ev-[a-f0-9]+)"></a>', report))
        assert set(re.findall(rb"\]\(#(ev-[a-f0-9]+)\)", report)) <= anchors
        assert b"completed_verified" not in report
