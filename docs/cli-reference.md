# CLI reference

Run with `handoff` or `python -m handoff`. All commands accept `--path ROOT`.
The provided directory sets the scan boundary.

| Command | Example | Effect |
|---|---|---|
| init | `handoff init` | Creates local configuration and storage |
| scan | `handoff scan --json` | Saves latest observations and emits JSON |
| generate | `handoff generate --output-dir ./reports` | Publishes both Markdown reports |
| status | `handoff status` | Shows saved progress categories and timestamp |
| check | `handoff check` | Compares repository inventory to publication |
| explain | `handoff explain ID` | Shows the stored record and its evidence |
| validate | `handoff validate` | Checks report integrity and evidence references |
| update | `handoff update --yes` | Shows the managed diff and applies the update |
| skill | `handoff skill --provider both` | Installs or checks project skill copies |

`scan --verbose` lists inspected paths. `--quiet` hides the summary.
`generate --force` and `update --force` allow replacement of edited managed
blocks after explicit operator review. Files with invalid markers are refused.
Content outside the managed block is preserved byte for byte. Existing report
versions are retained under `.handoff/backups/` when changed. Repeating an
unchanged update preserves the existing reports and publication timestamp.

Exit codes are 0 on success, 1 on a handled failure or cancellation, 2 on stale
state or a usage error, and 3 on report or evidence validation failure.
`check` reports limited scan coverage as unable to verify the full scope.
`validate` checks stored digests against current source bytes.

Configure limits and Git-style excludes in `.handoff/config.yaml`. Optionally set
`test_report: junit.xml` to include the aggregate counts from an existing JUnit
artifact within the scan boundary. Counts distinguish failures from errors.
External artifacts have unverified provenance and cannot prove completion.
Explain may show an artifact-declared timestamp, commit, or recognized
framework. Raw command lines and logs stay out of stored evidence.

Declare externally tracked planned and blocked work through explicit references:

```yaml
work_items:
  - path: docs/migration-plan.md
    state: not_started
  - path: docs/deployment-blocker.md
    state: blocked
```

The path must be in the visible inventory. HandOff records the declaration and
links to its context. It does not copy the linked document's contents.
