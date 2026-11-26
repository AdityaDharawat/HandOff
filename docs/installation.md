# Install HandOff for VS Code

Use desktop VS Code 1.95 or newer and Python 3.11 or newer with venv and pip.
Git is optional for running HandOff. The first GitHub VSIX release is pending.
Build a local candidate using the [release guide](releasing.md). When a release
is available, use its VSIX and verify the supplied SHA-256 checksum.

## Install from the editor

1. Open **Extensions** in VS Code.
2. Open the Extensions view's **…** menu and select **Install from VSIX…**.
3. Select the downloaded VSIX and reload the editor if prompted.
4. Open a local repository you trust, then run **HandOff: Analyze Current Repository**
   from the Command Palette. Select a folder if VS Code asks.
5. Choose **Install engine** at the first-run prompt. HandOff creates a
   dedicated Python environment in VS Code extension storage and installs the
   engine included in the VSIX. Initial dependency installation may use your
   Python package index. Analysis and export then run offline.
6. Use **HandOff: Open Dashboard** to inspect the results. Use **HandOff:
   Generate Handover Reports** to save the dashboard and reports under
   `.handoff` in the selected workspace.

## Install from a terminal

From the directory containing the downloaded asset:

```sh
code --install-extension ./handoff-project-intelligence-0.1.0.vsix
code --list-extensions --show-versions
```

Look for `handoff-local.handoff-project-intelligence@0.1.0`. If the shell
cannot find `code`, use the VS Code UI. On macOS you can add the CLI to PATH
using **Shell Command: Install 'code' command in PATH** in the Command Palette.

## Update or roll back

Download the VSIX for the version you want and install it through the same UI
or CLI. To replace a newer version with an older one, use **Uninstall** in the
Extensions view first. Keep the previous VSIX if you need to roll back.
Check the installed version with the command above. Check GitHub Releases
manually for updates. A changed bundled wheel may prompt for engine setup again.

## Python setup

Restart VS Code after installing Python so it sees your updated PATH.
On Windows the extension checks the Python launcher and PATH. On macOS and
Linux it checks `python3` and `python`. Set `handoff.pythonPath` in user
settings to the absolute executable path if VS Code can't find your interpreter.
On Linux, install your distribution's Python venv package if venv or ensurepip
is missing. For a disconnected machine, provision a virtual environment with
the bundled wheel and its dependencies from a trusted local wheelhouse, then
point the setting at that environment's Python executable.

See [VS Code's VSIX installation documentation](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace#_install-from-a-vsix).
