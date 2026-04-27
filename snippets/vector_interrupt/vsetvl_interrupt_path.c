#include <stdint.h>

#include "xs_snippet.h"
#include "xs_vsetvl_interrupt_path.h"


static int vsetvl_interrupt_path_run(xsrt_env_t *env) {
  unsigned long iterations;

  if (env == 0) {
    return -1;
  }

  env->flags |= (uint64_t) XS_VSETVL_FLAG_ENTERED;
  iterations = 8u + (unsigned long) (env->seed & 0xfu);

  for (unsigned long index = 0; index < iterations; ++index) {
    xs_vsetvl_emit_zero_zero_zero();
  }

  env->snippet_id = XS_VSETVL_SNIPPET_MAGIC;
  env->flags |= (uint64_t) XS_VSETVL_FLAG_COMPLETED;
  return 0;
}


const xsrt_snippet_desc_t snippet_vsetvl_interrupt_path = {
  .id = "vsetvl_interrupt_path",
  .run = vsetvl_interrupt_path_run,
};
