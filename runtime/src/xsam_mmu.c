#include "xsam/mmu.h"

enum {
  XSAM_MMU_PTE_LEAF_BITS = XSAM_MMU_PTE_R | XSAM_MMU_PTE_W | XSAM_MMU_PTE_X,
  XSAM_MMU_FAULT_PPN_POISON = (uintptr_t)1 << 53,
};

static uintptr_t g_host_satp;

static void xsam_mmu_zero_words(uintptr_t *words, size_t count) {
  size_t index;

  if (words == 0) {
    return;
  }

  for (index = 0; index < count; ++index) {
    words[index] = 0u;
  }
}

static uintptr_t xsam_mmu_pt_root_entries(uint8_t top_bits) {
  return (uintptr_t)1u << top_bits;
}

static void xsam_mmu_pt_reset(
    xsam_mmu_page_table_t *pt,
    uint8_t levels,
    uint8_t top_bits,
    uint8_t csr_mode,
    uint8_t is_guest_stage) {
  if (pt == 0) {
    return;
  }

  pt->root = (void *)pt->root_storage;
  pt->root_entries = xsam_mmu_pt_root_entries(top_bits);
  pt->allocated_pages = 0u;
  pt->levels = levels;
  pt->top_bits = top_bits;
  pt->csr_mode = csr_mode;
  pt->is_guest_stage = is_guest_stage;
  xsam_mmu_zero_words(pt->root_storage, pt->root_entries);
}

static uintptr_t xsam_mmu_make_leaf_pte(
    const xsam_mmu_page_table_t *pt,
    uintptr_t pa,
    uintptr_t prot,
    int fault_mapping) {
  uintptr_t pte_value;
  uintptr_t ppn;

  ppn = pa >> 12;
  pte_value = XSAM_MMU_PTE_V | prot | (ppn << 10);
  if (pt != 0 && pt->is_guest_stage != 0) {
    pte_value |= XSAM_MMU_PTE_U;
  }
  if (fault_mapping != 0) {
    pte_value |= XSAM_MMU_FAULT_PPN_POISON;
  }
  return pte_value;
}

static uintptr_t xsam_mmu_pt_ppn(const xsam_mmu_page_table_t *pt) {
  if (pt == 0 || pt->root == 0) {
    return 0u;
  }
  return (uintptr_t)pt->root >> 12;
}

static uintptr_t xsam_mmu_pt_level_bits(const xsam_mmu_page_table_t *pt, int level) {
  if (pt == 0) {
    return 0u;
  }
  return level == pt->levels - 1 ? pt->top_bits : 9u;
}

static uintptr_t xsam_mmu_pt_level_shift(const xsam_mmu_page_table_t *pt, int level) {
  uintptr_t shift;
  int current;

  if (pt == 0) {
    return 0u;
  }

  shift = 12u;
  for (current = 0; current < level; ++current) {
    shift += xsam_mmu_pt_level_bits(pt, current);
  }
  return shift;
}

static uintptr_t xsam_mmu_pt_level_size(const xsam_mmu_page_table_t *pt, int level) {
  return (uintptr_t)1u << xsam_mmu_pt_level_shift(pt, level);
}

static uintptr_t xsam_mmu_pt_level_index(
    const xsam_mmu_page_table_t *pt,
    uintptr_t va,
    int level) {
  uintptr_t bits;
  uintptr_t mask;

  bits = xsam_mmu_pt_level_bits(pt, level);
  mask = ((uintptr_t)1u << bits) - 1u;
  return (va >> xsam_mmu_pt_level_shift(pt, level)) & mask;
}

static int xsam_mmu_pte_is_leaf(uintptr_t pte_value) {
  return (pte_value & XSAM_MMU_PTE_LEAF_BITS) != 0u;
}

static uintptr_t *xsam_mmu_alloc_table_page(xsam_mmu_page_table_t *pt) {
  uintptr_t *page;

  if (pt == 0) {
    return 0;
  }

  if (pt->allocated_pages >= XSAM_MMU_MAX_PT_PAGES) {
    return 0;
  }

  page = pt->page_storage[pt->allocated_pages];
  pt->allocated_pages += 1u;
  xsam_mmu_zero_words(page, XSAM_MMU_PTE_PER_PAGE);
  return page;
}

static uintptr_t xsam_mmu_make_table_pte(uintptr_t *table_page) {
  return XSAM_MMU_PTE_V | (((uintptr_t)table_page >> 12) << 10);
}

static uintptr_t *xsam_mmu_pt_walk_level(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    int target_level,
    int create) {
  uintptr_t *table;
  uintptr_t *pte;
  uintptr_t *next_table;
  int level;

  if (pt == 0 || pt->root == 0) {
    return 0;
  }

  table = (uintptr_t *)pt->root;
  for (level = pt->levels - 1; level > target_level; --level) {
    pte = &table[xsam_mmu_pt_level_index(pt, va, level)];
    if ((*pte & XSAM_MMU_PTE_V) == 0u) {
      if (create == 0) {
        return 0;
      }
      next_table = xsam_mmu_alloc_table_page(pt);
      if (next_table == 0) {
        return 0;
      }
      *pte = xsam_mmu_make_table_pte(next_table);
    } else if (xsam_mmu_pte_is_leaf(*pte)) {
      return 0;
    }
    table = (uintptr_t *)(((uintptr_t)(*pte >> 10)) << 12);
  }

  return &table[xsam_mmu_pt_level_index(pt, va, target_level)];
}

static uintptr_t *xsam_mmu_pt_find_leaf_ptr(xsam_mmu_page_table_t *pt, uintptr_t va) {
  uintptr_t *table;
  uintptr_t *pte;
  int level;

  if (pt == 0 || pt->root == 0) {
    return 0;
  }

  table = (uintptr_t *)pt->root;
  for (level = pt->levels - 1; level >= 0; --level) {
    pte = &table[xsam_mmu_pt_level_index(pt, va, level)];
    if ((*pte & XSAM_MMU_PTE_V) == 0u) {
      return 0;
    }
    if (level == 0 || xsam_mmu_pte_is_leaf(*pte)) {
      return pte;
    }
    table = (uintptr_t *)(((uintptr_t)(*pte >> 10)) << 12);
  }

  return 0;
}

static void xsam_mmu_pt_map_level(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pte_value,
    int level) {
  uintptr_t *pte;

  pte = xsam_mmu_pt_walk_level(pt, va, level, 1);
  if (pte == 0) {
    return;
  }
  *pte = pte_value;
}

void xsam_mmu_env_init(xsam_mmu_env_t *env) {
  if (env == 0) {
    return;
  }

  *env = (xsam_mmu_env_t){
      .layout =
          {
              .page_size = XSAM_MMU_PAGE_SIZE,
              .test_pa = 0x80020000ull,
              .ro_alias_va = 0x900000000ull,
              .rw_alias_va = 0xa00000000ull,
              .fault_alias_va = 0xb00000000ull,
          },
      .alloc_cursor = 0u,
  };
}

void xsam_mmu_pt_init_sv39(xsam_mmu_page_table_t *pt) {
  xsam_mmu_pt_reset(pt, 3u, 9u, XSAM_MMU_SATP_MODE_SV39, 0u);
}

void xsam_mmu_pt_init_sv48(xsam_mmu_page_table_t *pt) {
  xsam_mmu_pt_reset(pt, 4u, 9u, XSAM_MMU_SATP_MODE_SV48, 0u);
}

void xsam_mmu_pt_init_sv39x4(xsam_mmu_page_table_t *pt) {
  xsam_mmu_pt_reset(pt, 3u, 11u, XSAM_MMU_HGATP_MODE_SV39X4, 1u);
}

void xsam_mmu_pt_init_sv48x4(xsam_mmu_page_table_t *pt) {
  xsam_mmu_pt_reset(pt, 4u, 11u, XSAM_MMU_HGATP_MODE_SV48X4, 1u);
}

void xsam_mmu_pt_map(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot) {
  xsam_mmu_pt_map_raw(pt, va, xsam_mmu_make_leaf_pte(pt, pa, prot, 0));
}

void xsam_mmu_pt_map_raw(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pte_value) {
  xsam_mmu_pt_map_level(pt, va, pte_value, 0);
}

void xsam_mmu_pt_map_fault(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot) {
  xsam_mmu_pt_map_raw(pt, va, xsam_mmu_make_leaf_pte(pt, pa, prot, 1));
}

void xsam_mmu_pt_map_superpage(
    xsam_mmu_page_table_t *pt,
    uintptr_t va,
    uintptr_t pa,
    uintptr_t prot,
    size_t page_count) {
  uintptr_t target_size;
  int level;

  if (pt == 0 || page_count == 0u) {
    return;
  }

  target_size = (uintptr_t)page_count * XSAM_MMU_PAGE_SIZE;
  for (level = pt->levels - 1; level >= 0; --level) {
    uintptr_t level_size = xsam_mmu_pt_level_size(pt, level);
    if (level_size != target_size) {
      continue;
    }
    if ((va % level_size) != 0u || (pa % level_size) != 0u) {
      return;
    }
    xsam_mmu_pt_map_level(pt, va, xsam_mmu_make_leaf_pte(pt, pa, prot, 0), level);
    return;
  }
}

void xsam_mmu_pt_map_identity_range(
    xsam_mmu_page_table_t *pt,
    uintptr_t start,
    size_t size,
    uintptr_t prot) {
  uintptr_t cursor;
  uintptr_t end;
  int mapped;
  int level;

  if (pt == 0 || size == 0u) {
    return;
  }
  if ((start % XSAM_MMU_PAGE_SIZE) != 0u || (size % XSAM_MMU_PAGE_SIZE) != 0u) {
    return;
  }

  end = start + size;
  cursor = start;
  while (cursor < end) {
    mapped = 0;
    for (level = pt->levels - 1; level >= 0; --level) {
      uintptr_t level_size = xsam_mmu_pt_level_size(pt, level);
      if ((cursor % level_size) != 0u || end - cursor < level_size) {
        continue;
      }
      xsam_mmu_pt_map_level(
          pt,
          cursor,
          xsam_mmu_make_leaf_pte(pt, cursor, prot, 0),
          level);
      cursor += level_size;
      mapped = 1;
      break;
    }
    if (mapped == 0) {
      return;
    }
  }
}

uintptr_t *xsam_mmu_pt_leaf_ptr(xsam_mmu_page_table_t *pt, uintptr_t va) {
  return xsam_mmu_pt_find_leaf_ptr(pt, va);
}

uintptr_t xsam_mmu_make_satp_pt(const xsam_mmu_page_table_t *pt, uintptr_t asid) {
  if (pt == 0) {
    return 0u;
  }

  return ((uintptr_t)pt->csr_mode << XSAM_MMU_SATP_MODE_SHIFT) |
         ((asid & 0xffffu) << 44) |
         xsam_mmu_pt_ppn(pt);
}

uintptr_t xsam_mmu_read_satp(void) {
#if defined(__riscv)
  uintptr_t value;

  __asm__ volatile("csrr %0, satp" : "=r"(value) : : "memory");
  return value;
#else
  return g_host_satp;
#endif
}

void xsam_mmu_write_satp(uintptr_t value) {
#if defined(__riscv)
  __asm__ volatile("csrw satp, %0" : : "rK"(value) : "memory");
#else
  g_host_satp = value;
#endif
}

void xsam_mmu_enable_sv39(const xsam_mmu_page_table_t *pt, uintptr_t asid) {
  xsam_mmu_write_satp(xsam_mmu_make_satp_pt(pt, asid));
  xsam_mmu_sfence_vma();
}

void xsam_mmu_enable_bare(void) {
  xsam_mmu_write_satp((uintptr_t)XSAM_MMU_SATP_MODE_BARE << XSAM_MMU_SATP_MODE_SHIFT);
  xsam_mmu_sfence_vma();
}

void xsam_mmu_sfence_vma(void) {
#if defined(__riscv)
  __asm__ volatile("sfence.vma" ::: "memory");
#endif
}

void xsam_mmu_hfence_vvma(uintptr_t addr, uintptr_t asid) {
#if defined(__riscv)
  if (addr == 0u && asid == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x11, x0, x0, x0" ::: "memory");
    return;
  }
  if (addr == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x11, x0, x0, %0" : : "r"(asid) : "memory");
    return;
  }
  if (asid == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x11, x0, %0, x0" : : "r"(addr) : "memory");
    return;
  }
  __asm__ volatile(".insn r 0x73, 0, 0x11, x0, %0, %1" : : "r"(addr), "r"(asid) : "memory");
#else
  (void)addr;
  (void)asid;
#endif
}

void xsam_mmu_hfence_gvma(uintptr_t addr, uintptr_t vmid) {
#if defined(__riscv)
  if (addr == 0u && vmid == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x31, x0, x0, x0" ::: "memory");
    return;
  }
  if (addr == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x31, x0, x0, %0" : : "r"(vmid) : "memory");
    return;
  }
  if (vmid == 0u) {
    __asm__ volatile(".insn r 0x73, 0, 0x31, x0, %0, x0" : : "r"(addr) : "memory");
    return;
  }
  __asm__ volatile(".insn r 0x73, 0, 0x31, x0, %0, %1" : : "r"(addr), "r"(vmid) : "memory");
#else
  (void)addr;
  (void)vmid;
#endif
}
