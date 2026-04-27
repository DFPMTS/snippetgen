# SnippetGen Demo

ELF-first baremetal snippet generator workspace for XiangShan-oriented workload construction, build, and run.

This repository is now beyond the initial skeleton stage. It can:

- load snippet manifests and suite YAMLs
- generate a deterministic harness
- build `test.elf`, `test.bin`, and `disasm`
- run workloads on XiangShan `emu`
- record structured run results under `build/<suite>/runs/`
- keep path-oriented and bug-hunting suites side by side
- generate MMU rule-driven pilot cases from structured YAML specs

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

Each run entry in `run_meta.json` and `batch_meta.json` now includes `finish_code`:

- `0`: XiangShan reported `HIT GOOD TRAP`
- `1`: XiangShan reported `HIT BAD TRAP`
- `N > 1`: XiangShan reported `Unknown trap code: N`
- `null`: the runner did not recover a guest semantic trap code

If you need a stable, reusable path for a repro case, pass `--batch-id`:

```bash
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Equivalent `make` entry points:

```bash
make repro-vsetvl
make repro-split-store
```

## Repository Map

### Core directories

- `generator/`: CLI, suite loading, harness emission, build, run orchestration
- `runtime/`
  - baremetal runtime used by generated workloads
- `snippets/`
  - concrete workload building blocks
- `suites/`
  - ordered snippet compositions
- `targets/`
  - target-specific run adapters
- `tests/`
  - loader, build, and run pipeline regression tests
- `docs/`
  - user docs, release notes, investigations, archived plans

### Important entry files

- `generator/cli.py`
  - top-level `build`, `run`, and `dump-plan` commands
- `generator/xsgen/emitter.py`
  - emits `generated_suite.c`
- `generator/xsgen/toolchain.py`
  - compiles, links, runs `objcopy`, emits `disasm`
- `generator/xsgen/run_batch.py`
  - batch run orchestration and ledger emission
- `generator/xsgen/mmu_rule_loader.py`
  - MMU rule schema validation and coverage taxonomy
- `generator/xsgen/mmu_rule_emitter.py`
  - emits `generated_mmu_rule.h`, `generated_mmu_rule.c`, and `mmu_coverage_ledger.json`
- `targets/xiangshan-verilator/run_target.py`
  - XiangShan `emu` adapter

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

## XiangShan Run Requirements

The XiangShan adapter assumes:

- `SNIPPETGEN_XS_ENV_SH` points to your local `xs-env/env.sh`
- `source "$SNIPPETGEN_XS_ENV_SH"` has been executed
- `NOOP_HOME/build/verilator-compile/emu` is available
- `NEMU_HOME/build/riscv64-nemu-interpreter-so` is available

If you need LightSSS wave dump on abort, the external XiangShan tree must also be prepared correctly:

- the `emu` must be trace-enabled, for example with `EMU_TRACE=fst`
- the local `emu.cpp` must preserve the LightSSS abort/bad-trap wakeup and `wave_path` handling

This repository does not vendor the external XiangShan tree. That setup remains a local integration step.

## Artifact Layout

### Build-only layout

```text
build/<suite>/
  generated_suite.c
  test.elf
  test.bin
  disasm
  build_manifest.json
  generated_mmu_rule.h     # only for MMU rule suites
  generated_mmu_rule.c     # only for MMU rule suites
  mmu_coverage_ledger.json # only for MMU rule suites
```

### Build-plus-run layout

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
      generated_mmu_rule.h     # only for MMU rule suites
      generated_mmu_rule.c     # only for MMU rule suites
      mmu_coverage_ledger.json # only for MMU rule suites
      lightsss-wave        # only on abort/bad-trap when external XiangShan tracing is active
```

## Documentation Index

### Start here

- [`docs/2026-04-10-xiangshan-emu-workload-howto.md`](docs/2026-04-10-xiangshan-emu-workload-howto.md)
  - practical XiangShan `emu` build/run guide
- [`docs/mmu-spec-in-case-out.md`](docs/mmu-spec-in-case-out.md)
  - MMU rule schema, generated artifacts, pilot suite, and coverage ledger guide
- [`docs/release-notes-2026-04-11.md`](docs/release-notes-2026-04-11.md)
  - what changed in this snapshot

### Investigation notes

- [`docs/2026-04-10-vsetvl-hang-investigation-notes.md`](docs/2026-04-10-vsetvl-hang-investigation-notes.md)
  - `vsetvl` and interrupt investigation trail

### Archived planning material

- [`docs/archive/README.md`](docs/archive/README.md)
  - archived drafts, requirements, and implementation plans

## For Agents

If you are an AI agent entering this repository cold, use this order:

1. Read `README.md`
2. Read the target suite YAML in `suites/`
3. For MMU suites, read `docs/mmu-spec-in-case-out.md` and the selected rules in `snippets/mmu_rules/`
4. Read the referenced snippet manifests in `snippets/manifests/`
5. Read the snippet sources under `snippets/`
6. Read `generator/cli.py`, `emitter.py`, `toolchain.py`, `run_batch.py`, and the MMU loader/emitter when relevant
7. Read `tests/test_snippet_loading.py`, `tests/test_build_pipeline.py`, `tests/test_run_pipeline.py`, and the MMU-focused tests when relevant

Recommended first commands:

```bash
python3 generator/cli.py dump-plan suites/misaligned_split_store_search_poc.yaml
python3 generator/cli.py build suites/misaligned_split_store_search_poc.yaml
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
python3 -m unittest tests.test_snippet_loading tests.test_build_pipeline
```

Avoid assumptions about:

- external XiangShan tree state
- whether LightSSS wave dump is patched in that external tree
- whether a pre-fix or post-fix `emu` is being used
