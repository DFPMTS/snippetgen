#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_RUNTIME_IDENTITY_SIZE = 0x40000000ull,
  XS_VEC_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_PROT_READ_FAULT = XSAM_MMU_PTE_X | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_PROT_STORE_FAULT = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_SV39_SRC_VA = 0x900200000ull,
  XS_VEC_SV39_DST_VA = 0x900201000ull,
  XS_VEC_CROSS_SRC_VA = 0x900210000ull,
  XS_VEC_CROSS_DST_VA = 0x900220000ull,
  XS_VEC_LOAD_PAGE_FAULT_VA = 0x900300000ull,
  XS_VEC_STORE_PAGE_FAULT_VA = 0x900301000ull,
  XS_VEC_LOAD_PERM_FAULT_VA = 0x900302000ull,
  XS_VEC_STORE_PERM_FAULT_VA = 0x900303000ull,
  XS_VEC_SINGLE_LEN = 16u,
  XS_VEC_CROSS_LEN = 16u,
  XS_VEC_CROSS_OFFSET = XS_VEC_PAGE_SIZE - 8u,
};

enum {
  XS_VEC_FAIL_VECTOR_SETUP = 10,
  XS_VEC_FAIL_BARE_HIT = 11,
  XS_VEC_FAIL_SV39_SETUP = 12,
  XS_VEC_FAIL_SV39_HIT = 13,
  XS_VEC_FAIL_CROSS_4K = 14,
  XS_VEC_FAIL_LOAD_PAGE_FAULT = 15,
  XS_VEC_FAIL_STORE_PAGE_FAULT = 16,
  XS_VEC_FAIL_LOAD_PERM_FAULT = 17,
  XS_VEC_FAIL_STORE_PERM_FAULT = 18,
};

static xsam_mmu_page_table_t g_stage1;
static uint8_t g_bare_src[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_bare_dst[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_sv39_src[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_sv39_dst[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_cross_src[XS_VEC_PAGE_SIZE * 2u] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_cross_dst[XS_VEC_PAGE_SIZE * 2u] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_perm_load_src[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));
static uint8_t g_perm_store_dst[XS_VEC_PAGE_SIZE] __attribute__((aligned(XS_VEC_PAGE_SIZE)));

static void xs_vec_fill(uint8_t *base, size_t offset, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 7u));
  }
}

static void xs_vec_zero(uint8_t *base, size_t offset, size_t len) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = 0u;
  }
}

static int xs_vec_mem_eq(const uint8_t *lhs, const uint8_t *rhs, size_t len) {
  const volatile uint8_t *left = (const volatile uint8_t *)lhs;
  const volatile uint8_t *right = (const volatile uint8_t *)rhs;
  size_t index;

  for (index = 0u; index < len; ++index) {
    if (left[index] != right[index]) {
      return 0;
    }
  }
  return 1;
}

static int xs_vec_roundtrip(
    uintptr_t load_addr,
    uintptr_t store_addr,
    const uint8_t *expected,
    uint8_t *observed,
    size_t len,
    int translated) {
  uintptr_t saved_status;
  int match;

  saved_status = 0u;
  if (xs_vector_mmu_set_vl_e8_m1(len) != len) {
    return -1;
  }
  if (translated != 0) {
    saved_status = xs_vector_mmu_enter_host_access();
  }
  xs_vector_mmu_vle8_v8_direct((const void *)load_addr);
  xs_vector_mmu_vse8_v8_direct((void *)store_addr);
  match = xs_vec_mem_eq(expected, observed, len);
  if (translated != 0) {
    xs_vector_mmu_leave_host_access(saved_status);
  }
  return match ? 0 : -1;
}

static int xs_vec_load_only(
    uintptr_t load_addr,
    const uint8_t *expected,
    size_t len,
    int translated) {
  uintptr_t saved_status;
  size_t index;

  saved_status = 0u;
  if (xs_vector_mmu_set_vl_e8_m1(len) != len) {
    return -1;
  }
  if (translated != 0) {
    saved_status = xs_vector_mmu_enter_host_access();
  }
  xs_vector_mmu_vle8_v8_direct((const void *)load_addr);
  for (index = 0u; index < len; ++index) {
    if (xs_vector_mmu_vmv_x_s_v8_u8() != expected[index]) {
      if (translated != 0) {
        xs_vector_mmu_leave_host_access(saved_status);
      }
      return -1;
    }
    xs_vector_mmu_vslide1down_v8();
  }
  if (translated != 0) {
    xs_vector_mmu_leave_host_access(saved_status);
  }
  return 0;
}

static int xs_vec_map_page(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    const void *page,
    uintptr_t prot) {
  xsam_mmu_pt_map(pt, va, (uintptr_t)page, prot);
  return xsam_mmu_pt_leaf_ptr(pt, va) == 0 ? -1 : 0;
}

static int xs_vec_map_two_pages(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    const void *pages,
    uintptr_t prot) {
  const uint8_t *base = (const uint8_t *)pages;

  return xs_vec_map_page(pt, va, base, prot) != 0 ||
      xs_vec_map_page(pt, va + XS_VEC_PAGE_SIZE, base + XS_VEC_PAGE_SIZE, prot) != 0;
}

static int xs_vec_setup_sv39(void) {
  xsam_mmu_pt_init_sv39(&g_stage1);
  xsam_mmu_pt_map_identity_range(
      &g_stage1,
      XS_VEC_RUNTIME_IDENTITY_BASE,
      XS_VEC_RUNTIME_IDENTITY_SIZE,
      XS_VEC_PROT_RWXAD);

  if (xs_vec_map_page(&g_stage1, XS_VEC_SV39_SRC_VA, g_sv39_src, XS_VEC_PROT_RWXAD) != 0 ||
      xs_vec_map_page(&g_stage1, XS_VEC_SV39_DST_VA, g_sv39_dst, XS_VEC_PROT_RWXAD) != 0 ||
      xs_vec_map_two_pages(&g_stage1, XS_VEC_CROSS_SRC_VA, g_cross_src, XS_VEC_PROT_RWXAD) != 0 ||
      xs_vec_map_two_pages(&g_stage1, XS_VEC_CROSS_DST_VA, g_cross_dst, XS_VEC_PROT_RWXAD) != 0 ||
      xs_vec_map_page(&g_stage1, XS_VEC_LOAD_PERM_FAULT_VA, g_perm_load_src, XS_VEC_PROT_READ_FAULT) != 0 ||
      xs_vec_map_page(&g_stage1, XS_VEC_STORE_PERM_FAULT_VA, g_perm_store_dst, XS_VEC_PROT_STORE_FAULT) != 0) {
    return -1;
  }

  xs_vector_mmu_clear_sum_mxr();
  xsam_mmu_enable_sv39(&g_stage1, 0u);
  return 0;
}

static int xs_vec_bare_hit(void) {
  xsam_mmu_enable_bare();
  xs_vec_fill(g_bare_src, 0u, XS_VEC_SINGLE_LEN, 0x21u);
  xs_vec_zero(g_bare_dst, 0u, XS_VEC_SINGLE_LEN);
  return xs_vec_roundtrip(
      (uintptr_t)g_bare_src,
      (uintptr_t)g_bare_dst,
      g_bare_src,
      g_bare_dst,
      XS_VEC_SINGLE_LEN,
      0);
}

static int xs_vec_bare_load_hit(void) {
  xsam_mmu_enable_bare();
  xs_vec_fill(g_bare_src, 0u, XS_VEC_SINGLE_LEN, 0x21u);
  return xs_vec_load_only(
      (uintptr_t)g_bare_src,
      g_bare_src,
      XS_VEC_SINGLE_LEN,
      0);
}

static int xs_vec_sv39_hit(void) {
  xs_vec_fill(g_sv39_src, 0u, XS_VEC_SINGLE_LEN, 0x41u);
  xs_vec_zero(g_sv39_dst, 0u, XS_VEC_SINGLE_LEN);
  return xs_vec_roundtrip(
      XS_VEC_SV39_SRC_VA,
      XS_VEC_SV39_DST_VA,
      g_sv39_src,
      g_sv39_dst,
      XS_VEC_SINGLE_LEN,
      1);
}

static int xs_vec_sv39_load_hit(void) {
  xs_vec_fill(g_sv39_src, 0u, XS_VEC_SINGLE_LEN, 0x41u);
  return xs_vec_load_only(
      XS_VEC_SV39_SRC_VA,
      g_sv39_src,
      XS_VEC_SINGLE_LEN,
      1);
}

static int xs_vec_cross_4k_hit(void) {
  xs_vec_fill(g_cross_src, XS_VEC_CROSS_OFFSET, XS_VEC_CROSS_LEN, 0x61u);
  xs_vec_zero(g_cross_dst, XS_VEC_CROSS_OFFSET, XS_VEC_CROSS_LEN);
  return xs_vec_roundtrip(
      XS_VEC_CROSS_SRC_VA + XS_VEC_CROSS_OFFSET,
      XS_VEC_CROSS_DST_VA + XS_VEC_CROSS_OFFSET,
      g_cross_src + XS_VEC_CROSS_OFFSET,
      g_cross_dst + XS_VEC_CROSS_OFFSET,
      XS_VEC_CROSS_LEN,
      1);
}

static int xs_vec_expect_fault(uint32_t mask, uintptr_t cause, uintptr_t addr, int store) {
  uintptr_t saved_status;

  xsam_mmu_expect_fault(mask);
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  if (store) {
    xs_vector_mmu_vse8_v8_direct((void *)addr);
  } else {
    xs_vector_mmu_vle8_v8_direct((const void *)addr);
  }
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_assert(mask) != 0) {
    return -1;
  }
  if (xsam_mmu_last_fault_cause() != cause || xsam_mmu_last_fault_tval() != addr) {
    return -1;
  }
  return 0;
}

static int xs_vec_basic_fault(void) {
  if (xs_vec_expect_fault(
          XSAM_MMU_FAULT_LOAD_PAGE,
          XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
          XS_VEC_LOAD_PAGE_FAULT_VA,
          0) != 0) {
    return XS_VEC_FAIL_LOAD_PAGE_FAULT;
  }
  return 0;
}

static int xs_vec_faults(void) {
  int rc;

  rc = xs_vec_basic_fault();
  if (rc != 0) {
    return rc;
  }
  if (xs_vec_expect_fault(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          XS_VEC_STORE_PAGE_FAULT_VA,
          1) != 0) {
    return XS_VEC_FAIL_STORE_PAGE_FAULT;
  }
  if (xs_vec_expect_fault(
          XSAM_MMU_FAULT_LOAD_PAGE,
          XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
          XS_VEC_LOAD_PERM_FAULT_VA,
          0) != 0) {
    return XS_VEC_FAIL_LOAD_PERM_FAULT;
  }
  if (xs_vec_expect_fault(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          XS_VEC_STORE_PERM_FAULT_VA,
          1) != 0) {
    return XS_VEC_FAIL_STORE_PERM_FAULT;
  }
  return 0;
}

static int xs_vec_common_setup(void) {
  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_FAIL_VECTOR_SETUP;
  }

  xsam_mmu_fault_install_handlers();
  return 0;
}

static int xs_vec_run_smoke(void) {
  int rc;

  rc = xs_vec_common_setup();
  if (rc != 0) {
    return rc;
  }
  if (xs_vec_bare_load_hit() != 0) {
    return XS_VEC_FAIL_BARE_HIT;
  }
  if (xs_vec_setup_sv39() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAIL_SV39_SETUP;
  }
  if (xs_vec_sv39_load_hit() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAIL_SV39_HIT;
  }

  rc = xs_vec_basic_fault();
  xsam_mmu_enable_bare();
  return rc;
}

static int xs_vec_run_replay_repro(void) {
  int rc;

  rc = xs_vec_common_setup();
  if (rc != 0) {
    return rc;
  }
  if (xs_vec_bare_hit() != 0) {
    return XS_VEC_FAIL_BARE_HIT;
  }
  if (xs_vec_setup_sv39() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAIL_SV39_SETUP;
  }
  if (xs_vec_sv39_hit() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAIL_SV39_HIT;
  }
  if (xs_vec_cross_4k_hit() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAIL_CROSS_4K;
  }

  rc = xs_vec_faults();
  xsam_mmu_enable_bare();
  return rc;
}

int kmh_v2_vector_mmu_smoke_main(void) {
  return xs_vec_run_smoke();
}

int kmh_v2_vector_mmu_replay_repro_main(void) {
  return xs_vec_run_replay_repro();
}
