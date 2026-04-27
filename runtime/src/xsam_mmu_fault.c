#include "xsam/mmu_fault.h"
#include "xsam/mmu_guest.h"

#include "xsrt_trap.h"

static uint32_t g_expected_mask;
static uint32_t g_seen_mask;
static uint32_t g_seen_count;
static uintptr_t g_last_cause;
static uintptr_t g_last_epc;
static uintptr_t g_last_tval;

static uintptr_t xsam_mmu_fault_advance_epc(uintptr_t cause, uintptr_t epc) {
  uint16_t insn_lo;

  switch (cause) {
    case XSAM_MMU_CAUSE_INST_ACCESS_FAULT:
    case XSAM_MMU_CAUSE_INST_PAGE_FAULT:
    case XSAM_MMU_CAUSE_INST_GUEST_PAGE_FAULT:
      return 4u;
    default:
      break;
  }

  insn_lo = *(volatile uint16_t *)epc;
  return (insn_lo & 0x3u) == 0x3u ? 4u : 2u;
}

static uint32_t xsam_mmu_mask_from_cause(uintptr_t cause) {
  switch (cause) {
    case XSAM_MMU_CAUSE_INST_ACCESS_FAULT:
      return XSAM_MMU_FAULT_INST_ACCESS;
    case XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT:
      return XSAM_MMU_FAULT_LOAD_ACCESS;
    case XSAM_MMU_CAUSE_STORE_ACCESS_FAULT:
      return XSAM_MMU_FAULT_STORE_ACCESS;
    case XSAM_MMU_CAUSE_INST_PAGE_FAULT:
      return XSAM_MMU_FAULT_INST_PAGE;
    case XSAM_MMU_CAUSE_LOAD_PAGE_FAULT:
      return XSAM_MMU_FAULT_LOAD_PAGE;
    case XSAM_MMU_CAUSE_STORE_PAGE_FAULT:
      return XSAM_MMU_FAULT_STORE_PAGE;
    case XSAM_MMU_CAUSE_INST_GUEST_PAGE_FAULT:
      return XSAM_MMU_FAULT_INST_GUEST_PAGE;
    case XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT:
      return XSAM_MMU_FAULT_LOAD_GUEST_PAGE;
    case XSAM_MMU_CAUSE_STORE_GUEST_PAGE_FAULT:
      return XSAM_MMU_FAULT_STORE_GUEST_PAGE;
    default:
      return 0u;
  }
}

static uint32_t xsam_mmu_fault_popcount(uint32_t value) {
  uint32_t count = 0u;

  while (value != 0u) {
    count += value & 1u;
    value >>= 1;
  }
  return count;
}

static xsrt_trap_frame_t *xsam_mmu_fault_trap_handler(xsrt_trap_frame_t *frame) {
  uint32_t fault_mask;

  if (frame == 0) {
    return frame;
  }

  if (xsam_mmu_handle_vs_trap(frame) != 0) {
    return frame;
  }

  fault_mask = xsam_mmu_mask_from_cause(frame->cause);
  if (fault_mask == 0u) {
    return frame;
  }

  xsam_mmu_record_fault(fault_mask, frame->cause, frame->epc, frame->tval);
  frame->epc += xsam_mmu_fault_advance_epc(frame->cause, frame->epc);
  return frame;
}

void xsam_mmu_fault_install_handlers(void) {
  xsrt_install_strap(xsam_mmu_fault_trap_handler);
}

void xsam_mmu_fault_reset(void) {
  g_expected_mask = 0u;
  g_seen_mask = 0u;
  g_seen_count = 0u;
  g_last_cause = 0u;
  g_last_epc = 0u;
  g_last_tval = 0u;
}

void xsam_mmu_expect_fault(uint32_t mask) {
  xsam_mmu_fault_reset();
  g_expected_mask = mask;
}

int xsam_mmu_fault_assert(uint32_t expected_mask) {
  if (g_expected_mask != expected_mask ||
      g_seen_mask != expected_mask ||
      g_seen_count != xsam_mmu_fault_popcount(expected_mask)) {
    g_last_cause = (uintptr_t)-1;
    return -1;
  }
  return 0;
}

void xsam_mmu_record_fault(uint32_t mask, uintptr_t cause, uintptr_t epc, uintptr_t tval) {
  g_seen_mask |= mask;
  if (mask != 0u) {
    g_seen_count += 1u;
  }
  g_last_cause = cause;
  g_last_epc = epc;
  g_last_tval = tval;
}

uint32_t xsam_mmu_fault_expected_mask(void) {
  return g_expected_mask;
}

uint32_t xsam_mmu_fault_seen_mask(void) {
  return g_seen_mask;
}

uintptr_t xsam_mmu_last_fault_cause(void) {
  return g_last_cause;
}

uintptr_t xsam_mmu_last_fault_epc(void) {
  return g_last_epc;
}

uintptr_t xsam_mmu_last_fault_tval(void) {
  return g_last_tval;
}
