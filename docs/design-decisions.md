# Design decisions

- Use static analysis and local metadata for the default workflow so repository
  scripts, APIs, and accounts are unnecessary.
- Store digests and fixed descriptions in place of raw source and commit messages
  to reduce disclosure and prevent prose from driving progress classification.
- Keep the published snapshot distinct from the latest exploratory scan so scanning
  cannot silently move the freshness baseline.
