# Release verification

## Local results

Environment: Windows x64 build 26300, VS Code 1.147.0, Python 3.12.10,
and Node.js 24.20.0. Tested asset: `handoff-project-intelligence-0.1.0.vsix`.
SHA-256: `c4252622e36ad85bd88f9813921b2fb0256789b852381e2d590a33737bcc2de1`.

| Check | Result |
| --- | --- |
| Python tests | Windows, Python 3.12.10: 56 passed, one existing Windows symlink test skipped |
| Ruff lint and formatting, mypy, TypeScript | Passed on Windows |
| VSIX contents and reproducibility | Verified the allowlisted package and the bundled wheel. Two rebuilds produced identical normalized VSIX bytes on this host |
| Bundled engine | Installed the extracted wheel in a new venv. Analyzed a synthetic repository outside the source directory, generated reports, and validated the output |
| VS Code | Installed the VSIX in a clean local profile and separate extensions directory. With an explicitly configured new Python environment, the installed extension analyzed a separate repository and opened the dashboard |
| Dependency audits | Python audit reported no known issues. npm reported three moderate advisories involving VSCE and its glob and minimatch dependencies. The VSIX contains no Node dependency tree |
| Fresh-machine acceptance | **Pending.** The local tests ran on the development host |
| Linux and macOS | **Pending.** GitHub Actions defines a packaged-engine smoke test for each OS. Editor acceptance still requires an actual run |
| GitHub Actions and publishing | Workflow files are prepared. GitHub-hosted execution and release creation are unverified |

The [dashboard overview](screenshots/dashboard.png) and
[architecture map](screenshots/architecture.png) were captured from synthetic
repositories. The offline dashboard passed browser checks for navigation,
graph selection and zoom, search, downloads, and mobile layout.

## Outstanding risks

The first-run consent dialog and default Python discovery still need a
fresh-machine walkthrough. Initial setup needs a reachable Python package
index or a pre-provisioned environment. The VSIX is unsigned. Keep the published
checksum and release tag alongside the asset. GitHub environment approval is
configured by the repository maintainer. A manual workflow dispatch is always
required.

## Fresh-machine procedure

Use a separate machine or clean VM for each target platform. Install only
desktop VS Code and Python 3.11+ with pip and venv. Download the VSIX and
checksum. Follow the [installation guide](installation.md) with an empty VS
Code profile and leave `handoff.pythonPath` unset. Analyze a synthetic
repository in a path containing spaces. Approve the engine setup, confirm the
dashboard opens, generate a handover, and validate it. Restart VS Code and
repeat the analysis with the network disconnected. Record the OS and CPU,
VS Code and Python versions, asset checksum, how you installed it, and any
failures. Keep synthetic screenshots and sanitized results.

## Public-source audit limits

The provided workspace contains source plus ignored local build environments,
dependency directories, and verification artifacts. These files remain local.
The Git metadata and remote were unavailable, so tracked files, full history,
and remote settings still require the [pre-publication audit](releasing.md).
GitHub security checks cover tracked path hygiene, redacted secret scanning,
and Python and Node dependency audits. Verify the repository's history and
rights to redistributed content before approval. HandOff's existing MIT
license remains in place.
