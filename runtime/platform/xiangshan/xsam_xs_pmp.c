#include "xsam_xs_platform.h"

#if defined(__riscv)
#define XSAM_XS_PMP_READ_CSR_CASE(csr_num_value, csr_operand) \
    case csr_num_value: __asm__ volatile("csrr %0, " #csr_operand : "=r"(value)); break
#define XSAM_XS_PMP_WRITE_CSR_CASE(csr_num_value, csr_operand) \
    case csr_num_value: __asm__ volatile("csrw " #csr_operand ", %0" : : "r"(value)); break
#define XSAM_XS_PMP_SET_CSR_CASE(csr_num_value, csr_operand) \
    case csr_num_value: __asm__ volatile("csrs " #csr_operand ", %0" : : "r"(value)); break
#define XSAM_XS_PMP_CLEAR_CSR_CASE(csr_num_value, csr_operand) \
    case csr_num_value: __asm__ volatile("csrc " #csr_operand ", %0" : : "r"(value)); break
#endif

static void xsam_xs_pmp_sync(void) {
#if defined(__riscv)
  __asm__ volatile("sfence.vma x0, x0" : : : "memory");
#endif
}

uint64_t xsam_xs_pmp_read_num(int csr_num) {
  uint64_t value = 0u;

#if defined(__riscv)
  switch (csr_num) {
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 0, 0x3a0);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 1, 0x3a1);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 2, 0x3a2);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 3, 0x3a3);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 4, 0x3a4);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 5, 0x3a5);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 6, 0x3a6);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 7, 0x3a7);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 8, 0x3a8);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 9, 0x3a9);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 10, 0x3aa);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 11, 0x3ab);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 12, 0x3ac);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 13, 0x3ad);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 14, 0x3ae);
    XSAM_XS_PMP_READ_CSR_CASE(XSAM_XS_PMPCFG_BASE + 15, 0x3af);
    case XSAM_XS_PMPADDR_BASE + 0: __asm__ volatile("csrr %0, pmpaddr0" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 1: __asm__ volatile("csrr %0, pmpaddr1" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 2: __asm__ volatile("csrr %0, pmpaddr2" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 3: __asm__ volatile("csrr %0, pmpaddr3" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 4: __asm__ volatile("csrr %0, pmpaddr4" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 5: __asm__ volatile("csrr %0, pmpaddr5" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 6: __asm__ volatile("csrr %0, pmpaddr6" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 7: __asm__ volatile("csrr %0, pmpaddr7" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 8: __asm__ volatile("csrr %0, pmpaddr8" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 9: __asm__ volatile("csrr %0, pmpaddr9" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 10: __asm__ volatile("csrr %0, pmpaddr10" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 11: __asm__ volatile("csrr %0, pmpaddr11" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 12: __asm__ volatile("csrr %0, pmpaddr12" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 13: __asm__ volatile("csrr %0, pmpaddr13" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 14: __asm__ volatile("csrr %0, pmpaddr14" : "=r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 15: __asm__ volatile("csrr %0, pmpaddr15" : "=r"(value)); break;
    default: break;
  }
#else
  (void) csr_num;
#endif
  return value;
}

void xsam_xs_pmp_write_num(int csr_num, uint64_t value) {
#if defined(__riscv)
  switch (csr_num) {
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 0, 0x3a0);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 1, 0x3a1);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 2, 0x3a2);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 3, 0x3a3);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 4, 0x3a4);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 5, 0x3a5);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 6, 0x3a6);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 7, 0x3a7);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 8, 0x3a8);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 9, 0x3a9);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 10, 0x3aa);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 11, 0x3ab);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 12, 0x3ac);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 13, 0x3ad);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 14, 0x3ae);
    XSAM_XS_PMP_WRITE_CSR_CASE(XSAM_XS_PMPCFG_BASE + 15, 0x3af);
    case XSAM_XS_PMPADDR_BASE + 0: __asm__ volatile("csrw pmpaddr0, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 1: __asm__ volatile("csrw pmpaddr1, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 2: __asm__ volatile("csrw pmpaddr2, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 3: __asm__ volatile("csrw pmpaddr3, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 4: __asm__ volatile("csrw pmpaddr4, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 5: __asm__ volatile("csrw pmpaddr5, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 6: __asm__ volatile("csrw pmpaddr6, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 7: __asm__ volatile("csrw pmpaddr7, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 8: __asm__ volatile("csrw pmpaddr8, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 9: __asm__ volatile("csrw pmpaddr9, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 10: __asm__ volatile("csrw pmpaddr10, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 11: __asm__ volatile("csrw pmpaddr11, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 12: __asm__ volatile("csrw pmpaddr12, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 13: __asm__ volatile("csrw pmpaddr13, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 14: __asm__ volatile("csrw pmpaddr14, %0" : : "r"(value)); break;
    case XSAM_XS_PMPADDR_BASE + 15: __asm__ volatile("csrw pmpaddr15, %0" : : "r"(value)); break;
    default: break;
  }
#else
  (void) csr_num;
  (void) value;
#endif
}

void xsam_xs_pmp_set_num(int csr_num, uint64_t value) {
#if defined(__riscv)
  switch (csr_num) {
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 0, 0x3a0);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 1, 0x3a1);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 2, 0x3a2);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 3, 0x3a3);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 4, 0x3a4);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 5, 0x3a5);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 6, 0x3a6);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 7, 0x3a7);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 8, 0x3a8);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 9, 0x3a9);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 10, 0x3aa);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 11, 0x3ab);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 12, 0x3ac);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 13, 0x3ad);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 14, 0x3ae);
    XSAM_XS_PMP_SET_CSR_CASE(XSAM_XS_PMPCFG_BASE + 15, 0x3af);
    default: break;
  }
#else
  (void) csr_num;
  (void) value;
#endif
}

void xsam_xs_pmp_clear_num(int csr_num, uint64_t value) {
#if defined(__riscv)
  switch (csr_num) {
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 0, 0x3a0);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 1, 0x3a1);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 2, 0x3a2);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 3, 0x3a3);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 4, 0x3a4);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 5, 0x3a5);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 6, 0x3a6);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 7, 0x3a7);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 8, 0x3a8);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 9, 0x3a9);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 10, 0x3aa);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 11, 0x3ab);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 12, 0x3ac);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 13, 0x3ad);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 14, 0x3ae);
    XSAM_XS_PMP_CLEAR_CSR_CASE(XSAM_XS_PMPCFG_BASE + 15, 0x3af);
    default: break;
  }
#else
  (void) csr_num;
  (void) value;
#endif
}

void xsam_xs_pmp_init(void) {
  for (uintptr_t index = 0u; index < XSAM_XS_PMP_COUNT; ++index) {
    xsam_xs_pmp_write_num(XSAM_XS_PMPADDR_BASE + index, ~(uint64_t) 0u);
  }

  xsam_xs_pmp_write_num(XSAM_XS_PMPCFG_BASE + 0u, 0u);
  xsam_xs_pmp_write_num(XSAM_XS_PMPCFG_BASE + 2u, 0u);
  xsam_xs_pmp_write_num(
      XSAM_XS_PMPCFG_BASE + 2u,
      ((uint64_t) (XSAM_XS_PMP_R | XSAM_XS_PMP_W | XSAM_XS_PMP_X | (XSAM_XS_PMP_A_NAPOT << 3)))
          << (8u * 7u));
  xsam_xs_pmp_sync();
}

void xsam_xs_pmp_enable_napot(
    uintptr_t pmp_reg,
    uintptr_t pmp_addr,
    uintptr_t pmp_size,
    int lock,
    uint8_t permission) {
  uint64_t set_content;
  uintptr_t cfg_offset;
  uintptr_t cfg_shift;

  if (pmp_reg >= XSAM_XS_PMP_COUNT || pmp_size == 0u || (pmp_size & (pmp_size - 1u)) != 0u) {
    return;
  }

  if (pmp_size != 4u) {
    pmp_addr |= (pmp_size >> 1u) - 1u;
  }

  xsam_xs_pmp_write_num(XSAM_XS_PMPADDR_BASE + pmp_reg, pmp_addr >> 2);

  set_content = (uint64_t) permission |
      ((uint64_t) (lock != 0) << 7u) |
      ((uint64_t) (pmp_size == 4u ? XSAM_XS_PMP_A_NA4 : XSAM_XS_PMP_A_NAPOT) << 3u);
  cfg_offset = pmp_reg > 7u ? 2u : 0u;
  cfg_shift = pmp_reg & 0x7u;
  xsam_xs_pmp_set_num(XSAM_XS_PMPCFG_BASE + cfg_offset, set_content << (cfg_shift * 8u));
  xsam_xs_pmp_sync();
}

void xsam_xs_pmp_enable_tor(
    uintptr_t pmp_reg,
    uintptr_t pmp_addr,
    uintptr_t pmp_size,
    int lock,
    uint8_t permission) {
  uint64_t set_content;
  uintptr_t cfg_offset;
  uintptr_t cfg_shift;

  if (pmp_reg >= XSAM_XS_PMP_COUNT || pmp_size == 0u) {
    return;
  }

  xsam_xs_pmp_write_num(XSAM_XS_PMPADDR_BASE + pmp_reg, (pmp_addr + pmp_size) >> 2);
  if (pmp_reg != 0u) {
    xsam_xs_pmp_write_num(XSAM_XS_PMPADDR_BASE + pmp_reg - 1u, pmp_addr >> 2);
  }

  set_content = (uint64_t) permission |
      ((uint64_t) (lock != 0) << 7u) |
      ((uint64_t) XSAM_XS_PMP_A_TOR << 3u);
  cfg_offset = pmp_reg > 7u ? 2u : 0u;
  cfg_shift = pmp_reg & 0x7u;
  xsam_xs_pmp_set_num(XSAM_XS_PMPCFG_BASE + cfg_offset, set_content << (cfg_shift * 8u));
  xsam_xs_pmp_sync();
}

void xsam_xs_pmp_disable(uintptr_t pmp_reg) {
  uintptr_t cfg_offset;
  uintptr_t cfg_shift;

  if (pmp_reg >= XSAM_XS_PMP_COUNT) {
    return;
  }
  cfg_offset = pmp_reg > 7u ? 2u : 0u;
  cfg_shift = pmp_reg & 0x7u;
  xsam_xs_pmp_clear_num(XSAM_XS_PMPCFG_BASE + cfg_offset, 0xffull << (cfg_shift * 8u));
  xsam_xs_pmp_write_num(XSAM_XS_PMPADDR_BASE + pmp_reg, ~(uint64_t) 0u);
  xsam_xs_pmp_sync();
}
