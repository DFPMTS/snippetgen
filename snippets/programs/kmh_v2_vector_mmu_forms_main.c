#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_FORMS_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_FORMS_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_FORMS_RUNTIME_IDENTITY_SIZE = 0x40000000ull,
  XS_VEC_FORMS_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FORMS_PROT_READ = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A,
  XS_VEC_FORMS_PROT_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FORMS_PROT_READ_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_FORMS_STRIDE_SRC_VA = 0x900600000ull,
  XS_VEC_FORMS_STRIDE_DST_VA = 0x900610000ull,
  XS_VEC_FORMS_INDEX_SRC_VA = 0x900620000ull,
  XS_VEC_FORMS_INDEX_DST_VA = 0x900630000ull,
  XS_VEC_FORMS_SEG_SRC_VA = 0x900640000ull,
  XS_VEC_FORMS_SEG_DST_VA = 0x900650000ull,
  XS_VEC_FORMS_STRIDE_FAULT_VA = 0x900660000ull,
  XS_VEC_FORMS_INDEX_FAULT_VA = 0x900670000ull,
  XS_VEC_FORMS_FOF_VA = 0x900680000ull,
  XS_VEC_FORMS_FOF_FIRST_FAULT_VA = 0x900690000ull,
  XS_VEC_FORMS_VSTART_SRC_VA = 0x9006a0000ull,
  XS_VEC_FORMS_VSTART_DST_VA = 0x9006b0000ull,
  XS_VEC_FORMS_CROSS_OFFSET = XS_VEC_FORMS_PAGE_SIZE - 8u,
  XS_VEC_FORMS_LEN = 16u,
  XS_VEC_FORMS_SMALL_LEN = 8u,
};

enum {
  XS_VEC_FORMS_FAIL_VECTOR_SETUP = 40,
  XS_VEC_FORMS_FAIL_SETUP = 41,
  XS_VEC_FORMS_FAIL_STRIDED_HIT = 42,
  XS_VEC_FORMS_FAIL_STRIDED_FAULT = 43,
  XS_VEC_FORMS_FAIL_INDEXED_HIT = 44,
  XS_VEC_FORMS_FAIL_INDEXED_FAULT = 45,
  XS_VEC_FORMS_FAIL_SEGMENT_HIT = 46,
  XS_VEC_FORMS_FAIL_FOF_LATER_FAULT = 47,
  XS_VEC_FORMS_FAIL_FOF_FIRST_FAULT = 48,
  XS_VEC_FORMS_FAIL_VSTART = 49,
};

static xsam_mmu_page_table_t g_forms_stage1;
static uint8_t g_stride_src[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_stride_dst[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_index_src[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_index_dst[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_seg_src[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_seg_dst[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_stride_fault_pages[2u * XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_index_fault_pages[2u * XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_fof_pages[2u * XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_vstart_src[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_vstart_dst[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_payload[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_indices[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));
static uint8_t g_scratch[XS_VEC_FORMS_PAGE_SIZE] __attribute__((aligned(XS_VEC_FORMS_PAGE_SIZE)));

static void xs_vec_forms_fill(uint8_t *base, size_t offset, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 7u));
  }
}

static void xs_vec_forms_set(uint8_t *base, size_t offset, size_t len, uint8_t value) {
  volatile uint8_t *dst = (volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = value;
  }
}

static int xs_vec_forms_region_value(const uint8_t *base, size_t offset, size_t len, uint8_t value) {
  const volatile uint8_t *src = (const volatile uint8_t *)(base + offset);
  size_t index;

  for (index = 0u; index < len; ++index) {
    if (src[index] != value) {
      return 0;
    }
  }
  return 1;
}

static int xs_vec_forms_region_eq(const uint8_t *base, size_t offset, const uint8_t *expected, size_t len) {
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

static int xs_vec_forms_expect_fault(uint32_t mask, uintptr_t cause, uintptr_t tval) {
  if (xsam_mmu_fault_assert(mask) != 0) {
    return -1;
  }
  if (xsam_mmu_last_fault_cause() != cause || xsam_mmu_last_fault_tval() != tval) {
    return -1;
  }
  xs_vector_mmu_write_vstart(0u);
  return 0;
}

static int xs_vec_forms_setup(void) {
  xsam_mmu_pt_init_sv39(&g_forms_stage1);
  xsam_mmu_pt_map_identity_range(
      &g_forms_stage1,
      XS_VEC_FORMS_RUNTIME_IDENTITY_BASE,
      XS_VEC_FORMS_RUNTIME_IDENTITY_SIZE,
      XS_VEC_FORMS_PROT_RWXAD);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_STRIDE_SRC_VA, (uintptr_t)g_stride_src, XS_VEC_FORMS_PROT_READ);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_STRIDE_DST_VA, (uintptr_t)g_stride_dst, XS_VEC_FORMS_PROT_WRITE);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_INDEX_SRC_VA, (uintptr_t)g_index_src, XS_VEC_FORMS_PROT_READ);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_INDEX_DST_VA, (uintptr_t)g_index_dst, XS_VEC_FORMS_PROT_WRITE);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_SEG_SRC_VA, (uintptr_t)g_seg_src, XS_VEC_FORMS_PROT_READ);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_SEG_DST_VA, (uintptr_t)g_seg_dst, XS_VEC_FORMS_PROT_WRITE);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_STRIDE_FAULT_VA, (uintptr_t)g_stride_fault_pages, XS_VEC_FORMS_PROT_READ_WRITE);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_INDEX_FAULT_VA, (uintptr_t)g_index_fault_pages, XS_VEC_FORMS_PROT_READ_WRITE);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_FOF_VA, (uintptr_t)g_fof_pages, XS_VEC_FORMS_PROT_READ);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_VSTART_SRC_VA, (uintptr_t)g_vstart_src, XS_VEC_FORMS_PROT_READ);
  xsam_mmu_pt_map(&g_forms_stage1, XS_VEC_FORMS_VSTART_DST_VA, (uintptr_t)g_vstart_dst, XS_VEC_FORMS_PROT_WRITE);
  if (xsam_mmu_pt_leaf_ptr(&g_forms_stage1, XS_VEC_FORMS_STRIDE_SRC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_forms_stage1, XS_VEC_FORMS_INDEX_SRC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_forms_stage1, XS_VEC_FORMS_SEG_SRC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_forms_stage1, XS_VEC_FORMS_FOF_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_forms_stage1, XS_VEC_FORMS_VSTART_SRC_VA) == 0) {
    return -1;
  }
  xs_vector_mmu_clear_sum_mxr();
  xsam_mmu_enable_sv39(&g_forms_stage1, 0u);
  return 0;
}

static int xs_vec_forms_strided_hit(void) {
  uintptr_t saved_status;
  size_t index;

  xs_vec_forms_fill(g_stride_src, 0u, 32u, 0x11u);
  xs_vec_forms_set(g_stride_dst, 0u, 32u, 0x55u);
  xs_vec_forms_set(g_scratch, 0u, XS_VEC_FORMS_SMALL_LEN, 0u);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vlse8_v8_direct((const void *)XS_VEC_FORMS_STRIDE_SRC_VA, 2);
  xs_vector_mmu_vse8_v8_direct(g_scratch);
  xs_vector_mmu_vle8_v8_direct(g_payload);
  xs_vector_mmu_vle8_v8_direct(g_scratch);
  xs_vector_mmu_vsse8_v8_direct((void *)XS_VEC_FORMS_STRIDE_DST_VA, 2);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  for (index = 0u; index < XS_VEC_FORMS_SMALL_LEN; ++index) {
    if (g_scratch[index] != g_stride_src[index * 2u] ||
        g_stride_dst[index * 2u] != g_stride_src[index * 2u] ||
        g_stride_dst[index * 2u + 1u] != 0x55u) {
      return -1;
    }
  }
  return 0;
}

static int xs_vec_forms_strided_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FORMS_STRIDE_FAULT_VA + XS_VEC_FORMS_CROSS_OFFSET;
  size_t index;

  xs_vec_forms_set(g_stride_fault_pages, XS_VEC_FORMS_CROSS_OFFSET, 8u, 0xa5u);
  xs_vec_forms_set(g_stride_fault_pages, XS_VEC_FORMS_PAGE_SIZE, 8u, 0xa5u);
  xs_vec_forms_fill(g_payload, 0u, XS_VEC_FORMS_SMALL_LEN, 0x21u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vlse8_v8_direct((const void *)addr, 2);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_forms_expect_fault(
          XSAM_MMU_FAULT_LOAD_PAGE,
          XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
          XS_VEC_FORMS_STRIDE_FAULT_VA + XS_VEC_FORMS_PAGE_SIZE) != 0) {
    return -1;
  }
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct(g_payload);
  xs_vector_mmu_vsse8_v8_direct((void *)addr, 2);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_forms_expect_fault(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          XS_VEC_FORMS_STRIDE_FAULT_VA + XS_VEC_FORMS_PAGE_SIZE) != 0) {
    return -1;
  }
  for (index = 0u; index < 4u; ++index) {
    if (g_stride_fault_pages[XS_VEC_FORMS_CROSS_OFFSET + index * 2u] != g_payload[index]) {
      return -1;
    }
    if (g_stride_fault_pages[XS_VEC_FORMS_CROSS_OFFSET + index * 2u + 1u] != 0xa5u) {
      return -1;
    }
  }
  return xs_vec_forms_region_value(g_stride_fault_pages, XS_VEC_FORMS_PAGE_SIZE, 8u, 0xa5u) ? 0 : -1;
}

static int xs_vec_forms_indexed_hit(void) {
  uintptr_t saved_status;
  static const uint8_t indices[XS_VEC_FORMS_SMALL_LEN] = {0u, 5u, 4u, 3u, 1u, 2u, 7u, 6u};
  size_t index;

  xs_vec_forms_fill(g_index_src, 0u, 32u, 0x31u);
  xs_vec_forms_set(g_index_dst, 0u, 32u, 0x77u);
  xs_vec_forms_set(g_scratch, 0u, XS_VEC_FORMS_SMALL_LEN, 0u);
  for (index = 0u; index < XS_VEC_FORMS_SMALL_LEN; ++index) {
    g_indices[index] = indices[index];
    g_payload[index] = (uint8_t)(0xd0u + index);
  }
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v9_direct(g_indices);
  xs_vector_mmu_vloxei8_v8_direct((const void *)XS_VEC_FORMS_INDEX_SRC_VA);
  xs_vector_mmu_vse8_v8_direct(g_scratch);
  xs_vector_mmu_vle8_v8_direct(g_payload);
  xs_vector_mmu_vsoxei8_v8_direct((void *)XS_VEC_FORMS_INDEX_DST_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  for (index = 0u; index < XS_VEC_FORMS_SMALL_LEN; ++index) {
    if (g_scratch[index] != g_index_src[indices[index]] ||
        g_index_dst[indices[index]] != g_payload[index]) {
      return -1;
    }
  }
  return 0;
}

static int xs_vec_forms_indexed_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FORMS_INDEX_FAULT_VA + XS_VEC_FORMS_PAGE_SIZE - 4u;
  size_t index;

  xs_vec_forms_set(g_index_fault_pages, XS_VEC_FORMS_PAGE_SIZE - 4u, 4u, 0xb6u);
  xs_vec_forms_set(g_index_fault_pages, XS_VEC_FORMS_PAGE_SIZE, XS_VEC_FORMS_SMALL_LEN, 0xb6u);
  for (index = 0u; index < XS_VEC_FORMS_SMALL_LEN; ++index) {
    g_indices[index] = (uint8_t)index;
    g_payload[index] = (uint8_t)(0xe0u + index);
  }
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v9_direct(g_indices);
  xs_vector_mmu_vloxei8_v8_direct((const void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_forms_expect_fault(
          XSAM_MMU_FAULT_LOAD_PAGE,
          XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
          XS_VEC_FORMS_INDEX_FAULT_VA + XS_VEC_FORMS_PAGE_SIZE) != 0) {
    return -1;
  }
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct(g_payload);
  xs_vector_mmu_vle8_v9_direct(g_indices);
  xs_vector_mmu_vsoxei8_v8_direct((void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_forms_expect_fault(
          XSAM_MMU_FAULT_STORE_PAGE,
          XSAM_MMU_CAUSE_STORE_PAGE_FAULT,
          XS_VEC_FORMS_INDEX_FAULT_VA + XS_VEC_FORMS_PAGE_SIZE) != 0) {
    return -1;
  }
  if (!xs_vec_forms_region_eq(g_index_fault_pages, XS_VEC_FORMS_PAGE_SIZE - 4u, g_payload, 4u)) {
    return -1;
  }
  return xs_vec_forms_region_value(
      g_index_fault_pages,
      XS_VEC_FORMS_PAGE_SIZE,
      XS_VEC_FORMS_SMALL_LEN,
      0xb6u) ? 0 : -1;
}

static int xs_vec_forms_segment_hit(void) {
  uintptr_t saved_status;
  size_t index;

  for (index = 0u; index < XS_VEC_FORMS_SMALL_LEN; ++index) {
    g_seg_src[index * 2u] = (uint8_t)(0x41u + index);
    g_seg_src[index * 2u + 1u] = (uint8_t)(0x81u + index);
  }
  xs_vec_forms_set(g_seg_dst, 0u, XS_VEC_FORMS_SMALL_LEN * 2u, 0x66u);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_SMALL_LEN) != XS_VEC_FORMS_SMALL_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vlseg2e8_v8_direct((const void *)XS_VEC_FORMS_SEG_SRC_VA);
  xs_vector_mmu_vsseg2e8_v8_direct((void *)XS_VEC_FORMS_SEG_DST_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  return xs_vec_forms_region_eq(g_seg_dst, 0u, g_seg_src, XS_VEC_FORMS_SMALL_LEN * 2u) ? 0 : -1;
}

static int xs_vec_forms_fof_later_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FORMS_FOF_VA + XS_VEC_FORMS_CROSS_OFFSET;

  xs_vec_forms_fill(g_fof_pages, XS_VEC_FORMS_CROSS_OFFSET, 8u, 0x51u);
  xs_vec_forms_set(g_scratch, 0u, XS_VEC_FORMS_LEN, 0u);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_LEN) != XS_VEC_FORMS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8ff_v8_direct((const void *)addr);
  xs_vector_mmu_vse8_v8_direct(g_scratch);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u || xs_vector_mmu_read_vl() != 8u) {
    return -1;
  }
  if (!xs_vec_forms_region_eq(g_scratch, 0u, g_fof_pages + XS_VEC_FORMS_CROSS_OFFSET, 8u)) {
    return -1;
  }
  return xs_vec_forms_region_value(g_scratch, 8u, 8u, 0u) ? 0 : -1;
}

static int xs_vec_forms_fof_first_fault(void) {
  uintptr_t saved_status;
  uintptr_t addr = XS_VEC_FORMS_FOF_FIRST_FAULT_VA;

  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_LEN) != XS_VEC_FORMS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8ff_v8_direct((const void *)addr);
  xs_vector_mmu_leave_host_access(saved_status);
  return xs_vec_forms_expect_fault(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      addr);
}

static int xs_vec_forms_vstart_store_resume(void) {
  uintptr_t saved_status;

  xs_vec_forms_fill(g_vstart_src, 0u, XS_VEC_FORMS_LEN, 0x61u);
  xs_vec_forms_set(g_vstart_dst, 0u, XS_VEC_FORMS_LEN, 0xccu);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_FORMS_LEN) != XS_VEC_FORMS_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct((const void *)XS_VEC_FORMS_VSTART_SRC_VA);
  xs_vector_mmu_write_vstart(4u);
  xs_vector_mmu_vse8_v8_direct((void *)XS_VEC_FORMS_VSTART_DST_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  if (xsam_mmu_fault_seen_mask() != 0u || xs_vector_mmu_read_vstart() != 0u) {
    return -1;
  }
  if (!xs_vec_forms_region_value(g_vstart_dst, 0u, 4u, 0xccu)) {
    return -1;
  }
  return xs_vec_forms_region_eq(g_vstart_dst, 4u, g_vstart_src + 4u, XS_VEC_FORMS_LEN - 4u) ? 0 : -1;
}

int main(void) {
  int rc;

  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  xsam_mmu_fault_install_handlers();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_FORMS_FAIL_VECTOR_SETUP;
  }
  if (xs_vec_forms_setup() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_SETUP;
  }

  rc = xs_vec_forms_strided_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_STRIDED_HIT;
  }
  rc = xs_vec_forms_strided_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_STRIDED_FAULT;
  }
  rc = xs_vec_forms_indexed_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_INDEXED_HIT;
  }
  rc = xs_vec_forms_indexed_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_INDEXED_FAULT;
  }
  rc = xs_vec_forms_segment_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_SEGMENT_HIT;
  }
  rc = xs_vec_forms_fof_later_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_FOF_LATER_FAULT;
  }
  rc = xs_vec_forms_fof_first_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_FORMS_FAIL_FOF_FIRST_FAULT;
  }
  rc = xs_vec_forms_vstart_store_resume();
  xsam_mmu_enable_bare();
  return rc == 0 ? 0 : XS_VEC_FORMS_FAIL_VSTART;
}
