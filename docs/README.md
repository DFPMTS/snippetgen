# Docs Index

This directory is split by audience:

- current user-facing guides stay at the top level
- short run evidence summaries live under `run-notes/`
- machine-readable evidence lives under `evidence/`
- historical drafts, checkpoints, and release snapshots live under `archive/`
- agent-generated design and implementation records live under `superpowers/`

## Start Here

- [`../README.md`](../README.md)
  - repository overview, quick start, suite map, and generated artifact layout
- [`2026-04-10-xiangshan-emu-workload-howto.md`](2026-04-10-xiangshan-emu-workload-howto.md)
  - practical XiangShan `emu` build/run guide
- [`mmu-spec-in-case-out.md`](mmu-spec-in-case-out.md)
  - MMU rule schema, generated artifacts, pilot suite, and coverage ledger guide
- [`2026-04-27-kmh-mmu-layer1-run-notes.md`](2026-04-27-kmh-mmu-layer1-run-notes.md)
  - Kunminghu v2/v3 layer-1 MMU rule corpus, runner profile, build, and run evidence notes

## Investigation Notes

- [`2026-04-10-vsetvl-hang-investigation-notes.md`](2026-04-10-vsetvl-hang-investigation-notes.md)
  - `vsetvl`, interrupt response, and common-path abort investigation trail
- [`2026-04-13-prefetchw-difftest-investigation-notes.md`](2026-04-13-prefetchw-difftest-investigation-notes.md)
  - `prefetch.w`, `M_PFW`, delayed `tl_denied`, and NEMU difftest investigation trail

## Run Notes And Evidence

- [`run-notes/README.md`](run-notes/README.md)
  - short real-run summaries grouped by feature area
- [`evidence/README.md`](evidence/README.md)
  - persisted batch metadata, generated suite records, and runner manifest examples

## Historical Material

- [`archive/README.md`](archive/README.md)
  - old requirements, plans, checkpoints, debug logs, and release snapshots
- [`superpowers/plans/`](superpowers/plans/)
  - historical implementation plans generated during development
- [`superpowers/specs/`](superpowers/specs/)
  - historical design drafts generated during development
