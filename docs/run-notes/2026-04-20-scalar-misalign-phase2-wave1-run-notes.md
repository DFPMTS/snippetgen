# Scalar Misalign Phase 2 Wave 1 Run Notes

## Suites

- `scalar_misalign_load_split_templates_poc`
- `scalar_misalign_store_split_templates_poc`
- `scalar_misalign_cross_page_faults_poc`

## Real Run Results

- `real_scalar_misalign_load_split_templates_8401`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_store_split_templates_8402`: `good_trap`, `finish_code=0`
- `real_scalar_misalign_cross_page_faults_8403`: `good_trap`, `finish_code=0`

## Evidence Paths

- `build/scalar_misalign_load_split_templates_poc/runs/real_scalar_misalign_load_split_templates_8401/batch_meta.json`
- `build/scalar_misalign_store_split_templates_poc/runs/real_scalar_misalign_store_split_templates_8402/batch_meta.json`
- `build/scalar_misalign_cross_page_faults_poc/runs/real_scalar_misalign_cross_page_faults_8403/batch_meta.json`

## Stdout Tail Summary

- `load_split_templates`: `HIT GOOD TRAP at pc = 0x80000030`
- `store_split_templates`: `HIT GOOD TRAP at pc = 0x80000030`
- `cross_page_faults`: `HIT GOOD TRAP at pc = 0x80000030`
