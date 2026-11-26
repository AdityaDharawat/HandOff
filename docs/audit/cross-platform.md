# Cross-platform verification

| Environment | Command or procedure | Outcome |
|---|---|---|
| Windows CPython 3.12.10, editable | `python -m pytest -q -ra -p no:cacheprovider --basetemp .verification-audit-verified --cov=handoff` | 52 passed, 1 skipped, 88% coverage |
| Windows CPython 3.12.10, clean source archive | `uv pip install --reinstall --python .verification-env-3.12/Scripts/python.exe .verification-audit-release-dist/handoff_continuity-0.1.0.tar.gz` then `python -m pytest -q -ra -p no:cacheprovider --basetemp .verification-audit-source-final` in that environment | Final suite 52 passed and 1 skipped; an earlier clean archive install also ran a quiet module scan outside the checkout |
| Windows CPython 3.12.10, clean wheel | `uv pip install --python .verification-wheel-env/Scripts/python.exe .verification-audit-final-dist/handoff_continuity-0.1.0-py3-none-any.whl` | Installed; module scan, generate, check and validate passed from the parent directory against a path with a space and an accented character |
| Windows launcher | `.venv/Scripts/handoff.exe --help` | Application Control blocked execution with OS error 4551. Wheel metadata provides the console entry point |
| Windows CPython 3.11.18 and 3.13.18 | `uv python install 3.11 3.13`, then create and inspect separate environment interpreters | Download and environment creation completed; Application Control blocked running both environments with OS error 4551 |
| Linux | `wsl.exe --list --quiet`, `docker info --format '{{.OSType}}'` | No general-purpose Linux distro listed. Docker Linux engine unavailable |
| macOS | No runner present | Unverified |

Windows junction coverage passed. Real symlinks were skipped. Missing Git
was simulated, and the outside-checkout smoke fixture ran without a Git
repository. Codex CLI 0.150.1 and Claude Code 2.1.247 printed versions.
`python scripts/sync_skills.py --check` passed and local skill installation
and frontmatter were tested. Live client sessions were not run with project
content under the no-external-services constraint. Hosted workflow execution
remains pending.
