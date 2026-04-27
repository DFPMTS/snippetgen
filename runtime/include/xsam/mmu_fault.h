#ifndef XSAM_MMU_FAULT_H
#define XSAM_MMU_FAULT_H

#include <stdint.h>

enum {
  XSAM_MMU_CAUSE_INST_ACCESS_FAULT = 1,
  XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT = 5,
  XSAM_MMU_CAUSE_STORE_ACCESS_FAULT = 7,
  XSAM_MMU_CAUSE_INST_PAGE_FAULT = 12,
  XSAM_MMU_CAUSE_LOAD_PAGE_FAULT = 13,
  XSAM_MMU_CAUSE_STORE_PAGE_FAULT = 15,
  XSAM_MMU_CAUSE_INST_GUEST_PAGE_FAULT = 20,
  XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT = 21,
  XSAM_MMU_CAUSE_STORE_GUEST_PAGE_FAULT = 23,
};

enum {
  XSAM_MMU_FAULT_INST_ACCESS = 1u << 0,
  XSAM_MMU_FAULT_INST_PAGE = 1u << 1,
  XSAM_MMU_FAULT_INST_GUEST_PAGE = 1u << 2,
  XSAM_MMU_FAULT_LOAD_PAGE = 1u << 3,
  XSAM_MMU_FAULT_STORE_PAGE = 1u << 4,
  XSAM_MMU_FAULT_LOAD_ACCESS = 1u << 5,
  XSAM_MMU_FAULT_STORE_ACCESS = 1u << 6,
  XSAM_MMU_FAULT_LOAD_GUEST_PAGE = 1u << 7,
  XSAM_MMU_FAULT_STORE_GUEST_PAGE = 1u << 8,
};

void xsam_mmu_fault_install_handlers(void);
void xsam_mmu_fault_reset(void);
void xsam_mmu_expect_fault(uint32_t mask);
int xsam_mmu_fault_assert(uint32_t expected_mask);
void xsam_mmu_record_fault(uint32_t mask, uintptr_t cause, uintptr_t epc, uintptr_t tval);
uint32_t xsam_mmu_fault_expected_mask(void);
uint32_t xsam_mmu_fault_seen_mask(void);
uintptr_t xsam_mmu_last_fault_cause(void);
uintptr_t xsam_mmu_last_fault_epc(void);
uintptr_t xsam_mmu_last_fault_tval(void);

#endif
