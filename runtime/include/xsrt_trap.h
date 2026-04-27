#ifndef XSRT_TRAP_H
#define XSRT_TRAP_H

#include <stdint.h>

typedef struct xsrt_trap_frame xsrt_trap_frame_t;
typedef struct xsrt_trap_scratch xsrt_trap_scratch_t;

struct xsrt_trap_frame {
  uint64_t epc;
  uint64_t cause;
  uint64_t tval;
  uint64_t status;
  uint64_t gpr[32];
};

/*
 * This layout matches the fixed offsets consumed by trap.S before it knows
 * whether the incoming trap is a timer interrupt or a synchronous exception.
 */
struct xsrt_trap_scratch {
  uint64_t mtimecmp_addr;
  uint64_t mtime_addr;
  uint64_t delta;
  uint64_t env_ptr;
  uint64_t periodic;
  uint64_t cte_active;
  uint64_t scratch_a1;
  uint64_t scratch_a2;
  uint64_t scratch_a3;
};

typedef xsrt_trap_frame_t *(*xsrt_trap_handler_t)(xsrt_trap_frame_t *);

void xsrt_install_strap(xsrt_trap_handler_t fn);
xsrt_trap_frame_t *xsrt_dispatch_strap(xsrt_trap_frame_t *frame);
void xsrt_reset_mscratch_for_sync_traps(void);

#endif
