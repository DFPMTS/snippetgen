# 2026-05-19 Kunminghu v2 Vector MMU Next Run Notes

## Scope

This note tracks the next v2-only vector MMU layer after the original
`kmh_mmu_layer1_v2_vector_smoke` suite.

Suite family:

- `suites/kmh_mmu_layer1_v2_vector_widths.yaml`
  - `e8/e16/e32/e64` unit-stride vector load/store hit under Sv39 host translation
- `suites/kmh_mmu_layer1_v2_vector_faults.yaml`
  - cross-page second-page invalid and mapped-no-permission vector load/store fault
  - masked load/store masked-off fault suppression
  - masked load/store masked-on fault trigger
- `suites/kmh_mmu_layer1_v2_vector_forms.yaml`
  - strided, indexed, segment, fault-only-first, and `vstart` vector memory forms
- `suites/kmh_mmu_layer1_v2_vector_attr.yaml`
  - PMP deny, PMA/MMIO, and PBMT/NC attribute witnesses
- `suites/kmh_mmu_layer1_v2_vector_hyp.yaml`
  - ordinary vector load/store cases for onlyStage1, onlyStage2, and allStage

The suites are v2-only. They are not v3 evidence, and they are not intended to
cover PTW/L2TLB contention, merged miss, replay timing, or vector pipeline
micro-op ordering.

`kmh_mmu_layer1_v2_vector_smoke` remains the shortest pass-only unit-stride
load smoke. The no-fence vector load/store replay assertion shape is kept separately as
`kmh_mmu_layer1_v2_vector_replay_repro` and must not be turned into a pass-only
regression by adding unrelated instructions or fences.

## Build Checks

Use these checks before target runs:

```bash
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_widths.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_faults.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_forms.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_attr.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_attr_mmio_identity_repro.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_hyp.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_replay_repro.yaml

python3 -m unittest \
  tests.test_kmh_mmu_layer1_inventory.KMHMMULayer1InventoryTest.test_kmh_layer1_suites_resolve_and_keep_v3_vector_free
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_widths_suite_builds_multi_eew_opcodes
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_faults_suite_builds_masked_vector_opcodes
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_forms_suite_builds_non_unit_vector_opcodes
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_attr_suite_builds_attribute_coverage_artifact
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_attr_mmio_identity_repro_suite_builds_bug_repro
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_hyp_suite_builds_guest_mode_vector_program
python3 -m unittest \
  tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_hyp_stage2_and_allstage_suites_build_isolated_cases
```

Do not run build-pipeline cases for the same suite concurrently. They clean
shared build directories in `setUp`.

## Target Commands

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_widths.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_widths_20260519

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_faults.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_faults_20260519

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_forms.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_forms_20260519

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_attr.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_attr_20260519

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_hyp.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_hyp_20260519
```

For known failing repros, use explicit batch ids and keep them out of pass-only
regression gates:

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_replay_repro.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_replay_repro_20260520_r13_nofence

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_attr_mmio_identity_repro.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_attr_mmio_identity_repro_20260520_r13_bug
```

Vector coverage summary:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_v2_vector_smoke/runs/kmh_v2_vector_smoke_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_widths/runs/kmh_v2_vector_widths_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_faults/runs/kmh_v2_vector_faults_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_forms/runs/kmh_v2_vector_forms_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_attr/runs/kmh_v2_vector_attr_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_hyp/runs/kmh_v2_vector_hyp_20260520_r13_loadonly/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_attr_mmio_identity_repro/runs/kmh_v2_vector_attr_mmio_identity_repro_20260520_r13_bug/batch_meta.json \
  build/kmh_mmu_layer1_v2_vector_replay_repro/runs/kmh_v2_vector_replay_repro_20260520_r13_nofence/batch_meta.json
```

The vector coverage ledger carries per-item `fail_codes` metadata for the v2
suite family. When a multi-case suite exits through a known self-check
`finish_code`, `run_batch.py` marks the completed prefix as `ran`, the matching
failing item as `failed_or_blocked`, and the remaining suffix as
`generated_not_run`. If the run aborts before a structured finish code, such as
the replay RTL assertion, the repro remains fully `failed_or_blocked`.

## Failure Policy

If a target run fails, keep the failing test shape intact and record the
failure. Do not insert unrelated instructions, fences, padding, or lower-stress
variants to make the normal regression pass. If a pass-only reduced suite is
needed later, keep it separate from the bug repro and document the difference.

## 2026-05-20 Results

Host/build checks:

- `python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_widths.yaml`
  - PASS
- `python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v2_vector_faults.yaml`
  - PASS
- `python3 generator/cli.py dump-plan` for smoke, widths, faults, forms, attr, and hyp suites
  - PASS
- `python3 -m unittest tests.test_kmh_mmu_layer1_inventory.KMHMMULayer1InventoryTest.test_kmh_layer1_suites_resolve_and_keep_v3_vector_free`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_mmu_suite_builds_real_vector_memory_opcodes`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_widths_suite_builds_multi_eew_opcodes`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_faults_suite_builds_masked_vector_opcodes`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_forms_suite_builds_non_unit_vector_opcodes`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_attr_suite_builds_attribute_coverage_artifact`
  - PASS
- `python3 -m unittest tests.test_build_pipeline.BuildPipelineTest.test_kmh_v2_vector_hyp_suite_builds_guest_mode_vector_program`
  - PASS
- `python3 -m unittest tests.test_mmu_coverage_summary`
  - PASS
- `python3 -m unittest tests.test_run_pipeline.RunPipelineTest.test_run_batch_marks_vector_mmu_coverage_by_target_result`
  - PASS

Target evidence:

- `build/kmh_mmu_layer1_v2_vector_smoke/runs/kmh_v2_vector_smoke_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `runner_revision`: `4d1d56db9374d8163c1475e0ebf41265ec85d240`
  - `diff_revision`: `cb15254c9bd09d36bf74853300302b7c4e59910f`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
- `build/kmh_mmu_layer1_v2_vector_widths/runs/kmh_v2_vector_widths_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `runner_revision`: `4d1d56db9374d8163c1475e0ebf41265ec85d240`
  - `diff_revision`: `cb15254c9bd09d36bf74853300302b7c4e59910f`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
- `build/kmh_mmu_layer1_v2_vector_faults/runs/kmh_v2_vector_faults_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
- `build/kmh_mmu_layer1_v2_vector_forms/runs/kmh_v2_vector_forms_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
- `build/kmh_mmu_layer1_v2_vector_hyp/runs/kmh_v2_vector_hyp_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - note: aggregate hyp includes onlyStage1, onlyStage2, and allStage vector load/store representatives. Round 7 fixes the onlyStage1 cases to program `vsatp` and execute the vector memory access with guest-data translation rather than host `satp`.
- `build/kmh_mmu_layer1_v2_vector_hyp_only_stage1_hit/runs/kmh_v2_vector_hyp_only_stage1_hit_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - note: isolated onlyStage1 hit uses `vsatp` with `hgatp=0`.
- `build/kmh_mmu_layer1_v2_vector_hyp_only_stage1_fault/runs/kmh_v2_vector_hyp_only_stage1_fault_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - note: isolated onlyStage1 fault uses `vsatp` with `hgatp=0`.
- `build/kmh_mmu_layer1_v2_vector_attr/runs/kmh_v2_vector_attr_20260520_r13_loadonly/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - detail: aggregate attr includes PMP load deny, PMP store deny, translated MMIO `load access fault`, and PBMT reserved-fault witnesses.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio_direct/runs/kmh_v2_vector_attr_mmio_direct_20260520_r3_final/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - note: direct platform `mtime` read sanity passes.
- `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_layer1_attr_ctrl_20260520_r3_scalar_mmio_compare/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `0`
  - result: `HIT GOOD TRAP`
  - note: scalar `host_pma_mmio_attribute` uses the same `mtime` MMIO contract and passes on the same v2 runner.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio_identity_repro/runs/kmh_v2_vector_attr_mmio_identity_repro_20260520_r13_bug/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `1`
  - result: `HIT BAD TRAP`
  - detail: preserved bug repro for the old no-fault translated-MMIO store-back assumption. It executes `vle64.v v8,(0x900730ff8)` followed by `vse64.v v8,(g_scratch)` under `MPRV=1,MPP=S` and still bad-traps. Keep this path out of pass-only gates until the expected architectural/design behavior is settled.
- `build/kmh_mmu_layer1_v2_vector_replay_repro/runs/kmh_v2_vector_replay_repro_20260520_r13_nofence/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `runner_revision`: `4d1d56db9374d8163c1475e0ebf41265ec85d240`
  - `diff_revision`: `cb15254c9bd09d36bf74853300302b7c4e59910f`
  - `seed`: `241027`
  - result: `RTL assertion`
  - detail: `LoadQueueReplay.sv:22867`, `vector load, should not have replay entry 29 when commit or flush`; this is preserved as a real no-fence replay blocker.

Historical MMIO diagnostics:

- `build/kmh_mmu_layer1_v2_vector_attr_mmio/runs/kmh_v2_vector_attr_mmio_20260520_r3_final/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `1`
  - result: `HIT BAD TRAP`
  - detail: stale pre-Round-6 no-fault expectation. The current checked-in MMIO attribute witness classifies the translated vector MMIO access as `load access fault` and good-traps in `kmh_v2_vector_attr_mmio_20260520_r6_access_fault`.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio/runs/kmh_v2_vector_attr_mmio_20260520_r4_debug/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `1`
  - result: `HIT BAD TRAP`
  - detail: unchanged-source rerun of the translated vector MMIO witness. The generated program still executes `vle64.v v8,(0x900730ff8)` followed by `vse64.v v8,(g_scratch)` under `MPRV=1,MPP=S`.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio/runs/kmh_v2_vector_attr_mmio_20260520_r4_diag_branch/batch_meta.json`
  - temporary diagnostic run, not checked in as a pass criterion
  - result: `HIT BAD TRAP at pc = 0x800018fc`
  - detail: the temporary callsite maps to the `xsam_mmu_fault_seen_mask() != 0` branch after the vector load/store pair. This rules out the final `observed < before` and `observed > after` value checks as the first failing condition.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio/runs/kmh_v2_vector_attr_mmio_20260520_r4_diag_fault_class/batch_meta.json`
  - temporary diagnostic run, not checked in as a pass criterion
  - result: `HIT BAD TRAP at pc = 0x8000193c`
  - detail: the temporary callsite maps to `xsam_mmu_last_fault_cause() == 15`, a store page fault.
- `build/kmh_mmu_layer1_v2_vector_attr_mmio/runs/kmh_v2_vector_attr_mmio_20260520_r4_diag_tval/batch_meta.json`
  - temporary diagnostic run, not checked in as a pass criterion
  - result: `HIT BAD TRAP at pc = 0x8000198a`
  - detail: the temporary callsite maps to `store page fault` with `tval == g_scratch`. The scratch page is covered by the runtime identity mapping with RWXAD permissions, so the current blocker is the store-back side of the vector MMIO witness: `vle64.v` from the translated MMIO VA is followed by `vse64.v` to identity-mapped scratch, and that `vse64.v` records a store page fault.
- `build/kmh_mmu_layer1_v2_vector_attr/runs/kmh_v2_vector_attr_20260520_r3_final/batch_meta.json`
  - `runner_profile`: `kmh-v2/difftest`
  - `seed`: `241027`
  - `finish_code`: `1`
  - result: `HIT BAD TRAP`
  - detail: stale pre-Round-6 aggregate attr run. The current aggregate attr evidence is `kmh_v2_vector_attr_20260520_r6_access_fault`, which good-traps with the translated MMIO path classified as `load access fault`.

Coverage summary for the final recorded vector runs:

- `smoke`: 3 items `ran`
- `widths`: 4 items `ran`
- `faults`: 6 items `ran`
- `forms`: 8 items `ran`
- `attr`: 4 items `ran`
- `hyp`: 7 items `ran`
- `attr_mmio_identity_repro`: 1 item `failed_or_blocked`
- `replay_repro`: 7 items `failed_or_blocked`

Known blocked vector runs:

- `replay_repro`: 7 items `failed_or_blocked` by the replay assertion
- `attr_mmio_identity_repro`: 1 item `failed_or_blocked` by the old no-fault translated-MMIO store-back shape. Round 4 diagnostics narrowed one failing condition to a store page fault on `vse64.v` store-back to identity-mapped `g_scratch`; Round 5 diagnostics also showed that a translated MMIO `vle64.v` can be classified as `load access fault` with `tval == 0x900730ff8`. The checked-in pass-only attr suite now treats that PMA/MMIO result as the expected attribute-limit fault and keeps the no-fault store-back assumption isolated as a repro.

During round-2 H-extension bring-up, the onlyStage2 and allStage vector suites
timed out before the first committed-instruction marker when the test entered
VS with the generic `xsam_mmu_enter_vs` trampoline. That path depends on an
SRET/VS trap-return chain that this baremetal runtime does not fully install.
The checked-in H vector cases now keep the same ordinary vector load/store
instructions and the same stage1/stage2 page-table setup, but execute the data
access with `MPRV=1`, `MPP=S`, and `MPV=1`. This exercises the guest data
translation path directly and the isolated plus aggregate H suites now
good-trap on the v2 target.

During bring-up, `kmh_v2_vector_widths_20260519` produced `HIT BAD TRAP`.
That was a test-construction issue, not a DUT bug: the first version requested
`vl=8` for every EEW, which is not a valid expectation for `e32,m1` or `e64,m1`
when VLEN is 128. The checked-in version requests `vl=16/8/4/2` for
`e8/e16/e32/e64`, respectively. No unrelated instruction padding or fence was
added to make the case pass.

During round-1 bring-up, `kmh_mmu_layer1_v2_vector_faults` and
`kmh_mmu_layer1_v2_vector_forms` initially exceeded the default target
instruction budget. Root cause was test self-check overhead: the programs used
large 4K/8K byte loops to initialize or verify whole pages even though the
vector instruction under test could only affect a small cross-page window.
The checked-in version keeps the same vector memory instructions and fault
addresses, but limits initialization and second-page non-write checks to the
actually observable vector window. This is a testcase fix, not a DUT workaround.
