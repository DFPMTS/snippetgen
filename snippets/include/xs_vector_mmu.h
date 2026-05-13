#ifndef XS_VECTOR_MMU_H
#define XS_VECTOR_MMU_H

#include <stddef.h>
#include <stdint.h>

enum {
  XS_VECTOR_MMU_VSETVLI_T0_A0_E8_M1_TA_MA = 0x0c0572d7u,
  XS_VECTOR_MMU_VLE8_V8_A0 = 0x02050407u,
  XS_VECTOR_MMU_VSE8_V8_A1 = 0x02058427u,
  XS_VECTOR_MMU_MSTATUS_MPP_MASK = (uintptr_t)3u << 11,
  XS_VECTOR_MMU_MSTATUS_MPP_S = (uintptr_t)1u << 11,
  XS_VECTOR_MMU_MSTATUS_MPRV = (uintptr_t)1u << 17,
  XS_VECTOR_MMU_MSTATUS_SUM = (uintptr_t)1u << 18,
  XS_VECTOR_MMU_MSTATUS_MXR = (uintptr_t)1u << 19,
  XS_VECTOR_MMU_MSTATUS_VS_DIRTY = (uintptr_t)3u << 9,
};

#if !defined(__riscv)
static uint8_t xs_vector_mmu_shadow[256];
static size_t xs_vector_mmu_shadow_len;
#endif

static inline uintptr_t xs_vector_mmu_host_access_status(uintptr_t saved_status) {
  return (saved_status & ~((uintptr_t)XS_VECTOR_MMU_MSTATUS_MPP_MASK)) |
      XS_VECTOR_MMU_MSTATUS_MPP_S |
      XS_VECTOR_MMU_MSTATUS_MPRV |
      XS_VECTOR_MMU_MSTATUS_VS_DIRTY;
}

static inline void xs_vector_mmu_enable_vector_state(void) {
#if defined(__riscv)
  uintptr_t status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(status) : : "memory");
  status |= XS_VECTOR_MMU_MSTATUS_VS_DIRTY;
  __asm__ volatile("csrw mstatus, %0" : : "r"(status) : "memory");
#endif
}

static inline void xs_vector_mmu_clear_sum_mxr(void) {
#if defined(__riscv)
  uintptr_t status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(status) : : "memory");
  status &= ~(XS_VECTOR_MMU_MSTATUS_SUM | XS_VECTOR_MMU_MSTATUS_MXR);
  __asm__ volatile("csrw mstatus, %0" : : "r"(status) : "memory");
#endif
}

static inline uintptr_t xs_vector_mmu_enter_host_access(void) {
#if defined(__riscv)
  uintptr_t status;
  uintptr_t new_status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(status) : : "memory");
  new_status = xs_vector_mmu_host_access_status(status);
  __asm__ volatile("csrw mstatus, %0" : : "r"(new_status) : "memory");
  return status;
#else
  return 0u;
#endif
}

static inline void xs_vector_mmu_leave_host_access(uintptr_t saved_status) {
#if defined(__riscv)
  __asm__ volatile("csrw mstatus, %0" : : "r"(saved_status) : "memory");
#else
  (void)saved_status;
#endif
}

static inline size_t xs_vector_mmu_set_vl_e8_m1(size_t requested_vl) {
#if defined(__riscv)
  uintptr_t actual_vl;

  __asm__ volatile(
      "mv a0, %1\n\t"
      ".word 0x0c0572d7\n\t"
      "mv %0, t0\n\t"
      : "=r"(actual_vl)
      : "r"(requested_vl)
      : "a0", "t0", "memory");
  return (size_t)actual_vl;
#else
  xs_vector_mmu_shadow_len = requested_vl;
  return requested_vl;
#endif
}

static inline void xs_vector_mmu_vle8_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02050407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = 0u; index < xs_vector_mmu_shadow_len; ++index) {
    xs_vector_mmu_shadow[index] = src[index];
  }
#endif
}

static inline void xs_vector_mmu_vse8_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a1, %0\n\t"
      ".word 0x02058427\n\t"
      :
      : "r"(addr)
      : "a1", "memory");
#else
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t index;

  for (index = 0u; index < xs_vector_mmu_shadow_len; ++index) {
    dst[index] = xs_vector_mmu_shadow[index];
  }
#endif
}

static inline void xs_vector_mmu_fence(void) {
#if defined(__riscv)
  __asm__ volatile("fence rw, rw" ::: "memory");
#endif
}

#endif
