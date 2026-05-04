# 2026-04-21 Random Suite Generation Run Notes

Generator batch:

- Pool: `scalar_misalign_full`
- Generator seed: `20260421`
- Suite count: `3`
- Run count per suite: `5`
- Batch index:
  - `docs/evidence/random-suite-generation/generated_suites/record_scalar_misalign_full_rand_batch.json`

Generated suites:

- `record_scalar_misalign_full_rand_000.yaml`
- `record_scalar_misalign_full_rand_001.yaml`
- `record_scalar_misalign_full_rand_002.yaml`

Real `emu` results:

- Verification env:
  - `SNIPPETGEN_RUN_MAX_CYCLES=60000`
  - `SNIPPETGEN_RUN_MAX_INSTR=60000`

- `long_record_scalar_misalign_full_rand_000_fix3`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/random-suite-generation/record_scalar_misalign_full_rand_000_batch_meta.json`

- `long_record_scalar_misalign_full_rand_001_fix3`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/random-suite-generation/record_scalar_misalign_full_rand_001_batch_meta.json`

- `long_record_scalar_misalign_full_rand_002_fix3`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/random-suite-generation/record_scalar_misalign_full_rand_002_batch_meta.json`
