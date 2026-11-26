# Architecture

Typer is the entry point. Core loads project-local configuration, captures a
snapshot, and invokes the intelligence layer. The scanner walks bounded text
inputs, uses Python syntax trees and tokens for structural observations, and
queries Git index, tree, and commit metadata. Intelligence consumes only those
observations. Reports render the snapshot, validators check its references and
managed sections, and freshness compares a new capture with the publication
baseline.

Storage uses schema version 1, a cooperative lock, and atomic per-file
replacement. HandOff restores report files after a handled publication error.
A process interruption between writes can require reviewing local backups and
regenerating the report pair.

## Desktop distribution

The VSIX bundles the TypeScript host, dashboard assets, and a platform-neutral
Python wheel. The host discovers a Python 3.11+ interpreter and can bootstrap
a venv under VS Code global storage. The wheel hash selects the managed
environment, so a changed engine can be installed beside an older version.
A machine-scoped Python setting supports pre-provisioned environments.

The editor calls the engine through a versioned JSON bridge using a subprocess
without a shell. It sends the selected local workspace path for static analysis.
VS Code workspace trust gates analysis. The dashboard and exports share the
same model and assets as the CLI. GitHub Actions builds and verifies the
distribution asset using the workflow in the release guide.
