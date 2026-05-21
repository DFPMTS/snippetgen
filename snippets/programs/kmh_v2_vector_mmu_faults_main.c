#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_FAULT_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_FAULT_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_FAULT_RUNTIME_IDENTITY_SIZE = 0x40000000ull,
  XS_VEC_FAULT_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FAULT_PROT_READ = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A,
  XS_VEC_FAULT_PROT_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FAULT_PROT_NO_READ = XSAM_MMU_PTE_X | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FAULT_PROT_NO_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FAULT_LOAD_CROSS_VA = 0x900500000ull,
  XS_VEC_FAULT_STORE_CROSS_VA = 0x900510000ull,
  XS_VEC_FAULT_MASK_SRC_VA = 0x900520000ull,
  XS_VEC_FAULT_MASK_DST_VA = 0x900530000ull,
  XS_VEC_FAULT_MASK_ON_LOAD_VA = 0x900540000ull,
  XS_VEC_FAULT_MASK_ON_STORE_VA = 0x900550000ull,
  XS_VEC_FAULT_LOAD_PERM_CROSS_VA = 0x900560000ull,
  XS_VEC_FAULT_STORE_PERM_CROSS_VA = 0x900570000ull,
  XS_VEC_FAULT_CROSS_OFFSET = XS_VEC_FAULT_PAGE_SIZE - 8u,
  XS_VEC_FAULT_CROSS_LEN = 16u,
  XS_VEC_FAULT_MASK_LEN = 16u,
  XS_VEC_FAULT_MASK_BYTES = (XS_VEC_FAULT_MASK_LEN + 7u) / 8u,
};

enum {
  XS_VEC_FAULT_FAIL_VECTOR_SETUP = 30,
  XS_VEC_FAULT_FAIL_SETUP = 31,
  XS_VEC_FAULT_FAIL_CROSS_LOAD = 32,
  XS_VEC_FAULT_FAIL_CROSS_STORE = 33,
  XS_VEC_FAULT_FAIL_MASKED_LOAD_SUPPRESS = 34,
  XS_VEC_FAULT_FAIL_MASKED_STORE_SUPPRESS = 35,
  XS_VEC_FAULT_FAIL_MASKED_LOAD_TRIGGER = 36,
  XS_VEC_FAULT_FAIL_MASKED_STORE_TRIGGER = 37,
  XS_VEC_FAULT_FAIL_PERM_LOAD = 38,
  XS_VEC_FAULT_FAIL_PERM_STORE = 39,
};

static xsam_mmu_page_table_t g_fault_stage1;
static uint8_t g_cross_load_page[XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_cross_store_pages[2u * XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_mask_src_page[XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_mask_dst_pages[2u * XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_mask_on_load_page[XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_mask_on_store_pages[2u * XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_perm_load_pages[2u * XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_perm_store_pages[2u * XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));
static uint8_t g_mask_bytes[XS_VEC_FAULT_PAGE_SIZE] __attribute__((aligned(XS_VEC_FAULT_PAGE_SIZE)));

static void xs_vec_fault_fill(uint8_t *base, size_t offset, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 11u));
  }
}

static void xs_vec_fault_set(uint8_t *base, size_t offset, size_t len, uint8_t value) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = value;
  }
}

static int xs_vec_fault_region_eq(const uint8_t *base, size_t offset, const uint8_t *expected, size_t len) {
  const volatile uint8_t *lhs = (const volatile uint8_t *)(base + offset);
  const volatile uint8_t *rhs = (const volatile uint8_t *)expected;
  size_t index;

  for (index = 0u; index < len; ++index) {
    if (lhs[index] != rhs[index]) {
      return 0;
    }
  }
  return 1;
}

static int xs_vec_fault_region_value(const uint8_t *base, size_t offset, size_t len, uint8_t value) {
  const volatile uint8_t *src = (const volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    if (src[index] != value) {
      return 0;
    }
  }
  return 1;
}

static void xs_vec_fault_make_mask(uint16_t bits) {
  xs_vec_fault_set(g_mask_bytes, 0u, XS_VEC_FAULT_MASK_BYTES, 0u);
  g_mask_bytes[0] = (uint8_t)(bits & 0xffu);
  g_mask_bytes[1] = (uint8_t)((bits >> 8) & 0xffu);
}

static int xs_vec_fault_setup(void) {
  xsam_mmu_pt_init_sv39(&g_fault_stage1);
  xsam_mmu_pt_map_identity_range(
      &g_fault_stage1,
      XS_VEC_FAULT_RUNTIME_IDENTITY_BASE,
      XS_VEC_FAULT_RUNTIME_IDENTITY_SIZE,
      XS_VEC_FAULT_PROT_RWXAD);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_LOAD_CROSS_VA, (uintptr_t)g_cross_load_page, XS_VEC_FAULT_PROT_READ);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_STORE_CROSS_VA, (uintptr_t)g_cross_store_pages, XS_VEC_FAULT_PROT_WRITE);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_MASK_SRC_VA, (uintptr_t)g_mask_src_page, XS_VEC_FAULT_PROT_READ);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_MASK_DST_VA, (uintptr_t)g_mask_dst_pages, XS_VEC_FAULT_PROT_WRITE);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_MASK_ON_LOAD_VA, (uintptr_t)g_mask_on_load_page, XS_VEC_FAULT_PROT_READ);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_MASK_ON_STORE_VA, (uintptr_t)g_mask_on_store_pages, XS_VEC_FAULT_PROT_WRITE);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_LOAD_PERM_CROSS_VA, (uintptr_t)g_perm_load_pages, XS_VEC_FAULT_PROT_READ);
  xsam_mmu_pt_map(
      &g_fault_stage1,
      XS_VEC_FAULT_LOAD_PERM_CROSS_VA + XS_VEC_FAULT_PAGE_SIZE,
      (uintptr_t)g_perm_load_pages + XS_VEC_FAULT_PAGE_SIZE,
      XS_VEC_FAULT_PROT_NO_READ);
  xsam_mmu_pt_map(&g_fault_stage1, XS_VEC_FAULT_STORE_PERM_CROSS_VA, (uintptr_t)g_perm_store_pages, XS_VEC_FAULT_PROT_WRITE);
  xsam_mmu_pt_map(
      &g_fault_stage1,
      XS_VEC_FAULT_STORE_PERM_CROSS_VA + XS_VEC_FAULT_PAGE_SIZE,
      (uintptr_t)g_perm_store_pages + XS_VEC_FAULT_PAGE_SIZE,
      XS_VEC_FAULT_PROT_NO_WRITE);
  if (xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_LOAD_CROSS_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_STORE_CROSS_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_MASK_SRC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_MASK_DST_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_LOAD_PERM_CROSS_VA + XS_VEC_FAULT_PAGE_SIZE) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_fault_stage1, XS_VEC_FAULT_STORE_PERM_CROSS_VA + XS_VEC_FAULT_PAGE_SIZE) == 0) {
    return -1;
  }
  xs_vector_mmu_clear_sum_mxr();
  xsam_mmu_enable_sv39(&g_fault_stage1, 0u);
  return 0;
}

static int xs_vec_fault_expect_mask(uint32_t mask, uintptr_t cause, uintptr_t tval) {
  if (xsam_mmu_fault_assert(mask) != 0) {
    return -1;
  }
  if (xsam_mmu_last_fault_cause() != cause || xsam_mmu_last_fault_tval() != tval) {
    return -1;
  }
  return 0;
}

static int xs_vec_fault_cross_load_common(uintptr_t base_va, uint8_t *backing) {
  uintptr_t saved_status;
  uintptr_t addr = base_va + XS_VEC_FAULT_CROSS_OFFSET;

  xs_vec_fault_fill(backing, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0x21u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct((const void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  return xs_vec_fault_expect_mask(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      base_va + XS_VEC_FAULT_PAGE_SIZE);
}

static int xs_vec_fault_cross_load(void) {
  return xs_vec_fault_cross_load_common(XS_VEC_FAULT_LOAD_CROSS_VA, g_cross_load_page);
}

static int xs_vec_fault_perm_load(void) {
  return xs_vec_fault_cross_load_common(XS_VEC_FAULT_LOAD_PERM_CROSS_VA, g_perm_load_pages);
}

static int xs_vec_fault_cross_store_common(uintptr_t base_va, uint8_t *backing, uint8_t seed) {
  uintptr_t saved_status;
  uintptr_t addr = base_va + XS_VEC_FAULT_CROSS_OFFSET;

  xs_vec_fault_set(backing, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0xacu);
  xs_vec_fault_set(backing, XS_VEC_FAULT_PAGE_SIZE, XS_VEC_FAULT_CROSS_LEN, 0xacu);
  xs_vec_fault_fill(g_mask_src_page, 0u, XS_VEC_FAULT_CROSS_LEN, seed);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct(g_mask_src_page);
  xs_vector_mmu_vse8_v8_direct((void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_fault_expect_mask(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          base_va + XS_VEC_FAULT_PAGE_SIZE) != 0) {
    return -1;
  }
  if (!xs_vec_fault_region_eq(backing, XS_VEC_FAULT_CROSS_OFFSET, g_mask_src_page, 8u)) {
    return -1;
  }
  return xs_vec_fault_region_value(
      backing,
      XS_VEC_FAULT_PAGE_SIZE,
      XS_VEC_FAULT_CROSS_LEN,
      0xacu) ? 0 : -1;
}

static int xs_vec_fault_cross_store(void) {
  return xs_vec_fault_cross_store_common(XS_VEC_FAULT_STORE_CROSS_VA, g_cross_store_pages, 0x31u);
}

static int xs_vec_fault_perm_store(void) {
  return xs_vec_fault_cross_store_common(XS_VEC_FAULT_STORE_PERM_CROSS_VA, g_perm_store_pages, 0x39u);
}

static int xs_vec_fault_masked_load_suppresses_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FAULT_MASK_SRC_VA + XS_VEC_FAULT_CROSS_OFFSET;
  uint8_t expected[8];

  xs_vec_fault_fill(g_mask_src_page, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0x41u);
  xs_vec_fault_set(expected, 0u, sizeof(expected), 0u);
  xs_vec_fault_fill(expected, 0u, 8u, 0x41u);
  xs_vec_fault_set(g_mask_dst_pages, 0u, XS_VEC_FAULT_MASK_LEN, 0u);
  xs_vec_fault_make_mask(0x00ffu);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v0_direct(g_mask_bytes);
  xs_vector_mmu_vle8_v8_masked((const void *)addr);
  xs_vector_mmu_vse8_v8_direct(g_mask_dst_pages);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u || xsam_mmu_last_fault_cause() != 0u) {
    return -1;
  }
  return xs_vec_fault_region_eq(g_mask_dst_pages, 0u, expected, sizeof(expected)) ? 0 : -1;
}

static int xs_vec_fault_masked_store_suppresses_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FAULT_MASK_DST_VA + XS_VEC_FAULT_CROSS_OFFSET;

  xs_vec_fault_set(g_mask_dst_pages, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0x7eu);
  xs_vec_fault_set(g_mask_dst_pages, XS_VEC_FAULT_PAGE_SIZE, XS_VEC_FAULT_MASK_LEN, 0x7eu);
  xs_vec_fault_fill(g_mask_src_page, 0u, XS_VEC_FAULT_CROSS_LEN, 0x51u);
  xs_vec_fault_make_mask(0x00ffu);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v0_direct(g_mask_bytes);
  xs_vector_mmu_vle8_v8_direct(g_mask_src_page);
  xs_vector_mmu_vse8_v8_masked((void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u || xsam_mmu_last_fault_cause() != 0u) {
    return -1;
  }
  if (!xs_vec_fault_region_eq(g_mask_dst_pages, XS_VEC_FAULT_CROSS_OFFSET, g_mask_src_page, 8u)) {
    return -1;
  }
  return xs_vec_fault_region_value(
      g_mask_dst_pages,
      XS_VEC_FAULT_PAGE_SIZE,
      XS_VEC_FAULT_MASK_LEN,
      0x7eu) ? 0 : -1;
}

static int xs_vec_fault_masked_load_triggers_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FAULT_MASK_ON_LOAD_VA + XS_VEC_FAULT_CROSS_OFFSET;

  xs_vec_fault_fill(g_mask_on_load_page, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0x61u);
  xs_vec_fault_make_mask(0xffffu);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v0_direct(g_mask_bytes);
  xs_vector_mmu_vle8_v8_masked((const void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  return xs_vec_fault_expect_mask(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      XS_VEC_FAULT_MASK_ON_LOAD_VA + XS_VEC_FAULT_PAGE_SIZE);
}

static int xs_vec_fault_masked_store_triggers_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FAULT_MASK_ON_STORE_VA + XS_VEC_FAULT_CROSS_OFFSET;

  xs_vec_fault_set(g_mask_on_store_pages, XS_VEC_FAULT_CROSS_OFFSET, 8u, 0x89u);
  xs_vec_fault_set(g_mask_on_store_pages, XS_VEC_FAULT_PAGE_SIZE, XS_VEC_FAULT_MASK_LEN, 0x89u);
  xs_vec_fault_fill(g_mask_src_page, 0u, XS_VEC_FAULT_CROSS_LEN, 0x71u);
  xs_vec_fault_make_mask(0xffffu);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FAULT_CROSS_LEN) != XS_VEC_FAULT_CROSS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v0_direct(g_mask_bytes);
  xs_vector_mmu_vle8_v8_direct(g_mask_src_page);
  xs_vector_mmu_vse8_v8_masked((void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_fault_expect_mask(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          XS_VEC_FAULT_MASK_ON_STORE_VA + XS_VEC_FAULT_PAGE_SIZE) != 0) {
    return -1;
  }
  if (!xs_vec_fault_region_eq(g_mask_on_store_pages, XS_VEC_FAULT_CROSS_OFFSET, g_mask_src_page, 8u)) {
    return -1;
  }
  return xs_vec_fault_region_value(
      g_mask_on_store_pages,
      XS_VEC_FAULT_PAGE_SIZE,
      XS_VEC_FAULT_MASK_LEN,
      0x89u) ? 0 : -1;
}

int main(void) {
  int rc;

  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  xsam_mmu_fault_install_handlers();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_FAULT_FAIL_VECTOR_SETUP;
  }
  if (xs_vec_fault_setup() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_SETUP;
  }

  rc = xs_vec_fault_cross_load();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_CROSS_LOAD;
  }
  rc = xs_vec_fault_cross_store();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_CROSS_STORE;
  }
  rc = xs_vec_fault_perm_load();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_PERM_LOAD;
  }
  rc = xs_vec_fault_perm_store();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_PERM_STORE;
  }
  rc = xs_vec_fault_masked_load_suppresses_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_MASKED_LOAD_SUPPRESS;
  }
  rc = xs_vec_fault_masked_store_suppresses_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_MASKED_STORE_SUPPRESS;
  }
  rc = xs_vec_fault_masked_load_triggers_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FAULT_FAIL_MASKED_LOAD_TRIGGER;
  }
  rc = xs_vec_fault_masked_store_triggers_fault();
  xsam_mmu_enable_bare();
  return rc == 0 ? 0 : XS_VEC_FAULT_FAIL_MASKED_STORE_TRIGGER;
}
