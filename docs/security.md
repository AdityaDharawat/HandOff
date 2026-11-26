# Security

HandOff reads bounded text inputs and exports structural descriptions, relative
paths, identifiers, and digests. Secret-like filenames, linked paths, and common
credential directories are skipped. Raw code, test output, variable values, and
commit messages stay out of generated sections. Review filenames, metadata, and
manual notes before sharing. Filenames can contain sensitive information.

HandOff uses safe YAML loading, rejects nonportable output paths, and renders
untrusted display text as Markdown entities. It does not execute target tests or
commands found in project files. Git queries read raw objects and index entries
without invoking configured content filters. No core command requires a network.
Git itself and the local runtime are part of the trusted environment.

Path checks cannot prevent every race with another process modifying directories
during scanning or publishing. Run against a stable workspace. Only HandOff
writers participate in the lock. Externally modified backups and local snapshots
are user-controlled data. Validation is a consistency check without signatures.
