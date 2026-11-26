# Owner-controlled publication exclusions

HandOff requires an owner-controlled private exclusion policy for release
preflight. Routine development and public CI use generic checks. The release
preflight validates the private policy before inspecting the exact staged
source and distribution archives. Missing or invalid policy blocks release.
Keep the local policy, its backup and native Git ignore overlay private.

## Local setup

The repository owner keeps `.handoff-private-exclusions.yml` at the workspace
root. Version 1 uses UTF-8 JSON, a subset of YAML. Start with the
[synthetic example](private-exclusion-policy.example.json) only when authoring
a new policy. The migrated owner copy preserves the original private rules
and includes their baseline outcomes. Keep that copy in private storage.
Recover it from the owner backup if it is missing. An example policy cannot
stand in for the repository's actual policy.

`git_ignore` contains exact unanchored directory names ending in `/`, with
each required spelling. `tracked_dirs` contains their lowercase basenames
without the trailing slash. The tracked-path check rejects protected
ancestors anywhere in the index, including forced adds. Each `regression`
row records a repository-relative file path, the Git-ignore decision, the
tracked-path decision, and whether the private rule alone ignored the file.
Include root and nested controls that exercise each rule. For additions,
privately record the expected outcomes before enabling the rule and review
the policy diff with the owner. Keep the random private nonce in the policy. The public SHA-256 seal binds the exact normalized policy to the reviewed source revision without storing its contents. To authorize an updated policy, use a new 32-byte random nonce, compute SHA-256 over its canonical JSON (ASCII, sorted keys, separators comma and colon with no spaces), and review the resulting change to `scripts/private-exclusion-policy.sha256`. Rotate the environment secret to the corresponding validated policy. The tool rejects absolute paths, traversal,
wildcards, executable configuration, duplicate keys and unsupported versions.

```sh
python scripts/publication_preflight.py --validate-only
python scripts/publication_preflight.py --validate-only --write-local-ignore
python scripts/publication_preflight.py --archive dist/NAME.tar.gz --archive dist/NAME.vsix
```

The second command creates an ignored native Git pattern file without printing
its content. In an existing owner checkout, privately append those exact lines
to the checkout's Git info/exclude file, keeping existing entries. Run Git
from that checkout and verify root and nested legacy paths privately. When
updating the policy, regenerate the local overlay and replace its prior block
in info/exclude. The preflight applies the private rules independently of the
local Git overlay. A fresh public clone has the generic rules, so owner
checkouts need this setup before handling legacy private directories.

Run the last command against the reviewed Git index and the exact archives
intended for distribution. A `--manifest` scan can inspect a proposed export
when Git metadata is unavailable. Review manifest completeness separately.
The release workflow scans the index it checked out. For an independent
archive layout, licence and digest check, run `scripts/verify_vsix.py`.

## GitHub environment

1. In the authorized repository, open **Settings → Environments → New environment**
   and name it `release`. Restrict deployments to reviewed release tags and set
   required reviewers where available. Protect the tag namespace using a ruleset.
2. Under **Environment secrets**, add `HANDOFF_PRIVATE_EXCLUSION_POLICY`. Paste
   the exact validated owner policy content. Keep a copy in owner-controlled
   storage. Keep the environment secret scoped to the manual release workflow.
3. Dispatch `release.yml` against the reviewed release tag with `publish=false`
   and approve its environment checks. The policy is available only in the
   relevant preflight steps. It passes directly via an environment variable,
   with no temporary policy file or artifact. Fork pull requests run generic CI.
4. Review the rehearsal before giving separate publication approval. If the
   workflow reports a missing or invalid policy, restore and validate the owner
   copy. Keep the rehearsal blocked until it passes.

Diagnostics report only the error class. Keep policy patterns and any private
regression details out of issues, logs and shared audit reports.
