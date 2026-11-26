# Clean-machine VSIX acceptance

On each target platform use a fresh VM or machine with desktop VS Code and
Python 3.11+ with pip and venv. Copy only the candidate VSIX, its
`SHA256SUMS`, and `scripts/prepare_vscode_acceptance.py` to the machine.

```sh
python prepare_vscode_acceptance.py handoff-project-intelligence-0.1.0.vsix SHA256SUMS
```

Use `py -3` or `python3` if `python` is unavailable. Change to the temporary
directory printed by the script. Run these commands in PowerShell or a POSIX shell.

```sh
code --version
code --user-data-dir ./profile --extensions-dir ./extensions --install-extension ./handoff-project-intelligence-0.1.0.vsix
code --user-data-dir ./profile --extensions-dir ./extensions --list-extensions --show-versions
code --user-data-dir ./profile --extensions-dir ./extensions "./Sample Repository"
```

1. Confirm the installed identity ends in `@0.1.0`. Trust the synthetic
   sample, leave `handoff.pythonPath` unset, and run **HandOff: Analyze Current
   Repository**. Cancel the first prompt and confirm the workspace remains
   usable. Run again, choose **Install engine**, and verify analysis completes.
2. Open **HandOff: Open Dashboard** and switch to **Architecture**. Confirm
   that `main.py` imports `helper.py`. Follow the source link and confirm
   VS Code opens `helper.py` from the sample workspace.
3. Run **HandOff: Generate Handover Reports**, confirm the write, open the
   generated dashboard under `.handoff`, and run **HandOff: Validate
   Analysis**. Expect zero issues.
4. Close VS Code, disconnect networking, and reopen the isolated profile.
   Run analysis and confirm the managed engine is reused.
5. For an update, verify a second legitimate release and install it into
   the same profile. Check the displayed version and repeat analysis.
   For rollback, uninstall and reinstall the earlier verified asset.

```sh
code --user-data-dir ./profile --extensions-dir ./extensions --uninstall-extension handoff-local.handoff-project-intelligence
code --user-data-dir ./profile --extensions-dir ./extensions --install-extension ./handoff-project-intelligence-0.1.0.vsix
code --user-data-dir ./profile --extensions-dir ./extensions --list-extensions --show-versions
```

Record OS and CPU, VS Code and Python versions, VSIX checksum, first-run
package-index availability, and a result for each step. Use **PASS**,
**FAIL**, **NOT TESTED** or **BLOCKED**. Keep trial profiles, logs and
generated reports out of the source repository.
