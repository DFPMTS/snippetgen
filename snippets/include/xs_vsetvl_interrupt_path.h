#ifndef XS_VSETVL_INTERRUPT_PATH_H
#define XS_VSETVL_INTERRUPT_PATH_H

#include <stdint.h>

enum {
  XS_VSETVL_FLAG_ENTERED = 1u << 5,
  XS_VSETVL_FLAG_COMPLETED = 1u << 6,
  XS_VSETVL_SNIPPET_MAGIC = 0x56534554u,
  XS_VSETVL_MATCH = 0x80007057u,
};

static inline void xs_vsetvl_emit_zero_zero_zero(void) {
  /*
   * Emit real `vsetvl zero, zero, zero` without requiring the assembler to
   * parse RVV mnemonics from the global -march setting.
   */
  __asm__ volatile(".word 0x80007057" ::: "memory");
}

#endif
