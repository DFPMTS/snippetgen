#include <stdint.h>

#include "xsam/am.h"
#include "xsam/program_snippet.h"
#include "xs_interrupt_response.h"
#include "xsrt_intr.h"
#include "xsrt_trap.h"

enum {
  XSAM_TIMER_EVENT_FLAG = 1u << 10,
  XSAM_TIMER_EVENT_TIMEOUT = 41,
  XSAM_TIMER_EVENT_TIMER_NOT_EXPIRED = 42,
  XSAM_TIMER_EVENT_SPINS = 65536u,
};

static xsam_context_t *am_timer_event_handler(xsam_event_t event, xsam_context_t *ctx) {
  xsrt_env_t *env = xsam_current_env();

  if (env != 0 && event.event == XSAM_EVENT_IRQ_TIMER) {
    env->flags |= (uint64_t) XSAM_TIMER_EVENT_FLAG;
  }
  return ctx;
}

static int am_timer_event_finish(int code) {
  xsam_intr_write(0);
  xsrt_timer_set_cte_active(0);
  xsrt_install_strap(0);
  return code;
}

int main(void) {
  xsrt_env_t *env = xsam_current_env();
  uint64_t last_time;
  uint64_t last_compare;

  if (env == 0) {
    return 11;
  }

  if (xsam_cte_init(am_timer_event_handler) != 0) {
    return 12;
  }

  xsam_intr_write(1);
  env->flags |= (uint64_t) XS_INTERRUPT_FLAG_TIMER_ARMED;
  last_time = 0u;
  last_compare = 0u;

  for (uint64_t spin = 0; spin < XSAM_TIMER_EVENT_SPINS; ++spin) {
    if ((env->flags & (uint64_t) XSAM_TIMER_EVENT_FLAG) != 0u) {
      env->flags |= (uint64_t) XS_INTERRUPT_FLAG_TRAP_OBSERVED;
      return am_timer_event_finish(0);
    }
    last_time = xsrt_timer_read_uptime();
    last_compare = xsrt_timer_read_compare();
    __asm__ volatile("nop" ::: "memory");
  }

  if (last_time < last_compare) {
    return am_timer_event_finish(XSAM_TIMER_EVENT_TIMER_NOT_EXPIRED);
  }

  return am_timer_event_finish(XSAM_TIMER_EVENT_TIMEOUT);
}
