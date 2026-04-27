---
name: snippetgen-development
description: Use when working in the DFPMTS/snippetgen repository on generator, runtime, snippets, suites, MMU rules, tests, docs, XiangShan runs, or dev-branch integration.
---

# SnippetGen Development

## Purpose

Use this as the project-local operating guide for `snippetgen`. It keeps agents aligned on repository entry points, verification levels, and evidence discipline.

## First Checks

- Run `git status -sb` from the repository root before editing.
- Prefer relative `git` commands from the repository root.
- Treat `upstream/dev` as the integration target unless the user says otherwise.
- Do not change `origin` or force-push without explicit instruction.

## Reading Order

1. `README.md`
2. Target suite in `suites/`
3. For MMU work, `docs/mmu-spec-in-case-out.md` and selected rules in `snippets/mmu_rules/`
4. Referenced manifests in `snippets/manifests/`
5. Referenced sources in `snippets/`, `runtime/`, or `generator/xsgen/`
6. Focused tests in `tests/`

## Common Workflows

### Add or change a snippet suite

- Update snippet source, manifest, and suite YAML together.
- Run `python3 generator/cli.py dump-plan <suite.yaml>`.
- Run `python3 generator/cli.py build <suite.yaml>`.
- Add or adjust `tests/test_snippet_loading.py` and `tests/test_build_pipeline.py`.

### Add or change MMU rules

- Read `docs/mmu-spec-in-case-out.md` first.
- Keep rules under `snippets/mmu_rules/`; keep suite selection in `compose.mmu.rule_ids`.
- Validate rule vocabulary through `generator/xsgen/mmu_rule_loader.py`, not ad-hoc parsing.
- Preserve `mmu_coverage_ledger.json` semantics: `defined_only`, `generated_not_run`, `ran`, `gap`.
- Run:

```bash
python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v
python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
```

### Change generator or runtime behavior

- Add focused tests before relying on full-suite coverage.
- For runtime surface changes, check `tests/test_runtime_surface.py`, `tests/test_am_program_snippet_runtime.py`, `tests/test_mmu_runtime_surface.py`, and CTE/VME tests as relevant.
- For run classification changes, check `tests/test_run_pipeline.py`.

### Run on XiangShan

- Use `SNIPPETGEN_XS_ENV_SH=/path/to/xs-env/env.sh` and source it, or set `XS_PROJECT_ROOT`, `NEMU_HOME`, and `NOOP_HOME` explicitly.
- Use stable `--seed` and `--batch-id` values for repros.
- Do not claim target success unless logs show a semantic result such as `HIT GOOD TRAP` and metadata records `finish_code: 0`.
- Keep generated run artifacts under `build/`; do not commit machine evidence unless the user explicitly asks.

## Verification Matrix

- Docs-only: `git diff --check`, `python3 -m unittest tests.test_repo_layout -v`.
- Suite/schema changes: add `dump-plan` and focused loader/build tests.
- Generator/runtime changes: run focused tests plus `python3 -m unittest discover -s tests -v`.
- Target-semantics claims: run the relevant XiangShan suite and inspect `batch_meta.json`, `run_meta.json`, `stdout.log`, and any coverage ledger.

## Commit Hygiene

- Keep commits reviewable: docs, generator, runtime, snippets, and tests should be split when the diff is large.
- Do not commit `build/` outputs or local machine paths as release documentation.
- If `dev` already contains a merged PR, cherry-pick only remaining commits rather than reopening old branch history.
