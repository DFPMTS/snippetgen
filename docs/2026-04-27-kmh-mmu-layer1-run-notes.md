# 2026-04-27 KMH MMU Layer 1 Run Notes

## Scope

This note records the first RLCR verification pass for Kunminghu v2/v3
memblock MMU layer-1 tests.

Version constraint used in this pass:

- v3 excludes vector rules.
- v2 may include vector rules later, but no vector rule was added in this pass.

## Changes Under Test

- Added `snippets/mmu_rules/kmh_layer1/` with a first functional MMU rule
  corpus.
- Added v2/v3/full/fault/hyp suite entry points.
- Added inventory tests that reject unsupported first-layer claims.
- Fixed the generic MMU runner so allStage hit data seed/observe resolves
  through stage2 to HPA instead of stopping at stage1 GPA.

## Host Verification

Command:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter tests.test_kmh_mmu_layer1_inventory -v
```

Result:

- `Ran 20 tests`
- `OK`

Commands:

```bash
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_full.yaml
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_v3_smoke.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_v3_smoke.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_faults.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_hyp.yaml
```

Result:

- All dump/build commands completed.
- Build manifests were generated under `build/kmh_mmu_layer1_*`.

### Round 1 host expansion

Command:

```bash
python3 -m unittest \
  tests.test_mmu_rule_loader \
  tests.test_mmu_rule_emitter \
  tests.test_kmh_mmu_layer1_inventory \
  tests.test_runner_profiles \
  tests.test_run_pipeline \
  -v
```

Result:

- `Ran 66 tests`
- `OK`

Command:

```bash
python3 -m unittest discover -s tests -v
```

Result:

- `Ran 241 tests`
- `OK (skipped=1)`

Commands:

```bash
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_full.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_v3_smoke.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_v2_smoke.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_host_perm.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_attr_ctrl.yaml
```

Result:

- All commands completed.
- `build/kmh_mmu_layer1_full/mmu_coverage_ledger.json` had no
  `"state": "gap"` entries after the first-wave taxonomy expansion.
- The full suite now selects 24 rules.

## Target Runs

### v3 smoke

Command:

```bash
env SNIPPETGEN_RUN_MAX_CYCLES=300000 SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --batch-id kmh_v3_smoke_241027_r0 \
  --timeout-sec 600
```

Result:

- `status: "timeout"`
- `labels: ["built", "timeout"]`
- `notes: "timeout after 600s"`
- Batch: `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_241027_r0/batch_meta.json`

Observed stdout stopped at:

```text
[FORK_INFO pid(89)] enable fork debugging...
```

There was no `The first instruction of core 0 has commited` line and no trap
result.

### v2/v3 explicit profile smoke attempts

Commands:

```bash
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_smoke.yaml \
  --seed 241027 \
  --batch-id kmh_v2_smoke_profile_missing_r1b \
  --timeout-sec 60 \
  --runner-profile kmh-v2/difftest

python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --batch-id kmh_v3_smoke_profile_missing_r1b \
  --timeout-sec 60 \
  --runner-profile kmh-v3/difftest
```

Result:

- Both commands returned nonzero because the explicit profile manifest is not
  present in this workspace.
- Both batch entries had `status: "error"` and
  `labels: ["error", "runner_profile"]`.
- The recorded note was
  `runner manifest missing: /nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json`.
- Evidence:
  - `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_smoke_profile_missing_r1b/batch_meta.json`
  - `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_profile_missing_r1b/batch_meta.json`

This is the intended failure mode for `--runner-profile`: v2/v3 evidence must
come from the frozen profile manifest and binaries, not from an implicit host
fallback.

### Default host runner probe

Command:

```bash
env SNIPPETGEN_RUN_MAX_CYCLES=120000 SNIPPETGEN_RUN_MAX_INSTR=120000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --batch-id kmh_v3_smoke_default_r1 \
  --timeout-sec 180
```

Result:

- `status: "timeout"`
- `labels: ["built", "timeout"]`
- `notes: "timeout after 180s"`
- Batch: `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_default_r1/batch_meta.json`

Manual no-diff probes at 100 and 1000 cycles completed with
`EXCEEDING CYCLE/INSTR LIMIT` and `instrCnt = 0` for both the MMU smoke image
and an `am_hello_main_poc` image.

Follow-up command:

```bash
env SNIPPETGEN_RUN_MAX_CYCLES=5000 SNIPPETGEN_RUN_MAX_INSTR=5000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --batch-id kmh_v3_smoke_default_5k_r1 \
  --timeout-sec 180
```

Result:

- `status: "limit_exceeded"`
- `labels: ["built", "ran", "limit_exceeded"]`
- `notes: "EXCEEDING CYCLE/INSTR LIMIT"`
- `runner_path: "/nfs/home/liujunqi/XS/xs-env/XiangShan/build/verilator-compile/emu"`
- `diff_path: "/nfs/home/liujunqi/XS/xs-env/NEMU/build/riscv64-nemu-interpreter-so"`
- Batch: `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_default_5k_r1/batch_meta.json`

The 5000-cycle difftest/fork run reached the first committed instruction,
enabled difftest, and exited at `pc = 0x8000215a` with `instrCnt = 152`,
`cycleCnt = 5000`, and about 75 seconds of host time. A matching 5000-cycle
manual `--no-diff` run reached the same PC and instruction count in about
74 seconds. This narrows the earlier 120000-cycle timeout: the MMU smoke image
does start, but it is slow enough that the default large budget is not useful
for quick smoke triage in this environment.

### Existing MMU bare baseline

Command:

```bash
env SNIPPETGEN_RUN_MAX_CYCLES=120000 SNIPPETGEN_RUN_MAX_INSTR=120000 \
python3 generator/cli.py run suites/mmu_bare_identity_poc.yaml \
  --seed 241024 \
  --batch-id baseline_mmu_bare_241024_r0 \
  --timeout-sec 180
```

Result:

- `status: "timeout"`
- `labels: ["built", "timeout"]`
- `notes: "timeout after 180s"`
- Batch: `build/mmu_bare_identity_poc/runs/baseline_mmu_bare_241024_r0/batch_meta.json`

This shows the target problem is not unique to the new `kmh_layer1` rules.

### Existing non-MMU baseline

Command:

```bash
env SNIPPETGEN_RUN_MAX_CYCLES=120000 SNIPPETGEN_RUN_MAX_INSTR=120000 \
python3 generator/cli.py run suites/am_hello_main_poc.yaml \
  --seed 241024 \
  --batch-id baseline_am_hello_241024_r0 \
  --timeout-sec 180
```

Result:

- `status: "ran"`
- `finish_code: 0`
- `labels: ["built", "ran", "good_trap"]`
- Batch: `build/am_hello_main_poc/runs/baseline_am_hello_241024_r0/batch_meta.json`

This confirms the current `emu + NEMU` environment can run at least one
non-MMU snippetgen workload successfully.

### Manual no-fork MMU bare check

Command:

```bash
timeout 120 /nfs/home/liujunqi/XS/xs-env/XiangShan/build/verilator-compile/emu \
  -s 241024 \
  -C 120000 \
  -I 120000 \
  -i build/mmu_bare_identity_poc/runs/baseline_mmu_bare_241024_r0/seed_241024/test.bin \
  --diff /nfs/home/liujunqi/XS/xs-env/NEMU/build/riscv64-nemu-interpreter-so \
  --force-dump-result
```

Result:

- Host command exited with `124` from `timeout`.

This suggests `--enable-fork` is not the only cause of the MMU workload hang.

## Findings

### Fixed: allStage hit data used GPA instead of HPA

The generic MMU runner seeded and observed memory using `xs_mapping_pa_for_addr`
on the primary mapping. For allStage hit rules, the primary mapping translates
GVA to GPA, not HPA. A real two-stage hit must seed and observe memory at the
stage2-translated HPA.

Fix:

- Added `xs_effective_pa_for_addr()`.
- `xs_seed_rule_memory()` and `xs_run_observe_checks()` now resolve through
  stage2 when the rule mode is `allStage`.

### Fixed: context-switch rules did not distinguish old and new roots

Round 1 added `satp_asid_switch` and `vsatp_hgatp_context_switch`, but their
first implementation used the same page-table roots before and after the
context switch. That was too weak: a broken context switch could still read the
same value and pass.

Round 2 strengthens this by adding switched-context mappings:

- `satp_asid_switch` now maps the same VA in the initial root and in a switched
  root, with different physical targets.
- `vsatp_hgatp_context_switch` now has switched stage1 and switched stage2
  mappings, with different GPA/HPA targets.
- The generated runner now has separate switched page-table roots and a
  distinct switched seed value. The observed value must come from the switched
  root after `switch_satp_context`, `switch_vsatp_context`, or
  `switch_hgatp_context`.

Focused check:

```bash
python3 -m unittest \
  tests.test_mmu_rule_loader \
  tests.test_mmu_rule_emitter \
  tests.test_kmh_mmu_layer1_inventory \
  -v
```

Result:

- `Ran 29 tests`
- `OK`

### Open: explicit KMH v2/v3 runner cache is absent

Round 2 searched the local workspace for available runner binaries:

```bash
find /nfs/home/liujunqi/XS -type f -name emu -o -name '*nemu*interpreter*'
find /nfs/home/liujunqi -maxdepth 6 -type f -name emu
```

Result:

- Only one `emu` was found:
  `/nfs/home/liujunqi/XS/xs-env/XiangShan/build/verilator-compile/emu`.
- Several NEMU references exist under `xs-env`, but there is no separate frozen
  `/nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json` and no separate
  checked v2/v3 `emu` pair in the searched paths.

I did not create a fake `kmh-v2/difftest` or `kmh-v3/difftest` manifest pointing
at the single default host runner. That would produce profile-looking metadata
without proving the intended v2/v3 matrix.

### Open: default large-budget MMU runs are too slow for current timeout

The original 120000-cycle v3 smoke and `mmu_bare_identity_poc` runs timed out
under the default adapter path. A narrower 5000-cycle v3 smoke run did reach
the first committed instruction and exited cleanly at the configured
cycle/instruction limit with 152 committed instructions. The current issue is
therefore not "the KMH MMU smoke image never starts"; it is that the full
default budget is too slow for quick triage on this host, and the existing
`mmu_bare_identity_poc` still needs a separate narrowed probe.

Useful artifacts:

- `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_241027_r0/seed_241027/stdout.log`
- `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_default_5k_r1/seed_241027/stdout.log`
- `build/mmu_bare_identity_poc/runs/baseline_mmu_bare_241024_r0/seed_241024/stdout.log`
- `build/am_hello_main_poc/runs/baseline_am_hello_241024_r0/seed_241024/stdout.log`

Observed image difference still worth investigating before claiming a target
bug:

- `mmu_bare_identity_poc` has a separate zero-sized RW `LOAD` segment for
  aligned `.bss`.
- `am_hello_main_poc` has a single RWE `LOAD` segment.

The current evidence is not enough to claim that segment layout is the root
cause, only that it is a concrete difference between the failing MMU baseline
and the passing non-MMU baseline.

## Round 3 Update

Round 3 supersedes the earlier "runner cache is absent" blocker. Real
Kunminghu v2 and v3 difftest runners now exist outside the git repo at:

```text
/nfs/home/liujunqi/XS/artifacts/kmh-runners/
```

The cache manifest is:

```text
/nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json
```

Cached runner profiles:

- `kmh-v2/difftest`
  - XiangShan branch: `kunminghu-v2`
  - XiangShan revision: `a53602a45ac2c2d9430013bdb72942bf399bdb81`
  - Embedded commit string: `a53602a45a`, `dirty: 0`
  - Build config: `KunminghuV2Config`
  - emu sha256: `e904f3fbd83cb6f3bb7c4bfbe3c780523fa70158ab95b6945534d7c1f94b061a`
  - Coremark sanity: `instrCnt = 216`, `cycleCnt = 5000`, `pc = 0x800027c6`
- `kmh-v3/difftest`
  - XiangShan branch: `kunminghu-v3`
  - XiangShan revision: `b8ff9a271d5c6794083ded7c1954e29e670e8986`
  - Embedded commit string: `b8ff9a271d`, `dirty: 0`
  - Build config: `KunminghuV2Config`
  - Note: v3 still exposes the Kunminghu CHI config under the deprecated
    `KunminghuV2Config` class name.
  - emu sha256: `28c15f722dcc92cc73d805ebb97004c3871ed0e7621aff5f8f36a266b0924da8`
  - Coremark sanity: `instrCnt = 238`, `cycleCnt = 5000`, `pc = 0x800027c6`
- Shared NEMU revision: `43f6b0ce4aae3ee1171430bd9a0a55cbd833efc3`
- Shared NEMU sha256:
  `768a9e2be7b303e4b472f775da5564e0992fad75b7d5d3b74454e034ddf967bf`

Build-system notes:

- Bare `make emu` builds the default `TLConfig`; it is not a valid
  Kunminghu v2/v3 runner cache source.
- Both branches hardcode some Chisel collateral under `./build` via
  `FileRegisters.write(fileDir = "./build")`. For isolated build directories,
  `chisel_db.cpp`, `constantin.cpp`, `perfCCT.cpp`, `generated-src`, `plusArgs`,
  and related headers must be copied from `./build` into the selected
  `BUILD_DIR` before recursive `difftest` compilation.
- Relative `BUILD_DIR=build-kmhv*` is unsafe because recursive
  `make -C difftest` interprets it relative to `XiangShan/difftest`. Use an
  absolute `BUILD_DIR`.

### Round 3 host verification

Commands:

```bash
python3 -m unittest \
  tests.test_mmu_rule_loader \
  tests.test_mmu_rule_emitter \
  tests.test_kmh_mmu_layer1_inventory \
  tests.test_runner_profiles \
  tests.test_run_pipeline \
  -v
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_bare_identity.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_sv39_alias.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_only_stage1_load_hit.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_superpage.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_sfence_remap.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_satp_asid_switch.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_all_stage_hlv_hit.yaml
python3 -m json.tool /nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json
python3 -m unittest tests.test_runner_profiles -v
python3 -m unittest discover -s tests -v
```

Results:

- Focused unit suite: `Ran 67 tests`, `OK`.
- All listed build commands completed.
- The external runner manifest parses as valid JSON.
- Runner profile tests after adding real v2/v3 manifest entries:
  `Ran 5 tests`, `OK`.
- Full unittest discovery after adding the PA collision guard:
  `Ran 243 tests`, `OK (skipped=1)`.

### Round 3 target runs

The combined v2 smoke suite is too large for the quick 20k and 100k limits:

- `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_smoke_profile_20k_r3/batch_meta.json`
  - `EXCEEDING CYCLE/INSTR LIMIT`
  - `instrCnt = 20006`, `cycleCnt = 16928`, `pc = 0x80001834`
- `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_smoke_profile_100k_r3/batch_meta.json`
  - `EXCEEDING CYCLE/INSTR LIMIT`
  - `instrCnt = 100001`, `cycleCnt = 59406`, `pc = 0x800007ac`

For practical regression triage, Round 3 added single-rule shard suites under
`suites/kmh_mmu_layer1_case_*.yaml`.

v2 shard results:

- `kmh_mmu_layer1_case_bare_identity`
  - Batch:
    `build/kmh_mmu_layer1_case_bare_identity/runs/kmh_v2_case_bare_identity_50k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 20357`, `cycleCnt = 17956`
- `kmh_mmu_layer1_case_sv39_alias`
  - Batch:
    `build/kmh_mmu_layer1_case_sv39_alias/runs/kmh_v2_case_sv39_alias_100k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 24063`, `cycleCnt = 20176`
- `kmh_mmu_layer1_case_superpage`
  - Batch:
    `build/kmh_mmu_layer1_case_superpage/runs/kmh_v2_case_superpage_100k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 19092`, `cycleCnt = 17780`
- `kmh_mmu_layer1_case_only_stage1_load_hit`
  - Batch:
    `build/kmh_mmu_layer1_case_only_stage1_load_hit/runs/kmh_v2_case_only_stage1_load_hit_100k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 20489`, `cycleCnt = 18218`
- `kmh_mmu_layer1_case_sfence_remap`
  - Batch:
    `build/kmh_mmu_layer1_case_sfence_remap/runs/kmh_v2_case_sfence_remap_100k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 21182`, `cycleCnt = 19395`
- `kmh_mmu_layer1_case_satp_asid_switch`
  - Fixed batch:
    `build/kmh_mmu_layer1_case_satp_asid_switch/runs/kmh_v2_case_satp_asid_switch_100k_r3_fixed_pa/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 24105`, `cycleCnt = 20323`
- `kmh_mmu_layer1_case_all_stage_hlv_hit`
  - Batch:
    `build/kmh_mmu_layer1_case_all_stage_hlv_hit/runs/kmh_v2_case_all_stage_hlv_hit_150k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 26544`, `cycleCnt = 23130`

v3 shard results:

- `kmh_mmu_layer1_case_bare_identity`
  - Batch:
    `build/kmh_mmu_layer1_case_bare_identity/runs/kmh_v3_case_bare_identity_50k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 20350`, `cycleCnt = 16228`
- `kmh_mmu_layer1_case_satp_asid_switch`
  - Batch:
    `build/kmh_mmu_layer1_case_satp_asid_switch/runs/kmh_v3_case_satp_asid_switch_100k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 24105`, `cycleCnt = 18553`
- `kmh_mmu_layer1_case_all_stage_hlv_hit`
  - Batch:
    `build/kmh_mmu_layer1_case_all_stage_hlv_hit/runs/kmh_v3_case_all_stage_hlv_hit_150k_r3/batch_meta.json`
  - `HIT GOOD TRAP`, `instrCnt = 26544`, `cycleCnt = 20231`

### Fixed: rule data PAs collided with generated runtime state

The first v2 `satp_asid_switch` shard run failed with a bad trap:

```text
isa pma check failed, vaddr=0x11223344556678a8, paddr=0x11223344556678a8
HIT BAD TRAP
```

This was a test/rule allocation bug, not a hardware MMU bug. The generated ELF
placed page-table/runtime data across the same low physical range used by the
rule data pages. In the failing image, symbols included:

```text
_bss_start        0x80004000
xsam_heap         0x8000c090
stage2_switch.0   0x80010000
stage1_switch.1   0x80038000
stage2.2          0x80060000
stage1.3          0x80088000
_bss_end          0x800b0098
_end/_heap_start  0x800f1000
```

The rule had used `pa: 0x80038000`, which overlapped `stage1_switch.1`. The
test seed `0x1122334455667788` corrupted the page-table root, producing the
invalid physical address seen by NEMU.

Fix:

- Moved low `0x8002xxxx`/`0x8003xxxx` rule data physical addresses to the
  `0x810xxxxx` range in `snippets/mmu_rules/kmh_layer1/*.yaml`.
- Kept the pilot rules aligned with the same safe address range.
- Added single-rule shard suites so address/allocation failures are easier to
  isolate than in the combined smoke suite.

Post-fix evidence:

- v2 `satp_asid_switch` fixed batch:
  `build/kmh_mmu_layer1_case_satp_asid_switch/runs/kmh_v2_case_satp_asid_switch_100k_r3_fixed_pa/batch_meta.json`
- v3 `satp_asid_switch` batch:
  `build/kmh_mmu_layer1_case_satp_asid_switch/runs/kmh_v3_case_satp_asid_switch_100k_r3/batch_meta.json`

Both batches report `HIT GOOD TRAP`.

### Round 4 smoke and grouped regression matrix

Round 4 reduced the v2/v3 smoke suites to a true representative smoke:

- `bare_identity`
- `satp_asid_switch`
- `all_stage_hlv_hit`

The wider first-layer coverage now lives in grouped regression suites and
single-rule diagnostic shards, so a quick smoke no longer exceeds the practical
profile-backed run budget.

Smoke evidence:

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_v2_smoke` | `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_smoke_profile_minimal_r4/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70366`, `cycleCnt = 46618` | selected 3 rules `ran`, 21 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_v3_smoke` | `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_profile_minimal_r4/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70359`, `cycleCnt = 40739` | selected 3 rules `ran`, 21 rules `defined_only` |

Grouped matrix evidence:

| Group | Profile | Batch | Result | Coverage ledger state |
|-------|---------|-------|--------|-----------------------|
| `host_perm` | `kmh-v2/difftest` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 166582`, `cycleCnt = 98049` | selected 8 rules `ran`, 16 rules `defined_only` |
| `host_perm` | `kmh-v3/difftest` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 166582`, `cycleCnt = 84048` | selected 8 rules `ran`, 16 rules `defined_only` |
| `attr_ctrl` | `kmh-v2/difftest` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 142676`, `cycleCnt = 86872` | selected 6 rules `ran`, 18 rules `defined_only` |
| `attr_ctrl` | `kmh-v3/difftest` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 142676`, `cycleCnt = 74637` | selected 6 rules `ran`, 18 rules `defined_only` |
| `hyp` | `kmh-v2/difftest` | `build/kmh_mmu_layer1_hyp/runs/kmh_v2_hyp_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 152871`, `cycleCnt = 98008` | selected 6 rules `ran`, 18 rules `defined_only` |
| `hyp` | `kmh-v3/difftest` | `build/kmh_mmu_layer1_hyp/runs/kmh_v3_hyp_profile_r4_fixed/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 152871`, `cycleCnt = 81455` | selected 6 rules `ran`, 18 rules `defined_only` |
| `faults` | `kmh-v2/difftest` | `build/kmh_mmu_layer1_faults/runs/kmh_v2_faults_profile_r4/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 154892`, `cycleCnt = 97944` | selected 7 rules `ran`, 17 rules `defined_only` |
| `faults` | `kmh-v3/difftest` | `build/kmh_mmu_layer1_faults/runs/kmh_v3_faults_profile_r4/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 154924`, `cycleCnt = 83782` | selected 7 rules `ran`, 17 rules `defined_only` |

The grouped matrix was run with explicit runner profiles and with
`SNIPPETGEN_RUN_MAX_CYCLES=300000` and `SNIPPETGEN_RUN_MAX_INSTR=300000`.

### Round 4 fixes from target verification

The v2/v3 runs found three test construction issues. No v2/v3 DUT MMU bug was
isolated by the first-layer matrix after these fixes.

1. `fault_repair_retry` checked memory too early.

   The first v2 `host_perm` grouped run bad-trapped. Isolation showed
   `fault_repair_retry` failed as a single rule:
   `build/kmh_mmu_layer1_case_fault_repair_retry/runs/kmh_v2_case_fault_repair_retry_120k_r4/batch_meta.json`.

   Root cause: `xs_rule_fault_checks()` reused the normal hit observe path,
   so `memory_value_match` was evaluated immediately after the expected first
   page fault, before the handler repaired the page table and before the
   re-execute load produced the expected value.

   Fix: fault checks now validate only fault/attribute observations during the
   fault phase and defer `memory_value_match` for
   `repair_then_reexecute` rules until the post-reexecute hit check.

   Fixed evidence:

   - `build/kmh_mmu_layer1_case_fault_repair_retry/runs/kmh_v2_case_fault_repair_retry_120k_r4_fixed/batch_meta.json`
     - `HIT GOOD TRAP`, `instrCnt = 22134`, `cycleCnt = 21279`
   - Full `host_perm` v2/v3 grouped runs both pass, as listed above.

2. `host_pbmt_nc` did not satisfy PBMT enable preconditions and mixed in cache
   writeback behavior.

   The first v2 `attr_ctrl` grouped run bad-trapped. Isolation showed
   `host_pbmt_nc` needed `menvcfg.PBMTE`/`henvcfg.PBMTE` enabled before the
   PBMT PTE bits were architecture-visible. After enabling PBMTE, v2 and v3
   both exposed a difftest mismatch at the PBMT NC load: the runner seeded the
   target PA with a cached physical store, then the NC load bypassed dirty
   cache state. NEMU has no cache and observed the seed; DUT observed memory
   value `0`.

   This was outside the first-layer PBMT translation/attribute scope, so the
   rule now checks `attribute_policy_match` only, and the runner skips cached
   seed stores for PBMT NC rules.

   Fixed evidence:

   - `build/kmh_mmu_layer1_case_host_pbmt_nc/runs/kmh_v2_case_host_pbmt_nc_120k_r4_pbmte_noseed/batch_meta.json`
     - `HIT GOOD TRAP`, `instrCnt = 20384`, `cycleCnt = 18069`
   - `build/kmh_mmu_layer1_case_host_pbmt_nc/runs/kmh_v3_case_host_pbmt_nc_120k_r4_pbmte_noseed/batch_meta.json`
     - `HIT GOOD TRAP`, `instrCnt = 20384`, `cycleCnt = 16464`
   - Full `attr_ctrl` v2/v3 grouped runs both pass, as listed above.

3. `hsv_store_hit` treated guest stores as loads during observation.

   The first v2 `hyp` grouped run bad-trapped. Isolation showed
   `only_stage2_hlv_hit`, `hlvx_exec_hit`, `two_stage_fault`, and
   `vsatp_hgatp_context_switch` all passed, while `hsv_store_hit` failed as a
   single rule:
   `build/kmh_mmu_layer1_case_hsv_store_hit/runs/kmh_v2_case_hsv_store_hit_150k_r4/batch_meta.json`.

   Root cause: the runner issued `guest_store` correctly, but
   `memory_value_match` only treated `trigger_op: store` as a store observe
   path. `guest_store`/`requestor: hsv` fell through to the load comparison and
   compared an unset `primary_value` against the seed.

   Fix: `guest_store`, `requestor: store`, and `requestor: hsv` now share the
   translated-HPA store observation path.

   Fixed evidence:

   - `build/kmh_mmu_layer1_case_hsv_store_hit/runs/kmh_v2_case_hsv_store_hit_150k_r4_fixed/batch_meta.json`
     - `HIT GOOD TRAP`, `instrCnt = 20978`, `cycleCnt = 19357`
   - `build/kmh_mmu_layer1_case_hsv_store_hit/runs/kmh_v3_case_hsv_store_hit_150k_r4_fixed/batch_meta.json`
     - `HIT GOOD TRAP`, `instrCnt = 20978`, `cycleCnt = 17002`
   - Full `hyp` v2/v3 grouped runs both pass, as listed above.

### Round 4 host verification

Commands:

```bash
python3 -m unittest tests.test_kmh_mmu_layer1_inventory -v
python3 -m unittest discover -s tests -v
```

Results:

- Focused inventory test after runner fixes: `Ran 9 tests`, `OK`.
- Full unittest discovery: `Ran 246 tests`, `OK (skipped=1)`.

### Round 5 review fixes

The Round 5 code review found three implementation issues outside the target
MMU behavior itself.

1. The runner profile default manifest path was hard-coded to one machine-local
   absolute path. It is now derived from the `snippetgen` checkout:
   `../artifacts/kmh-runners/manifest.json`, with
   `SNIPPETGEN_KMH_RUNNER_MANIFEST` still available as an override.

2. Raw PTE runtime observation used `mapping->pa` even when `raw_pte.value`
   encoded a different leaf PPN. The runner now decodes the raw PTE PPN field
   for leaf raw-PTE mappings before memory seeding, PMP placement, and
   `memory_value_match` checks.

3. Runner profile alias collision validation depended on JSON order. It now
   finds the unique non-alias canonical profile for a shared `emu` path and
   accepts aliases before or after their canonical entry.

Additional review-fix validation:

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_v2_smoke` | `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_smoke_profile_r5_manifest_default/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70604`, `cycleCnt = 47450` | selected 3 rules `ran`, 21 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_v3_smoke` | `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_smoke_profile_r5_manifest_default/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70604`, `cycleCnt = 41287` | selected 3 rules `ran`, 21 rules `defined_only` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm_profile_r5_raw_pte_decode/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 167141`, `cycleCnt = 99769` | selected 8 rules `ran`, 16 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm_profile_r5_raw_pte_decode/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 167141`, `cycleCnt = 85216` | selected 8 rules `ran`, 16 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_case_raw_pte_load_hit` | `build/kmh_mmu_layer1_case_raw_pte_load_hit/runs/kmh_v3_case_raw_pte_load_hit_r5/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 20521`, `cycleCnt = 16540` | selected 1 rule `ran`, 23 rules `defined_only` |

Round 5 host validation:

```bash
python3 -m unittest \
  tests.test_runner_profiles \
  tests.test_kmh_mmu_layer1_inventory \
  tests.test_mmu_rule_loader \
  tests.test_mmu_rule_emitter \
  -v
python3 -m unittest discover -s tests -v
git diff --check
```

Results:

- Focused review-fix unit suite: `Ran 41 tests`, `OK`.
- Full unittest discovery: `Ran 249 tests`, `OK (skipped=1)`.
- `git diff --check`: no whitespace errors.

### Round 6 review fixes

The Round 6 code review found two coverage-strength issues in the generated
rule runner.

1. `attribute_policy_match` only checked that some attribute policy metadata
   was present. It now derives the expected policy from the rule coverage tags
   and compares the generated descriptor exactly:
   - `attr.pbmt_nc` requires `XS_GENERATED_MMU_ATTR_PBMT_NC`
   - `attr.pma` requires `XS_GENERATED_MMU_ATTR_PMA`
   - `attr.mmio` requires `XS_GENERATED_MMU_ATTR_MMIO`
   - `attr.pmp_deny` requires `pmp_deny != 0`

   This covers both the hit observe path and the fault observe path, so dropping
   one side of a PMA/MMIO descriptor no longer still satisfies
   `attribute_policy_match`.

2. The explicit `hfence_gvma` action used `rule->trigger_addr` directly. For
   `allStage` rules that address is a GVA, but `hfence.gvma` is
   guest-physical-address scoped. The runner now resolves the current
   stage-1 mapping and passes the GPA to `xsam_mmu_hfence_gvma()`.

Target validation used the same grouped-run limit budget as Round 4:
`SNIPPETGEN_RUN_MAX_CYCLES=300000` and
`SNIPPETGEN_RUN_MAX_INSTR=300000`.

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_profile_r6_300k/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 144763`, `cycleCnt = 91890` | selected 6 rules `ran`, 18 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_profile_r6_300k/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 144763`, `cycleCnt = 78171` | selected 6 rules `ran`, 18 rules `defined_only` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v2_hyp_profile_r6_300k/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 153263`, `cycleCnt = 99408` | selected 6 rules `ran`, 18 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v3_hyp_profile_r6_300k/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 153263`, `cycleCnt = 82182` | selected 6 rules `ran`, 18 rules `defined_only` |

Earlier Round 6 reruns with the default 120000 instruction/cycle limit produced
`limit_exceeded` for `attr_ctrl`; that was a run-budget issue, not a semantic
failure. Round 4 had already established these grouped suites need a 300000
limit budget.

Round 6 host validation:

```bash
python3 -m unittest tests.test_kmh_mmu_layer1_inventory tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v
python3 -m unittest discover -s tests -v
git diff --check
```

Results:

- Focused review-fix unit suite: `Ran 36 tests`, `OK`.
- Full unittest discovery: `Ran 251 tests`, `OK (skipped=1)`.
- `git diff --check`: no whitespace errors.

### Round 7 review fixes

Round 7 tightened `attribute_policy_match` again so the observation is no
longer self-referential.

The runner now requires an architecture-visible runtime witness for each
attribute class it claims:

- `attr.pmp_deny`: the translated access must raise the rule's expected access
  fault and matching `tval`.
- `attr.pbmt_nc`: the rule uses a raw PTE with PBMT NC bits while PBMTE is
  intentionally disabled. A target that recognizes PBMT reserved semantics must
  raise the expected page fault; a target that ignores PBMT bits would not
  satisfy the rule.
- `attr.pma` / `attr.mmio`: the rule maps a virtual address to the platform
  CLINT mtime MMIO register. The runner compares a translated load through the
  page table against direct platform MMIO reads around it, so ordinary cached
  RAM behavior is no longer enough to satisfy `attribute_policy_match`.

This supersedes the Round 4 PBMT witness. `host_pbmt_nc` no longer enables
PBMTE and merely checks descriptor metadata; it intentionally keeps PBMTE
disabled and expects the reserved-PBMT page fault as the runtime signal.

Target validation again used
`SNIPPETGEN_RUN_MAX_CYCLES=300000` and
`SNIPPETGEN_RUN_MAX_INSTR=300000`.

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_profile_r7_runtime_attr/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145387`, `cycleCnt = 93653` | selected 6 rules `ran`, 18 rules `defined_only` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_profile_r7_runtime_attr/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145384`, `cycleCnt = 79038` | selected 6 rules `ran`, 18 rules `defined_only` |

Round 7 host validation:

```bash
python3 -m unittest tests.test_kmh_mmu_layer1_inventory tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v
python3 -m unittest discover -s tests -v
git diff --check
```

Results:

- Focused review-fix unit suite: `Ran 37 tests`, `OK`.
- Full unittest discovery: `Ran 252 tests`, `OK (skipped=1)`.
- `git diff --check`: no whitespace errors.

### Round 8 review fixes

Round 8 fixed three consistency issues in the new first-layer rule surface.

1. `attr.nc` is now normalized in `xs_rule_expected_attr_flags()` to the
   PBMT-NC descriptor bit. A rule that covers only `attr.nc` and uses
   `attribute_policy_match` is accepted and runnable instead of comparing
   against an empty expected attribute descriptor.

2. PMA and MMIO tags are now independent:
   - `setup.attributes.pma: io` generates `XS_GENERATED_MMU_ATTR_PMA`.
   - `setup.attributes.mmio: true` generates `XS_GENERATED_MMU_ATTR_MMIO`.
   - The loader rejects `attr.mmio` unless `mmio: true` is explicit.
   - The runtime CLINT mtime witness is required for any rule with the MMIO
     descriptor bit, not only rules that also carry the PMA bit.

3. `switch_asid_context` and `switch_vmid_context` now preserve the current
   page-table root while changing only the ASID/VMID tag. Root-changing
   behavior remains with `switch_satp_context`, `switch_vsatp_context`, and
   `switch_hgatp_context`.

Target validation used
`SNIPPETGEN_RUN_MAX_CYCLES=300000` and
`SNIPPETGEN_RUN_MAX_INSTR=300000`.

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_profile_r8_attr_independent/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145623`, `cycleCnt = 93826` | selected 6 rules `ran`, 18 rules `defined_only`; `attr.nc`, `attr.pma`, and `attr.mmio` all `ran` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_profile_r8_attr_independent/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145623`, `cycleCnt = 79365` | selected 6 rules `ran`, 18 rules `defined_only`; `attr.nc`, `attr.pma`, and `attr.mmio` all `ran` |

Round 8 host validation:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter tests.test_kmh_mmu_layer1_inventory -v
python3 -m unittest discover -s tests -v
git diff --check
```

Results:

- Focused review-fix unit suite: `Ran 41 tests`, `OK`.
- Full unittest discovery: `Ran 256 tests`, `OK (skipped=1)`.
- `git diff --check`: no whitespace errors.

### Round 9 review fixes

Round 9 fixed two coverage and schema consistency issues.

1. PBMT-NC encoded directly in `raw_pte.value` is now recognized by both the
   rule loader and emitter. The PBMT field is decoded from PTE bits 62:61, so
   numeric raw PTE rules can carry `attr.nc` / `attr.pbmt_nc` coverage without
   also requiring the structured `raw_pte.pbmt: nc` spelling.

2. `only_stage1_load_hit` no longer claims `page.identity`. Its mapping is a
   real stage-1 translation from `0x900010000` to `0x81031000`, so the
   identity coverage ledger now only reports the real identity rules.

Build validation:

```bash
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
```

Result:

- Build completed:
  `build/kmh_mmu_layer1_full/build_manifest.json`
- `build/kmh_mmu_layer1_full/mmu_coverage_ledger.json` has no gaps.
- `page.identity` is now covered by `bare_identity` and
  `hybrid_load_identity`, not by `only_stage1_load_hit`.

Round 9 host validation:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter tests.test_kmh_mmu_layer1_inventory -v
python3 -m unittest discover -s tests -v
git diff --check
```

Result:

- Focused review-fix unit suite: `Ran 44 tests`, `OK`.
- Full unittest discovery: `Ran 259 tests`, `OK (skipped=1)`.
- `git diff --check`: no whitespace errors.

## 2026-05-12 RLCR baseline and first-layer gap pass

This pass used the cached runner manifest at
`/nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json`.

Runner revisions:

- `kmh-v2/difftest`: XiangShan `f3cc750109cc2a0ff6c12a920221f1a5a324bc75`,
  config `KunminghuV2Config`.
- `kmh-v3/difftest`: XiangShan `689ee6be18a7483206754c53e2d7a327ed53eaa6`,
  config `CHIConfig`.
- NEMU reference: `43f6b0ce4aae3ee1171430bd9a0a55cbd833efc3`.

Baseline smoke and group runs used seed `241027`. Smoke used
`SNIPPETGEN_RUN_MAX_CYCLES=300000` and `SNIPPETGEN_RUN_MAX_INSTR=300000`.
Group runs used `SNIPPETGEN_RUN_MAX_CYCLES=1200000` and
`SNIPPETGEN_RUN_MAX_INSTR=1200000`.

Initial baseline results before the gap-rule expansion:

| Profile | Suite | Batch | Result |
|---------|-------|-------|--------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_v2_smoke` | `build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_mmu_smoke_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70601`, `cycleCnt = 40961` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_v3_smoke` | `build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_mmu_smoke_20260512_rlcr_r0_retry1800/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 70594`, `cycleCnt = 41262` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 167140`, `cycleCnt = 83461` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145623`, `cycleCnt = 79981` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v2_hyp_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 153256`, `cycleCnt = 82067` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_faults` | `build/kmh_mmu_layer1_faults/runs/kmh_v2_faults_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 155644`, `cycleCnt = 84060` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 167133`, `cycleCnt = 85200` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_attr_ctrl` | `build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 145622`, `cycleCnt = 79204` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v3_hyp_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 153253`, `cycleCnt = 81195` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_faults` | `build/kmh_mmu_layer1_faults/runs/kmh_v3_faults_20260512_rlcr_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 155642`, `cycleCnt = 84526` |

The first v3 smoke attempt
`build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_mmu_smoke_20260512_rlcr_r0/batch_meta.json`
timed out at `--timeout-sec 600` before a semantic trap. The retry above used
`--timeout-sec 1800` and completed normally.

Smoke coverage summary example:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_v2_smoke/runs/kmh_v2_mmu_smoke_20260512_rlcr_r0/batch_meta.json \
  build/kmh_mmu_layer1_v3_smoke/runs/kmh_v3_mmu_smoke_20260512_rlcr_r0_retry1800/batch_meta.json
```

First-layer gap rules added in this pass:

- Permission negatives: `load_read_perm_fault`,
  `store_write_perm_fault`, `host_mxr_exec_load_fault`,
  `host_sum_user_load_fault`, `load_accessed_bit_fault`,
  `store_dirty_bit_fault`, and `hlvx_exec_perm_fault`.
- Two-stage fault classification: `all_stage_stage1_page_fault`,
  `only_stage2_hlv_guest_fault`, and `only_stage2_hsv_guest_fault`.
- Superpage combinations: `superpage_load_hit`,
  `only_stage2_superpage_hlv_hit`, and
  `all_stage_superpage_stage2_4k_hit`.
- Context/fence semantics: `only_stage2_vmid_switch`.

Build validation:

```bash
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
```

The full build completed at `build/kmh_mmu_layer1_full/build_manifest.json`,
and `mmu-coverage-summary build/kmh_mmu_layer1_full/mmu_coverage_ledger.json`
reported 38 selected rules and 43 selected tags as `generated_not_run` with no
taxonomy gaps.

Single-case build validation also passed for every new `kmh_mmu_layer1_case_*`
suite added with the gap rules.

Current post-gap coverage summary example:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm_gap_rules_20260512_r0/batch_meta.json \
  build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v2_attr_ctrl_20260512_rlcr_r0/batch_meta.json \
  build/kmh_mmu_layer1_hyp/runs/kmh_v2_hyp_current_20260512_r1/batch_meta.json \
  build/kmh_mmu_layer1_faults/runs/kmh_v2_faults_current_20260512_r1/batch_meta.json \
  build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm_gap_rules_20260512_r0/batch_meta.json \
  build/kmh_mmu_layer1_attr_ctrl/runs/kmh_v3_attr_ctrl_20260512_rlcr_r0/batch_meta.json \
  build/kmh_mmu_layer1_hyp/runs/kmh_v3_hyp_current_20260512_r1/batch_meta.json \
  build/kmh_mmu_layer1_faults/runs/kmh_v3_faults_current_20260512_r1/batch_meta.json \
  build/kmh_mmu_layer1_case_superpage_load_hit/runs/kmh_v2_case_superpage_load_hit_20260512_r1/batch_meta.json \
  build/kmh_mmu_layer1_case_superpage_load_hit/runs/kmh_v3_case_superpage_load_hit_20260512_r1/batch_meta.json
```

This summary reported 10 successful entries. The current `hyp` run ledgers
selected all 13 rules in `suites/kmh_mmu_layer1_hyp.yaml`, including
`only_stage2_vmid_switch`. The current `faults` run ledgers selected all 17
rules in `suites/kmh_mmu_layer1_faults.yaml`. The aggregate coverage view kept
v2 and v3 profile states separate and had no taxonomy gaps.

The older `kmh_v2_hyp_gap_rules_20260512_r0` and
`kmh_v3_hyp_gap_rules_20260512_r0` batches selected 12 rules and are retained
only as historical evidence. The older `kmh_v2_faults_20260512_rlcr_r0` and
`kmh_v3_faults_20260512_rlcr_r0` batches selected 7 rules and are not current
post-gap `faults` evidence.

Current post-gap target validation:

| Profile | Suite | Batch | Result | Coverage ledger state |
|---------|-------|-------|--------|-----------------------|
| `kmh-v2/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm_gap_rules_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 292242`, `cycleCnt = 135625` | selected 14 rules `ran`, 23 rules `defined_only`; permission-negative tags `pte.r`, `pte.w`, `pte.x`, `pte.u`, `pte.a`, and `pte.d` all `ran` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_host_perm` | `build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm_gap_rules_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 292242`, `cycleCnt = 140394` | selected 14 rules `ran`, 23 rules `defined_only`; permission-negative tags `pte.r`, `pte.w`, `pte.x`, `pte.u`, `pte.a`, and `pte.d` all `ran` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v2_hyp_current_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 312862`, `cycleCnt = 152739` | selected 13 rules `ran`, 25 rules `defined_only`; includes `only_stage2_vmid_switch`; `ctrl.vmid`, `ctrl.hgatp`, `ctrl.vsatp`, `exception.page_fault`, `exception.guest_page_fault`, `requestor.hlv`, `requestor.hlvx`, `requestor.hsv`, `page.superpage`, `mode.onlyStage2`, and `mode.allStage` all `ran` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_hyp` | `build/kmh_mmu_layer1_hyp/runs/kmh_v3_hyp_current_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 312861`, `cycleCnt = 152974` | selected 13 rules `ran`, 25 rules `defined_only`; includes `only_stage2_vmid_switch`; `ctrl.vmid`, `ctrl.hgatp`, `ctrl.vsatp`, `exception.page_fault`, `exception.guest_page_fault`, `requestor.hlv`, `requestor.hlvx`, `requestor.hsv`, `page.superpage`, `mode.onlyStage2`, and `mode.allStage` all `ran` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_faults` | `build/kmh_mmu_layer1_faults/runs/kmh_v2_faults_current_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 370861`, `cycleCnt = 176776` | selected 17 rules `ran`, 21 rules `defined_only`; `exception.page_fault`, `exception.access_fault`, `exception.guest_page_fault`, `guest.two_stage`, `guest.vs_only`, `priv.mxr`, `priv.sum`, `pte.a`, `pte.d`, `pte.r`, `pte.w`, and `pte.x` all `ran` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_faults` | `build/kmh_mmu_layer1_faults/runs/kmh_v3_faults_current_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 370859`, `cycleCnt = 181183` | selected 17 rules `ran`, 21 rules `defined_only`; `exception.page_fault`, `exception.access_fault`, `exception.guest_page_fault`, `guest.two_stage`, `guest.vs_only`, `priv.mxr`, `priv.sum`, `pte.a`, `pte.d`, `pte.r`, `pte.w`, and `pte.x` all `ran` |
| `kmh-v2/difftest` | `kmh_mmu_layer1_case_superpage_load_hit` | `build/kmh_mmu_layer1_case_superpage_load_hit/runs/kmh_v2_case_superpage_load_hit_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 19054`, `cycleCnt = 16334` | selected `superpage_load_hit` as `ran`; `requestor.load`, `mode.host_single_stage`, and `page.superpage` all `ran` |
| `kmh-v3/difftest` | `kmh_mmu_layer1_case_superpage_load_hit` | `build/kmh_mmu_layer1_case_superpage_load_hit/runs/kmh_v3_case_superpage_load_hit_20260512_r1/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 19053`, `cycleCnt = 16141` | selected `superpage_load_hit` as `ran`; `requestor.load`, `mode.host_single_stage`, and `page.superpage` all `ran` |

The v3 `hyp` group timeout from `kmh_v3_hyp_gap_rules_20260512_r0` did not
reproduce with the current 13-rule suite in
`kmh_v3_hyp_current_20260512_r1`, so no split-suite workaround is required for
the current evidence set. Earlier single-case v3 runs also reached
`HIT GOOD TRAP`:

| Suite | Batch | Result |
|-------|-------|--------|
| `kmh_mmu_layer1_case_hlvx_exec_perm_fault` | `build/kmh_mmu_layer1_case_hlvx_exec_perm_fault/runs/kmh_v3_case_hlvx_exec_perm_fault_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 22148`, `cycleCnt = 18908` |
| `kmh_mmu_layer1_case_all_stage_stage1_page_fault` | `build/kmh_mmu_layer1_case_all_stage_stage1_page_fault/runs/kmh_v3_case_all_stage_stage1_page_fault_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 26616`, `cycleCnt = 20851` |
| `kmh_mmu_layer1_case_only_stage2_hlv_guest_fault` | `build/kmh_mmu_layer1_case_only_stage2_hlv_guest_fault/runs/kmh_v3_case_only_stage2_hlv_guest_fault_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 21355`, `cycleCnt = 18004` |
| `kmh_mmu_layer1_case_only_stage2_hsv_guest_fault` | `build/kmh_mmu_layer1_case_only_stage2_hsv_guest_fault/runs/kmh_v3_case_only_stage2_hsv_guest_fault_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 21257`, `cycleCnt = 17900` |
| `kmh_mmu_layer1_case_only_stage2_superpage_hlv_hit` | `build/kmh_mmu_layer1_case_only_stage2_superpage_hlv_hit/runs/kmh_v3_case_only_stage2_superpage_hlv_hit_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 19683`, `cycleCnt = 16828` |
| `kmh_mmu_layer1_case_all_stage_superpage_stage2_4k_hit` | `build/kmh_mmu_layer1_case_all_stage_superpage_stage2_4k_hit/runs/kmh_v3_case_all_stage_superpage_stage2_4k_hit_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 25190`, `cycleCnt = 19962` |
| `kmh_mmu_layer1_case_only_stage2_vmid_switch` | `build/kmh_mmu_layer1_case_only_stage2_vmid_switch/runs/kmh_v3_case_only_stage2_vmid_switch_20260512_r0/batch_meta.json` | `HIT GOOD TRAP`, `instrCnt = 25559`, `cycleCnt = 20140` |

The same VMID/HGATP switch single-case also passed on v2:
`build/kmh_mmu_layer1_case_only_stage2_vmid_switch/runs/kmh_v2_case_only_stage2_vmid_switch_20260512_r0/batch_meta.json`
with `HIT GOOD TRAP`, `instrCnt = 25566`, and `cycleCnt = 20717`.

Round validation:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter tests.test_kmh_mmu_layer1_inventory -v
python3 -m unittest tests.test_mmu_coverage_summary tests.test_runner_profiles -v
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
```

Results:

- Focused MMU inventory/schema/emitter suite: `Ran 41 tests`, `OK`.
- Coverage summary and runner profile suite: `Ran 11 tests`, `OK`.
- Full KMH layer-1 build: completed.
