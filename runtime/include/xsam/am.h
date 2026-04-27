#ifndef XSAM_AM_H
#define XSAM_AM_H

#include <stddef.h>
#include <stdint.h>

typedef struct xsam_context xsam_context_t;
typedef struct xsam_address_space xsam_address_space_t;

typedef struct {
  void *start;
  void *end;
} xsam_area_t;

typedef struct {
  int event;
  uintptr_t cause;
  uintptr_t ref;
  const char *msg;
} xsam_event_t;

#include "xsam/context.h"

enum {
  XSAM_EVENT_NULL = 0,
  XSAM_EVENT_ERROR,
  XSAM_EVENT_IRQ_SOFT,
  XSAM_EVENT_IRQ_TIMER,
  XSAM_EVENT_IRQ_IODEV,
  XSAM_EVENT_PAGEFAULT,
  XSAM_EVENT_SYSCALL,
  XSAM_EVENT_YIELD,
};

enum {
  XSAM_PROT_NONE = 0x0,
  XSAM_PROT_READ = 0x2,
  XSAM_PROT_WRITE = 0x4,
  XSAM_PROT_EXEC = 0x8,
};

extern xsam_area_t xsam_heap;

void xsam_putc(char ch);
void xsam_halt(int code) __attribute__((__noreturn__));

int xsam_ioe_init(void);
size_t xsam_io_read(uint32_t dev, uintptr_t reg, void *buf, size_t size);
size_t xsam_io_write(uint32_t dev, uintptr_t reg, const void *buf, size_t size);

int xsam_cte_init(xsam_context_t *(*handler)(xsam_event_t event, xsam_context_t *ctx));
void xsam_yield(void);
int xsam_intr_read(void);
void xsam_intr_write(int enable);

int xsam_vme_init(void *(*pgalloc)(size_t size), void (*pgfree)(void *));
void xsam_protect(xsam_address_space_t *as);
void xsam_unprotect(xsam_address_space_t *as);
void xsam_map(xsam_address_space_t *as, void *va, void *pa, int prot);
void xsam_map_fault(xsam_address_space_t *as, void *va, void *pa, int prot);
void xsam_map_rv_hugepage(
    xsam_address_space_t *as,
    void *va,
    void *pa,
    int prot,
    int pagetable_level);

int xsam_mpe_init(void (*entry)(void));
int xsam_ncpu(void);
int xsam_cpu(void);
intptr_t xsam_atomic_xchg(volatile intptr_t *addr, intptr_t newval);

#endif
