#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam/mmu_guest.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_HYP_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_HYP_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_HYP_RUNTIME_IDENTITY_SIZE = 0x00400000ull,
  XS_VEC_HYP_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_HYP_PROT_READ = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A,
  XS_VEC_HYP_PROT_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_HYP_PROT_NO_READ = XSAM_MMU_PTE_X | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_HYP_S1_SRC_VA = 0x900800000ull,
  XS_VEC_HYP_S1_DST_VA = 0x900810000ull,
  XS_VEC_HYP_S1_FAULT_VA = 0x900820000ull,
  XS_VEC_HYP_S2_SRC_GPA = 0x80420000ull,
  XS_VEC_HYP_S2_DST_GPA = 0x80421000ull,
  XS_VEC_HYP_S2_FAULT_GPA = 0x80422000ull,
  XS_VEC_HYP_ALL_SRC_GVA = 0xc00020000ull,
  XS_VEC_HYP_ALL_DST_GVA = 0xc00021000ull,
  XS_VEC_HYP_ALL_S1_FAULT_GVA = 0xc00022000ull,
  XS_VEC_HYP_ALL_S2_FAULT_GVA = 0xc00023000ull,
  XS_VEC_HYP_ALL_SRC_GPA = 0x80430000ull,
  XS_VEC_HYP_ALL_DST_GPA = 0x80431000ull,
  XS_VEC_HYP_ALL_S1_FAULT_GPA = 0x80432000ull,
  XS_VEC_HYP_ALL_S2_FAULT_GPA = 0x80433000ull,
  XS_VEC_HYP_LEN = 8u,
};

enum {
  XS_VEC_HYP_FAIL_VECTOR_SETUP = 60,
  XS_VEC_HYP_FAIL_ONLY_STAGE1_HIT = 61,
  XS_VEC_HYP_FAIL_ONLY_STAGE1_FAULT = 62,
  XS_VEC_HYP_FAIL_ONLY_STAGE2_HIT = 63,
  XS_VEC_HYP_FAIL_ONLY_STAGE2_GPF = 64,
  XS_VEC_HYP_FAIL_ALL_STAGE_HIT = 65,
  XS_VEC_HYP_FAIL_ALL_STAGE_S1_FAULT = 66,
  XS_VEC_HYP_FAIL_ALL_STAGE_S2_GPF = 67,
};

typedef struct xs_vec_hyp_args {
  uintptr_t src;
  uintptr_t dst;
  size_t len;
} xs_vec_hyp_args_t;

static xsam_mmu_page_table_t g_stage1;
static xsam_mmu_page_table_t g_stage2;
static uint8_t g_s1_src[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_s1_dst[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_s1_fault[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_s2_src[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_s2_dst[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_all_src[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_all_dst[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));
static uint8_t g_payload[XS_VEC_HYP_PAGE_SIZE] __attribute__((aligned(XS_VEC_HYP_PAGE_SIZE)));

static int xs_vec_hyp_common_setup(void) {
  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  xs_vector_mmu_enable_vs_vector_state();
  xsam_mmu_fault_install_handlers();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_HYP_FAIL_VECTOR_SETUP;
  }
  return 0;
}

static int xs_vec_hyp_finish_case(int rc, int fail_code) {
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
  return rc == 0 ? 0 : fail_code;
}

static void xs_vec_hyp_fill(uint8_t *base, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 5u));
  }
}

static void xs_vec_hyp_set(uint8_t *base, size_t len, uint8_t value) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = value;
  }
}

static int xs_vec_hyp_region_eq(const uint8_t *lhs, const uint8_t *rhs, size_t len) {
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

static int xs_vec_hyp_expect_fault(uint32_t mask, uintptr_t cause, uintptr_t tval) {
  if (xsam_mmu_fault_assert(mask) != 0) {
    return -1;
  }
  if (xsam_mmu_last_fault_cause() != cause || xsam_mmu_last_fault_tval() != tval) {
    return -1;
  }
  return 0;
}

static int xs_vec_hyp_guest_roundtrip(const xs_vec_hyp_args_t *args) {
  uintptr_t saved_status;

  if (args == 0) {
    return -1;
  }
  if (xs_vector_mmu_set_vl_e8_m1(args->len) != args->len) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_guest_access();
  xs_vector_mmu_vle8_v8_direct((const void *)args->src);
  xs_vector_mmu_vse8_v8_direct((void *)args->dst);
  xs_vector_mmu_leave_guest_access(saved_status);
  return 0;
}

static int xs_vec_hyp_guest_load_only(const xs_vec_hyp_args_t *args) {
  uintptr_t saved_status;

  if (args == 0) {
    return -1;
  }
  if (xs_vector_mmu_set_vl_e8_m1(args->len) != args->len) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_guest_access();
  xs_vector_mmu_vle8_v8_direct((const void *)args->src);
  xs_vector_mmu_leave_guest_access(saved_status);
  return 0;
}

static void xs_vec_hyp_map_runtime_identity_stage1(xsam_mmu_page_table_t *stage1) {
  xsam_mmu_pt_map_identity_range(
      stage1,
      XS_VEC_HYP_RUNTIME_IDENTITY_BASE,
      XS_VEC_HYP_RUNTIME_IDENTITY_SIZE,
      XS_VEC_HYP_PROT_RWXAD);
}

static void xs_vec_hyp_map_runtime_identity_stage2(xsam_mmu_page_table_t *stage2) {
  xsam_mmu_pt_map_identity_range(
      stage2,
      XS_VEC_HYP_RUNTIME_IDENTITY_BASE,
      XS_VEC_HYP_RUNTIME_IDENTITY_SIZE,
      XS_VEC_HYP_PROT_RWXAD);
}

static int xs_vec_hyp_only_stage1_hit(void) {
  xs_vec_hyp_args_t args;

  xsam_mmu_pt_init_sv39(&g_stage1);
  xs_vec_hyp_map_runtime_identity_stage1(&g_stage1);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_S1_SRC_VA, (uintptr_t)g_s1_src, XS_VEC_HYP_PROT_READ);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_S1_DST_VA, (uintptr_t)g_s1_dst, XS_VEC_HYP_PROT_WRITE);
  xs_vec_hyp_fill(g_s1_src, XS_VEC_HYP_LEN, 0x21u);
  xs_vec_hyp_set(g_s1_dst, XS_VEC_HYP_LEN, 0u);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(&g_stage1, 1u));
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
  xsam_mmu_hfence_vvma(0u, 0u);
  xsam_mmu_expect_fault(0u);
  args = (xs_vec_hyp_args_t){XS_VEC_HYP_S1_SRC_VA, XS_VEC_HYP_S1_DST_VA, XS_VEC_HYP_LEN};
  if (xs_vec_hyp_guest_roundtrip(&args) != 0) {
    return -1;
  }
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  return xs_vec_hyp_region_eq(g_s1_src, g_s1_dst, XS_VEC_HYP_LEN) ? 0 : -1;
}

static int xs_vec_hyp_only_stage1_fault(void) {
  xs_vec_hyp_args_t args = {XS_VEC_HYP_S1_FAULT_VA, 0u, XS_VEC_HYP_LEN};

  xsam_mmu_pt_init_sv39(&g_stage1);
  xs_vec_hyp_map_runtime_identity_stage1(&g_stage1);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_S1_FAULT_VA, (uintptr_t)g_s1_fault, XS_VEC_HYP_PROT_NO_READ);
  xs_vec_hyp_fill(g_s1_fault, XS_VEC_HYP_LEN, 0x31u);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(&g_stage1, 1u));
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
  xsam_mmu_hfence_vvma(0u, 0u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vec_hyp_guest_load_only(&args) != 0) {
    return -1;
  }
  return xs_vec_hyp_expect_fault(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      XS_VEC_HYP_S1_FAULT_VA);
}

static int xs_vec_hyp_only_stage2_hit(void) {
  xs_vec_hyp_args_t args;

  xsam_mmu_pt_init_sv39x4(&g_stage2);
  xs_vec_hyp_map_runtime_identity_stage2(&g_stage2);
  xsam_mmu_pt_map(&g_stage2, XS_VEC_HYP_S2_SRC_GPA, (uintptr_t)g_s2_src, XS_VEC_HYP_PROT_READ);
  xsam_mmu_pt_map(&g_stage2, XS_VEC_HYP_S2_DST_GPA, (uintptr_t)g_s2_dst, XS_VEC_HYP_PROT_WRITE);
  xs_vec_hyp_fill(g_s2_src, XS_VEC_HYP_LEN, 0x41u);
  xs_vec_hyp_set(g_s2_dst, XS_VEC_HYP_LEN, 0u);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(&g_stage2, 2u));
  xsam_mmu_hfence_gvma(0u, 0u);
  xsam_mmu_expect_fault(0u);
  args = (xs_vec_hyp_args_t){XS_VEC_HYP_S2_SRC_GPA, XS_VEC_HYP_S2_DST_GPA, XS_VEC_HYP_LEN};
  if (xs_vec_hyp_guest_roundtrip(&args) != 0) {
    return -1;
  }
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  return xs_vec_hyp_region_eq(g_s2_src, g_s2_dst, XS_VEC_HYP_LEN) ? 0 : -1;
}

static int xs_vec_hyp_only_stage2_guest_fault(void) {
  xs_vec_hyp_args_t args = {XS_VEC_HYP_S2_FAULT_GPA, 0u, XS_VEC_HYP_LEN};

  xsam_mmu_pt_init_sv39x4(&g_stage2);
  xs_vec_hyp_map_runtime_identity_stage2(&g_stage2);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(&g_stage2, 3u));
  xsam_mmu_hfence_gvma(0u, 0u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_GUEST_PAGE);
  if (xs_vec_hyp_guest_load_only(&args) != 0) {
    return -1;
  }
  return xs_vec_hyp_expect_fault(
      XSAM_MMU_FAULT_LOAD_GUEST_PAGE,
      XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT,
      XS_VEC_HYP_S2_FAULT_GPA);
}

static int xs_vec_hyp_all_stage_hit(void) {
  xs_vec_hyp_args_t args;

  xsam_mmu_pt_init_sv39(&g_stage1);
  xsam_mmu_pt_init_sv39x4(&g_stage2);
  xs_vec_hyp_map_runtime_identity_stage1(&g_stage1);
  xs_vec_hyp_map_runtime_identity_stage2(&g_stage2);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_ALL_SRC_GVA, XS_VEC_HYP_ALL_SRC_GPA, XS_VEC_HYP_PROT_READ);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_ALL_DST_GVA, XS_VEC_HYP_ALL_DST_GPA, XS_VEC_HYP_PROT_WRITE);
  xsam_mmu_pt_map(&g_stage2, XS_VEC_HYP_ALL_SRC_GPA, (uintptr_t)g_all_src, XS_VEC_HYP_PROT_READ);
  xsam_mmu_pt_map(&g_stage2, XS_VEC_HYP_ALL_DST_GPA, (uintptr_t)g_all_dst, XS_VEC_HYP_PROT_WRITE);
  xs_vec_hyp_fill(g_all_src, XS_VEC_HYP_LEN, 0x51u);
  xs_vec_hyp_set(g_all_dst, XS_VEC_HYP_LEN, 0u);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(&g_stage1, 4u));
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(&g_stage2, 4u));
  xsam_mmu_hfence_vvma(0u, 0u);
  xsam_mmu_hfence_gvma(0u, 0u);
  xsam_mmu_expect_fault(0u);
  args = (xs_vec_hyp_args_t){XS_VEC_HYP_ALL_SRC_GVA, XS_VEC_HYP_ALL_DST_GVA, XS_VEC_HYP_LEN};
  if (xs_vec_hyp_guest_roundtrip(&args) != 0) {
    return -1;
  }
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  return xs_vec_hyp_region_eq(g_all_src, g_all_dst, XS_VEC_HYP_LEN) ? 0 : -1;
}

static int xs_vec_hyp_all_stage_stage1_fault(void) {
  xs_vec_hyp_args_t args = {XS_VEC_HYP_ALL_S1_FAULT_GVA, 0u, XS_VEC_HYP_LEN};

  xsam_mmu_pt_init_sv39(&g_stage1);
  xsam_mmu_pt_init_sv39x4(&g_stage2);
  xs_vec_hyp_map_runtime_identity_stage1(&g_stage1);
  xs_vec_hyp_map_runtime_identity_stage2(&g_stage2);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_ALL_S1_FAULT_GVA, XS_VEC_HYP_ALL_S1_FAULT_GPA, XS_VEC_HYP_PROT_NO_READ);
  xsam_mmu_pt_map(&g_stage2, XS_VEC_HYP_ALL_S1_FAULT_GPA, (uintptr_t)g_payload, XS_VEC_HYP_PROT_READ);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(&g_stage1, 5u));
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(&g_stage2, 5u));
  xsam_mmu_hfence_vvma(0u, 0u);
  xsam_mmu_hfence_gvma(0u, 0u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vec_hyp_guest_load_only(&args) != 0) {
    return -1;
  }
  return xs_vec_hyp_expect_fault(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      XS_VEC_HYP_ALL_S1_FAULT_GVA);
}

static int xs_vec_hyp_all_stage_stage2_guest_fault(void) {
  xs_vec_hyp_args_t args = {XS_VEC_HYP_ALL_S2_FAULT_GVA, 0u, XS_VEC_HYP_LEN};

  xsam_mmu_pt_init_sv39(&g_stage1);
  xsam_mmu_pt_init_sv39x4(&g_stage2);
  xs_vec_hyp_map_runtime_identity_stage1(&g_stage1);
  xs_vec_hyp_map_runtime_identity_stage2(&g_stage2);
  xsam_mmu_pt_map(&g_stage1, XS_VEC_HYP_ALL_S2_FAULT_GVA, XS_VEC_HYP_ALL_S2_FAULT_GPA, XS_VEC_HYP_PROT_READ);
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, xsam_mmu_make_vsatp_pt(&g_stage1, 6u));
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, xsam_mmu_make_hgatp_pt(&g_stage2, 6u));
  xsam_mmu_hfence_vvma(0u, 0u);
  xsam_mmu_hfence_gvma(0u, 0u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_GUEST_PAGE);
  if (xs_vec_hyp_guest_load_only(&args) != 0) {
    return -1;
  }
  return xs_vec_hyp_expect_fault(
      XSAM_MMU_FAULT_LOAD_GUEST_PAGE,
      XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT,
      XS_VEC_HYP_ALL_S2_FAULT_GVA);
}

int kmh_v2_vector_mmu_hyp_only_stage1_hit_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_only_stage1_hit(), XS_VEC_HYP_FAIL_ONLY_STAGE1_HIT);
}

int kmh_v2_vector_mmu_hyp_only_stage1_fault_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_only_stage1_fault(), XS_VEC_HYP_FAIL_ONLY_STAGE1_FAULT);
}

int kmh_v2_vector_mmu_hyp_only_stage2_hit_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_only_stage2_hit(), XS_VEC_HYP_FAIL_ONLY_STAGE2_HIT);
}

int kmh_v2_vector_mmu_hyp_only_stage2_gpf_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_only_stage2_guest_fault(), XS_VEC_HYP_FAIL_ONLY_STAGE2_GPF);
}

int kmh_v2_vector_mmu_hyp_all_stage_hit_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_all_stage_hit(), XS_VEC_HYP_FAIL_ALL_STAGE_HIT);
}

int kmh_v2_vector_mmu_hyp_all_stage_s1_fault_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_all_stage_stage1_fault(), XS_VEC_HYP_FAIL_ALL_STAGE_S1_FAULT);
}

int kmh_v2_vector_mmu_hyp_all_stage_s2_gpf_main(void) {
  int rc = xs_vec_hyp_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_hyp_finish_case(xs_vec_hyp_all_stage_stage2_guest_fault(), XS_VEC_HYP_FAIL_ALL_STAGE_S2_GPF);
}

int kmh_v2_vector_mmu_hyp_main(void) {
  int rc;

  rc = xs_vec_hyp_common_setup();
  if (rc != 0) {
    return rc;
  }

  rc = xs_vec_hyp_only_stage1_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ONLY_STAGE1_HIT;
  }
  rc = xs_vec_hyp_only_stage1_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ONLY_STAGE1_FAULT;
  }
  rc = xs_vec_hyp_only_stage2_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ONLY_STAGE2_HIT;
  }
  rc = xs_vec_hyp_only_stage2_guest_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ONLY_STAGE2_GPF;
  }
  rc = xs_vec_hyp_all_stage_hit();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ALL_STAGE_HIT;
  }
  rc = xs_vec_hyp_all_stage_stage1_fault();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_HYP_FAIL_ALL_STAGE_S1_FAULT;
  }
  rc = xs_vec_hyp_all_stage_stage2_guest_fault();
  xsam_mmu_enable_bare();
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_VSATP, 0u);
  xsam_mmu_write_hyp_csr(XSAM_MMU_CSR_HGATP, 0u);
  return rc == 0 ? 0 : XS_VEC_HYP_FAIL_ALL_STAGE_S2_GPF;
}
