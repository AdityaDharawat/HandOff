# Limitations

- Detailed static inspection is Python-oriented. Other languages get file-level
  classification. Entry points and dependency manifests are hints.
- HandOff does not infer architecture, objectives, commands, or rationale from
  prose. ADR discovery uses directory conventions. Progress applies to observed
  functions, not complete features.
- JUnit artifacts report recorded counts. Their origin and relevance to the
  current revision require independent confirmation.
- Git metadata covers visible scanned text files, raw blob changes, and recent
  commit IDs. Git normalization, modes, and deleted or skipped paths are outside
  this comparison. Freshness catches removals from a prior inventory.
- Ignored, non-UTF-8, linked, binary, oversized, and out-of-budget content is
  outside the scan. Submodules have no independent Git state in the report.
- One publication baseline is kept per project. Keep the report output directory
  stable. Remnants of interrupted multi-file publishing may need manual recovery.
- General dependency semantics, feature-level verification mapping, and live
  cross-agent evaluation remain pending.
