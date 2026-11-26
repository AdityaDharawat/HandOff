# Future web distribution proposal

A separate, opt-in website could accept a repository ZIP, run the same
static analysis and present the same dashboard and evidence-linked exports.
The desktop extension and CLI would continue to work locally.

## Processing flow

1. Explain upload handling and retention before accepting an archive. Send a
   ZIP to private temporary storage and issue a short-lived job identifier.
2. Queue analysis. A per-job worker extracts files into an isolated directory.
   Enforce limits on archive size, total extracted bytes, compression ratio,
   file count, path depth, execution time, and memory. Reject traversal,
   symlinks, special entries, duplicate paths, and nested archives.
3. Run the existing Python analyzer from a pinned, prebuilt worker image with
   no outbound network, read-only application code, and per-job writable
   storage. Never run uploaded code, tests, install scripts, or Git hooks.
4. Produce the versioned model, reports, and static dashboard through the
   same engine and asset pipeline. Serve the dashboard on an isolated origin
   with a restrictive CSP. Use short-lived authenticated artifact links.
5. Remove archives, extracted contents, and output on expiration or deletion.
   Keep operational logs free of names, source, credentials, and raw content.

## Before implementation

Define a retention window, abuse controls, upload quotas, and the hosting
cost model. Treat missing Git history as absent evidence. Verify parity against
the CLI using a synthetic ZIP and compare normalized snapshots and evidence.
Test archive handling limits and isolation before accepting public uploads.
