# KMH Layer 1 MMU Rules

This directory stores first-wave Kunminghu v2/v3 MMU rules for the
`snippetgen` MMU rule runner. The scope is functional and architecture-visible:
translation result, permission result, trap cause, memory observation, and
fence/control effects that the current generic runner can check.

Version policy:

- v3 excludes vector rules in the first wave.
- v2 may include vector rules in later suites.

Future coverage boundaries:

- ITLB concurrent miss ownership is future coverage for a monitor or stress
  layer.
- prefetch filtering, drop reason, replay timing, merged miss policy, duplicate
  suppression, and stale response pipeline kill are future coverage and are not
  claimed by these first-layer rules.

First-wave structured coverage now includes raw PTE emission, PMP deny,
PBMT/NC, PMA/MMIO attribute records, MXR, SUM, ASID, VMID, satp/vsatp/hgatp
context actions, hfence actions, and fault `repair_then_reexecute`.
The attribute rules must have a runtime witness: PMP deny is observed as an
access fault, PBMT NC is observed as a reserved-PBMT page fault when PBMTE is
disabled, and PMA/MMIO is observed by translating a load to the platform CLINT
mtime MMIO page. Precise downstream cacheability timing still belongs to a
monitor or trace-backed layer.
The context-switch rules use paired initial and `context: switch` mappings with
different physical targets, so the observed value depends on the switched
satp/vsatp/hgatp root rather than merely re-reading the same old mapping.

| Rule | Requestor | Mode | Expect | Observe | Coverage |
|------|-----------|------|--------|---------|----------|
| bare_identity | load | bare | hit | memory_value_match | requestor.load, mode.bare, page.identity |
| sv39_alias | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, page.alias |
| superpage | store | host_single_stage | hit | memory_value_match | requestor.store, mode.host_single_stage, page.superpage, pte.w |
| sfence_remap | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, page.alias, ctrl.sfence |
| only_stage1_load_hit | load | onlyStage1 | hit | memory_value_match | requestor.load, mode.onlyStage1 |
| raw_pte_load_hit | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, pte.raw, pte.v, pte.r, pte.a, pte.d |
| host_mxr_exec_load | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, pte.x, pte.a, priv.mxr |
| host_sum_user_load | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, pte.u, priv.sum |
| host_pmp_deny | load | host_single_stage | access_fault | fault_cause_match, attribute_policy_match | requestor.load, mode.host_single_stage, exception.access_fault, attr.pmp_deny |
| host_pbmt_nc | load | host_single_stage | page_fault | fault_cause_match, attribute_policy_match | requestor.load, mode.host_single_stage, exception.page_fault, pte.raw, attr.nc, attr.pbmt_nc |
| host_pma_mmio_attribute | load | host_single_stage | hit | attribute_policy_match | requestor.load, mode.host_single_stage, attr.pma, attr.mmio |
| satp_asid_switch | load | host_single_stage | hit | memory_value_match | requestor.load, mode.host_single_stage, ctrl.satp, ctrl.asid |
| load_page_fault | load | host_single_stage | page_fault | fault_cause_match | requestor.load, mode.host_single_stage, exception.page_fault |
| store_page_fault | store | host_single_stage | page_fault | fault_cause_match | requestor.store, mode.host_single_stage, exception.page_fault |
| load_access_fault | load | host_single_stage | access_fault | fault_cause_match | requestor.load, mode.host_single_stage, exception.access_fault |
| store_access_fault | store | host_single_stage | access_fault | fault_cause_match | requestor.store, mode.host_single_stage, exception.access_fault |
| fault_repair_retry | load | host_single_stage | page_fault + repair_then_reexecute | fault_cause_match, memory_value_match | requestor.load, mode.host_single_stage, exception.page_fault, retry.repair_then_reexecute |
| hybrid_load_identity | hybrid_load | host_single_stage | hit | memory_value_match | requestor.hybrid_load, mode.host_single_stage, page.identity |
| only_stage2_hlv_hit | hlv | onlyStage2 | hit | memory_value_match | requestor.hlv, mode.onlyStage2, guest.vs_only |
| all_stage_hlv_hit | hlv | allStage | hit | memory_value_match | requestor.hlv, mode.allStage, guest.two_stage |
| hlvx_exec_hit | hlvx | onlyStage2 | hit | memory_value_match | requestor.hlvx, mode.onlyStage2, guest.vs_only |
| hsv_store_hit | hsv | onlyStage2 | hit | memory_value_match | requestor.hsv, mode.onlyStage2, guest.vs_only |
| two_stage_fault | hlv | allStage | guest_page_fault | fault_cause_match | requestor.hlv, mode.allStage, guest.two_stage, exception.guest_page_fault |
| vsatp_hgatp_context_switch | hlv | allStage | hit | memory_value_match | requestor.hlv, mode.allStage, guest.two_stage, ctrl.vsatp, ctrl.hgatp, ctrl.asid, ctrl.vmid, ctrl.hfence_vvma, ctrl.hfence_gvma |
