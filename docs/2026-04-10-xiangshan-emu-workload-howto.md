# How To Run `snippetgen-demo` Workloads On XiangShan `emu`

This document is the practical run guide for this repository.

It covers:

- how to build a workload
- how to run it on XiangShan `emu`
- where artifacts are written
- how to interpret `batch_meta.json`
- how to check LightSSS wave dumping on abort

## 1. Preconditions

Always enter the XiangShan environment first:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
```

This repository expects at least:

- `NOOP_HOME=$XS_PROJECT_ROOT/XiangShan`
- `NEMU_HOME=$XS_PROJECT_ROOT/NEMU`

`XS_PROJECT_ROOT` is expected to be the directory that contains:

- `XiangShan/`
- `NEMU/`
- `nexus-am/`
- `DRAMsim3/`

Without that environment, the adapter may fail to find:

- `emu`
- the NEMU reference shared object

## 2. Build A Workload

Example:

```bash
python3 generator/cli.py build suites/misaligned_split_store_search_poc.yaml
```

Expected outputs:

- `build/misaligned_split_store_search_poc/test.elf`
- `build/misaligned_split_store_search_poc/test.bin`
- `build/misaligned_split_store_search_poc/disasm`
- `build/misaligned_split_store_search_poc/build_manifest.json`

If you only want to inspect the suite composition first:

```bash
python3 generator/cli.py dump-plan suites/misaligned_split_store_search_poc.yaml
```

## 3. Run Through The Repository Adapter

Example:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_path_poc.yaml --seed 4660
```

This is the preferred path for all normal runs. Manual `emu` invocation is for debugging and tests only.

This path:

- rebuilds the suite for that seed
- runs XiangShan `emu`
- keeps stdout/stderr
- writes a structured batch summary plus per-seed metadata

Current run layout is batch-scoped and collision-free:

```text
build/<suite>/runs/
  <batch_id>/
    batch_meta.json
    seed_<N>/
```

If you need a stable repro directory, set `--batch-id` explicitly:

```bash
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Equivalent `make` shortcuts:

```bash
make repro-vsetvl
make repro-split-store
```

## 4. Run XiangShan `emu` Manually

Example:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"

python3 generator/cli.py build suites/vsetvl_interrupt_path_poc.yaml

$NOOP_HOME/build/verilator-compile/emu \
  -s 4660 \
  -C 20000 \
  -I 20000 \
  -i build/vsetvl_interrupt_path_poc/test.bin \
  --diff $NEMU_HOME/build/riscv64-nemu-interpreter-so \
  --force-dump-result
```

Expected normal-success markers:

- `The first instruction of core 0 has commited. Difftest enabled.`
- `HIT GOOD TRAP`

## 5. Where To Look After A Run

For `suite=<suite>`, `batch=<batch_id>`, and `seed=<N>`:

- `build/<suite>/runs/<batch_id>/batch_meta.json`
- `build/<suite>/runs/<batch_id>/seed_<N>/stdout.log`
- `build/<suite>/runs/<batch_id>/seed_<N>/stderr.log`
- `build/<suite>/runs/<batch_id>/seed_<N>/run_meta.json`
- `build/<suite>/runs/<batch_id>/seed_<N>/disasm`
- `build/<suite>/runs/<batch_id>/seed_<N>/test.elf`
- `build/<suite>/runs/<batch_id>/seed_<N>/test.bin`

Optional, only when external XiangShan tracing is active:

- `build/<suite>/runs/<batch_id>/seed_<N>/lightsss-wave`

## 6. Repro Cases

### Real interrupt response

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/interrupt_response_poc.yaml --seed 4660
```

Expected:

- `batch_meta.json` shows `status: "ran"`
- `labels` include `good_trap`

### Path-oriented `vsetvl`

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_path_poc.yaml --seed 4660
```

Expected:

- `batch_meta.json` shows `status: "ran"`
- `labels` include `good_trap`

### Misaligned split-store abort on a pre-fix XiangShan tree

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
SNIPPETGEN_RUN_MAX_CYCLES=12000 SNIPPETGEN_RUN_MAX_INSTR=12000 \
python3 generator/cli.py run suites/misaligned_split_store_search_poc.yaml --seed 0 --timeout-sec 140
```

Expected on the pre-fix `emu`:

- `batch_meta.json` shows `status: "abort"`
- `stdout.log` shows difftest mismatch on the detector loads
- if LightSSS trace support is enabled in the external XiangShan tree, `lightsss-wave` is dumped beside the logs

### `vsetvl` assertion repro on a pre-fix XiangShan tree

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Observed result:

- `build/vsetvl_interrupt_search_poc/runs/repro_4658_default/batch_meta.json` shows `status: "abort"`
- `stdout.log` contains `Assertion failed at .../Rob.sv:87863`
- `seed_4658/lightsss-wave` appears when the external XiangShan LightSSS patch is active

## 7. LightSSS Wave Dump Notes

Wave dumping on abort is an external XiangShan integration concern, not a pure repository concern.

To get `lightsss-wave` reliably, the external XiangShan tree must satisfy all of:

- `emu` is built with trace support, for example `EMU_TRACE=fst`
- the local `emu.cpp` preserves the LightSSS child wakeup path for `STATE_BADTRAP / STATE_ABORT`
- the local `fork_child_init()` keeps `wave_path` and enables commit trace

If `stdout.log` shows:

- `the oldest checkpoint start to dump wave and dump nemu log...`

but no `lightsss-wave` file appears, check the external XiangShan build first.

## 8. Common Failure Modes

### `runner missing`

Cause:

- `xs-env` not sourced
- `emu` or NEMU reference path missing

### `limit_exceeded`

Cause:

- workload did not finish before `-C/-I`

This is not the same as a bug or a deadlock by itself.

### `timeout`

Cause:

- host-side timeout expired before `emu` exited

Check `stdout.log` before concluding the workload is hung.

### `abort`

Cause:

- assertion
- difftest mismatch
- explicit simulator abort

This is the most useful case for LightSSS replay and wave dump.

## 9. Release Snapshot Notes

At the time of this document update:

- `disasm` is emitted beside every `test.elf`
- run directories are batch-scoped and support explicit `--batch-id`
- the misaligned split-store search case has a reproducible `abort` path on a pre-fix XiangShan tree
- the `vsetvl` interrupt search case has a common-path `abort` repro at `--seed 4658 --batch-id repro_4658_default`

For the current documentation index, see:

- [`README.md`](README.md)
