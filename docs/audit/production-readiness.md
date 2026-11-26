# Production readiness

Verdict **functional MVP**. The revised validation and publication checks
passed regressions, and the fresh-session trial produced passing patches in
both arms. Broader feature provenance, live client skill activation, hosted CI,
and Linux verification remain unverified.

The final Windows run passed 52 tests with one symlink skip and 88% line
coverage. Ruff and mypy passed. The wheel and source archive built, and
`pip-audit --skip-editable --cache-dir .audit-cache` reported no known
vulnerabilities in the audited dependencies. See the
[cross-platform record](cross-platform.md) for the platform and launcher limits.

## Resource workload

Run `python scripts/audit_workloads.py performance .verification-audit-performance`
with no existing output directory. These Windows CPython 3.12.10 timings
include Python allocation tracing during scanning. Report time measures rendering
both documents in memory. Outside inventory counts files not reached due to the
scan cap.

| Files | Inspected | Outside inventory | Encountered skips | Evidence | Scan s | Peak Python bytes | Snapshot bytes | Report s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 100 | 0 | 0 | 200 | 0.350 | 721,357 | 121,628 | 0.015 |
| 5,000 | 5,000 | 0 | 0 | 10,000 | 10.148 | 28,678,777 | 6,065,329 | 0.331 |
| 25,000 | 20,000 | 5,000 | 0 | 12,000 | 35.476 | 51,130,665 | 9,294,417 | 0.821 |

Ancestor lookups now use the current directory's parent chain. Evidence is
limited during scanning and the result states when the budget is exhausted.
The synthetic run is not a benchmark of large Git histories.

CI uses full commit pins verified with `git ls-remote`, disables persisted
checkout credentials, and runs mypy alongside lint, tests and build. The
workspace has no Git metadata or configured hosted Actions run. The separate
Gitleaks job remains unverified locally.

Before publication, run the hosted Linux and Windows jobs, run Gitleaks, and
verify live skill activation using explicitly approved synthetic inputs.
Repeat the continuation benchmark with larger linked workflows, dirty work
trees, and timed checkpoints. Review remaining crash and filesystem race risks.
