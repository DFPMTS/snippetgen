# MMU Interface Inventory

## Purpose

This inventory records the Round 0 analysis used to start the MMU `spec in, case out` implementation. It maps legacy `mmutest` responsibilities to a `snippetgen`-native surface and identifies the first-wave pilot classes.

## Runtime API Groups

- Environment and layout:
  - Own runtime initialization, allocator setup, kernel/test/guest address layout, and stage-2 identity segment defaults.
  - Legacy sources: `mmutest_vme_init`, `mmutest_kernel_as`, `mmutest_sv39_layout`, allocator helpers, kernel segments, and stage2 identity segments.
  - New surface direction: `xsam_mmu_env_*` and `xsam_mmu_layout_*`, not additional responsibilities inside the current `xsam_vme` recorder.

- Stage-1 and stage-2 page-table construction:
  - Own `Sv39`, `Sv48`, `Sv39x4`, `Sv48x4` root construction, ordinary mapping, raw PTE override, fault mapping, identity ranges, superpage metadata, leaf lookup, and leaf pointer access.
  - Legacy sources: `mmutest_pt_init_sv39`, `mmutest_pt_init_sv48`, `mmutest_pt_init_sv39x4`, `mmutest_pt_init_sv48x4`, `mmutest_pt_map`, `mmutest_pt_map_raw`, `mmutest_pt_map_fault`, `mmutest_pt_map_identity_range`, `mmutest_stage2_identity_map_kernel`, `mmutest_pt_leaf_ptr`, `mmutest_map`, `mmutest_map_fault`, `mmutest_map_hugepage`, `mmutest_remap`, `mmutest_read_leaf_pte`.

- Fault arming and observation:
  - Own expected fault masks, observed fault masks, last `sepc`, last cause, `tval`, handler install/reset, and compressed-aware EPC advance.
  - Legacy sources: `mmutest_fault_install_handlers`, `mmutest_fault_reset`, `mmutest_expect_fault`, `mmutest_fault_assert`, and the per-cause fault handlers in `mmutest_vme_fault.c`.

- Control, CSR, and fence helpers:
  - Own `satp`, `vsatp`, `hgatp`, `ASID`, `VMID`, hypervisor CSR read/write, `sfence.vma`, `hfence.vvma`, `hfence.gvma`, and bare-mode switching.
  - Legacy sources: `mmutest_make_vsatp`, `mmutest_make_vsatp_pt`, `mmutest_make_hgatp_bare`, `mmutest_make_hgatp_pt`, `mmutest_read_hyp_csr`, `mmutest_write_hyp_csr`, `mmutest_sfence_vma`, `mmutest_hfence_vvma`, `mmutest_hfence_gvma`, `mmutest_switch_to_bare`.

- Guest and H-extension execution helpers:
  - Own VS entry/resume, HLV/HSV probes, VS ecall return, and guest trap return behavior.
  - Legacy sources: `mmutest_enter_vs`, `mmutest_hlv_d`, `mmutest_hsv_d`, VS trampoline/resume assembly, and VS ecall handler logic.

## Semantics To Preserve

- Fault taxonomy must stay explicit: fetch/load/store, page/access/guest-page causes, and corresponding expected-fault masks.
- Address-translation mode encoding must preserve page size, `satp`/`hgatp` mode shifts, ASID/VMID shifts, and `Sv39`/`Sv48`/`Sv39x4`/`Sv48x4` mode values.
- Fault mapping must keep page-fault and access-fault semantics separate. Permission-missing or invalid PTEs are not the same as valid translations to denied or poisoned physical targets.
- Superpage metadata must remain explicit through a page-table level field.
- Guest-stage mappings must preserve the legacy behavior of adding `PTE_U` where needed.
- Fault handlers must preserve compressed-aware EPC advance for data faults and the VS resume behavior for instruction/guest faults.
- PBMT/N encodings should be available even if most first-wave pilots do not depend on them yet.

## Current SnippetGen Integration Points

- `runtime/include/xsam/vme.h` and `runtime/src/xsam_vme.c` are AM-compatible mapping recorders, not complete MMU control layers.
- `runtime/include/xsrt_trap.h` and `runtime/src/xsrt_trap.c` already provide a synchronous trap hook that MMU fault observation can reuse.
- Existing `nexus_memscan_*` programs prove the pipeline can carry MMU-like AM programs, but they inline page-table, `satp`, PMP, MPRV, and trap logic.
- `generator/xsgen/program_harness.py`, `generator/xsgen/emitter.py`, and `generator/xsgen/toolchain.py` are the stable path for `am_program` build integration.
- `toolchain.runtime_sources()` is a static list, so new runtime sources must be added there explicitly.

## First-Wave Pilot Classes

- `sv39_alias`: proves host single-stage alias mapping and basic runtime page-table setup.
- `load_page_fault` or `store_page_fault`: proves permission/invalid-PTE fault behavior.
- `load_access_fault` or `store_access_fault`: proves the access-fault path stays distinct from page fault.
- `superpage`: proves non-4K leaf construction and level metadata.
- `sfence_remap`: proves control-plane invalidation and remap helpers.
- `two_stage_fault` or `two_stage_happy`: forces `vsatp`, `hgatp`, `hfence`, and guest-stage mapping into the public design.

## Implementation Risks

- Extending `xsam_vme` directly would mix a mapping recorder with real MMU control semantics. Keep the new surface under dedicated `xsam/mmu*.h` headers.
- Trap ownership is currently a single synchronous hook. MMU fault observation must either own it during MMU tests or avoid conflicting with CTE.
- Rule vocabulary must be fixed early. Requestor, mode, result, and coverage tags need validation before emitter work starts.
- Coverage ledger should be built with the rule loader/emitter rather than bolted on after generated cases exist.
- Host compile tests can validate API shape, but guest/two-stage semantic confidence eventually needs target execution.
