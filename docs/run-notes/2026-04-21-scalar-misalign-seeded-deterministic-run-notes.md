# 2026-04-21 Scalar Misalign Seeded Deterministic Run Notes

Standalone deterministic suites:

- `record_scalar_misalign_load_split_74565`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/load_split_74565_batch_meta.json`

- `record_scalar_misalign_store_split_144470`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/store_split_144470_batch_meta.json`

- `record_scalar_misalign_forward_overlap_214375`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/forward_overlap_214375_batch_meta.json`

- `record_scalar_misalign_cross_page_284280`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/cross_page_284280_batch_meta.json`

Family combo suites:

- `record_scalar_misalign_templates_combo_350881`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/templates_combo_350881_batch_meta.json`

- `record_scalar_misalign_fault_forward_combo_420786`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/fault_forward_combo_420786_batch_meta.json`

- `fix2_scalar_misalign_family_combo_420786`: `good_trap`, `finish_code=0`
- Evidence: `docs/evidence/scalar-misalign-seeded-deterministic/family_combo_420786_batch_meta.json`

Exploratory note:

- `seed_scalar_misalign_family_combo_490691` hit `timeout after 120s` under the default run timeout, so it is not part of the acceptance evidence set.
