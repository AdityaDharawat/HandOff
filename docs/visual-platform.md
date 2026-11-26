# Visual platform

The Python package owns classification, state, rendering and publication. The
extension invokes `python -I -m handoff.bridge COMMAND --path ROOT` with an
absolute root path and a version-1 JSON envelope. `analyze` is read-only;
`generate` publishes the package, `validate` checks artifacts and source
content, and `version` identifies the bridge. Size and time limits apply to
subprocess output. Cancellation of analysis retains the previous model.

## Analysis schema

`project-analysis.json` has schema version 1. It contains the original
versioned snapshot and provenance IDs, counts, detected languages, package
declarations, static import edges, and analysis notes. Each edge has source
and target repository paths and a source line. JavaScript and TypeScript
support covers unambiguous single-line relative imports and the root
`tsconfig.json` `@/*` mapping. Other aliases, runtime imports and
framework-specific routing remain unknown.
Package versions are declared constraints. URLs and raw command arguments
stay out of results. Findings describe observations and verification limits.

## Publication

The default output is `.handoff/`; `handoff.outputDirectory` can select a
subdirectory. The output contains seven Markdown reports, five standalone SVGs,
four versioned data exports, an offline dashboard, a digest manifest and a ZIP.
The ZIP excludes source files and includes any preserved manual notes in reports.
A package-specific snapshot preserves the existing CLI publication baseline.
Writes reuse the existing report transaction, conflict detection, and rollback.
The manifest and source validation are consistency checks without signatures.
A hard interruption may still require reviewing backups.

The dashboard serves the same local assets in a VS Code webview and an offline
HTML export. Webview messages are restricted to known operation types and
source navigation is checked against the current inventory and workspace.
Archived dashboard links resolve to source when the package sits in its analyzed
repository at the original output location. Restricted or virtual workspaces
are unsupported. Dependencies may need network access for first-time engine
installation. Analysis, export and the generated dashboard work offline.

See [extension installation and packaging](../vscode-extension/README.md)
and the [pre-change audit](audit/visual-platform-baseline.md).
