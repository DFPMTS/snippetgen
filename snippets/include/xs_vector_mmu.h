#ifndef XS_VECTOR_MMU_H
#define XS_VECTOR_MMU_H

#include <stddef.h>
#include <stdint.h>

enum {
  XS_VECTOR_MMU_VSETVLI_T0_A0_E8_M1_TA_MA = 0x0c0572d7u,
  XS_VECTOR_MMU_VSETVLI_T0_A0_E16_M1_TA_MA = 0x0c8572d7u,
  XS_VECTOR_MMU_VSETVLI_T0_A0_E32_M1_TA_MA = 0x0d0572d7u,
  XS_VECTOR_MMU_VSETVLI_T0_A0_E64_M1_TA_MA = 0x0d8572d7u,
  XS_VECTOR_MMU_VLE8_V0_A0 = 0x02050007u,
  XS_VECTOR_MMU_VLE8_V8_A0 = 0x02050407u,
  XS_VECTOR_MMU_VLE8_V9_A0 = 0x02050487u,
  XS_VECTOR_MMU_VLE16_V8_A0 = 0x02055407u,
  XS_VECTOR_MMU_VLE32_V8_A0 = 0x02056407u,
  XS_VECTOR_MMU_VLE64_V8_A0 = 0x02057407u,
  XS_VECTOR_MMU_VSE8_V8_A1 = 0x02058427u,
  XS_VECTOR_MMU_VSE16_V8_A1 = 0x0205d427u,
  XS_VECTOR_MMU_VSE32_V8_A1 = 0x0205e427u,
  XS_VECTOR_MMU_VSE64_V8_A1 = 0x0205f427u,
  XS_VECTOR_MMU_VLE8_V8_A0_MASKED = 0x00050407u,
  XS_VECTOR_MMU_VSE8_V8_A1_MASKED = 0x00058427u,
  XS_VECTOR_MMU_VLSE8_V8_A0_A1 = 0x0ab50407u,
  XS_VECTOR_MMU_VSSE8_V8_A0_A1 = 0x0ab50427u,
  XS_VECTOR_MMU_VLOXEI8_V8_A0_V9 = 0x0e950407u,
  XS_VECTOR_MMU_VSOXEI8_V8_A0_V9 = 0x0e950427u,
  XS_VECTOR_MMU_VLSEG2E8_V8_A0 = 0x22050407u,
  XS_VECTOR_MMU_VSSEG2E8_V8_A0 = 0x22050427u,
  XS_VECTOR_MMU_VLE8FF_V8_A0 = 0x03050407u,
  XS_VECTOR_MMU_VMV_X_S_A0_V8 = 0x42802557u,
  XS_VECTOR_MMU_VSLIDE1DOWN_VX_V8_V8_ZERO = 0x3e806457u,
  XS_VECTOR_MMU_MSTATUS_MPP_MASK = (uintptr_t)3u << 11,
  XS_VECTOR_MMU_MSTATUS_MPP_S = (uintptr_t)1u << 11,
  XS_VECTOR_MMU_MSTATUS_MPRV = (uintptr_t)1u << 17,
  XS_VECTOR_MMU_MSTATUS_SUM = (uintptr_t)1u << 18,
  XS_VECTOR_MMU_MSTATUS_MXR = (uintptr_t)1u << 19,
  XS_VECTOR_MMU_MSTATUS_MPV = (uintptr_t)1ull << 39,
  XS_VECTOR_MMU_MSTATUS_VS_DIRTY = (uintptr_t)3u << 9,
};

#if !defined(__riscv)
static uint8_t xs_vector_mmu_shadow[512];
static uint8_t xs_vector_mmu_index_shadow[512];
static uint8_t xs_vector_mmu_mask_shadow[64];
static size_t xs_vector_mmu_shadow_vl;
static size_t xs_vector_mmu_shadow_vstart;
static size_t xs_vector_mmu_shadow_eew_bytes = 1u;
#endif

static inline uintptr_t xs_vector_mmu_host_access_status(uintptr_t saved_status) {
  return (saved_status & ~(XS_VECTOR_MMU_MSTATUS_MPP_MASK | XS_VECTOR_MMU_MSTATUS_MPV)) |
      XS_VECTOR_MMU_MSTATUS_MPP_S |
      XS_VECTOR_MMU_MSTATUS_MPRV |
      XS_VECTOR_MMU_MSTATUS_VS_DIRTY;
}

static inline uintptr_t xs_vector_mmu_guest_access_status(uintptr_t saved_status) {
  return xs_vector_mmu_host_access_status(saved_status) | XS_VECTOR_MMU_MSTATUS_MPV;
}

static inline void xs_vector_mmu_enable_vector_state(void) {
#if defined(__riscv)
  uintptr_t status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(status) : : "memory");
  status |= XS_VECTOR_MMU_MSTATUS_VS_DIRTY;
  __asm__ volatile("csrw mstatus, %0" : : "r"(status) : "memory");
#endif
}

static inline void xs_vector_mmu_enable_vs_vector_state(void) {
#if defined(__riscv)
  uintptr_t status;

  __asm__ volatile("csrr %0, 0x200" : "=r"(status) : : "memory");
  status |= XS_VECTOR_MMU_MSTATUS_VS_DIRTY;
  __asm__ volatile("csrw 0x200, %0" : : "r"(status) : "memory");
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

static inline uintptr_t xs_vector_mmu_enter_guest_access(void) {
#if defined(__riscv)
  uintptr_t status;
  uintptr_t new_status;

  __asm__ volatile("csrr %0, mstatus" : "=r"(status) : : "memory");
  new_status = xs_vector_mmu_guest_access_status(status);
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

static inline void xs_vector_mmu_leave_guest_access(uintptr_t saved_status) {
  xs_vector_mmu_leave_host_access(saved_status);
}

static inline size_t xs_vector_mmu_set_vl_shadow(size_t requested_vl, size_t eew_bytes) {
#if !defined(__riscv)
  xs_vector_mmu_shadow_vl = requested_vl;
  xs_vector_mmu_shadow_vstart = 0u;
  xs_vector_mmu_shadow_eew_bytes = eew_bytes;
#else
  (void)requested_vl;
  (void)eew_bytes;
#endif
  return requested_vl;
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
  return xs_vector_mmu_set_vl_shadow(requested_vl, 1u);
#endif
}

static inline size_t xs_vector_mmu_set_vl_e16_m1(size_t requested_vl) {
#if defined(__riscv)
  uintptr_t actual_vl;

  __asm__ volatile(
      "mv a0, %1\n\t"
      ".word 0x0c8572d7\n\t"
      "mv %0, t0\n\t"
      : "=r"(actual_vl)
      : "r"(requested_vl)
      : "a0", "t0", "memory");
  return (size_t)actual_vl;
#else
  return xs_vector_mmu_set_vl_shadow(requested_vl, 2u);
#endif
}

static inline size_t xs_vector_mmu_set_vl_e32_m1(size_t requested_vl) {
#if defined(__riscv)
  uintptr_t actual_vl;

  __asm__ volatile(
      "mv a0, %1\n\t"
      ".word 0x0d0572d7\n\t"
      "mv %0, t0\n\t"
      : "=r"(actual_vl)
      : "r"(requested_vl)
      : "a0", "t0", "memory");
  return (size_t)actual_vl;
#else
  return xs_vector_mmu_set_vl_shadow(requested_vl, 4u);
#endif
}

static inline size_t xs_vector_mmu_set_vl_e64_m1(size_t requested_vl) {
#if defined(__riscv)
  uintptr_t actual_vl;

  __asm__ volatile(
      "mv a0, %1\n\t"
      ".word 0x0d8572d7\n\t"
      "mv %0, t0\n\t"
      : "=r"(actual_vl)
      : "r"(requested_vl)
      : "a0", "t0", "memory");
  return (size_t)actual_vl;
#else
  return xs_vector_mmu_set_vl_shadow(requested_vl, 8u);
#endif
}

static inline size_t xs_vector_mmu_read_vl(void) {
#if defined(__riscv)
  uintptr_t value;

  __asm__ volatile("csrr %0, 0xc20" : "=r"(value) : : "memory");
  return (size_t)value;
#else
  return xs_vector_mmu_shadow_vl;
#endif
}

static inline size_t xs_vector_mmu_read_vstart(void) {
#if defined(__riscv)
  uintptr_t value;

  __asm__ volatile("csrr %0, 0x008" : "=r"(value) : : "memory");
  return (size_t)value;
#else
  return xs_vector_mmu_shadow_vstart;
#endif
}

static inline void xs_vector_mmu_write_vstart(size_t value) {
#if defined(__riscv)
  __asm__ volatile("csrw 0x008, %0" : : "r"(value) : "memory");
#else
  xs_vector_mmu_shadow_vstart = value;
#endif
}

#if !defined(__riscv)
static inline void xs_vector_mmu_shadow_load(const void *addr, size_t eew_bytes) {
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t len = xs_vector_mmu_shadow_vl * eew_bytes;
  size_t start = xs_vector_mmu_shadow_vstart * eew_bytes;
  size_t index;

  for (index = start; index < len; ++index) {
    xs_vector_mmu_shadow[index] = src[index];
  }
  xs_vector_mmu_shadow_vstart = 0u;
}

static inline void xs_vector_mmu_shadow_store(void *addr, size_t eew_bytes) {
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t len = xs_vector_mmu_shadow_vl * eew_bytes;
  size_t start = xs_vector_mmu_shadow_vstart * eew_bytes;
  size_t index;

  for (index = start; index < len; ++index) {
    dst[index] = xs_vector_mmu_shadow[index];
  }
  xs_vector_mmu_shadow_vstart = 0u;
}

static inline int xs_vector_mmu_mask_active(size_t index) {
  return (xs_vector_mmu_mask_shadow[index / 8u] & (uint8_t)(1u << (index % 8u))) != 0u;
}
#endif

static inline void xs_vector_mmu_vle8_v0_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02050007\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t len = (xs_vector_mmu_shadow_vl + 7u) / 8u;
  size_t index;

  for (index = 0u; index < len; ++index) {
    xs_vector_mmu_mask_shadow[index] = src[index];
  }
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
  xs_vector_mmu_shadow_load(addr, 1u);
#endif
}

static inline void xs_vector_mmu_vle8_v9_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02050487\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = 0u; index < xs_vector_mmu_shadow_vl; ++index) {
    xs_vector_mmu_index_shadow[index] = src[index];
  }
#endif
}

static inline void xs_vector_mmu_vle16_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02055407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  xs_vector_mmu_shadow_load(addr, 2u);
#endif
}

static inline void xs_vector_mmu_vle32_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02056407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  xs_vector_mmu_shadow_load(addr, 4u);
#endif
}

static inline void xs_vector_mmu_vle64_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x02057407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  xs_vector_mmu_shadow_load(addr, 8u);
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
  xs_vector_mmu_shadow_store(addr, 1u);
#endif
}

static inline void xs_vector_mmu_vse16_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a1, %0\n\t"
      ".word 0x0205d427\n\t"
      :
      : "r"(addr)
      : "a1", "memory");
#else
  xs_vector_mmu_shadow_store(addr, 2u);
#endif
}

static inline void xs_vector_mmu_vse32_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a1, %0\n\t"
      ".word 0x0205e427\n\t"
      :
      : "r"(addr)
      : "a1", "memory");
#else
  xs_vector_mmu_shadow_store(addr, 4u);
#endif
}

static inline void xs_vector_mmu_vse64_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a1, %0\n\t"
      ".word 0x0205f427\n\t"
      :
      : "r"(addr)
      : "a1", "memory");
#else
  xs_vector_mmu_shadow_store(addr, 8u);
#endif
}

static inline void xs_vector_mmu_vle8_v8_masked(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x00050407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    if (xs_vector_mmu_mask_active(index)) {
      xs_vector_mmu_shadow[index] = src[index];
    }
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vse8_v8_masked(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a1, %0\n\t"
      ".word 0x00058427\n\t"
      :
      : "r"(addr)
      : "a1", "memory");
#else
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    if (xs_vector_mmu_mask_active(index)) {
      dst[index] = xs_vector_mmu_shadow[index];
    }
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vlse8_v8_direct(const void *addr, intptr_t stride) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      "mv a1, %1\n\t"
      ".word 0x0ab50407\n\t"
      :
      : "r"(addr), "r"(stride)
      : "a0", "a1", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    xs_vector_mmu_shadow[index] = src[index * (size_t)stride];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vsse8_v8_direct(void *addr, intptr_t stride) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      "mv a1, %1\n\t"
      ".word 0x0ab50427\n\t"
      :
      : "r"(addr), "r"(stride)
      : "a0", "a1", "memory");
#else
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    dst[index * (size_t)stride] = xs_vector_mmu_shadow[index];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vloxei8_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x0e950407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    xs_vector_mmu_shadow[index] = src[xs_vector_mmu_index_shadow[index]];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vsoxei8_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x0e950427\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    dst[xs_vector_mmu_index_shadow[index]] = xs_vector_mmu_shadow[index];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vlseg2e8_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x22050407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  const volatile uint8_t *src = (const volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    xs_vector_mmu_shadow[index] = src[index * 2u];
    xs_vector_mmu_index_shadow[index] = src[index * 2u + 1u];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vsseg2e8_v8_direct(void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x22050427\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  volatile uint8_t *dst = (volatile uint8_t *)addr;
  size_t index;

  for (index = xs_vector_mmu_shadow_vstart; index < xs_vector_mmu_shadow_vl; ++index) {
    dst[index * 2u] = xs_vector_mmu_shadow[index];
    dst[index * 2u + 1u] = xs_vector_mmu_index_shadow[index];
  }
  xs_vector_mmu_shadow_vstart = 0u;
#endif
}

static inline void xs_vector_mmu_vle8ff_v8_direct(const void *addr) {
#if defined(__riscv)
  __asm__ volatile(
      "mv a0, %0\n\t"
      ".word 0x03050407\n\t"
      :
      : "r"(addr)
      : "a0", "memory");
#else
  xs_vector_mmu_shadow_load(addr, 1u);
#endif
}

static inline uint8_t xs_vector_mmu_vmv_x_s_v8_u8(void) {
#if defined(__riscv)
  uintptr_t value;

  __asm__ volatile(
      ".word 0x42802557\n\t"
      "mv %0, a0\n\t"
      : "=r"(value)
      :
      : "a0", "memory");
  return (uint8_t)value;
#else
  return xs_vector_mmu_shadow[0];
#endif
}

static inline void xs_vector_mmu_vslide1down_v8(void) {
#if defined(__riscv)
  __asm__ volatile(".word 0x3e806457" : : : "memory");
#else
  size_t index;

  for (index = 0u; index + 1u < xs_vector_mmu_shadow_vl; ++index) {
    xs_vector_mmu_shadow[index] = xs_vector_mmu_shadow[index + 1u];
  }
  if (xs_vector_mmu_shadow_vl > 0u) {
    xs_vector_mmu_shadow[xs_vector_mmu_shadow_vl - 1u] = 0u;
  }
#endif
}

#endif
