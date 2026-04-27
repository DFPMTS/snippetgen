#include "xsam/vme.h"

typedef struct xsam_vme_mapping xsam_vme_mapping_t;
typedef struct xsam_vme_root xsam_vme_root_t;

struct xsam_vme_mapping {
  uintptr_t va;
  uintptr_t pa;
  int prot;
  int kind;
  int level;
  xsam_vme_mapping_t *next;
};

struct xsam_vme_root {
  size_t mapping_count;
  xsam_vme_mapping_t *head;
};

enum {
  XSAM_VME_PAGE_SIZE = 4096u,
};

static uintptr_t xsam_vme_mapping_size(const xsam_vme_mapping_t *mapping) {
  uintptr_t size;
  int level;

  if (mapping == 0) {
    return 0u;
  }

  size = XSAM_VME_PAGE_SIZE;
  for (level = 0; level < mapping->level; ++level) {
    size *= 512u;
  }
  return size;
}

static void *(*g_pgalloc)(size_t size);
static void (*g_pgfree)(void *ptr);
static int g_vme_enabled;

static void xsam_vme_zero(void *ptr, size_t size) {
  unsigned char *bytes;

  if (ptr == 0) {
    return;
  }

  bytes = (unsigned char *) ptr;
  for (size_t index = 0; index < size; ++index) {
    bytes[index] = 0u;
  }
}

static xsam_vme_root_t *xsam_vme_root(const xsam_address_space_t *as) {
  if (as == 0) {
    return 0;
  }
  return (xsam_vme_root_t *) as->ptr;
}

static void *xsam_vme_alloc_page(void) {
  void *page;

  if (g_pgalloc == 0) {
    return 0;
  }

  page = g_pgalloc(XSAM_VME_PAGE_SIZE);
  xsam_vme_zero(page, XSAM_VME_PAGE_SIZE);
  return page;
}

static void xsam_vme_record(
    xsam_address_space_t *as,
    void *va,
    void *pa,
    int prot,
    int kind,
    int level) {
  xsam_vme_root_t *root;
  xsam_vme_mapping_t *mapping;

  root = xsam_vme_root(as);
  if (root == 0) {
    return;
  }

  mapping = (xsam_vme_mapping_t *) xsam_vme_alloc_page();
  if (mapping == 0) {
    return;
  }

  mapping->va = (uintptr_t) va;
  mapping->pa = (uintptr_t) pa;
  mapping->prot = prot;
  mapping->kind = kind;
  mapping->level = level;
  mapping->next = root->head;
  root->head = mapping;
  root->mapping_count += 1u;
}

int xsam_vme_init(void *(*pgalloc)(size_t size), void (*pgfree)(void *)) {
  if (pgalloc == 0 || pgfree == 0) {
    g_pgalloc = 0;
    g_pgfree = 0;
    g_vme_enabled = 0;
    return -1;
  }

  g_pgalloc = pgalloc;
  g_pgfree = pgfree;
  g_vme_enabled = 1;
  return 0;
}

void xsam_protect(xsam_address_space_t *as) {
  if (as == 0) {
    return;
  }

  as->pgsize = XSAM_VME_PAGE_SIZE;
  as->area.start = (void *) (uintptr_t) 0xc0000000ull;
  as->area.end = (void *) (uintptr_t) 0xf0000000ull;
  as->ptr = g_vme_enabled != 0 ? xsam_vme_alloc_page() : 0;
}

void xsam_unprotect(xsam_address_space_t *as) {
  xsam_vme_root_t *root;
  xsam_vme_mapping_t *mapping;
  xsam_vme_mapping_t *next;

  if (as == 0 || g_pgfree == 0 || as->ptr == 0) {
    return;
  }

  root = xsam_vme_root(as);
  mapping = root->head;
  while (mapping != 0) {
    next = mapping->next;
    g_pgfree(mapping);
    mapping = next;
  }
  g_pgfree(as->ptr);
  as->ptr = 0;
}

void xsam_map(xsam_address_space_t *as, void *va, void *pa, int prot) {
  xsam_vme_record(as, va, pa, prot, XSAM_VME_MAP_NORMAL, 0);
}

void xsam_map_fault(xsam_address_space_t *as, void *va, void *pa, int prot) {
  xsam_vme_record(as, va, pa, prot, XSAM_VME_MAP_FAULT, 0);
}

void xsam_map_rv_hugepage(
    xsam_address_space_t *as,
    void *va,
    void *pa,
    int prot,
    int pagetable_level) {
  xsam_vme_record(as, va, pa, prot, XSAM_VME_MAP_HUGEPAGE, pagetable_level);
}

size_t xsam_vme_mapping_count(const xsam_address_space_t *as) {
  xsam_vme_root_t *root;

  root = xsam_vme_root(as);
  if (root == 0) {
    return 0u;
  }

  return root->mapping_count;
}

int xsam_vme_lookup(
    const xsam_address_space_t *as,
    void *va,
    void **pa_out,
    int *prot_out,
    int *kind_out,
    int *level_out) {
  xsam_vme_root_t *root;
  xsam_vme_mapping_t *mapping;
  uintptr_t mapping_end;
  uintptr_t mapping_size;
  uintptr_t offset;
  uintptr_t target_va;

  root = xsam_vme_root(as);
  if (root == 0) {
    return 0;
  }

  target_va = (uintptr_t) va;
  mapping = root->head;
  while (mapping != 0) {
    mapping_size = xsam_vme_mapping_size(mapping);
    mapping_end = mapping->va + mapping_size;
    if (mapping_size != 0u && target_va >= mapping->va && target_va < mapping_end) {
      offset = target_va - mapping->va;
      if (pa_out != 0) {
        *pa_out = (void *) (mapping->pa + offset);
      }
      if (prot_out != 0) {
        *prot_out = mapping->prot;
      }
      if (kind_out != 0) {
        *kind_out = mapping->kind;
      }
      if (level_out != 0) {
        *level_out = mapping->level;
      }
      return 1;
    }
    mapping = mapping->next;
  }

  return 0;
}
