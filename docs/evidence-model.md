# Evidence model

Snapshots contain timestamped observations, file digests, Git metadata,
configuration fingerprints, and findings. Evidence IDs are derived from source
type, relative location, observation description, and optional commit ID.
Findings cite one or more records and carry a confidence distinct from progress.

Verified denotes a directly observed property. Inferred denotes a supported
interpretation. Uncertain denotes ambiguity in an observation's interpretation.
Unknown denotes a question the scan could not answer. A verified observation of
a test artifact does not independently verify the underlying feature.

The current schema version is 1. Unsupported and corrupt snapshots return an
explicit error. Keep old snapshots separately if a future schema requires
regeneration.
