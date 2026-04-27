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
- `snippets/mmu_rules/pilot/*.yaml`
  - rule database consumed by the pilot suites.
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

## Adding A Rule

1. Add a YAML file under `snippets/mmu_rules/pilot/` or a new rule group.
2. Use only supported `requestor`, `mode`, `expect.result`, action phases, actions, and coverage tags.
3. Add mappings under `setup.mappings`; use `stage: stage2` for guest-physical mappings and `fault: true` for fault probes.
4. Add the rule id to a suite's `compose.mmu.rule_ids`.
5. Run:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
```

If the new rule changes runtime behavior, also run a target-level XiangShan seed and check `batch_meta.json`, `stdout.log`, and `mmu_coverage_ledger.json`.

## Historical Design Material

The implementation plan, design draft, and interface inventory were moved to `docs/archive/`. They are useful for understanding why the interface was shaped this way, but they are not the normal usage entry point.
