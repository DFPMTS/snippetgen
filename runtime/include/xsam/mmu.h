#ifndef XSAM_MMU_H
#define XSAM_MMU_H

#include <stddef.h>
#include <stdint.h>

enum {
  XSAM_MMU_PAGE_SIZE = 4096u,
  XSAM_MMU_PTE_PER_PAGE = 512u,
  XSAM_MMU_ROOT_MAX_PTES = 2048u,
  XSAM_MMU_MAX_PT_PAGES = 32u,
  XSAM_MMU_PTE_V = 1u << 0,
  XSAM_MMU_PTE_R = 1u << 1,
  XSAM_MMU_PTE_W = 1u << 2,
  XSAM_MMU_PTE_X = 1u << 3,
  XSAM_MMU_PTE_U = 1u << 4,
  XSAM_MMU_PTE_G = 1u << 5,
  XSAM_MMU_PTE_A = 1u << 6,
  XSAM_MMU_PTE_D = 1u << 7,
  XSAM_MMU_SATP_MODE_SHIFT = 60,
  XSAM_MMU_SATP_MODE_BARE = 0u,
  XSAM_MMU_SATP_MODE_SV39 = 8u,
  XSAM_MMU_SATP_MODE_SV48 = 9u,
  XSAM_MMU_HGATP_MODE_SV39X4 = 8u,
  XSAM_MMU_HGATP_MODE_SV48X4 = 9u,
};

typedef struct xsam_mmu_page_table {
  void *root;
  size_t root_entries;
  size_t allocated_pages;
  uint8_t levels;
  uint8_t top_bits;
  uint8_t csr_mode;
  uint8_t is_guest_stage;
  uintptr_t root_storage[XSAM_MMU_ROOT_MAX_PTES] __attribute__((aligned(16384)));
  uintptr_t page_storage[XSAM_MMU_MAX_PT_PAGES][XSAM_MMU_PTE_PER_PAGE] __attribute__((aligned(4096)));
} xsam_mmu_page_table_t;

typedef struct xsam_mmu_layout {
  size_t page_size;
  uintptr_t test_pa;
  uintptr_t ro_alias_va;
  uintptr_t rw_alias_va;
  uintptr_t fault_alias_va;
} xsam_mmu_layout_t;

typedef struct xsam_mmu_env {
  xsam_mmu_layout_t layout;
  uintptr_t alloc_cursor;
} xsam_mmu_env_t;

void xsam_mmu_env_init(xsam_mmu_env_t *env);
void xsam_mmu_pt_init_sv39(xsam_mmu_page_table_t *pt);
void xsam_mmu_pt_init_sv48(xsam_mmu_page_table_t *pt);
void xsam_mmu_pt_init_sv39x4(xsam_mmu_page_table_t *pt);
void xsam_mmu_pt_init_sv48x4(xsam_mmu_page_table_t *pt);
void xsam_mmu_pt_map(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot);
void xsam_mmu_pt_map_raw(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pte_value);
void xsam_mmu_pt_map_fault(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot);
void xsam_mmu_pt_map_superpage(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot,
    size_t page_count);
void xsam_mmu_pt_map_identity_range(
    xsam_mmu_page_table_t *pt,
    uintptr_t start,
    size_t size,
    uintptr_t prot);
uintptr_t *xsam_mmu_pt_leaf_ptr(xsam_mmu_page_table_t *pt, uintptr_t va);
uintptr_t xsam_mmu_make_satp_pt(const xsam_mmu_page_table_t *pt, uintptr_t asid);
uintptr_t xsam_mmu_read_satp(void);
void xsam_mmu_write_satp(uintptr_t value);
void xsam_mmu_enable_sv39(const xsam_mmu_page_table_t *pt, uintptr_t asid);
void xsam_mmu_enable_bare(void);
void xsam_mmu_sfence_vma(void);
void xsam_mmu_hfence_vvma(uintptr_t addr, uintptr_t asid);
void xsam_mmu_hfence_gvma(uintptr_t addr, uintptr_t vmid);

#endif
