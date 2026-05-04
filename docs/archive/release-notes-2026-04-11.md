# Release Notes 2026-04-11

This snapshot turns `snippetgen-demo` from a build-only PoC into a repository that can:

- generate deterministic baremetal workloads
- build `ELF/bin/disasm`
- run workloads on XiangShan `emu`
- keep machine-readable run ledgers
- hold path-oriented suites and bug-hunting suites in one place

## Highlights

### 1. Multi-seed run pipeline

The repository now supports:

- `python3 generator/cli.py run ... --seed <N>`
- `python3 generator/cli.py run ... --seeds <A,B,C>`
- `python3 generator/cli.py run ... --seed-range <L:R>`
- `python3 generator/cli.py run ... --batch-id <NAME>`
- `python3 generator/cli.py run ... --jobs <N>`

Run artifacts are isolated per seed under:

```text
build/<suite>/runs/<batch_id>/seed_<N>/
```

and summarized by:

```text
build/<suite>/runs/<batch_id>/batch_meta.json
```

Parallel seed exploration keeps the current batch contract intact:

- default remains serial with `--jobs 1`
- only the `run` phase executes concurrently
- per-seed outputs remain isolated
- the final batch ledger stays ordered by input seed

### 2. Real XiangShan `emu` integration

The run adapter now targets the real XiangShan environment:

- XiangShan `emu`
- NEMU diff reference
- structured `stdout.log` / `stderr.log`
- weak result labels such as `good_trap`, `abort`, `timeout`, and `limit_exceeded`

### 3. `disasm` is now a first-class artifact

Every build emits:

- `test.elf`
- `test.bin`
- `disasm`

This makes it easier for humans and agents to confirm that the final ELF really contains the intended instruction sequence.

### 4. New suites

The repository now includes:

- `scalar_load_legality_poc`
- `vsetvl_interrupt_path_poc`
- `interrupt_response_poc`
- `vsetvl_interrupt_search_poc`
- `misaligned_split_store_search_poc`

### 5. Reproducible pre-fix misaligned split-store abort

On a pre-fix XiangShan tree, the current `misaligned_split_store_search_poc` can reproduce an `abort` path via the repository `run` command.

Reference command:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
SNIPPETGEN_RUN_MAX_CYCLES=12000 SNIPPETGEN_RUN_MAX_INSTR=12000 \
python3 generator/cli.py run suites/misaligned_split_store_search_poc.yaml --seed 0 --timeout-sec 140
```

Expected result:

- `batch_meta.json` records `status: "abort"`
- `stdout.log` contains difftest mismatch and `ABORT`

### 6. Common-path `vsetvl` abort with LightSSS output

On a pre-fix XiangShan tree, the current `vsetvl_interrupt_search_poc` can `ABORT` through the repository common path:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/vsetvl_interrupt_search_poc.yaml --seed 4658 --batch-id repro_4658_default
```

Observed result:

- `build/vsetvl_interrupt_search_poc/runs/repro_4658_default/batch_meta.json` records `status: "abort"`
- `stdout.log` contains `Assertion failed at .../Rob.sv:87863`
- `seed_4658/lightsss-wave` is emitted when the external XiangShan LightSSS patch is active

## Documentation Layout

### Main entry points

- [`README.md`](../README.md)
- [`2026-04-10-xiangshan-emu-workload-howto.md`](2026-04-10-xiangshan-emu-workload-howto.md)

### Investigation notes

- [`2026-04-10-vsetvl-hang-investigation-notes.md`](2026-04-10-vsetvl-hang-investigation-notes.md)

### Archived planning material

- [`archive/README.md`](archive/README.md)

## External Coupling

This repository does not vendor the external XiangShan tree.

If you want LightSSS wave dump on abort:

- the external `emu` must be built with trace support
- the external XiangShan `emu.cpp` must keep the local abort-wave patch
- your local XiangShan environment should be provided via `SNIPPETGEN_XS_ENV_SH` or exported `XS_PROJECT_ROOT` / `NOOP_HOME` / `NEMU_HOME`

The repository-side run adapter already passes `wave_path`; whether a wave file actually appears depends on that external build.
