# Publication reliability

Run `python -m pytest -q tests/integration/test_audit_regressions.py tests/integration/test_publication_recovery.py tests/integration/test_cli.py`.

The reviewed Windows regressions cover manual notes on either side of the
managed block, unchanged generate and update, rejection of unmanaged reports,
backup recovery, cancellation, rollback after snapshot-write failure, and an
external edit after the first replacement. Report content and the published
snapshot remain byte-for-byte unchanged during a no-op update. Check now
distinguishes a managed report edit from repository changes, and validate
rejects stale evidence even when the edited file kept its original timestamp.

Atomic replacement applies to each file. A hard kill or disk failure can still
interrupt a multi-file publication or its rollback. Inspect local backups under
`.handoff/backups/` and use `validate` before trusting the result. Real disk
exhaustion and hard-kill recovery were not tested.
