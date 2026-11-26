# Release HandOff through GitHub

GitHub hosts the source and GitHub Releases distributes the VSIX. The extension
identifier uses the local publisher name `handoff-local`. The workflow uses the
repository's GitHub Actions token.

## First public repository setup

- About description: Local repository analysis, interactive project dashboards,
  and evidence-based developer handovers for VS Code and the command line.
- Topics: `vscode-extension`, `project-handover`, `developer-tools`,
  `static-analysis`, `python`, `local-first`, `vsix`.
- Enable private vulnerability reporting and protect the default branch. Configure
  the `release` environment with the approved policy secret, protected tags, and reviewer approval. Follow the [owner setup](private-exclusion-policy.md).
- Audit the actual Git index and history before changing visibility. Run
  `git ls-files`, `git status --short --ignored`, `git log --all --stat`,
  `python scripts/publication_preflight.py`, and a redacted Gitleaks history scan.
  Review tracked nested repositories, analysis
  data, ignored artifacts accidentally staged before the rules changed, and
  developer-specific paths. Review tracked file ownership and third-party
  notices. The source and extension declare MIT and the VSIX carries the
  repository notice.

## Build and verify locally

Use Node 24.20.0 and Python 3.12.10. Activate a build virtual environment
or set `HANDOFF_BUILD_PYTHON` to the absolute interpreter path when your
build Python isn't the default.

```sh
python -m pip install -r scripts/vsix-build-requirements.txt
cd vscode-extension
npm ci
npm run build
npm run package
cd ..
python scripts/verify_vsix.py vscode-extension/handoff-project-intelligence-0.1.0.vsix --normalize
```

Keep only the current wheel in the generated `vscode-extension/engine`
directory before building a new version. Repeated builds in CI compare
the normalized VSIX bytes. The verifier checks the package layout, extension
metadata, MIT license, bundled wheel and source assets. The SHA-256 digest is
published alongside the VSIX. Release notes live under `docs/releases`.

## Approve and create a release

The read-only rehearsal requires the policy and checks both source and built assets.

1. Review the source revision, CI results, release notes, and installation
   report. Versions in `pyproject.toml`, `vscode-extension/package.json`, and
   `vscode-extension/package-lock.json` must match. Use a new tag and version
   for an update after publication.
2. After explicit approval, push the reviewed revision and its matching
   `vX.Y.Z` tag. Dispatch the workflow against that tag using the GitHub CLI.

   ```sh
   gh workflow run release.yml --ref v0.1.0 -f tag=v0.1.0 -f publish=false
   ```
3. Review the rehearsal before dispatching again with `-f publish=true` after
   explicit publication approval. The workflow reruns tests, security checks, deterministic packaging, and
   packaged engine smoke tests. The publish job verifies the downloaded
   asset and checksum, then creates the release with its notes and both
   assets. Approve the environment deployment if configured.
4. Confirm the release assets and install the downloaded VSIX using the
   [end-user guide](installation.md).

Use [GitHub CLI release documentation](https://cli.github.com/manual/gh_release_create)
for details on the release command.

## Optional Open VSX

Open VSX may later mirror the tested VSIX for compatible editors. If maintainers
choose to add it, confirm namespace ownership, the publisher agreement, extension
identity, and editor compatibility. Keep its publishing token in a separately
approved workflow. GitHub distribution proceeds independently.
See the [Open VSX publishing guide](https://github.com/eclipse-openvsx/openvsx/wiki/Publishing-Extensions).
