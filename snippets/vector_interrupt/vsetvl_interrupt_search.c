#include <stdint.h>

#include "xs_snippet.h"
#include "xs_interrupt_response.h"
#include "xs_vsetvl_interrupt_path.h"
#include "xsrt_intr.h"

#define XS_VSETVL_X1() xs_vsetvl_emit_zero_zero_zero()
#define XS_VSETVL_X2() do { XS_VSETVL_X1(); XS_VSETVL_X1(); } while (0)
#define XS_VSETVL_X4() do { XS_VSETVL_X2(); XS_VSETVL_X2(); } while (0)
#define XS_VSETVL_X8() do { XS_VSETVL_X4(); XS_VSETVL_X4(); } while (0)


static unsigned long vsetvl_search_skid(unsigned long lane, unsigned long count) {
  for (unsigned long index = 0; index < count; ++index) {
    __asm__ volatile(
        "addi %[lane], %[lane], 1\n"
        "xori %[lane], %[lane], 7\n"
        "andi %[lane], %[lane], 255\n"
        : [lane] "+r"(lane)
        :
        : "memory");
  }

  return lane;
}


static int vsetvl_interrupt_search_run(xsrt_env_t *env) {
  unsigned long iterations;
  unsigned long pre_pad;

  if (env == 0) {
    return -1;
  }

  env->flags |= (uint64_t) (XS_INTERRUPT_FLAG_TIMER_ARMED | XS_VSETVL_FLAG_ENTERED);

  iterations = 256u + (unsigned long) ((env->seed >> 4) & 0x7fu);
  pre_pad = (unsigned long) (env->seed & 0x7u);

  (void) vsetvl_search_skid((unsigned long) env->seed, pre_pad);
  xsrt_enable_stimer();
  xsrt_timer_arm_periodic_delta(8u + (uint64_t) ((env->seed >> 13) & 0x7u));

  for (unsigned long index = 0; index < iterations; ++index) {
    XS_VSETVL_X8();
  }

  env->snippet_id = XS_VSETVL_SNIPPET_MAGIC ^ (uint64_t) iterations;
  env->flags |= (uint64_t) XS_VSETVL_FLAG_COMPLETED;
  return 0;
}


const xsrt_snippet_desc_t snippet_vsetvl_interrupt_search = {
  .id = "vsetvl_interrupt_search",
  .run = vsetvl_interrupt_search_run,
};
