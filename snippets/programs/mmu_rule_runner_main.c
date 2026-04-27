#include <stddef.h>
#include <stdint.h>

#include "generated_mmu_rule.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam/mmu_guest.h"
#include "xsam_xs_platform.h"
#include "xsrt_trap.h"

static const uintptr_t XS_RULE_HSTATUS_SPVP_MASK = (uintptr_t)1 << 8;
static const uintptr_t XS_RULE_RUNTIME_IDENTITY_BASE = 0x80000000ull;
static const uintptr_t XS_RULE_RUNTIME_IDENTITY_SIZE = 0x40000000ull;
static const uintptr_t XS_RULE_RUNTIME_VS_STAGE1_IDENTITY_SIZE = 0x00400000ull;
static const uintptr_t XS_RULE_RUNTIME_STAGE2_IDENTITY_SIZE = 0x00400000ull;
static const uintptr_t XS_RULE_PTE_LEAF_PERMS = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X;
static const uint32_t XS_RULE_EXEC_SEED = 0x00008067u;
static const unsigned long XS_RULE_PRIMARY_SEED = 0x1122334455667788ull;
static const unsigned long XS_RULE_STORE_VALUE = 0x5566778899aabbccull;
static const unsigned long XS_RULE_REMAP_VALUE = 0x8877665544332211ull;

typedef struct {
  unsigned long primary_value;
  unsigned long secondary_value;
} xs_rule_observation_t;

static int xs_string_eq(const char *lhs, const char *rhs) {
  if (lhs == 0 || rhs == 0) {
    return 0;
  }
  while (*lhs != '\0' && *rhs != '\0') {
    if (*lhs != *rhs) {
      return 0;
    }
    lhs += 1;
    rhs += 1;
  }
  return *lhs == *rhs;
}

static const xs_generated_mmu_mapping_t *xs_primary_mapping(const xs_generated_mmu_rule_t *rule) {
  if (rule == 0 || rule->mapping_count == 0u) {
    return 0;
  }
  return &rule->mappings[0];
}

static uintptr_t xs_mapping_size_bytes(const xs_generated_mmu_mapping_t *mapping) {
  if (mapping == 0) {
    return 0u;
  }
  return (uintptr_t)mapping->page_count * XSAM_MMU_PAGE_SIZE;
}

static int xs_mapping_covers_addr(const xs_generated_mmu_mapping_t *mapping, uintptr_t addr) {
  if (mapping == 0) {
    return 0;
  }
  return addr >= mapping->va && (addr - mapping->va) < xs_mapping_size_bytes(mapping);
}

static uintptr_t xs_mapping_pa_for_addr(
    const xs_generated_mmu_mapping_t *mapping,
    uintptr_t addr) {
  if (mapping == 0) {
    return 0u;
  }
  if (!xs_mapping_covers_addr(mapping, addr)) {
    return mapping->pa;
  }
  return mapping->pa + (addr - mapping->va);
}

static uintptr_t xs_page_base(uintptr_t addr) {
  return addr & ~((uintptr_t)XSAM_MMU_PAGE_SIZE - 1u);
}

static const xs_generated_mmu_mapping_t *xs_mapping_for_addr(
    const xs_generated_mmu_rule_t *rule,
    uintptr_t addr) {
  size_t index;

  if (rule == 0) {
    return 0;
  }

  for (index = 0; index < rule->mapping_count; ++index) {
    if (xs_mapping_covers_addr(&rule->mappings[index], addr)) {
      return &rule->mappings[index];
    }
  }
  return xs_primary_mapping(rule);
}

static const xs_generated_mmu_mapping_t *xs_stage2_mapping_for_addr(
    const xs_generated_mmu_rule_t *rule,
    uintptr_t addr) {
  size_t index;

  if (rule == 0) {
    return 0;
  }

  for (index = 0; index < rule->mapping_count; ++index) {
    const xs_generated_mmu_mapping_t *candidate = &rule->mappings[index];
    if ((candidate->flags & XS_GENERATED_MMU_FLAG_STAGE2) != 0u &&
        xs_mapping_covers_addr(candidate, addr)) {
      return candidate;
    }
  }
  return 0;
}

static const xs_generated_mmu_mapping_t *xs_repair_mapping_for_addr(
    const xs_generated_mmu_rule_t *rule,
    uintptr_t addr,
    uintptr_t *action_addr) {
  const xs_generated_mmu_mapping_t *mapping;
  const xs_generated_mmu_mapping_t *stage2_mapping;

  if (action_addr != 0) {
    *action_addr = addr;
  }
  mapping = xs_mapping_for_addr(rule, addr);
  if (rule == 0 || mapping == 0 ||
      !xs_string_eq(rule->expected_result, "guest_page_fault") ||
      (mapping->flags & XS_GENERATED_MMU_FLAG_STAGE2) != 0u) {
    return mapping;
  }

  uintptr_t guest_pa = xs_mapping_pa_for_addr(mapping, addr);
  stage2_mapping = xs_stage2_mapping_for_addr(rule, guest_pa);
  if (stage2_mapping == 0) {
    return mapping;
  }
  if (action_addr != 0) {
    *action_addr = guest_pa;
  }
  return stage2_mapping;
}

static xsam_mmu_page_table_t *xs_select_table(
    const xs_generated_mmu_mapping_t *mapping,
    xsam_mmu_page_table_t *stage1,
    xsam_mmu_page_table_t *stage2) {
  if (mapping != 0 && (mapping->flags & XS_GENERATED_MMU_FLAG_STAGE2) != 0u) {
    return stage2;
  }
  return stage1;
}

static void xs_phys_store_u64(uintptr_t addr, unsigned long value) {
  *(volatile unsigned long *)addr = value;
}

static unsigned long xs_phys_load_u64(uintptr_t addr) {
  return *(volatile unsigned long *)addr;
}

static void xs_phys_store_u32(uintptr_t addr, uint32_t value) {
  *(volatile uint32_t *)addr = value;
}

static uint32_t xs_phys_load_u32(uintptr_t addr) {
  return *(volatile uint32_t *)addr;
}

static unsigned long xs_host_load_u64(uintptr_t addr) {
#if defined(__riscv)
  unsigned long value;
  uintptr_t new_status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(new_status) : : "memory");
  new_status = (new_status & ~((uintptr_t)3u << 11)) |
      ((uintptr_t)1u << 11) |
      ((uintptr_t)1u << 17);
  __asm__ volatile(
      "csrrw t0, mstatus, %2\n\t"
      "ld %0, 0(%1)\n\t"
      "csrw mstatus, t0\n\t"
      : "=r"(value)
      : "r"(addr), "r"(new_status)
      : "t0", "memory");
  return value;
#else
  return *(unsigned long *)addr;
#endif
}

static void xs_host_store_u64(uintptr_t addr, unsigned long value) {
#if defined(__riscv)
  uintptr_t new_status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(new_status) : : "memory");
  new_status = (new_status & ~((uintptr_t)3u << 11)) |
      ((uintptr_t)1u << 11) |
      ((uintptr_t)1u << 17);
  __asm__ volatile(
      "csrrw t0, mstatus, %2\n\t"
      "sd %1, 0(%0)\n\t"
      "csrw mstatus, t0\n\t"
      :
      : "r"(addr), "r"(value), "r"(new_status)
      : "t0", "memory");
#else
  *(unsigned long *)addr = value;
#endif
}

static unsigned long xs_guest_load_u64(uintptr_t addr) {
  uintptr_t saved_hstatus;
  unsigned long value;

  saved_hstatus = xsam_mmu_read_hyp_csr(XSAM_MMU_CSR_HSTATUS);
  xsam_mmu_write_hyp_csr(
      XSAM_MMU_CSR_HSTATUS,
      saved_hstatus | XS_RULE_HSTATUS_SPVP_MASK);
  value = xsam_mmu_hlv_d(addr);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HSTATUS, saved_hstatus);
  return value;
}

static unsigned long xs_guest_hlvx_wu(uintptr_t addr) {
#if defined(__riscv)
  unsigned long value;

  __asm__ volatile(".insn i 0x73, 0x4, %0, %1, 0x683"
                   : "=r"(value)
                   : "r"(addr)
                   : "memory");
  return value;
#else
  return (unsigned long)xs_phys_load_u32(addr);
#endif
}

static unsigned long xs_guest_exec_load_u32(uintptr_t addr) {
  uintptr_t saved_hstatus;
  unsigned long value;

  saved_hstatus = xsam_mmu_read_hyp_csr(XSAM_MMU_CSR_HSTATUS);
  xsam_mmu_write_hyp_csr(
      XSAM_MMU_CSR_HSTATUS,
      saved_hstatus | XS_RULE_HSTATUS_SPVP_MASK);
  value = xs_guest_hlvx_wu(addr);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HSTATUS, saved_hstatus);
  return value;
}

static void xs_guest_store_u64(uintptr_t addr, unsigned long value) {
  uintptr_t saved_hstatus;

  saved_hstatus = xsam_mmu_read_hyp_csr(XSAM_MMU_CSR_HSTATUS);
  xsam_mmu_write_hyp_csr(
      XSAM_MMU_CSR_HSTATUS,
      saved_hstatus | XS_RULE_HSTATUS_SPVP_MASK);
  xsam_mmu_hsv_d(addr, value);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HSTATUS, saved_hstatus);
}

static uintptr_t xs_fault_leaf_perm(uintptr_t prot, uintptr_t fallback) {
  if ((prot & (uintptr_t)XS_RULE_PTE_LEAF_PERMS) != 0u) {
    return prot;
  }
  return prot | fallback;
}

static uintptr_t xs_fault_perm_override(const xs_generated_mmu_rule_t *rule, uintptr_t prot) {
  if (rule == 0) {
    return prot;
  }
  if (xs_string_eq(rule->requestor, "store") || xs_string_eq(rule->requestor, "hsv")) {
    return xs_fault_leaf_perm(prot & ~((uintptr_t)XSAM_MMU_PTE_W), XSAM_MMU_PTE_R);
  }
  if (xs_string_eq(rule->requestor, "hlvx")) {
    return xs_fault_leaf_perm(prot & ~((uintptr_t)XSAM_MMU_PTE_X), XSAM_MMU_PTE_R);
  }
  return xs_fault_leaf_perm(prot & ~((uintptr_t)XSAM_MMU_PTE_R), XSAM_MMU_PTE_W);
}

static void xs_apply_mapping(
    const xs_generated_mmu_rule_t *rule,
    const xs_generated_mmu_mapping_t *mapping,
    xsam_mmu_page_table_t *stage1,
    xsam_mmu_page_table_t *stage2) {
  size_t page_index;
  xsam_mmu_page_table_t *target;

  if (mapping == 0) {
    return;
  }

  target = xs_select_table(mapping, stage1, stage2);
  if ((mapping->flags & XS_GENERATED_MMU_FLAG_SUPERPAGE) != 0u &&
      mapping->page_count > 1u &&
      (mapping->flags & XS_GENERATED_MMU_FLAG_FAULT) == 0u) {
    xsam_mmu_pt_map_superpage(target, mapping->va, mapping->pa, mapping->prot, mapping->page_count);
    if (xsam_mmu_pt_leaf_ptr(target, mapping->va) != 0) {
      return;
    }
  }

  for (page_index = 0; page_index < mapping->page_count; ++page_index) {
    uintptr_t page_offset = (uintptr_t)page_index * XSAM_MMU_PAGE_SIZE;
    uintptr_t va = mapping->va + page_offset;
    uintptr_t pa = mapping->pa + page_offset;
    if ((mapping->flags & XS_GENERATED_MMU_FLAG_FAULT) != 0u &&
        xs_string_eq(rule->expected_result, "access_fault")) {
      xsam_mmu_pt_map_fault(target, va, pa, mapping->prot);
    } else if ((mapping->flags & XS_GENERATED_MMU_FLAG_FAULT) != 0u) {
      xsam_mmu_pt_map(target, va, pa, xs_fault_perm_override(rule, mapping->prot));
    } else {
      xsam_mmu_pt_map(target, va, pa, mapping->prot);
    }
  }
}

static void xs_seed_rule_memory(const xs_generated_mmu_rule_t *rule) {
  const xs_generated_mmu_mapping_t *primary;
  const xs_generated_mmu_mapping_t *secondary;
  uintptr_t primary_pa;
  uintptr_t secondary_pa;

  primary = xs_mapping_for_addr(rule, rule->trigger_addr);
  secondary = xs_mapping_for_addr(rule, rule->secondary_addr);
  if (primary == 0) {
    return;
  }
  primary_pa = xs_mapping_pa_for_addr(primary, rule->trigger_addr);
  secondary_pa = xs_mapping_pa_for_addr(secondary, rule->secondary_addr);

  if (xs_string_eq(rule->trigger_op, "store_then_load")) {
    xs_phys_store_u64(primary_pa, 0u);
    if (secondary != 0 && secondary_pa != primary_pa) {
      xs_phys_store_u64(secondary_pa, 0u);
    }
    return;
  }

  if (xs_string_eq(rule->trigger_op, "store")) {
    xs_phys_store_u64(primary_pa, 0u);
    return;
  }

  if (xs_string_eq(rule->trigger_op, "remap_then_load")) {
    xs_phys_store_u64(primary_pa, XS_RULE_PRIMARY_SEED);
    xs_phys_store_u64(primary_pa + XSAM_MMU_PAGE_SIZE, XS_RULE_REMAP_VALUE);
    return;
  }

  if (xs_string_eq(rule->requestor, "hlvx")) {
    xs_phys_store_u32(primary_pa, XS_RULE_EXEC_SEED);
    return;
  }

  xs_phys_store_u64(primary_pa, XS_RULE_PRIMARY_SEED);
}

static unsigned long xs_expected_observation_value(const xs_generated_mmu_rule_t *rule) {
  if (rule != 0 && xs_string_eq(rule->requestor, "hlvx")) {
    return (unsigned long)XS_RULE_EXEC_SEED;
  }
  return XS_RULE_PRIMARY_SEED;
}

static int xs_rule_uses_stage2(const xs_generated_mmu_rule_t *rule) {
  if (rule == 0) {
    return 0;
  }
  return xs_string_eq(rule->mode, "onlyStage2") ||
      xs_string_eq(rule->mode, "allStage");
}

static int xs_rule_uses_all_stage(const xs_generated_mmu_rule_t *rule) {
  return rule != 0 && xs_string_eq(rule->mode, "allStage");
}

static void xs_configure_rule_context(
    const xs_generated_mmu_rule_t *rule,
    xsam_mmu_page_table_t *stage1,
    xsam_mmu_page_table_t *stage2) {
  size_t index;

  xsam_mmu_pt_init_sv39(stage1);
  xsam_mmu_pt_init_sv39x4(stage2);
  xs_seed_rule_memory(rule);
  if ((rule->fault_mask != 0u) &&
      (xs_string_eq(rule->mode, "host_single_stage") ||
       xs_string_eq(rule->mode, "onlyStage1"))) {
    xsam_mmu_pt_map_identity_range(
        stage1,
        XS_RULE_RUNTIME_IDENTITY_BASE,
        XS_RULE_RUNTIME_IDENTITY_SIZE,
        XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
            XSAM_MMU_PTE_A | XSAM_MMU_PTE_D);
  }
  if (xs_rule_uses_all_stage(rule)) {
    xsam_mmu_pt_map_identity_range(
        stage1,
        XS_RULE_RUNTIME_IDENTITY_BASE,
        XS_RULE_RUNTIME_VS_STAGE1_IDENTITY_SIZE,
        XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
            XSAM_MMU_PTE_A | XSAM_MMU_PTE_D);
  }
  if (xs_rule_uses_stage2(rule)) {
    xsam_mmu_pt_map_identity_range(
        stage2,
        XS_RULE_RUNTIME_IDENTITY_BASE,
        XS_RULE_RUNTIME_STAGE2_IDENTITY_SIZE,
        XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
            XSAM_MMU_PTE_A | XSAM_MMU_PTE_D);
  }
  for (index = 0; index < rule->mapping_count; ++index) {
    xs_apply_mapping(rule, &rule->mappings[index], stage1, stage2);
  }

  if (xs_string_eq(rule->mode, "bare")) {
    xsam_mmu_enable_bare();
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
    return;
  }

  if (xs_string_eq(rule->mode, "host_single_stage") || xs_string_eq(rule->mode, "onlyStage1")) {
    xsam_mmu_enable_sv39(stage1, 1u);
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
    return;
  }

  xsam_mmu_enable_bare();
  if (xs_string_eq(rule->mode, "onlyStage2")) {
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(stage2, 2u));
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
    xsam_mmu_hfence_gvma(0u, 0u);
    return;
  }
  if (xs_string_eq(rule->mode, "allStage")) {
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(stage1, 3u));
    xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(stage2, 2u));
    xsam_mmu_hfence_vvma(0u, 0u);
    xsam_mmu_hfence_gvma(0u, 0u);
  }
}

static void xs_noop_vs(void *arg) {
  (void)arg;
}

static int xs_run_action(
    const char *action,
    const xs_generated_mmu_rule_t *rule,
    xsam_mmu_page_table_t *stage1,
    xsam_mmu_page_table_t *stage2) {
  const xs_generated_mmu_mapping_t *mapping;
  xsam_mmu_page_table_t *target;
  uintptr_t action_pa;
  uintptr_t action_addr;
  uintptr_t action_va;

  if (action == 0) {
    return 0;
  }

  mapping = xs_mapping_for_addr(rule, rule->trigger_addr);
  target = xs_select_table(mapping, stage1, stage2);

  if (xs_string_eq(action, "sfence_vma")) {
    xsam_mmu_sfence_vma();
    return 0;
  }
  if (xs_string_eq(action, "hfence_vvma")) {
    xsam_mmu_hfence_vvma(rule->trigger_addr, 0u);
    return 0;
  }
  if (xs_string_eq(action, "hfence_gvma")) {
    xsam_mmu_hfence_gvma(rule->trigger_addr, 0u);
    return 0;
  }
  if (xs_string_eq(action, "switch_bare_mode")) {
    xsam_mmu_enable_bare();
    return 0;
  }
  if (xs_string_eq(action, "restore_stage1")) {
    xsam_mmu_enable_sv39(stage1, 1u);
    return 0;
  }
  if (xs_string_eq(action, "enter_vs")) {
    xsam_mmu_enter_vs(xs_noop_vs, 0);
    return 0;
  }
  if (xs_string_eq(action, "record_fault_snapshot")) {
    (void)xsam_mmu_last_fault_cause();
    (void)xsam_mmu_last_fault_tval();
    return 0;
  }
  if (mapping == 0 || target == 0) {
    return -1;
  }
  action_va = xs_page_base(rule->trigger_addr);
  action_pa = xs_mapping_pa_for_addr(mapping, action_va);
  if (xs_string_eq(action, "remap_alias")) {
    xsam_mmu_pt_map(target, action_va, action_pa + XSAM_MMU_PAGE_SIZE, mapping->prot);
    return 0;
  }
  if (xs_string_eq(action, "repair_fault_mapping")) {
    mapping = xs_repair_mapping_for_addr(rule, rule->trigger_addr, &action_addr);
    target = xs_select_table(mapping, stage1, stage2);
    if (mapping == 0 || target == 0) {
      return -1;
    }
    action_va = xs_page_base(action_addr);
    action_pa = xs_mapping_pa_for_addr(mapping, action_va);
    xsam_mmu_pt_map(target, action_va, action_pa, mapping->prot);
    xsam_mmu_sfence_vma();
    return 0;
  }
  return -1;
}

static int xs_run_actions(
    const char *const *actions,
    size_t action_count,
    const xs_generated_mmu_rule_t *rule,
    xsam_mmu_page_table_t *stage1,
    xsam_mmu_page_table_t *stage2) {
  size_t index;

  for (index = 0; index < action_count; ++index) {
    if (xs_run_action(actions[index], rule, stage1, stage2) != 0) {
      return -1;
    }
  }
  return 0;
}

static int xs_run_trigger(
    const xs_generated_mmu_rule_t *rule,
    xs_rule_observation_t *observation) {
  const xs_generated_mmu_mapping_t *primary;

  if (rule == 0 || observation == 0) {
    return -1;
  }

  primary = xs_mapping_for_addr(rule, rule->trigger_addr);
  if (primary == 0) {
    return -1;
  }

  observation->primary_value = 0u;
  observation->secondary_value = 0u;
  if (xs_string_eq(rule->requestor, "hlvx")) {
    observation->primary_value = xs_guest_exec_load_u32(rule->trigger_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "store_then_load")) {
    xs_host_store_u64(rule->trigger_addr, XS_RULE_STORE_VALUE);
    observation->secondary_value = xs_host_load_u64(rule->secondary_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "remap_then_load")) {
    observation->primary_value = xs_host_load_u64(rule->trigger_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "hlv_load")) {
    observation->primary_value = xs_guest_load_u64(rule->trigger_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "guest_store") || xs_string_eq(rule->requestor, "hsv")) {
    xs_guest_store_u64(rule->trigger_addr, XS_RULE_STORE_VALUE);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "guest_load") || xs_string_eq(rule->requestor, "hlv")) {
    observation->primary_value = xs_guest_load_u64(rule->trigger_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "load")) {
    observation->primary_value = xs_host_load_u64(rule->trigger_addr);
    return 0;
  }
  if (xs_string_eq(rule->trigger_op, "store")) {
    xs_host_store_u64(rule->trigger_addr, XS_RULE_STORE_VALUE);
    return 0;
  }
  return -1;
}

static int xs_run_observe_checks(
    const xs_generated_mmu_rule_t *rule,
    const xs_rule_observation_t *observation) {
  size_t index;
  const xs_generated_mmu_mapping_t *primary;
  uintptr_t primary_pa;

  if (rule == 0 || observation == 0) {
    return -1;
  }

  primary = xs_mapping_for_addr(rule, rule->trigger_addr);
  if (primary == 0) {
    return -1;
  }
  primary_pa = xs_mapping_pa_for_addr(primary, rule->trigger_addr);

  for (index = 0; index < rule->observe_count; ++index) {
    const char *observe = rule->observe[index];
    if (xs_string_eq(observe, "memory_value_match")) {
      if (xs_string_eq(rule->trigger_op, "store_then_load")) {
        if (observation->secondary_value != XS_RULE_STORE_VALUE ||
            xs_phys_load_u64(primary_pa) != XS_RULE_STORE_VALUE) {
          return -1;
        }
        continue;
      }
      if (xs_string_eq(rule->trigger_op, "store")) {
        if (xs_phys_load_u64(primary_pa) != XS_RULE_STORE_VALUE) {
          return -1;
        }
        continue;
      }
      if (xs_string_eq(rule->trigger_op, "remap_then_load")) {
        if (observation->primary_value != XS_RULE_REMAP_VALUE) {
          return -1;
        }
        continue;
      }
      if (observation->primary_value != xs_expected_observation_value(rule)) {
        return -1;
      }
      continue;
    }
    if (xs_string_eq(observe, "fault_cause_match")) {
      if (xsam_mmu_last_fault_cause() != rule->expected_cause ||
          xsam_mmu_last_fault_tval() != rule->trigger_addr) {
        return -1;
      }
      continue;
    }
    return -1;
  }
  return 0;
}

static int xs_rule_fault_checks(
    const xs_generated_mmu_rule_t *rule,
    const xs_rule_observation_t *observation) {
  if (rule->fault_mask == 0u) {
    return -1;
  }
  if (xsam_mmu_fault_assert(rule->fault_mask) != 0) {
    return -1;
  }
  return xs_run_observe_checks(rule, observation);
}

static int xs_run_rule(const xs_generated_mmu_rule_t *rule) {
  static xsam_mmu_page_table_t stage1;
  static xsam_mmu_page_table_t stage2;
  xs_rule_observation_t observation;
  int rc;

  if (rule == 0) {
    return -1;
  }

  xsam_xs_pmp_init();
  xsam_mmu_fault_install_handlers();
  xs_configure_rule_context(rule, &stage1, &stage2);
  rc = xs_run_actions(rule->before_actions, rule->before_action_count, rule, &stage1, &stage2);
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return rc;
  }

  if (rule->fault_mask != 0u) {
    xsam_mmu_expect_fault(rule->fault_mask);
  } else {
    xsam_mmu_fault_reset();
  }
  rc = xs_run_trigger(rule, &observation);
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return rc;
  }

  if (xs_string_eq(rule->expected_result, "page_fault") ||
      xs_string_eq(rule->expected_result, "access_fault") ||
      xs_string_eq(rule->expected_result, "guest_page_fault")) {
    rc = xs_run_actions(rule->handler_actions, rule->handler_action_count, rule, &stage1, &stage2);
    if (rc == 0) {
      rc = xs_rule_fault_checks(rule, &observation);
    }
  } else {
    if (xsam_mmu_fault_seen_mask() != 0u) {
      rc = -1;
    } else {
      rc = xs_run_observe_checks(rule, &observation);
    }
  }
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return rc;
  }

  rc = xs_run_actions(rule->post_actions, rule->post_action_count, rule, &stage1, &stage2);
  xsam_mmu_enable_bare();
  return rc;
}

static int xs_rule_runner_finish(int code) {
  xsam_mmu_enable_bare();
  xsrt_install_strap(0);
  return code;
}

int main(void) {
  size_t index;

  for (index = 0; index < xs_generated_mmu_rule_count; ++index) {
    if (xs_run_rule(xs_generated_mmu_rules[index]) != 0) {
      return xs_rule_runner_finish((int)(64u + index));
    }
  }
  return xs_rule_runner_finish(0);
}
