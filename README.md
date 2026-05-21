# SnippetGen Demo

An **ELF-first** baremetal snippet generator tailored for **XiangShan** workload construction and verification. It automates the full evaluation lifecycle:
**Suite YAML** => **Harness Gen** => **Build Artifacts (ELF/Bin)** => **XiangShan Run** => **Metadata**

## Core Model

SnippetGen is built around a small set of objects:

- **suite**: the top-level YAML workload composition under `suites/`. It selects snippets, MMU rules, seeds, target settings, and build/run metadata.
- **snippet**: a reusable workload building block, usually declared by metadata under `snippets/manifests/` and implemented under `snippets/`.
- **generated harness**: the deterministic C entry point emitted by SnippetGen. It wires selected snippets or MMU rules into one baremetal program.
- **target adapter**: target-specific run logic under `targets/`. The XiangShan adapter launches `emu`, captures logs, classifies traps, and writes run metadata.
- **MMU rule**: a structured YAML rule under `snippets/mmu_rules/` that describes requestor, translation mode, setup, trigger, expected result, observations, and coverage tags.
- **runner profile**: a reusable prebuilt XiangShan/NEMU runner pair, so Kunminghu v2/v3 binaries can be built once and reused across runs.

## Prerequisites

Build-only workflows need:

- Python 3
- Python dependencies from `requirements.txt`
- a RISC-V toolchain in `PATH`

XiangShan run workflows additionally need:

- `NOOP_HOME/build/verilator-compile/emu` is available
- `NEMU_HOME/build/riscv64-nemu-interpreter-so` is available
- `SNIPPETGEN_XS_ENV_SH` points to your local `xs-env/env.sh` and `source "$SNIPPETGEN_XS_ENV_SH"` has been executed

LightSSS wave dumps on abort or bad trap are optional. If you need them, the external XiangShan tree must also be prepared correctly:

- the `emu` must be trace-enabled, for example with `EMU_TRACE=fst`
- the local `emu.cpp` must preserve the LightSSS abort/bad-trap wakeup and `wave_path` handling

This repository does not vendor the external XiangShan tree. That setup remains a local integration step.

## Quick Start

### 1. Build one suite

```bash
python3 generator/cli.py build suites/scalar_load_legality_poc.yaml
```

Artifacts are written to:

- `build/scalar_load_legality_poc/test.elf`
- `build/scalar_load_legality_poc/test.bin`
- `build/scalar_load_legality_poc/disasm`
- `build/scalar_load_legality_poc/build_manifest.json`

### 2. Inspect and build the MMU pilot suite

The MMU flow uses a small rule database under `snippets/mmu_rules/pilot/` and emits generated C/header artifacts for the generic MMU runner.

```bash
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
```

Additional MMU artifacts are written beside the normal build outputs:

- `build/mmu_pilot_rules_poc/generated_mmu_rule.h`
- `build/mmu_pilot_rules_poc/generated_mmu_rule.c`
- `build/mmu_pilot_rules_poc/mmu_coverage_ledger.json`

### 3. Run one suite on XiangShan `emu`

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_path_poc.yaml --seed 4660
```

Run artifacts are written to:

- `build/<suite>/runs/<batch_id>/batch_meta.json`
- `build/<suite>/runs/<batch_id>/seed_<N>/test.elf`
- `build/<suite>/runs/<batch_id>/seed_<N>/test.bin`
- `build/<suite>/runs/<batch_id>/seed_<N>/disasm`
- `build/<suite>/runs/<batch_id>/seed_<N>/stdout.log`
- `build/<suite>/runs/<batch_id>/seed_<N>/stderr.log`
- `build/<suite>/runs/<batch_id>/seed_<N>/run_meta.json`

Each run entry in `run_meta.json` and `batch_meta.json` includes `finish_code`:

- `0`: XiangShan reported `HIT GOOD TRAP`
- `1`: XiangShan reported `HIT BAD TRAP`
- `N > 1`: XiangShan reported `Unknown trap code: N`
- `null`: the runner did not recover a guest semantic trap code

Run status classification uses these first-class buckets where applicable:
`ran` with `good_trap`, `bad_trap`, `timeout`, `difftest_mismatch`,
`critical_error`, `abort` with `rtl_assert`, `build_fail`, and
`run_infra_fail`.

If you need a stable, reusable path for a repro case, pass `--batch-id`:

```bash
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Equivalent `make` entry points:

```bash
make repro-vsetvl
make repro-split-store
```

### 4. Run Kunminghu MMU layer-1 suites

Kunminghu v2 and v3 runs should use cached runner profiles. The profile names
are resolved from `../artifacts/kmh-runners/manifest.json`, so these commands
do not depend on the currently checked-out XiangShan branch.

```bash
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_smoke.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_mmu_smoke

python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --timeout-sec 2400 \
  --runner-profile kmh-v3/difftest \
  --batch-id kmh_v3_mmu_smoke
```

Group baselines use the same pattern with
`suites/kmh_mmu_layer1_host_perm.yaml`,
`suites/kmh_mmu_layer1_attr_ctrl.yaml`, `suites/kmh_mmu_layer1_hyp.yaml`, and
`suites/kmh_mmu_layer1_faults.yaml`. Use a larger instruction/cycle budget for
group runs:

```bash
SNIPPETGEN_RUN_MAX_CYCLES=1200000 \
SNIPPETGEN_RUN_MAX_INSTR=1200000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_host_perm.yaml \
  --seed 241027 \
  --timeout-sec 2400 \
  --runner-profile kmh-v3/difftest \
  --batch-id kmh_v3_host_perm
```

After runs complete, summarize profile-separated MMU coverage:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_host_perm/runs/kmh_v2_host_perm/batch_meta.json \
  build/kmh_mmu_layer1_host_perm/runs/kmh_v3_host_perm/batch_meta.json
```

The v2 vector MMU smoke suite is intentionally separate from the v2/v3 scalar
baseline. It emits real unit-stride vector load instructions with local `.word`
encodings and keeps the global toolchain ISA at `rv64gc`. The smoke suite is
the pass-only short path: Bare load hit, Sv39 host load hit, and one vector
load page-fault recovery case.

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_smoke.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_smoke_<date>
```

Do not run this suite as v3 evidence. The v3 smoke/full MMU suites stay
vector-free until a separate v3 vector plan exists.

The no-fence vector load/store replay assertion shape is kept in a separate
repro suite. It is expected to fail on the current v2 runner and should not be
used as pass-only regression evidence:

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_replay_repro.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_replay_repro_<date>
```

The v2-only vector MMU layer is split into focused suites. Keep the
`SNIPPETGEN_RUN_MAX_*` budget on target runs; the default target budget is too
small for some fault/form cases and can misclassify a valid run as
`limit_exceeded`.

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_widths.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_widths_<date>

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_faults.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_faults_<date>

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_forms.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_forms_<date>

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_attr.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_attr_<date>

SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_hyp.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_hyp_<date>
```

`vector_widths` covers `e8/e16/e32/e64` unit-stride load/store hit under Sv39
host translation. `vector_faults` covers cross-page second-page faults and
masked load/store fault suppression or triggering. `vector_forms` covers
strided, indexed, segment, fault-only-first, and `vstart` cases. `vector_attr`
covers PMP/PMA/PBMT/NC/MMIO attribute scenarios. `vector_hyp` covers ordinary
vector load/store cases under representative H-extension translation modes.
Current target evidence should be read per sub-suite: PMP load/store, PBMT,
and the translated MMIO access-fault attribute cases pass in both isolated and
aggregate attr runs. The old no-fault `vle64.v` plus `vse64.v` translated-MMIO
store-back shape is preserved as a separate failing repro. The H-extension
vector suites now good-trap for onlyStage1, onlyStage2, and allStage
representatives in both isolated and aggregate runs. The live blocker is the
no-fence vector replay repro.

Vector suites emit `vector_mmu_coverage.json` instead of scalar
`mmu_coverage_ledger.json`. Each vector coverage item may also carry
`fail_codes` metadata so a late self-check failure can preserve the completed
prefix as `ran`, the failing item as `failed_or_blocked`, and the remaining
suffix as `generated_not_run` instead of flattening the whole suite to one
state. Summarize current vector evidence with one or more batch metadata paths:

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

If a target run fails, record the failure as evidence; do not add unrelated
instructions, fences, padding, or lower-stress variants to turn a failing case
into a pass-only regression. Keep bug repros and any future pass-only reduced
suite separate.

## CLI Reference

Run commands from the repository root with `python3 generator/cli.py <command> ...`.

| Command                       | Purpose                                                  |
| ----------------------------- | -------------------------------------------------------- |
| `list-snippets`               | List available snippet manifests.                        |
| `list-suite-pools`            | List configured suite generation pools.                  |
| `dump-plan <suite>`           | Print the resolved suite plan without building.          |
| `build [suite]`               | Generate the harness and build ELF/bin/disasm artifacts. |
| `run <suite>`                 | Build and run one suite on the selected target.          |
| `generate-suites`             | Generate YAML suites from configured suite pools.        |
| `mmu-coverage-summary <path>` | Summarize MMU coverage ledgers or batch metadata.        |

`run` requires exactly one seed selector:

| Option               | Purpose                                    |
| -------------------- | ------------------------------------------ |
| `--seed <N>`         | Run one deterministic seed.                |
| `--seeds <A,B,C>`    | Run an explicit comma-separated seed list. |
| `--seed-range <A:B>` | Run a deterministic seed range.            |

Additional `run` options:

| Option                    | Purpose                                                                                            |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| `--batch-id <name>`       | Use a stable run directory under `build/<suite>/runs/`. Useful for repros and regression evidence. |
| `--jobs <N>`              | Run multiple seeds in parallel when the target adapter supports it.                                |
| `--timeout-sec <N>`       | Override the per-run timeout.                                                                      |
| `--runner-profile <name>` | Use a reusable prebuilt XiangShan/NEMU runner profile, for example a Kunminghu v2 or v3 profile.   |

For the parser-defined interface, run:

```bash
python3 generator/cli.py --help
python3 generator/cli.py run --help
```

For MMU coverage, pass one or more `batch_meta.json` or
`mmu_coverage_ledger.json` paths:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_v2_smoke/runs/<batch_id>/batch_meta.json \
  build/kmh_mmu_layer1_v3_smoke/runs/<batch_id>/batch_meta.json
```

## Project Layout

### Source Tree

```text
snippetgen/
  generator/
    cli.py                    # build/run/dump-plan entry point
    xsgen/
      emitter.py              # emits generated_suite.c
      toolchain.py            # compiles ELF/bin/disasm artifacts
      run_batch.py            # multi-seed run orchestration and ledgers
      mmu_rule_loader.py      # MMU rule schema validation and coverage taxonomy
      mmu_rule_emitter.py     # emits generated_mmu_rule.{h,c} and coverage ledger
      runner_profiles.py      # reusable XiangShan/Kunminghu runner profiles
  runtime/                    # bare-metal runtime linked into generated programs
  snippets/
    manifests/                # snippet metadata
    programs/                 # standalone AM-style or custom program entries
    mmu_rules/                # structured MMU rule databases
  suites/                     # YAML workload compositions
  targets/
    xiangshan-verilator/      # XiangShan emu target adapter
  tests/                      # loader, build, run, runtime, and MMU regressions
  docs/                       # guides, run notes, investigations, archived plans
```

### Generated Outputs

Build-only commands write artifacts under `build/<suite>/`:

```text
build/<suite>/
  generated_suite.c
  test.elf
  test.bin
  disasm
  build_manifest.json
  generated_mmu_rule.h        # only for MMU rule suites
  generated_mmu_rule.c        # only for MMU rule suites
  mmu_coverage_ledger.json    # only for MMU rule suites
```

Run commands write seed-isolated artifacts under `build/<suite>/runs/<batch_id>/`:

```text
build/<suite>/runs/
  <batch_id>/
    batch_meta.json
    seed_<N>/
      generated_suite.c
      test.elf
      test.bin
      disasm
      stdout.log
      stderr.log
      run_meta.json
      generated_mmu_rule.h        # only for MMU rule suites
      generated_mmu_rule.c        # only for MMU rule suites
      mmu_coverage_ledger.json    # only for MMU rule suites
      lightsss-wave               # only on abort/bad-trap when external tracing is active
```

### Where To Start

| Task                                 | Start Here                                  |
| ------------------------------------ | ------------------------------------------- |
| Build or run a suite                 | `generator/cli.py`                          |
| Understand suite composition         | target YAML under `suites/`                 |
| Understand generated harnesses       | `generator/xsgen/emitter.py`                |
| Debug build artifacts                | `generator/xsgen/toolchain.py`              |
| Debug batch run metadata             | `generator/xsgen/run_batch.py`              |
| Debug XiangShan emu invocation       | `targets/xiangshan-verilator/run_target.py` |
| Add or inspect MMU rules             | `snippets/mmu_rules/`                       |
| Debug MMU rule parsing               | `generator/xsgen/mmu_rule_loader.py`        |
| Debug MMU generated C output         | `generator/xsgen/mmu_rule_emitter.py`       |
| Use prebuilt Kunminghu v2/v3 runners | `generator/xsgen/runner_profiles.py`        |
| Find expected behavior               | relevant tests under `tests/`               |

## Stable Suites

### Build and runtime smoke suites

- `suites/scalar_load_legality_poc.yaml`
  - baseline ELF-first scalar load legality path
- `suites/vsetvl_interrupt_path_poc.yaml`
  - minimal path-oriented `vsetvl` plus interrupt-related setup
- `suites/interrupt_response_poc.yaml`
  - proves real timer interrupt delivery is visible to the runtime

### MMU spec-in/case-out suites

- `suites/mmu_bare_identity_poc.yaml`
  - smallest MMU rule-runner smoke suite with one bare identity rule
- `suites/mmu_pilot_rules_poc.yaml`
  - pilot MMU rule bundle covering bare identity, Sv39 alias, superpage, `sfence` remap, load page fault, and two-stage guest-page-fault paths
- `suites/kmh_mmu_layer1_v2_smoke.yaml` and `suites/kmh_mmu_layer1_v3_smoke.yaml`
  - cached-runner smoke entries for Kunminghu v2/v3; v3 remains vector-free in this wave
- `suites/kmh_mmu_layer1_v2_vector_smoke.yaml`
  - v2-only vector memory MMU stable smoke covering vector enable, Bare hit, Sv39 host single-stage hit, and one vector load page-fault recovery check
- `suites/kmh_mmu_layer1_v2_vector_replay_repro.yaml`
  - v2-only no-fence vector replay assertion repro; keep separate from pass-only regression evidence
- `suites/kmh_mmu_layer1_v2_vector_widths.yaml`
  - v2-only vector memory MMU width suite covering `e8/e16/e32/e64` unit-stride load/store hit under Sv39 host translation
- `suites/kmh_mmu_layer1_v2_vector_faults.yaml`
  - v2-only vector memory MMU fault suite covering cross-page second-page faults and masked load/store fault behavior
- `suites/kmh_mmu_layer1_v2_vector_attr*.yaml`
  - v2-only vector memory MMU attribute witnesses; PMP load/store, MMIO access-fault, and PBMT sub-suites pass on the v2 runner, while the old no-fault MMIO store-back shape remains isolated as a repro
- `suites/kmh_mmu_layer1_v2_vector_hyp*.yaml`
  - v2-only vector memory MMU H-extension witnesses; onlyStage1, onlyStage2, allStage isolated sub-suites and aggregate hyp now pass on the v2 runner
- `suites/kmh_mmu_layer1_host_perm.yaml`, `suites/kmh_mmu_layer1_attr_ctrl.yaml`, `suites/kmh_mmu_layer1_hyp.yaml`, and `suites/kmh_mmu_layer1_faults.yaml`
  - group baselines for first-layer MMU permission, attribute/control, H-extension, and fault coverage

### Investigation and bug-hunting suites

- `suites/vsetvl_interrupt_search_poc.yaml`
  - periodic timer plus dense bundled `vsetvl zero, zero, zero` search workload
- `suites/misaligned_split_store_search_poc.yaml`
  - misaligned split-store forwarding search workload for the `sqNeedDeq` bug class
- `suites/prefetchw_tl_denied_fault_poc.yaml`
  - one illegal-address `load` that must trap plus one illegal-address `prefetch.w` that must not trap

## Repro Commands

### Real interrupt response

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/interrupt_response_poc.yaml --seed 4660
```

Expected result:

- `batch_meta.json` records `status: "ran"`
- `stdout.log` reaches `HIT GOOD TRAP`
- the check snippet confirms that a real timer interrupt was observed

### Path-oriented `vsetvl`

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_path_poc.yaml --seed 4660
```

Expected result:

- `status: "ran"`
- `labels` include `good_trap`

### MMU pilot rules

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml --seed 51967 --batch-id mmu_pilot_verify
```

Expected result:

- the matching `batch_meta.json` entry records `status: "ran"` and `finish_code: 0`
- `stdout.log` reaches `HIT GOOD TRAP`
- `mmu_coverage_ledger.json` promotes the selected pilot rules to `ran`
- the pilot bundle includes the `two_stage_fault` rule, which covers `requestor.hlv`, `mode.allStage`, `guest.two_stage`, and `exception.guest_page_fault`

### Illegal-address `load` plus `prefetch.w`

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/prefetchw_tl_denied_fault_poc.yaml --seed 4660
```

Expected result:

- `status: "ran"`
- the suite reaches `finish_check`
- the snippet performs exactly one `ld` and one `prefetch.w` on the same low-address target
- the normal `ld` is expected to take a load access fault
- `prefetch.w` is expected not to raise a software-visible trap

### Misaligned split-store abort on pre-fix XiangShan

This case is intended for a XiangShan tree that still contains the pre-fix `sqNeedDeq` behavior.

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
SNIPPETGEN_RUN_MAX_CYCLES=12000 SNIPPETGEN_RUN_MAX_INSTR=12000 \
python3 generator/cli.py run suites/misaligned_split_store_search_poc.yaml --seed 0 --timeout-sec 140
```

Expected result on the pre-fix `emu`:

- `batch_meta.json` records `status: "abort"`
- `stdout.log` shows difftest mismatch on the detector loads
- if LightSSS tracing is enabled in the external XiangShan tree, `seed_0/lightsss-wave` is dumped beside the logs

### `vsetvl` ROB assertion on a pre-fix XiangShan tree

Use the repository common path directly:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Observed result:

- `build/vsetvl_interrupt_search_poc/runs/repro_4658_default/batch_meta.json` records `status: "abort"`
- `stdout.log` contains:
  - `Assertion failed at .../Rob.sv:87863`
  - `ABORT at pc = 0x800002ac`
- `seed_4658/lightsss-wave` is dumped beside the logs when the external XiangShan LightSSS patch is active

## Further Reading

The full documentation index lives in [`docs/README.md`](docs/README.md).

Common entry points:

- [`docs/2026-04-10-xiangshan-emu-workload-howto.md`](docs/2026-04-10-xiangshan-emu-workload-howto.md): XiangShan `emu` build/run guide.
- [`docs/mmu-spec-in-case-out.md`](docs/mmu-spec-in-case-out.md): MMU rule schema and coverage ledger guide.
- [`docs/2026-04-27-kmh-mmu-layer1-run-notes.md`](docs/2026-04-27-kmh-mmu-layer1-run-notes.md): Kunminghu v2/v3 MMU layer-1 notes.
