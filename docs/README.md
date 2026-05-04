# Docs Index

This directory is split into four kinds of material:

## Start Here

- [`../README.md`](../README.md)
  - repository overview, quick start, suite map, agent entry points
- [`2026-04-10-xiangshan-emu-workload-howto.md`](2026-04-10-xiangshan-emu-workload-howto.md)
  - build and run workloads on XiangShan `emu`
- [`mmu-spec-in-case-out.md`](mmu-spec-in-case-out.md)
  - MMU rule schema, generated artifacts, pilot suite, and coverage ledger guide
- [`2026-04-27-kmh-mmu-layer1-run-notes.md`](2026-04-27-kmh-mmu-layer1-run-notes.md)
  - Kunminghu v2/v3 layer-1 MMU rule corpus, profile, build, and run evidence notes
- [`release-notes-2026-04-11.md`](release-notes-2026-04-11.md)
  - current release snapshot

## MMU Rule Interface

- [`mmu-spec-in-case-out.md`](mmu-spec-in-case-out.md)
  - start here for `suites/mmu_pilot_rules_poc.yaml`, `snippets/mmu_rules/pilot/`, `generated_mmu_rule.*`, and `mmu_coverage_ledger.json`
- [`2026-04-27-kmh-mmu-layer1-run-notes.md`](2026-04-27-kmh-mmu-layer1-run-notes.md)
  - current Kunminghu layer-1 MMU verification notes and environment blockers
- [`archive/2026-04-24-mmu-interface-inventory.md`](archive/2026-04-24-mmu-interface-inventory.md)
  - historical inventory mapping legacy `mmutest` responsibilities to the new `xsam_mmu_*` surface
- [`archive/2026-04-24-mmu-spec-in-case-out-interface-design.md`](archive/2026-04-24-mmu-spec-in-case-out-interface-design.md)
  - historical design draft
- [`archive/2026-04-24-mmu-spec-in-case-out-interface-plan.md`](archive/2026-04-24-mmu-spec-in-case-out-interface-plan.md)
  - historical implementation plan

## Investigation Notes

- [`2026-04-10-vsetvl-hang-investigation-notes.md`](2026-04-10-vsetvl-hang-investigation-notes.md)
  - `vsetvl` and interrupt investigation trail
- [`2026-04-13-prefetchw-difftest-investigation-notes.md`](2026-04-13-prefetchw-difftest-investigation-notes.md)
  - `prefetch.w`, `M_PFW`, delayed `tl_denied`, and NEMU difftest investigation trail

## Archived Plans And Drafts

- [`archive/README.md`](archive/README.md)
  - archived requirements, plans, and drafts

## Intended Reading Order For Agents

1. [`../README.md`](../README.md)
2. target suite in `suites/`
3. for MMU suites, [`mmu-spec-in-case-out.md`](mmu-spec-in-case-out.md) and selected rules in `snippets/mmu_rules/`
4. snippet manifests in `snippets/manifests/`
5. snippet sources in `snippets/`
6. generator pipeline in `generator/xsgen/`
7. tests in `tests/`
