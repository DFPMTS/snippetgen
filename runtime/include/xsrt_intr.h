#ifndef XSRT_INTR_H
#define XSRT_INTR_H

#include <stdint.h>

void xsrt_enable_stimer(void);
void xsrt_disable_stimer(void);
void xsrt_timer_arm_delta(uint64_t cycles);
void xsrt_timer_arm_periodic_delta(uint64_t cycles);
void xsrt_timer_set_cte_active(int active);
int xsrt_timer_trap_state_active(void);
uint64_t xsrt_timer_last_delta(void);
uint64_t xsrt_timer_read_uptime(void);
uint64_t xsrt_timer_read_compare(void);

#endif
