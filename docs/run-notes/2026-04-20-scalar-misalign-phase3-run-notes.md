# Scalar Misalign Phase 3 Run Notes

## Suites

- `scalar_misalign_store_forward_search_poc`
- `scalar_misalign_cross_page_fault_search_poc`
- `scalar_misalign_replay_probe_poc`

## Real Run Results

- `real_scalar_misalign_store_forward_search_8501_fix1`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_cross_page_fault_search_8502_fix1`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_replay_probe_8503`: `good_trap`, `finish_code=0`

## Evidence Paths

- `build/scalar_misalign_store_forward_search_poc/runs/real_scalar_misalign_store_forward_search_8501_fix1/batch_meta.json`
- `build/scalar_misalign_cross_page_fault_search_poc/runs/real_scalar_misalign_cross_page_fault_search_8502_fix1/batch_meta.json`
- `build/scalar_misalign_replay_probe_poc/runs/real_scalar_misalign_replay_probe_8503/batch_meta.json`

## Stdout Tail Summary

- `store_forward_search`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 930`, `cycleCnt = 5800`
- `cross_page_fault_search`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 1157`, `cycleCnt = 7321`
- `replay_probe`: `HIT GOOD TRAP at pc = 0x80000030`, `instrCnt = 1504`, `cycleCnt = 6319`
