#include "xsam/am.h"

#include "xsrt_intr.h"
#include "xsrt_trap.h"

static xsam_context_t *(*g_event_handler)(xsam_event_t event, xsam_context_t *ctx);
static int g_interrupt_enabled;

enum {
  XSAM_MCAUSE_INTERRUPT = 1ull << 63,
  XSAM_MCAUSE_MSIP = XSAM_MCAUSE_INTERRUPT | 3u,
  XSAM_MCAUSE_MTIP = XSAM_MCAUSE_INTERRUPT | 7u,
  XSAM_MCAUSE_MEIP = XSAM_MCAUSE_INTERRUPT | 11u,
  XSAM_MCAUSE_ECALL_M = 11u,
  XSAM_MCAUSE_IPF = 12u,
  XSAM_MCAUSE_LPF = 13u,
  XSAM_MCAUSE_SPF = 15u,
  XSAM_INTR_TIMER_DELTA = 64u,
};

static int xsam_is_pagefault(uint64_t cause) {
  return cause == XSAM_MCAUSE_IPF || cause == XSAM_MCAUSE_LPF || cause == XSAM_MCAUSE_SPF;
}

static xsam_event_t xsam_event_from_frame(const xsrt_trap_frame_t *frame) {
  xsam_event_t event;

  event.event = XSAM_EVENT_ERROR;
  event.cause = frame->cause;
  event.ref = frame->tval;
  event.msg = 0;

  if (frame->cause == XSAM_MCAUSE_MSIP) {
    event.event = XSAM_EVENT_IRQ_SOFT;
  } else if (frame->cause == XSAM_MCAUSE_MTIP) {
    event.event = XSAM_EVENT_IRQ_TIMER;
  } else if (frame->cause == XSAM_MCAUSE_MEIP) {
    event.event = XSAM_EVENT_IRQ_IODEV;
  } else if (frame->cause == XSAM_MCAUSE_ECALL_M) {
    event.event = frame->gpr[17] == (uint64_t) -1ll ? XSAM_EVENT_YIELD : XSAM_EVENT_SYSCALL;
  } else if (xsam_is_pagefault(frame->cause)) {
    event.event = XSAM_EVENT_PAGEFAULT;
  }

  return event;
}

static void xsam_context_from_frame(xsam_context_t *ctx, const xsrt_trap_frame_t *frame) {
  for (int index = 0; index < 32; ++index) {
    ctx->gpr[index] = (uintptr_t) frame->gpr[index];
  }
  ctx->cause = (uintptr_t) frame->cause;
  ctx->status = (uintptr_t) frame->status;
  ctx->epc = (uintptr_t) frame->epc;
  if (frame->cause == XSAM_MCAUSE_ECALL_M) {
    ctx->epc += 4u;
  }
  ctx->pdir = 0;
}

static void xsam_context_to_frame(xsrt_trap_frame_t *frame, const xsam_context_t *ctx) {
  for (int index = 0; index < 32; ++index) {
    frame->gpr[index] = (uint64_t) ctx->gpr[index];
  }
  frame->cause = (uint64_t) ctx->cause;
  frame->status = (uint64_t) ctx->status;
  frame->epc = (uint64_t) ctx->epc;
}

static xsrt_trap_frame_t *xsam_cte_trap_handler(xsrt_trap_frame_t *frame) {
  xsam_context_t ctx;
  xsam_context_t *next_ctx;
  xsam_event_t event;

  if (frame == 0 || g_event_handler == 0) {
    return frame;
  }

  xsam_context_from_frame(&ctx, frame);
  event = xsam_event_from_frame(frame);
  next_ctx = g_event_handler(event, &ctx);
  if (next_ctx != 0) {
    xsam_context_to_frame(frame, next_ctx);
  }
  return frame;
}

int xsam_cte_init(xsam_context_t *(*handler)(xsam_event_t event, xsam_context_t *ctx)) {
  if (handler == 0) {
    return -1;
  }

  g_event_handler = handler;
  xsrt_install_strap(xsam_cte_trap_handler);
  xsrt_timer_set_cte_active(handler != 0);
  return 0;
}

void xsam_yield(void) {
#if defined(__riscv)
  __asm__ volatile("li a7, -1\n\tecall" : : : "a7", "memory");
#else
  return;
#endif
}

int xsam_intr_read(void) {
  return g_interrupt_enabled;
}

void xsam_intr_write(int enable) {
  g_interrupt_enabled = (enable != 0);
  if (g_interrupt_enabled) {
    xsrt_enable_stimer();
    xsrt_timer_arm_periodic_delta(XSAM_INTR_TIMER_DELTA);
  } else {
    xsrt_disable_stimer();
  }
}
