# Scalar Misalign Phase 1 Run Notes

## Suites

- `scalar_misalign_load_in_16b_poc`
- `scalar_misalign_load_cross_16b_poc`
- `scalar_misalign_store_in_16b_poc`
- `scalar_misalign_store_cross_16b_poc`
- `scalar_misalign_store_load_overlap_poc`

## Real Run Results

- `real_scalar_misalign_load_in_16b_8301`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_load_cross_16b_8302`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_store_in_16b_8303`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_store_cross_16b_8304`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_store_load_overlap_8305`: `good_trap`, `finish_code=0`

## Evidence Paths

- `build/scalar_misalign_load_in_16b_poc/runs/real_scalar_misalign_load_in_16b_8301/batch_meta.json`
- `build/scalar_misalign_load_cross_16b_poc/runs/real_scalar_misalign_load_cross_16b_8302/batch_meta.json`
- `build/scalar_misalign_store_in_16b_poc/runs/real_scalar_misalign_store_in_16b_8303/batch_meta.json`
- `build/scalar_misalign_store_cross_16b_poc/runs/real_scalar_misalign_store_cross_16b_8304/batch_meta.json`
- `build/scalar_misalign_store_load_overlap_poc/runs/real_scalar_misalign_store_load_overlap_8305/batch_meta.json`

## Stdout Tail Summary

- `load_in_16b`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 358`, `cycleCnt = 5058`
- `load_cross_16b`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 394`, `cycleCnt = 5072`
- `store_in_16b`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 387`, `cycleCnt = 5076`
- `store_cross_16b`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 484`, `cycleCnt = 5218`
- `store_load_overlap`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 413`, `cycleCnt = 5083`
