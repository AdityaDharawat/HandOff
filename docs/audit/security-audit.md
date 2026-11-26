# Security audit

Run `python -m pytest -q -ra tests/security tests/unit/test_scanner_audit.py`
on a runner with a writable pytest temporary directory.

| Severity | Finding and impact | Remediation and evidence |
|---|---|---|
| High | A destination edited between report replacements could lose external changes | Recheck each report just before replacement. Failure-injection test preserves the external edit and rolls back the first write |
| Medium | Malformed Git metadata could abort capture and an unresolved index stage could be presented as ordinary tracked state | Reject malformed records; label unresolved entries. Parser regression covers malformed and conflicted records |
| Medium | An observation-dense file could produce excessive evidence and findings before storage limits applied | Cap evidence at 12,000 and disclose truncation. Regression exercises 12,001 comments |
| Low | Unsafe Unicode control and surrogate characters could survive portable path validation | Reject control, format and surrogate characters before path use |

No critical issue was established by the review. The existing tests cover
relative path boundaries, safe YAML, report integrity, and fake credentials
across console output, reports, and stored snapshots.
A Windows directory junction fixture passed. The real symlink fixture skipped
because this Windows session lacks creation permission.

Only reviewed Git plumbing commands are issued with fixed arguments and a
timeout. Raw repository prose and test logs remain outside generated sections.
Repository filenames and manual notes still need review before distribution.
The recheck narrows the filesystem race window. An externally modified path
can still change between the final check and replacement. Full crash atomicity
across two files plus a snapshot and every filesystem failure mode remain
unverified. A local run cannot establish the absence of security issues.
