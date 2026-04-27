#include <stdint.h>

#include "xs_prefetchw.h"
#include "xs_snippet.h"
#include "xsrt_csr.h"
#include "xsrt_trap.h"

volatile uint64_t xs_prefetchw_completed;
volatile uint64_t xs_prefetchw_phase;
volatile uint64_t xs_prefetchw_load_value;
volatile uint64_t xs_prefetchw_trap_count;
volatile uint64_t xs_prefetchw_last_phase;
volatile uint64_t xs_prefetchw_last_cause;
volatile uint64_t xs_prefetchw_last_tval;
volatile uint64_t xs_prefetchw_last_epc;
volatile uint64_t xs_prefetchw_target_addr;


static uint64_t prefetchw_trap_insn_len(uint64_t epc) {
  const uint16_t insn_lo = *(const volatile uint16_t *) (uintptr_t) epc;

  return ((insn_lo & 0x3u) == 0x3u) ? 4u : 2u;
}


static xsrt_trap_frame_t *prefetchw_trap_handler(xsrt_trap_frame_t *frame) {
  xsrt_env_t *env;

  /*
   * This snippet deliberately provokes faults and keeps running so the second
   * access can still execute. Record which phase trapped, then skip over the
   * faulting instruction. RISC-V uses mixed 16b/32b instructions here, so the
   * resume PC must advance by the decoded instruction length, not a hard-coded
   * 4 bytes.
   */
  xs_prefetchw_trap_count += 1u;
  xs_prefetchw_last_phase = xs_prefetchw_phase;
  xs_prefetchw_last_cause = frame->cause;
  xs_prefetchw_last_tval = frame->tval;
  xs_prefetchw_last_epc = frame->epc;
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_TRAP_COUNT, xs_prefetchw_trap_count);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_PHASE, xs_prefetchw_last_phase);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_CAUSE, xs_prefetchw_last_cause);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_TVAL, xs_prefetchw_last_tval);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_EPC, xs_prefetchw_last_epc);

  env = xsrt_current_env();
  if (env != 0) {
    env->last_trap_cause = frame->cause;
    env->last_trap_epc = frame->epc;
  }

  frame->epc += prefetchw_trap_insn_len(frame->epc);
  return frame;
}


static uint64_t prefetchw_load_issue(const uint8_t *ptr) {
  uint64_t value;

  __asm__ volatile("ld %0, 0(%1)" : "=r"(value) : "r"(ptr) : "memory");
  return value;
}


static void prefetchw_issue(const uint8_t *ptr) {
  register uintptr_t addr __asm__("a5") = (uintptr_t) ptr;

  __asm__ volatile(
      ".word 0x0037e013\n\t"
      "# prefetch.w 0(%0)"
      :
      : "r"(addr)
      : "memory");
}


static void prefetchw_set_phase(uint64_t phase) {
  xs_prefetchw_phase = phase;
}


static int prefetchw_tl_denied_fault_init(xsrt_env_t *env) {
  if (env == 0) {
    return -1;
  }

  xs_prefetchw_completed = 0u;
  xs_prefetchw_phase = (uint64_t) XS_PREFETCHW_PHASE_NONE;
  xs_prefetchw_load_value = 0u;
  xs_prefetchw_trap_count = 0u;
  xs_prefetchw_last_phase = (uint64_t) XS_PREFETCHW_PHASE_NONE;
  xs_prefetchw_last_cause = 0u;
  xs_prefetchw_last_tval = 0u;
  xs_prefetchw_last_epc = 0u;
  xs_prefetchw_target_addr = XS_PREFETCHW_TARGET_ADDR;

  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_TRAP_COUNT, 0u);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_PHASE, (uint64_t) XS_PREFETCHW_PHASE_NONE);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_CAUSE, 0u);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_TVAL, 0u);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LAST_EPC, 0u);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_TARGET_ADDR, xs_prefetchw_target_addr);
  xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LOAD_VALUE, 0u);

  xsrt_install_strap(prefetchw_trap_handler);
  return 0;
}


static int prefetchw_tl_denied_fault_run(xsrt_env_t *env) {
  const uint8_t *target = (const uint8_t *) (uintptr_t) xs_prefetchw_target_addr;
  uint64_t traps_before = 0u;
  uint64_t load_value;

  if (env == 0) {
    return -1;
  }

  /*
   * Step 1: prove the address is really illegal for an architectural load.
   * We snapshot trap_count first so we can tell whether this exact load caused
   * a new trap instead of relying on stale trap state from some earlier phase.
   */
  prefetchw_set_phase((uint64_t) XS_PREFETCHW_PHASE_LOAD);
  traps_before = xs_prefetchw_trap_count;
  load_value = prefetchw_load_issue(target);
  if (xs_prefetchw_trap_count == traps_before) {
    /*
     * No new trap means the chosen address is not a valid negative control for
     * this test, so stop immediately instead of letting the later prefetch
     * result confuse the diagnosis.
     */
    xs_prefetchw_load_value = load_value;
    xsrt_csr_write(XS_PREFETCHW_DEBUG_CSR_LOAD_VALUE, xs_prefetchw_load_value);
    env->snippet_id = (uint64_t) XS_PREFETCHW_PHASE_LOAD;
    XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_LOAD_NO_TRAP);
  }

  /*
   * A load trap is expected here, but it still has to be the right one:
   * attributed to the load phase, with load-access-fault mcause, and with a
   * nonzero EPC captured by the trap handler.
   */
  if (
      xs_prefetchw_last_phase != (uint64_t) XS_PREFETCHW_PHASE_LOAD ||
      xs_prefetchw_last_cause != (uint64_t) XS_PREFETCHW_EXPECTED_TRAP_CAUSE ||
      xs_prefetchw_last_epc == 0u) {
    env->snippet_id = xs_prefetchw_last_phase;
    XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_LOAD_BAD_TRAP);
  }

  env->flags |= (uint64_t) XS_PREFETCHW_FLAG_LOAD_PHASE_COMPLETED;

  /*
   * Step 2: hit the same illegal address with prefetch.w. The whole point of
   * this case is that the illegal load above may trap, but the prefetch must
   * not become a software-visible exception.
   */
  prefetchw_set_phase((uint64_t) XS_PREFETCHW_PHASE_PREFETCH);
  traps_before = xs_prefetchw_trap_count;
  prefetchw_issue(target);
  if (xs_prefetchw_trap_count != traps_before) {
    /* Any additional trap here means prefetch.w leaked an architectural fault. */
    xs_prefetchw_phase = (uint64_t) XS_PREFETCHW_PHASE_NONE;
    env->snippet_id = xs_prefetchw_last_phase;
    XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_PREFETCH_TRAP);
  }

  xs_prefetchw_phase = (uint64_t) XS_PREFETCHW_PHASE_NONE;
  xs_prefetchw_completed = 1u;
  env->flags |= (uint64_t) XS_PREFETCHW_FLAG_COMPLETED;
  env->flags |= (uint64_t) XS_PREFETCHW_FLAG_PREFETCH_PHASE_COMPLETED;
  env->snippet_id = xs_prefetchw_trap_count;
  return 0;
}


static void prefetchw_tl_denied_fault_fini(xsrt_env_t *env) {
  (void) env;
  xsrt_install_strap(0);
}


const xsrt_snippet_desc_t snippet_prefetchw_tl_denied_fault = {
  .id = "prefetchw_tl_denied_fault",
  .init = prefetchw_tl_denied_fault_init,
  .run = prefetchw_tl_denied_fault_run,
  .fini = prefetchw_tl_denied_fault_fini,
};
