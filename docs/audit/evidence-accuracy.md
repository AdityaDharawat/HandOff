# Evidence accuracy

Run `python -m pytest -q tests/unit/test_evidence_accuracy.py tests/integration/test_audit_regressions.py tests/integration/test_git_and_skill.py`.

| Scenario | Expected interpretation |
|---|---|
| Complete-looking function, untested implementation | Executable body observed, behavior unverified |
| Placeholder and mixed partial implementation | Local structural gap, feature scope uncertain |
| Disconnected function | Body observed, integration unknown |
| Failing test source | Test discovered, runtime outcomes unknown |
| External passing or failing JUnit | Counts from an external artifact, no feature verification |
| Misleading commit | Git metadata, no completion claim |
| Stale TODO | Marker observed separately from implementation status |
| README-only completion claim | No progress claim |
| Distributed implementation | Function-level observations, no integration conclusion |
| Configuration-only entry point | Script declaration, no completion claim |
| Operator declaration | Planned or blocked with declared provenance |

The Windows regression suite checks internal anchors, same-timestamp file
changes, missing references, invalid snapshots, and an external passing test
artifact cited as completion. The validator now checks current bytes against
stored fingerprints. Explain marks evidence as historical. No new snapshot
schema was needed. Existing schema-1 fields remain readable. Independent
feature provenance and historical lookup beyond saved snapshots remain outside
the verified scope.

JUnit artifact metadata can expose normalized timestamp, commit, and framework
declarations in explain output. Error counts are separate from assertion
failures. Raw commands and test logs are omitted. A declaration is never
promoted to observed Git history or an independently verified test run.
