#include "xsam/am.h"
#include "xsam/amdev.h"
#include "xsrt_env.h"
#include "xsam_xs_platform.h"

xsam_area_t xsam_heap = {0};

void xsam_putc(char ch) {
  xsam_dev_serial_send_t payload;

  payload.data = (uint8_t) ch;
  xsam_xs_serial_write(XSAM_DEVREG_SERIAL_SEND, &payload, sizeof(payload));
}

void xsam_halt(int code) {
  if (code == 0) {
    xsrt_finish_pass(xsrt_current_env());
    XSRT_BAD_TRAP(0u);
  }
  xsrt_finish_fail(xsrt_current_env(), (uint64_t) code);
  XSRT_BAD_TRAP((uint64_t) code);
}

int xsam_mpe_init(void (*entry)(void)) {
  (void) entry;
  return 0;
}

int xsam_ncpu(void) {
  return 1;
}

int xsam_cpu(void) {
  return 0;
}

intptr_t xsam_atomic_xchg(volatile intptr_t *addr, intptr_t newval) {
  return __atomic_exchange_n(addr, newval, __ATOMIC_ACQ_REL);
}
