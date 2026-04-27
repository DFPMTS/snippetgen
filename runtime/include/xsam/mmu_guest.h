#ifndef XSAM_MMU_GUEST_H
#define XSAM_MMU_GUEST_H

#include <stdint.h>

#include "xsam/mmu.h"
#include "xsrt_trap.h"

enum {
  XSAM_MMU_CSR_VSATP = 0x280,
  XSAM_MMU_CSR_HSTATUS = 0x600,
  XSAM_MMU_CSR_HENVCFG = 0x60a,
  XSAM_MMU_CSR_HGATP = 0x680,
  XSAM_MMU_VSATP_ASID_SHIFT = 44,
  XSAM_MMU_HGATP_VMID_SHIFT = 44,
};

uintptr_t xsam_mmu_read_hyp_csr(uintptr_t csr_num);
void xsam_mmu_write_hyp_csr(uintptr_t csr_num, uintptr_t value);
uintptr_t xsam_mmu_make_vsatp_pt(const xsam_mmu_page_table_t *pt, uintptr_t asid);
uintptr_t xsam_mmu_make_hgatp_pt(const xsam_mmu_page_table_t *pt, uintptr_t vmid);
unsigned long xsam_mmu_hlv_d(uintptr_t addr);
void xsam_mmu_hsv_d(uintptr_t addr, unsigned long value);
void xsam_mmu_enter_vs(void (*fn)(void *), void *arg);
int xsam_mmu_handle_vs_trap(xsrt_trap_frame_t *frame);

#endif
