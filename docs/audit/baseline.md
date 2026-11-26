# Audit baseline

Verified on Windows with CPython 3.12.10 before production edits. Git status returned
`fatal: not a git repository` for this workspace. Git-backed tests used disposable
repositories. Package versions included Pydantic 2.14.4, Typer 0.29.2, Rich 15.0.0,
PyYAML 6.0.4, pathspec 1.1.1 and Hatchling 1.33.0.

| Command | Observed result |
|---|---|
| `python -m pytest -q -ra -p no:cacheprovider --basetemp .verification-audit-baseline --cov=handoff` | 26 passed, 1 skipped, 88% coverage |
| `ruff check --no-cache .` | Passed |
| `ruff format --check --no-cache .` | Passed |
| `python -m build --no-isolation --outdir .verification-audit-dist` | Built wheel and source archive |
| `python -m handoff --help` | Listed nine commands |
| `python scripts/sync_skills.py --check` | Passed |

All nine commands ran against the disposable `.verification-audit-cli` copy of the
sample via `python -m handoff COMMAND --path .verification-audit-cli`. Explain used
`ev-27b79d1763a57e608df2`, and update used `--yes`. Skill installation added two
files, which the ensuing update reported.

The real symlink fixture skipped because this Windows session cannot create
symlinks. WSL listed Docker Desktop alone and `docker info --format '{{.OSType}}'`
could not reach the engine. The default sandbox command helper failed to start.
Baseline shell commands ran with scoped escalation.
