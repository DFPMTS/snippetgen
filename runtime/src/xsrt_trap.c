#include "xsrt_trap.h"

#include "xsrt_intr.h"

static xsrt_trap_scratch_t g_sync_trap_scratch;
static xsrt_trap_handler_t g_s_trap_handler;

extern void xsrt_trap_entry(void);

void xsrt_reset_mscratch_for_sync_traps(void) {
  /*
   * Keep mscratch valid even when only synchronous exceptions are enabled.
   * trap.S swaps a0 with mscratch before it can inspect mcause, so leaving
   * mscratch uninitialized causes the trap entry itself to fault.
   */
  g_sync_trap_scratch.env_ptr = 0u;
  g_sync_trap_scratch.mtime_addr = 0u;
  g_sync_trap_scratch.periodic = 0u;
  g_sync_trap_scratch.cte_active = 0u;
  g_sync_trap_scratch.scratch_a1 = 0u;
  g_sync_trap_scratch.scratch_a2 = 0u;
  g_sync_trap_scratch.scratch_a3 = 0u;
  __asm__ volatile("csrw mscratch, %0" : : "r"(&g_sync_trap_scratch) : "memory");
}

void xsrt_install_strap(xsrt_trap_handler_t fn) {
  g_s_trap_handler = fn;
  if (xsrt_timer_trap_state_active() == 0) {
    xsrt_reset_mscratch_for_sync_traps();
  }
  __asm__ volatile("csrw mtvec, %0" : : "r"(&xsrt_trap_entry) : "memory");
}

xsrt_trap_frame_t *xsrt_dispatch_strap(xsrt_trap_frame_t *frame) {
  if (g_s_trap_handler == 0) {
    return frame;
  }

  return g_s_trap_handler(frame);
}
