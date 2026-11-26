# HandOff for VS Code

Understand a local repository through architecture, implementation evidence,
test discovery and next steps. The extension runs the existing Python engine
locally and adds no telemetry or hosted analysis.

1. Build a local VSIX while the first GitHub release is pending, then install it with **Install from VSIX** in the Extensions view.
2. Open a trusted local repository and select the HandOff icon in the Activity Bar.
3. Choose **Analyze Current Repository**. Select a workspace folder when prompted.
4. Open evidence to navigate to source. Confirm before generating a package.

Install Python 3.11 or newer if automatic discovery finds none. Configure
`handoff.pythonPath` to use an existing interpreter. If the engine is absent,
HandOff can set up a dedicated environment with your consent. Initial dependency
installation may access the configured Python package index. Scanning and
export run offline. For isolated environments, point HandOff to an interpreter
with the bundled engine and dependencies already installed.

Outputs default to `.handoff` in the analyzed workspace. Open `index.html`
locally for the offline dashboard. **Export Handover Package** writes and
reveals the ZIP. Existing unmanaged reports or manually edited generated
artifacts cause a conflict and are preserved.

You can also run `code --install-extension ./handoff-project-intelligence-0.1.0.vsix`
from the download directory. Install a newer release the same way to update.

Build from the extension directory with `npm ci`, `npm run build`, then
`npm run package`. Set `HANDOFF_BUILD_PYTHON` to the Python executable with
HandOff's build dependencies. Open the repository root in VS Code and use the
Extension Development Host with this directory as `--extensionDevelopmentPath`.
