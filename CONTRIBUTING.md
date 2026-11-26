# Contributing to HandOff

Use Python 3.11 or newer. For extension changes, use the Node and Python build
versions in the [release guide](docs/releasing.md).

```sh
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m mypy
python -m pytest -ra
python scripts/sync_skills.py --check
```

Use a synthetic fixture to reproduce behavior, describe verification in the pull
request, and link the relevant issue. Keep scanning static and offline. Tie
generated findings to evidence and keep source snippets, raw Git messages,
logs, and credentials out of reports. Edit the skill manifest under
`src/handoff` and run `python scripts/sync_skills.py` to sync the copies.

See the [code of conduct](CODE_OF_CONDUCT.md) and [security policy](SECURITY.md).

Publication changes use the [owner-controlled exclusion policy](docs/private-exclusion-policy.md). Keep private policies and their Git overlays out of patches.
