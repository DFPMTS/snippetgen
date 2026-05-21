#include <stddef.h>
#include <stdint.h>

#include "xs_vector_mmu.h"
#include "xsam/mmu.h"
#include "xsam/mmu_fault.h"
#include "xsam_xs_platform.h"

enum {
  XS_VEC_ATTR_PAGE_SIZE = XSAM_MMU_PAGE_SIZE,
  XS_VEC_ATTR_RUNTIME_IDENTITY_BASE = 0x80000000ull,
  XS_VEC_ATTR_RUNTIME_IDENTITY_SIZE = 0x40000000ull,
  XS_VEC_ATTR_PROT_RWXAD = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X |
      XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_ATTR_PROT_READ = XSAM_MMU_PTE_R | XSAM_MMU_PTE_A,
  XS_VEC_ATTR_PROT_WRITE = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_A | XSAM_MMU_PTE_D,
  XS_VEC_ATTR_PMP_LOAD_VA = 0x900700000ull,
  XS_VEC_ATTR_PMP_STORE_VA = 0x900710000ull,
  XS_VEC_ATTR_PBMT_NC_VA = 0x900720000ull,
  XS_VEC_ATTR_MMIO_VA = 0x900730000ull,
  XS_VEC_ATTR_MMIO_PA = 0x3800b000ull,
  XS_VEC_ATTR_MMIO_OFFSET = 0xff8ull,
  XS_VEC_ATTR_PBMT_NC_PTE = (1ull << 0) | (1ull << 1) | (1ull << 6) | (1ull << 7) | (1ull << 61),
  XS_VEC_ATTR_LEN = 8u,
};

enum {
  XS_VEC_ATTR_FAIL_VECTOR_SETUP = 50,
  XS_VEC_ATTR_FAIL_SETUP = 51,
  XS_VEC_ATTR_FAIL_PMP_LOAD = 52,
  XS_VEC_ATTR_FAIL_PMP_STORE = 53,
  XS_VEC_ATTR_FAIL_MMIO_LOAD = 54,
  XS_VEC_ATTR_FAIL_PBMT_NC = 55,
};

static xsam_mmu_page_table_t g_attr_stage1;
static uint8_t g_pmp_load_page[XS_VEC_ATTR_PAGE_SIZE] __attribute__((aligned(XS_VEC_ATTR_PAGE_SIZE)));
static uint8_t g_pmp_store_page[XS_VEC_ATTR_PAGE_SIZE] __attribute__((aligned(XS_VEC_ATTR_PAGE_SIZE)));
static uint8_t g_pbmt_nc_page[XS_VEC_ATTR_PAGE_SIZE] __attribute__((aligned(XS_VEC_ATTR_PAGE_SIZE)));
static uint8_t g_scratch[XS_VEC_ATTR_PAGE_SIZE] __attribute__((aligned(XS_VEC_ATTR_PAGE_SIZE)));
static uint8_t g_payload[XS_VEC_ATTR_PAGE_SIZE] __attribute__((aligned(XS_VEC_ATTR_PAGE_SIZE)));

static uintptr_t g_attr_menvcfg;

static void xs_vec_attr_fill(uint8_t *base, size_t len, uint8_t seed) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = (uint8_t)(seed + (uint8_t)(index * 9u));
  }
}

static void xs_vec_attr_set(uint8_t *base, size_t len, uint8_t value) {
  volatile uint8_t *dst = (volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    dst[index] = value;
  }
}

static int xs_vec_attr_region_value(const uint8_t *base, size_t len, uint8_t value) {
  const volatile uint8_t *src = (const volatile uint8_t *)base;
  size_t index;

  for (index = 0u; index < len; ++index) {
    if (src[index] != value) {
      return 0;
    }
  }
  return 1;
}

static uintptr_t xs_vec_attr_read_menvcfg(void) {
#if defined(__riscv)
  uintptr_t value;

  __asm__ volatile("csrr %0, 0x30a" : "=r"(value) : : "memory");
  return value;
#else
  return g_attr_menvcfg;
#endif
}

static void xs_vec_attr_write_menvcfg(uintptr_t value) {
#if defined(__riscv)
  __asm__ volatile("csrw 0x30a, %0" : : "rK"(value) : "memory");
#else
  g_attr_menvcfg = value;
#endif
}

static int xs_vec_attr_expect_fault(uint32_t mask, uintptr_t cause, uintptr_t tval) {
  if (xsam_mmu_fault_assert(mask) != 0) {
    return -1;
  }
  if (xsam_mmu_last_fault_cause() != cause || xsam_mmu_last_fault_tval() != tval) {
    return -1;
  }
  return 0;
}

static int xs_vec_attr_setup(void) {
  uintptr_t raw_pte;

  xsam_mmu_pt_init_sv39(&g_attr_stage1);
  xsam_mmu_pt_map_identity_range(
      &g_attr_stage1,
      XS_VEC_ATTR_RUNTIME_IDENTITY_BASE,
      XS_VEC_ATTR_RUNTIME_IDENTITY_SIZE,
      XS_VEC_ATTR_PROT_RWXAD);
  xsam_mmu_pt_map(&g_attr_stage1, XS_VEC_ATTR_PMP_LOAD_VA, (uintptr_t)g_pmp_load_page, XS_VEC_ATTR_PROT_READ);
  xsam_mmu_pt_map(&g_attr_stage1, XS_VEC_ATTR_PMP_STORE_VA, (uintptr_t)g_pmp_store_page, XS_VEC_ATTR_PROT_WRITE);
  raw_pte = (((uintptr_t)g_pbmt_nc_page >> 12) << 10) | (uintptr_t)XS_VEC_ATTR_PBMT_NC_PTE;
  xsam_mmu_pt_map_raw(&g_attr_stage1, XS_VEC_ATTR_PBMT_NC_VA, raw_pte);
  xsam_mmu_pt_map(&g_attr_stage1, XS_VEC_ATTR_MMIO_VA, XS_VEC_ATTR_MMIO_PA, XS_VEC_ATTR_PROT_READ);
  if (xsam_mmu_pt_leaf_ptr(&g_attr_stage1, XS_VEC_ATTR_PMP_LOAD_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_attr_stage1, XS_VEC_ATTR_PMP_STORE_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_attr_stage1, XS_VEC_ATTR_PBMT_NC_VA) == 0 ||
      xsam_mmu_pt_leaf_ptr(&g_attr_stage1, XS_VEC_ATTR_MMIO_VA) == 0) {
    return -1;
  }
  xs_vector_mmu_clear_sum_mxr();
  xs_vec_attr_write_menvcfg(xs_vec_attr_read_menvcfg() & ~((uintptr_t)1ull << 62));
  xsam_mmu_enable_sv39(&g_attr_stage1, 0u);
  return 0;
}

static int xs_vec_attr_pmp_load_deny(void) {
  uintptr_t saved_status;

  xsam_xs_pmp_enable_napot(1u, (uintptr_t)g_pmp_load_page, XS_VEC_ATTR_PAGE_SIZE, 0, 0);
  xs_vec_attr_fill(g_pmp_load_page, XS_VEC_ATTR_LEN, 0x21u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_ACCESS);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_ATTR_LEN) != XS_VEC_ATTR_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct((const void *)XS_VEC_ATTR_PMP_LOAD_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  xsam_xs_pmp_disable(1u);
  return xs_vec_attr_expect_fault(
      XSAM_MMU_FAULT_LOAD_ACCESS,
      XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT,
      XS_VEC_ATTR_PMP_LOAD_VA);
}

static int xs_vec_attr_pmp_store_deny(void) {
  uintptr_t saved_status;

  xsam_xs_pmp_enable_napot(1u, (uintptr_t)g_pmp_store_page, XS_VEC_ATTR_PAGE_SIZE, 0, XSAM_XS_PMP_R);
  xs_vec_attr_set(g_pmp_store_page, XS_VEC_ATTR_LEN, 0xacu);
  xs_vec_attr_fill(g_payload, XS_VEC_ATTR_LEN, 0x31u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_ACCESS);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_ATTR_LEN) != XS_VEC_ATTR_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct(g_payload);
  xs_vector_mmu_vse8_v8_direct((void *)XS_VEC_ATTR_PMP_STORE_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  xsam_xs_pmp_disable(1u);
  if (xs_vec_attr_expect_fault(
          XSAM_MMU_FAULT_STORE_ACCESS,
          XSAM_MMU_CAUSE_STORE_ACCESS_FAULT,
          XS_VEC_ATTR_PMP_STORE_VA) != 0) {
    return -1;
  }
  return xs_vec_attr_region_value(g_pmp_store_page, XS_VEC_ATTR_LEN, 0xacu) ? 0 : -1;
}

static int xs_vec_attr_mmio_load(void) {
  uintptr_t saved_status;

  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_ACCESS);
  if (xs_vector_mmu_set_vl_e64_m1(1u) != 1u) {
    return -1;
  }
  if ((uintptr_t)xsam_xs_clint_mtime_addr() != XS_VEC_ATTR_MMIO_PA + XS_VEC_ATTR_MMIO_OFFSET) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle64_v8_direct((const void *)(XS_VEC_ATTR_MMIO_VA + XS_VEC_ATTR_MMIO_OFFSET));
  xs_vector_mmu_leave_host_access(saved_status);
  if (xs_vec_attr_expect_fault(
          XSAM_MMU_FAULT_LOAD_ACCESS,
          XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT,
          XS_VEC_ATTR_MMIO_VA + XS_VEC_ATTR_MMIO_OFFSET) != 0) {
    return -1;
  }
  return 0;
}

static int xs_vec_attr_mmio_identity_store_repro(void) {
  uintptr_t saved_status;
  uint64_t before;
  uint64_t after;
  uint64_t observed;

  xs_vec_attr_set(g_scratch, sizeof(g_scratch), 0u);
  xsam_mmu_expect_fault(0u);
  if (xs_vector_mmu_set_vl_e64_m1(1u) != 1u) {
    return -1;
  }
  if ((uintptr_t)xsam_xs_clint_mtime_addr() != XS_VEC_ATTR_MMIO_PA + XS_VEC_ATTR_MMIO_OFFSET) {
    return -1;
  }
  before = xsam_xs_clint_read_mtime();
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle64_v8_direct((const void *)(XS_VEC_ATTR_MMIO_VA + XS_VEC_ATTR_MMIO_OFFSET));
  xs_vector_mmu_vse64_v8_direct(g_scratch);
  xs_vector_mmu_leave_host_access(saved_status);
  after = xsam_xs_clint_read_mtime();
  if (xsam_mmu_fault_seen_mask() != 0u) {
    return -1;
  }
  observed = *(volatile uint64_t *)g_scratch;
  return before <= observed && observed <= after ? 0 : -1;
}

static int xs_vec_attr_pbmt_nc_reserved_fault(void) {
  uintptr_t saved_status;

  xs_vec_attr_fill(g_pbmt_nc_page, XS_VEC_ATTR_LEN, 0x41u);
  xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
  if (xs_vector_mmu_set_vl_e8_m1(XS_VEC_ATTR_LEN) != XS_VEC_ATTR_LEN) {
    return -1;
  }
  saved_status = xs_vector_mmu_enter_host_access();
  xs_vector_mmu_vle8_v8_direct((const void *)XS_VEC_ATTR_PBMT_NC_VA);
  xs_vector_mmu_leave_host_access(saved_status);
  return xs_vec_attr_expect_fault(
      XSAM_MMU_FAULT_LOAD_PAGE,
      XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
      XS_VEC_ATTR_PBMT_NC_VA);
}

static int xs_vec_attr_common_setup(void) {
  xsam_xs_pmp_init();
  xs_vector_mmu_enable_vector_state();
  xsam_mmu_fault_install_handlers();
  if (xs_vector_mmu_set_vl_e8_m1(1u) != 1u) {
    return XS_VEC_ATTR_FAIL_VECTOR_SETUP;
  }
  if (xs_vec_attr_setup() != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_ATTR_FAIL_SETUP;
  }
  return 0;
}

static int xs_vec_attr_finish_case(int rc, int fail_code) {
  xsam_mmu_enable_bare();
  return rc == 0 ? 0 : fail_code;
}

int kmh_v2_vector_mmu_attr_pmp_load_main(void) {
  int rc = xs_vec_attr_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_attr_finish_case(xs_vec_attr_pmp_load_deny(), XS_VEC_ATTR_FAIL_PMP_LOAD);
}

int kmh_v2_vector_mmu_attr_pmp_store_main(void) {
  int rc = xs_vec_attr_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_attr_finish_case(xs_vec_attr_pmp_store_deny(), XS_VEC_ATTR_FAIL_PMP_STORE);
}

int kmh_v2_vector_mmu_attr_mmio_main(void) {
  int rc = xs_vec_attr_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_attr_finish_case(xs_vec_attr_mmio_load(), XS_VEC_ATTR_FAIL_MMIO_LOAD);
}

int kmh_v2_vector_mmu_attr_mmio_identity_repro_main(void) {
  int rc = xs_vec_attr_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_attr_finish_case(xs_vec_attr_mmio_identity_store_repro(), XS_VEC_ATTR_FAIL_MMIO_LOAD);
}

int kmh_v2_vector_mmu_attr_mmio_direct_main(void) {
  int rc = xs_vec_attr_common_setup();
  uint64_t before;
  uint64_t after;

  if (rc != 0) {
    return rc;
  }
  before = xsam_xs_clint_read_mtime();
  after = xsam_xs_clint_read_mtime();
  rc = before <= after ? 0 : -1;
  return xs_vec_attr_finish_case(rc, XS_VEC_ATTR_FAIL_MMIO_LOAD);
}

int kmh_v2_vector_mmu_attr_pbmt_main(void) {
  int rc = xs_vec_attr_common_setup();

  if (rc != 0) {
    return rc;
  }
  return xs_vec_attr_finish_case(xs_vec_attr_pbmt_nc_reserved_fault(), XS_VEC_ATTR_FAIL_PBMT_NC);
}

int kmh_v2_vector_mmu_attr_main(void) {
  int rc;

  rc = xs_vec_attr_common_setup();
  if (rc != 0) {
    return rc;
  }
  rc = xs_vec_attr_pmp_load_deny();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_ATTR_FAIL_PMP_LOAD;
  }
  rc = xs_vec_attr_pmp_store_deny();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_ATTR_FAIL_PMP_STORE;
  }
  rc = xs_vec_attr_mmio_load();
  if (rc != 0) {
    xsam_mmu_enable_bare();
    return XS_VEC_ATTR_FAIL_MMIO_LOAD;
  }
  rc = xs_vec_attr_pbmt_nc_reserved_fault();
  xsam_mmu_enable_bare();
  return rc == 0 ? 0 : XS_VEC_ATTR_FAIL_PBMT_NC;
}
