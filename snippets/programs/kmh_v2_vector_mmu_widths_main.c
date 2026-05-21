#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_WIDTH_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_WIDTH_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_WIDTH_RUNTIME_IDENTITY_SIZE = 0x40000000ull,
  XS_VEC_WIDTH_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_WIDTH_SRC_VA = 0x900400000ull,
  XS_VEC_WIDTH_DST_VA = 0x900410000ull,
  XS_VEC_WIDTH_LEN = 8u,
};

enum {
  XS_VEC_WIDTH_FAIL_VECTOR_SETUP = 20,
  XS_VEC_WIDTH_FAIL_SETUP = 21,
  XS_VEC_WIDTH_FAIL_E8 = 22,
  XS_VEC_WIDTH_FAIL_E16 = 23,
  XS_VEC_WIDTH_FAIL_E32 = 24,
  XS_VEC_WIDTH_FAIL_E64 = 25,
};

typedef size_t (*xs_vec_width_set_vl_fn)(size_t requested_vl);
typedef void (*xs_vec_width_load_fn)(const void *addr);
typedef void (*xs_vec_width_store_fn)(void *addr);

typedef struct xs_vec_width_case {
  size_t eew_bytes;
  size_t vl;
  xs_vec_width_set_vl_fn set_vl;
  xs_vec_width_load_fn load;
  xs_vec_width_store_fn store;
  int fail_code;
  uint8_t seed;
} xs_vec_width_case_t;

static xsam_mmu_page_table_t g_width_stage1;
static uint8_t g_width_src[XS_VEC_WIDTH_PAGE_SIZE] __attribute__((aligned(XS_VEC_WIDTH_PAGE_SIZE)));
static uint8_t g_width_dst[XS_VEC_WIDTH_PAGE_SIZE] __attribute__((aligned(XS_VEC_WIDTH_PAGE_SIZE)));

static void xs_vec_width_fill(uint8_t *base, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 13u));
  }
}

static void xs_vec_width_zero(uint8_t *base, size_t len) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = 0u;
  }
}

static int xs_vec_width_mem_eq(const uint8_t *lhs, const uint8_t *rhs, size_t len) {
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

static int xs_vec_width_setup(void) {
  xsam_mmu_pt_init_sv39(&g_width_stage1);
  xsam_mmu_pt_map_identity_range(
      &g_width_stage1,
      XS_VEC_WIDTH_RUNTIME_IDENTITY_BASE,
      XS_VEC_WIDTH_RUNTIME_IDENTITY_SIZE,
      XS_VEC_WIDTH_PROT_RWXAD);
  xsam_mmu_pt_map(&g_width_stage1, XS_VEC_WIDTH_SRC_VA, (uintptr_t)g_width_src, XS_VEC_WIDTH_PROT_RWXAD);
  xsam_mmu_pt_map(&g_width_stage1, XS_VEC_WIDTH_DST_VA, (uintptr_t)g_width_dst, XS_VEC_WIDTH_PROT_RWXAD);
  if (xsam_mmu_pt_leaf_ptr(&g_width_stage1, XS_VEC_WIDTH_SRC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_width_stage1, XS_VEC_WIDTH_DST_VA) == 0) {
    return -1;
  }
  xs_vector_mmu_clear_sum_mxr();
  xsam_mmu_enable_sv39(&g_width_stage1, 0u);
  return 0;
}

static int xs_vec_width_roundtrip(const xs_vec_width_case_t *test_case) {
  uintptr_t saved_status;
  size_t byte_len = test_case->vl * test_case->eew_bytes;

  xs_vec_width_fill(g_width_src, byte_len, test_case->seed);
  xs_vec_width_zero(g_width_dst, byte_len);
  if (test_case->set_vl(test_case->vl) != test_case->vl) {
    return -1;
  }

  saved_status = xs_vector_mmu_enter_host_access();
  test_case->load((const void *)XS_VEC_WIDTH_SRC_VA);
  test_case->store((void *)XS_VEC_WIDTH_DST_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  return xs_vec_width_mem_eq(g_width_src, g_width_dst, byte_len) ? 0 : -1;
}

int main(void) {
  static const xs_vec_width_case_t cases[] = {
      {1u, 16u, xs_vector_mmu_set_vl_e8_m1, xs_vector_mmu_vle8_v8_direct, xs_vector_mmu_vse8_v8_direct, XS_VEC_WIDTH_FAIL_E8, 0x31u},
      {2u, 8u, xs_vector_mmu_set_vl_e16_m1, xs_vector_mmu_vle16_v8_direct, xs_vector_mmu_vse16_v8_direct, XS_VEC_WIDTH_FAIL_E16, 0x43u},
      {4u, 4u, xs_vector_mmu_set_vl_e32_m1, xs_vector_mmu_vle32_v8_direct, xs_vector_mmu_vse32_v8_direct, XS_VEC_WIDTH_FAIL_E32, 0x59u},
      {8u, 2u, xs_vector_mmu_set_vl_e64_m1, xs_vector_mmu_vle64_v8_direct, xs_vector_mmu_vse64_v8_direct, XS_VEC_WIDTH_FAIL_E64, 0x6du},
  };
  size_t index;

  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  xsam_mmu_fault_install_handlers();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_WIDTH_FAIL_VECTOR_SETUP;
  }
  if (xs_vec_width_setup() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_WIDTH_FAIL_SETUP;
  }

  for (index = 0u; index < sizeof(cases) / sizeof(cases[0]); ++index) {
    if (xs_vec_width_roundtrip(&cases[index]) != 0) {
      xsam_mmu_enable_bare();
      return cases[index].fail_code;
    }
  }

  xsam_mmu_enable_bare();
  return 0;
}
