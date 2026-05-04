# Evidence

This directory stores small, persisted evidence artifacts referenced by run notes and investigation notes.

These files are not portable configuration. Some JSON files intentionally preserve the original run metadata emitted by `snippetgen`, including machine-specific absolute paths. Treat those paths as historical evidence, not as values to copy into a local setup.

## Contents

- `kmh-mmu-layer1/`
  - runner manifest example for Kunminghu v2/v3 profile setup
- `random-suite-generation/`
  - generated suite YAML records and batch metadata for the random suite generation pass
- `scalar-misalign-family-combo/`
  - batch metadata for scalar misalign family combo runs
- `scalar-misalign-seeded-deterministic/`
  - batch metadata for seeded deterministic scalar misalign runs

For human-readable summaries, start from [`../run-notes/README.md`](../run-notes/README.md).
