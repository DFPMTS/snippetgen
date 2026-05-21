# MMU Spec-In Case-Out Interface

This document is the user-facing entry point for the MMU rule flow. It explains how a structured MMU rule becomes a generated bare-metal case, where the generated artifacts live, and which files to read when extending the pilot set.

## Purpose

The MMU interface turns small YAML rules into deterministic XiangShan workloads. Each rule describes the requestor, translation mode, mappings, trigger operation, expected result, observation points, and coverage tags. The build pipeline then emits C/header data for a generic runner instead of requiring every MMU scenario to hand-write page-table, trap, CSR, and fence boilerplate.

This is a first-wave functional interface. It is meant for spec-shaped MMU cases such as translation, page permissions, faults, `sfence`/`hfence`, and two-stage guest translation. It is not a waveform-only monitor, random microarchitectural stress generator, or full `mmutest` port.

## Entry Points

- `suites/mmu_bare_identity_poc.yaml`
  - smallest smoke suite using one `bare_identity` rule.
- `suites/mmu_pilot_rules_poc.yaml`
  - pilot bundle with bare identity, Sv39 alias, superpage, `sfence` remap, load page fault, and two-stage guest-page-fault rules.
- `suites/kmh_mmu_layer1_smoke.yaml`
  - smallest Kunminghu layer-1 MMU rule bundle.
- `suites/kmh_mmu_layer1_v2_smoke.yaml`
  - Kunminghu v2 scalar smoke entry.
- `suites/kmh_mmu_layer1_v2_vector_smoke.yaml`
  - Kunminghu v2-only vector memory MMU smoke; this is a dedicated AM program suite, not part of the YAML MMU rule corpus.
- `suites/kmh_mmu_layer1_v3_smoke.yaml`
  - Kunminghu v3 smoke entry; first-wave v3 suites intentionally exclude vector instruction cases.
- `suites/kmh_mmu_layer1_host_perm.yaml`, `suites/kmh_mmu_layer1_attr_ctrl.yaml`, `suites/kmh_mmu_layer1_hyp.yaml`, `suites/kmh_mmu_layer1_faults.yaml`, and `suites/kmh_mmu_layer1_full.yaml`
  - grouped Kunminghu layer-1 suites for permissions, attributes/control, H-extension translation, faults, and the full generated corpus.
- `snippets/mmu_rules/pilot/*.yaml`
  - rule database consumed by the pilot suites.
- `snippets/mmu_rules/kmh_layer1/*.yaml`
  - first-wave Kunminghu v2/v3 rule database with one YAML file per rule.
- `snippets/programs/mmu_rule_runner_main.c`
  - generic AM program runner that consumes generated MMU rule data.
- `generator/xsgen/mmu_rule_loader.py`
  - schema validation, mode normalization, supported vocabulary, and coverage taxonomy.
- `generator/xsgen/mmu_rule_emitter.py`
  - generated C/header output and coverage ledger emission.
- `runtime/include/xsam/mmu.h`
  - page-table, mapping, CSR, fence, and mode helper API.
- `runtime/include/xsam/mmu_fault.h`
  - expected fault arming and observed fault assertion API.
- `runtime/include/xsam/mmu_guest.h`
  - guest and H-extension helper API.

## Rule Shape

A minimal rule looks like this:

```yaml
id: load_page_fault
requestor: load
mode: host_single_stage
setup:
  mappings:
    - name: fault_page
      va: 0xb00000000
      pa: 0x80022000
      perms: [r, a]
      fault: true
trigger:
  op: load
  addr: fault_page
expect:
  result: page_fault
observe:
  - fault_cause_match
coverage_tags:
  - requestor.load
  - mode.host_single_stage
  - exception.page_fault
```

The loader currently requires:

- `id`: valid C-like identifier, unique within the rule directory.
- `requestor`: one of `load`, `hybrid_load`, `store`, `hlv`, `hlvx`, `hsv`.
- `mode`: one of `bare`, `host_single_stage`, `onlyStage1`, `onlyStage2`, `allStage`; legacy spellings `only_stage1`, `only_stage2`, and `all_stage` are normalized.
- `expect.result`: one of `hit`, `page_fault`, `access_fault`, `guest_page_fault`.
- `coverage_tags`: non-empty list from the built-in taxonomy in `mmu_rule_loader.py`.

Optional fields include `symbol`, `preconditions`, `setup`, `actions`, `trigger`, and `observe`. Supported action phases are `before_trigger`, `handler`, and `post_check`.

## Build Flow

MMU suites use the normal `build` and `run` commands. The extra MMU work is driven by the suite's `compose.mmu` section:

```yaml
compose:
  mode: sequence
  snippets:
    - init_basic_env
    - mmu_rule_runner_main
    - finish_check
  mmu:
    rule_dir: ../snippets/mmu_rules/pilot
    rule_ids:
      - bare_identity
      - sv39_alias
      - superpage
      - sfence_remap
      - load_page_fault
      - two_stage_fault
```

During build:

1. `suite_loader` resolves `rule_dir` and selected `rule_ids`.
2. `mmu_rule_loader` validates every rule in the rule directory.
3. `mmu_rule_emitter` writes `generated_mmu_rule.h`, `generated_mmu_rule.c`, and `mmu_coverage_ledger.json`.
4. `toolchain.py` compiles the generated MMU source with the normal generated suite and runtime sources.
5. `build_manifest.json` records the rule directory, selected rules, defined rules, coverage tags, and generated MMU artifact paths.

## Coverage Ledger

`mmu_coverage_ledger.json` tracks both rules and coverage tags. It intentionally separates four states:

- `defined_only`: the rule exists in the rule directory but this suite did not select it.
- `generated_not_run`: the rule was selected and generated, but there is no successful target run yet.
- `ran`: the target run reached semantic success and the selected rule is counted as run.
- `gap`: the taxonomy defines the coverage tag, but no rule currently covers it.

`run_batch.py` only promotes MMU coverage for successful target results. Host command success alone is not enough; the XiangShan adapter must classify a semantic good result such as `HIT GOOD TRAP` with `finish_code: 0`.

Use `mmu-coverage-summary` to read one or more ledgers or batch metadata files:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_v2_smoke/runs/<batch_id>/batch_meta.json \
  build/kmh_mmu_layer1_v3_smoke/runs/<batch_id>/batch_meta.json
```

The summary keeps each runner profile separate. When a batch entry selected MMU
rules but the target run did not reach semantic success, the summary reports
those selected rules and tags as `failed_or_blocked`. That is a derived reporting
state; the persisted `mmu_coverage_ledger.json` still uses the original
`generated_not_run` state.

## Commands

Inspect the pilot plan:

```bash
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
```

Build the pilot bundle:

```bash
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
```

Run the pilot bundle on XiangShan:

```bash
export SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh
source "$SNIPPETGEN_XS_ENV_SH"
python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml --seed 51967 --batch-id mmu_pilot_verify
```

The expected successful result is:

- the matching `batch_meta.json` entry has `status: "ran"`, `finish_code: 0`, and `labels` including `good_trap`.
- `stdout.log` contains `HIT GOOD TRAP`.
- `mmu_coverage_ledger.json` marks the selected pilot rules as `ran`.

## Kunminghu Layer-1 Flow

Build the full generated Kunminghu layer-1 corpus:

```bash
make kmh-mmu-layer1-build
```

The equivalent direct command is:

```bash
python3 generator/cli.py build suites/kmh_mmu_layer1_full.yaml
```

Run the smoke suites through explicit cached runner profiles:

```bash
make kmh-mmu-layer1-smoke-v2
make kmh-mmu-layer1-smoke-v3
```

The direct commands are:

```bash
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_smoke.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest

python3 generator/cli.py run suites/kmh_mmu_layer1_v3_smoke.yaml \
  --seed 241027 \
  --timeout-sec 2400 \
  --runner-profile kmh-v3/difftest
```

Group baselines should use explicit runner profiles and a larger guest budget:

```bash
SNIPPETGEN_RUN_MAX_CYCLES=1200000 \
SNIPPETGEN_RUN_MAX_INSTR=1200000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_host_perm.yaml \
  --seed 241027 \
  --timeout-sec 2400 \
  --runner-profile kmh-v3/difftest \
  --batch-id kmh_v3_host_perm
```

Repeat that command shape for `kmh_mmu_layer1_attr_ctrl.yaml`,
`kmh_mmu_layer1_hyp.yaml`, and `kmh_mmu_layer1_faults.yaml`. v3 remains
vector-free in this first layer; v2 vector MMU coverage uses the separate
`suites/kmh_mmu_layer1_v2_vector_smoke.yaml` suite.

Run the v2 vector MMU suite with the v2 cached runner profile only:

```bash
SNIPPETGEN_RUN_MAX_CYCLES=300000 \
SNIPPETGEN_RUN_MAX_INSTR=300000 \
python3 generator/cli.py run suites/kmh_mmu_layer1_v2_vector_smoke.yaml \
  --seed 241027 \
  --timeout-sec 1800 \
  --runner-profile kmh-v2/difftest \
  --batch-id kmh_v2_vector_mmu_<date>
```

This suite currently covers the pass-only unit-stride `vle8.v` smoke path for
Bare hit, Sv39 host single-stage hit, and one vector load page-fault recovery
check. Broader vector load/store forms and the known no-fence load/store replay
shape live in separate v2-only suites. The vector cases use local encoded
instructions and leave the global `-march` unchanged.

Summarize v2/v3 smoke coverage after both runs:

```bash
python3 generator/cli.py mmu-coverage-summary \
  build/kmh_mmu_layer1_v2_smoke/runs/<v2_batch>/batch_meta.json \
  build/kmh_mmu_layer1_v3_smoke/runs/<v3_batch>/batch_meta.json
```

Runner profiles are resolved from `../artifacts/kmh-runners/manifest.json`
relative to the `snippetgen` checkout unless `SNIPPETGEN_KMH_RUNNER_MANIFEST`
points at another manifest. An example manifest is checked in at
`docs/evidence/kmh-mmu-layer1/runner-manifest.example.json`.
When `--runner-profile` is set, the target adapter fails with
`labels: ["error", "runner_profile"]` if the manifest or named binary is
missing; it does not silently fall back to whatever `emu` is on the host.

Successful run evidence must include the generated `batch_meta.json`, each
seed's `run_meta.json`, `stdout.log`, `stderr.log`, runner profile name,
XiangShan revision, NEMU revision, `emu` path, and NEMU reference path. The
current run notes live in `docs/2026-04-27-kmh-mmu-layer1-run-notes.md`.

## Pilot And KMH Rule Sets

`snippets/mmu_rules/pilot/` remains the small interface smoke corpus for the
generic MMU rule runner. `snippets/mmu_rules/kmh_layer1/` is the formal
Kunminghu layer-1 corpus used for the v2/v3 regression matrix.

Do not add new Kunminghu coverage only to the pilot directory. New first-layer
rules should land in `kmh_layer1` first, then optionally be mirrored into
`pilot` only when the rule is useful as a tiny interface smoke case. If a pilot
rule and a KMH rule cover the same scenario, prefer keeping the KMH rule as the
source of coverage truth and treat the pilot copy as compatibility smoke. This
prevents the two directories from becoming independent rule universes.

## Adding A Rule

1. Add a YAML file under `snippets/mmu_rules/kmh_layer1/` for Kunminghu layer-1 coverage. Use `snippets/mmu_rules/pilot/` only for tiny interface smoke rules.
2. Use only supported `requestor`, `mode`, `expect.result`, action phases, actions, and coverage tags.
3. Add mappings under `setup.mappings`; use `stage: stage2` for guest-physical mappings. For first-layer permission faults, `fault: true` means the runner emits a leaf PTE that removes the requestor-required permission before the handler repairs it.
4. Add a single-case suite under `suites/kmh_mmu_layer1_case_<rule_id>.yaml`.
5. Add the rule id to the matching group suite and to `suites/kmh_mmu_layer1_full.yaml` after the single-case build works.
6. Run:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter tests.test_kmh_mmu_layer1_inventory -v
python3 generator/cli.py dump-plan suites/kmh_mmu_layer1_case_<rule_id>.yaml
python3 generator/cli.py build suites/kmh_mmu_layer1_case_<rule_id>.yaml
```

7. Run the single-case or containing group on both runner profiles, then check
   `batch_meta.json`, `stdout.log`, and `mmu_coverage_ledger.json`.

For the pilot directory, the equivalent smoke commands are:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
```

If the new rule changes runtime behavior, also run a target-level XiangShan seed and check `batch_meta.json`, `stdout.log`, and `mmu_coverage_ledger.json`.

## Deferred Scope

The layer-1 rule runner checks architecture-visible results: hit/fault outcome,
trap cause, translated memory value, and explicit control/fence effects. It
does not claim coverage for ITLB/DTLB concurrent miss ownership, prefetch drop
reason, PTW/L2TLB arbitration, merged-miss timing, replay cycle placement, or
stale response pipeline kill. Those remain second-layer or monitor-backed
verification work.

## Historical Design Material

The implementation plan, design draft, and interface inventory were moved to `docs/archive/`. They are useful for understanding why the interface was shaped this way, but they are not the normal usage entry point.
