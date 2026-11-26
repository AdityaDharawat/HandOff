# Visual platform readiness

**Local preview.** The scoped workflow was exercised on Windows with VS Code
1.147.0, Chrome, Node 24.20.0, and Python 3.12.10.

## Verified

- The final Python run reported 56 passed, one existing Windows symlink skip,
  and 86% coverage. Ruff lint and format and mypy passed.
- TypeScript compilation and `vsce package --allow-missing-repository` built
  an installable VSIX containing the compiled extension, dashboard assets, and
  a Python wheel. `code --install-extension` installed it to an isolated
  extensions directory, where `--list-extensions --show-versions` returned
  `handoff-local.handoff-project-intelligence@0.1.0`.
- A VS Code development-host smoke test exercised command registration, local analysis, and opening the webview.
- Chrome opened that HTML and exercised all eight views, graph keyboard
  selection, zoom, search, a download link, and the mobile viewport. A desktop
  screenshot was captured locally.
## Reproduction

Run `python -m pytest -q -ra -p no:cacheprovider --basetemp .verification-visual-release --cov=handoff`,
`ruff check --no-cache src tests`, and `python -m mypy`.
Build with `npm run build` and `npm run package` in the extension directory.
Use `python -I -m handoff.bridge generate --path ROOT --output .handoff/visual`
and the corresponding `validate` command to verify artifacts without changing
an existing CLI baseline. For browser checks use
`node vscode-extension/tests/dashboard-smoke.mjs BROWSER INDEX_HTML SCREENSHOT`.
The VS Code smoke harness is in `vscode-extension/tests/smoke.cjs`.

## Remaining acceptance work

The editor smoke covers activation, analysis and opening the webview. The
export used the same bridge directly. A manual editor walkthrough of source
navigation, confirmations, cancel, multi-root selection and artifact opening
remains outstanding. Initial engine installation and macOS/Linux editor hosts
need separate acceptance runs. The graph supports scoped static imports and
one explicit TypeScript alias convention. It does not infer all runtime,
service, database, or framework relations. Function and declaration findings
cannot verify whole features.
