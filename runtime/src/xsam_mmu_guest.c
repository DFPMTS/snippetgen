#include "xsam/mmu_guest.h"

enum {
  XSAM_MMU_EXC_VS_ECALL = 10,
  XSAM_MMU_MSTATUS_MPP_MASK = (uintptr_t)3 << 11,
  XSAM_MMU_MSTATUS_MPP_M = (uintptr_t)3 << 11,
  XSAM_MMU_MSTATUS_MPV_MASK = (uintptr_t)1 << 39,
  XSAM_MMU_SSTATUS_SPP_MASK = (uintptr_t)1 << 8,
  XSAM_MMU_HSTATUS_SPV_MASK = (uintptr_t)1 << 7,
};

static uintptr_t g_host_vsatp;
static uintptr_t g_host_hstatus;
static uintptr_t g_host_henvcfg;
static uintptr_t g_host_hgatp;

#if defined(__riscv)
volatile int xsam_mmu_vs_active;
volatile int xsam_mmu_vs_returned;
uintptr_t xsam_mmu_vs_saved_sstatus;
uintptr_t xsam_mmu_vs_saved_hstatus;

extern void xsam_mmu_vs_enter_asm(void (*fn)(void *), void *arg);
extern void xsam_mmu_vs_resume_asm(void);

__asm__(
    ".align 2\n"
    ".globl xsam_mmu_vs_trampoline_asm\n"
    "xsam_mmu_vs_trampoline_asm:\n"
    "  mv a0, s1\n"
    "  jalr s0\n"
    "  ecall\n"
    "1:\n"
    "  j 1b\n"
    "\n"
    ".globl xsam_mmu_vs_enter_asm\n"
    "xsam_mmu_vs_enter_asm:\n"
    "  addi sp, sp, -32\n"
    "  sd ra, 24(sp)\n"
    "  sd s0, 16(sp)\n"
    "  sd s1, 8(sp)\n"
    "  mv s0, a0\n"
    "  mv s1, a1\n"
    "  la t0, xsam_mmu_vs_trampoline_asm\n"
    "  csrw sepc, t0\n"
    "  la t0, xsam_mmu_vs_saved_sstatus\n"
    "  ld t1, 0(t0)\n"
    "  li t2, 0x100\n"
    "  or t1, t1, t2\n"
    "  csrw sstatus, t1\n"
    "  la t0, xsam_mmu_vs_saved_hstatus\n"
    "  ld t1, 0(t0)\n"
    "  li t2, 0x80\n"
    "  or t1, t1, t2\n"
    "  csrw 0x600, t1\n"
    "  sret\n"
    "\n"
    ".globl xsam_mmu_vs_resume_asm\n"
    "xsam_mmu_vs_resume_asm:\n"
    "  la t0, xsam_mmu_vs_saved_sstatus\n"
    "  ld t1, 0(t0)\n"
    "  csrw sstatus, t1\n"
    "  la t0, xsam_mmu_vs_saved_hstatus\n"
    "  ld t1, 0(t0)\n"
    "  csrw 0x600, t1\n"
    "  ld s1, 8(sp)\n"
    "  ld s0, 16(sp)\n"
    "  ld ra, 24(sp)\n"
    "  addi sp, sp, 32\n"
    "  ret\n");

static uintptr_t xsam_mmu_read_sstatus(void) {
  uintptr_t value;

  __asm__ volatile("csrr %0, sstatus" : "=r"(value) : : "memory");
  return value;
}

static void xsam_mmu_write_sstatus(uintptr_t value) {
  __asm__ volatile("csrw sstatus, %0" : : "rK"(value) : "memory");
}
#endif

static uintptr_t xsam_mmu_pt_ppn(const xsam_mmu_page_table_t *pt) {
  if (pt == 0 || pt->root == 0) {
    return 0u;
  }
  return (uintptr_t)pt->root >> 12;
}

uintptr_t xsam_mmu_read_hyp_csr(uintptr_t csr_num) {
#if defined(__riscv)
  uintptr_t value;

  switch (csr_num) {
    case XSAM_MMU_CSR_VSATP:
      __asm__ volatile("csrr %0, 0x280" : "=r"(value) : : "memory");
      return value;
    case XSAM_MMU_CSR_HSTATUS:
      __asm__ volatile("csrr %0, 0x600" : "=r"(value) : : "memory");
      return value;
    case XSAM_MMU_CSR_HENVCFG:
      __asm__ volatile("csrr %0, 0x60a" : "=r"(value) : : "memory");
      return value;
    case XSAM_MMU_CSR_HGATP:
      __asm__ volatile("csrr %0, 0x680" : "=r"(value) : : "memory");
      return value;
    default:
      return 0u;
  }
#else
  switch (csr_num) {
    case XSAM_MMU_CSR_VSATP:
      return g_host_vsatp;
    case XSAM_MMU_CSR_HSTATUS:
      return g_host_hstatus;
    case XSAM_MMU_CSR_HENVCFG:
      return g_host_henvcfg;
    case XSAM_MMU_CSR_HGATP:
      return g_host_hgatp;
    default:
      return 0u;
  }
#endif
}

void xsam_mmu_write_hyp_csr(uintptr_t csr_num, uintptr_t value) {
#if defined(__riscv)
  switch (csr_num) {
    case XSAM_MMU_CSR_VSATP:
      __asm__ volatile("csrw 0x280, %0" : : "rK"(value) : "memory");
      return;
    case XSAM_MMU_CSR_HSTATUS:
      __asm__ volatile("csrw 0x600, %0" : : "rK"(value) : "memory");
      return;
    case XSAM_MMU_CSR_HENVCFG:
      __asm__ volatile("csrw 0x60a, %0" : : "rK"(value) : "memory");
      return;
    case XSAM_MMU_CSR_HGATP:
      __asm__ volatile("csrw 0x680, %0" : : "rK"(value) : "memory");
      return;
    default:
      return;
  }
#else
  switch (csr_num) {
    case XSAM_MMU_CSR_VSATP:
      g_host_vsatp = value;
      return;
    case XSAM_MMU_CSR_HSTATUS:
      g_host_hstatus = value;
      return;
    case XSAM_MMU_CSR_HENVCFG:
      g_host_henvcfg = value;
      return;
    case XSAM_MMU_CSR_HGATP:
      g_host_hgatp = value;
      return;
    default:
      return;
  }
#endif
}

uintptr_t xsam_mmu_make_vsatp_pt(const xsam_mmu_page_table_t *pt, uintptr_t asid) {
  return ((uintptr_t)pt->csr_mode << XSAM_MMU_SATP_MODE_SHIFT) |
         ((asid & 0xffffu) << XSAM_MMU_VSATP_ASID_SHIFT) |
         xsam_mmu_pt_ppn(pt);
}

uintptr_t xsam_mmu_make_hgatp_pt(const xsam_mmu_page_table_t *pt, uintptr_t vmid) {
  return ((uintptr_t)pt->csr_mode << XSAM_MMU_SATP_MODE_SHIFT) |
         ((vmid & 0x3fffu) << XSAM_MMU_HGATP_VMID_SHIFT) |
         xsam_mmu_pt_ppn(pt);
}

unsigned long xsam_mmu_hlv_d(uintptr_t addr) {
#if defined(__riscv)
  unsigned long value;

  __asm__ volatile(".insn i 0x73, 4, %0, %1, 0x6c0"
                   : "=r"(value)
                   : "r"(addr)
                   : "memory");
  return value;
#else
  return *(unsigned long *)addr;
#endif
}

void xsam_mmu_hsv_d(uintptr_t addr, unsigned long value) {
#if defined(__riscv)
  __asm__ volatile(".insn s 0x73, 4, %1, 0x6e0(%0)" : : "r"(addr), "r"(value) : "memory");
#else
  *(unsigned long *)addr = value;
#endif
}

void xsam_mmu_enter_vs(void (*fn)(void *), void *arg) {
  if (fn != 0) {
#if defined(__riscv)
    xsam_mmu_vs_saved_sstatus = xsam_mmu_read_sstatus();
    xsam_mmu_vs_saved_hstatus = xsam_mmu_read_hyp_csr(XSAM_MMU_CSR_HSTATUS);
    xsam_mmu_vs_returned = 0;
    xsam_mmu_vs_active = 1;
    xsam_mmu_vs_enter_asm(fn, arg);
    xsam_mmu_vs_active = 0;
    if (xsam_mmu_vs_returned == 0) {
      xsam_mmu_write_sstatus(xsam_mmu_vs_saved_sstatus);
      xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HSTATUS, xsam_mmu_vs_saved_hstatus);
    }
#else
    fn(arg);
#endif
  }
}

int xsam_mmu_handle_vs_trap(xsrt_trap_frame_t *frame) {
#if defined(__riscv)
  uintptr_t hstatus;

  if (frame == 0 ||
      xsam_mmu_vs_active == 0 ||
      frame->cause != (uintptr_t)XSAM_MMU_EXC_VS_ECALL) {
    return 0;
  }

  hstatus = xsam_mmu_read_hyp_csr(XSAM_MMU_CSR_HSTATUS);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HSTATUS, hstatus & ~XSAM_MMU_HSTATUS_SPV_MASK);
  xsam_mmu_vs_returned = 1;
  frame->epc = (uintptr_t)xsam_mmu_vs_resume_asm;
  frame->status = (frame->status &
                   ~(XSAM_MMU_MSTATUS_MPP_MASK | XSAM_MMU_MSTATUS_MPV_MASK)) |
                  XSAM_MMU_MSTATUS_MPP_M;
  return 1;
#else
  (void)frame;
  return 0;
#endif
}
