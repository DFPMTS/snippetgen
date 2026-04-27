#ifndef XS_PREFETCHW_H
#define XS_PREFETCHW_H

#include <stdint.h>

enum {
  XS_PREFETCHW_EXPECTED_TRAP_CAUSE = 5u,
  XS_PREFETCHW_FLAG_COMPLETED = 0x40u,
  XS_PREFETCHW_FLAG_LOAD_PHASE_COMPLETED = 0x80u,
  XS_PREFETCHW_FLAG_PREFETCH_PHASE_COMPLETED = 0x100u,
  XS_PREFETCHW_DEBUG_CSR_TRAP_COUNT = 25u,
  XS_PREFETCHW_DEBUG_CSR_LAST_PHASE = 26u,
  XS_PREFETCHW_DEBUG_CSR_LAST_CAUSE = 27u,
  XS_PREFETCHW_DEBUG_CSR_LAST_TVAL = 28u,
  XS_PREFETCHW_DEBUG_CSR_LAST_EPC = 29u,
  XS_PREFETCHW_DEBUG_CSR_TARGET_ADDR = 30u,
  XS_PREFETCHW_DEBUG_CSR_LOAD_VALUE = 31u,
  XS_PREFETCHW_PHASE_NONE = 0u,
  XS_PREFETCHW_PHASE_LOAD = 1u,
  XS_PREFETCHW_PHASE_PREFETCH = 2u,
  XS_PREFETCHW_FAIL_LOAD_NO_TRAP = 201u,
  XS_PREFETCHW_FAIL_LOAD_BAD_TRAP = 202u,
  XS_PREFETCHW_FAIL_PREFETCH_TRAP = 203u,
};

#define XS_PREFETCHW_TARGET_ADDR ((uint64_t) 0x40000000ull)

extern volatile uint64_t xs_prefetchw_completed;
extern volatile uint64_t xs_prefetchw_phase;
extern volatile uint64_t xs_prefetchw_load_value;
extern volatile uint64_t xs_prefetchw_trap_count;
extern volatile uint64_t xs_prefetchw_last_phase;
extern volatile uint64_t xs_prefetchw_last_cause;
extern volatile uint64_t xs_prefetchw_last_tval;
extern volatile uint64_t xs_prefetchw_last_epc;
extern volatile uint64_t xs_prefetchw_target_addr;

#endif
