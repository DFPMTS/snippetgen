#include "xsrt_intr.h"

#include "xsrt_env.h"
#include "xsrt_trap.h"
#include "xsam_xs_platform.h"

static int g_stimer_enabled;
static uint64_t g_timer_delta;

extern void xsrt_trap_entry(void);

enum {
  XSRT_MSTATUS_MIE = 1u << 3,
  XSRT_MIE_MTIE = 1u << 7,
};

static xsrt_trap_scratch_t g_timer_state;

static void xsrt_refresh_timer_state(void) {
  g_timer_state.mtime_addr = xsam_xs_clint_mtime_addr();
  g_timer_state.mtimecmp_addr = xsam_xs_clint_mtimecmp_addr();
}

static void xsrt_install_timer_trap_state(void) {
  __asm__ volatile("csrw mscratch, %0" : : "r"(&g_timer_state) : "memory");
  __asm__ volatile("csrw mtvec, %0" : : "r"(&xsrt_trap_entry) : "memory");
}

void xsrt_enable_stimer(void) {
  g_stimer_enabled = 1;
  xsrt_refresh_timer_state();
  g_timer_state.env_ptr = (uint64_t) (uintptr_t) xsrt_current_env();
  {
    const unsigned long mie_mask = XSRT_MIE_MTIE;
    const unsigned long mstatus_mask = XSRT_MSTATUS_MIE;
    xsrt_install_timer_trap_state();
    __asm__ volatile("csrs mie, %0" : : "r"(mie_mask) : "memory");
    __asm__ volatile("csrs mstatus, %0" : : "r"(mstatus_mask) : "memory");
  }
}

void xsrt_disable_stimer(void) {
  g_stimer_enabled = 0;
  g_timer_state.periodic = 0;
  {
    const unsigned long mie_mask = XSRT_MIE_MTIE;
    __asm__ volatile("csrc mie, %0" : : "r"(mie_mask) : "memory");
  }
  /* After timer mode is disabled, synchronous traps still need valid scratch. */
  xsrt_reset_mscratch_for_sync_traps();
}

void xsrt_timer_arm_delta(uint64_t cycles) {
  if (g_stimer_enabled == 0) {
    return;
  }

  xsrt_refresh_timer_state();
  g_timer_delta = cycles;
  g_timer_state.delta = cycles;
  g_timer_state.env_ptr = (uint64_t) (uintptr_t) xsrt_current_env();
  g_timer_state.periodic = 0;
  xsam_xs_clint_write_mtimecmp(xsam_xs_clint_read_mtime() + cycles);
}

void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
  if (g_stimer_enabled == 0) {
    return;
  }

  xsrt_refresh_timer_state();
  g_timer_delta = cycles;
  g_timer_state.delta = cycles;
  g_timer_state.env_ptr = (uint64_t) (uintptr_t) xsrt_current_env();
  g_timer_state.periodic = 1;
  xsam_xs_clint_write_mtimecmp(xsam_xs_clint_read_mtime() + cycles);
}

void xsrt_timer_set_cte_active(int active) {
  g_timer_state.cte_active = (uint64_t) (active != 0);
  if (g_stimer_enabled != 0) {
    xsrt_install_timer_trap_state();
  }
}

int xsrt_timer_trap_state_active(void) {
  return g_stimer_enabled != 0;
}

uint64_t xsrt_timer_last_delta(void) {
  return g_timer_delta;
}

uint64_t xsrt_timer_read_uptime(void) {
  return xsam_xs_clint_read_mtime();
}

uint64_t xsrt_timer_read_compare(void) {
  return xsam_xs_clint_read_mtimecmp();
}
