.section .text.trap, "ax"
.align 4
.globl xsrt_trap_entry
.type xsrt_trap_entry, @function

#define XSRT_MCAUSE_MTIP 0x8000000000000007
#define XSRT_TIMER_STATE_MTIMECMP_ADDR 0
#define XSRT_TIMER_STATE_MTIME_ADDR 8
#define XSRT_TIMER_STATE_DELTA 16
#define XSRT_TIMER_STATE_ENV_PTR 24
#define XSRT_TIMER_STATE_PERIODIC 32
#define XSRT_TIMER_STATE_CTE_ACTIVE 40
#define XSRT_TIMER_STATE_SCRATCH_A1 48
#define XSRT_TIMER_STATE_SCRATCH_A2 56
#define XSRT_TIMER_STATE_SCRATCH_A3 64
#define XSRT_ENV_FLAGS 32
#define XSRT_ENV_FINISH_CODE 40
#define XSRT_ENV_INTERRUPT_COUNT 48
#define XSRT_ENV_LAST_TRAP_CAUSE 56
#define XSRT_ENV_LAST_TRAP_EPC 64
#define XSRT_FLAG_TRAP_OBSERVED 32
#define XSRT_MIE_MTIE 128
#define XSRT_FRAME_EPC 0
#define XSRT_FRAME_CAUSE 8
#define XSRT_FRAME_TVAL 16
#define XSRT_FRAME_STATUS 24
#define XSRT_FRAME_GPR_BASE 32
#define XSRT_REGBYTES 8
#define XSRT_FRAME_SIZE 288

#define XSRT_SAVE_REG(regno, regname) sd regname, (XSRT_FRAME_GPR_BASE + (regno * XSRT_REGBYTES))(sp)
#define XSRT_LOAD_REG(regno, regname) ld regname, (XSRT_FRAME_GPR_BASE + (regno * XSRT_REGBYTES))(sp)

xsrt_trap_entry:
  csrrw a0, mscratch, a0
  sd a1, XSRT_TIMER_STATE_SCRATCH_A1(a0)
  sd a2, XSRT_TIMER_STATE_SCRATCH_A2(a0)
  sd a3, XSRT_TIMER_STATE_SCRATCH_A3(a0)
  csrr a1, mcause
  li a2, XSRT_MCAUSE_MTIP
  bne a1, a2, xsrt_trap_entry_generic_restore

  ld a2, XSRT_TIMER_STATE_ENV_PTR(a0)
  beqz a2, xsrt_trap_entry_timer_done
  ld a3, XSRT_ENV_INTERRUPT_COUNT(a2)
  addi a3, a3, 1
  sd a3, XSRT_ENV_INTERRUPT_COUNT(a2)
  sd a1, XSRT_ENV_LAST_TRAP_CAUSE(a2)
  csrr a3, mepc
  sd a3, XSRT_ENV_LAST_TRAP_EPC(a2)
  ld a3, XSRT_ENV_FLAGS(a2)
  ori a3, a3, XSRT_FLAG_TRAP_OBSERVED
  sd a3, XSRT_ENV_FLAGS(a2)

xsrt_trap_entry_timer_done:
  ld a1, XSRT_TIMER_STATE_PERIODIC(a0)
  beqz a1, xsrt_trap_entry_timer_disable
  ld a1, XSRT_TIMER_STATE_MTIME_ADDR(a0)
  ld a2, 0(a1)
  ld a1, XSRT_TIMER_STATE_DELTA(a0)
  add a2, a2, a1
  ld a1, XSRT_TIMER_STATE_MTIMECMP_ADDR(a0)
  sd a2, 0(a1)
  ld a1, XSRT_TIMER_STATE_CTE_ACTIVE(a0)
  bnez a1, xsrt_trap_entry_generic_restore
  j xsrt_trap_entry_timer_restore

xsrt_trap_entry_timer_disable:
  li a3, XSRT_MIE_MTIE
  csrc mie, a3

  ld a1, XSRT_TIMER_STATE_CTE_ACTIVE(a0)
  bnez a1, xsrt_trap_entry_generic_restore

xsrt_trap_entry_timer_restore:
  ld a3, XSRT_TIMER_STATE_SCRATCH_A3(a0)
  ld a2, XSRT_TIMER_STATE_SCRATCH_A2(a0)
  ld a1, XSRT_TIMER_STATE_SCRATCH_A1(a0)
  csrrw a0, mscratch, a0
  mret

xsrt_trap_entry_generic_restore:
  ld a3, XSRT_TIMER_STATE_SCRATCH_A3(a0)
  ld a2, XSRT_TIMER_STATE_SCRATCH_A2(a0)
  ld a1, XSRT_TIMER_STATE_SCRATCH_A1(a0)
  csrrw a0, mscratch, a0

xsrt_trap_entry_generic:
  addi sp, sp, -XSRT_FRAME_SIZE

  XSRT_SAVE_REG(0, zero)
  XSRT_SAVE_REG(1, ra)
  XSRT_SAVE_REG(3, gp)
  XSRT_SAVE_REG(4, tp)
  XSRT_SAVE_REG(5, t0)
  XSRT_SAVE_REG(6, t1)
  XSRT_SAVE_REG(7, t2)
  XSRT_SAVE_REG(8, s0)
  XSRT_SAVE_REG(9, s1)
  XSRT_SAVE_REG(10, a0)
  XSRT_SAVE_REG(11, a1)
  XSRT_SAVE_REG(12, a2)
  XSRT_SAVE_REG(13, a3)
  XSRT_SAVE_REG(14, a4)
  XSRT_SAVE_REG(15, a5)
  XSRT_SAVE_REG(16, a6)
  XSRT_SAVE_REG(17, a7)
  XSRT_SAVE_REG(18, s2)
  XSRT_SAVE_REG(19, s3)
  XSRT_SAVE_REG(20, s4)
  XSRT_SAVE_REG(21, s5)
  XSRT_SAVE_REG(22, s6)
  XSRT_SAVE_REG(23, s7)
  XSRT_SAVE_REG(24, s8)
  XSRT_SAVE_REG(25, s9)
  XSRT_SAVE_REG(26, s10)
  XSRT_SAVE_REG(27, s11)
  XSRT_SAVE_REG(28, t3)
  XSRT_SAVE_REG(29, t4)
  XSRT_SAVE_REG(30, t5)
  XSRT_SAVE_REG(31, t6)

  addi t0, sp, XSRT_FRAME_SIZE
  sd t0, (XSRT_FRAME_GPR_BASE + (2 * XSRT_REGBYTES))(sp)

  csrr t0, mepc
  sd t0, XSRT_FRAME_EPC(sp)
  csrr t0, mcause
  sd t0, XSRT_FRAME_CAUSE(sp)
  csrr t0, mtval
  sd t0, XSRT_FRAME_TVAL(sp)
  csrr t0, mstatus
  sd t0, XSRT_FRAME_STATUS(sp)

  mv a0, sp
  call xsrt_dispatch_strap
  mv sp, a0

  ld t0, XSRT_FRAME_STATUS(sp)
  csrw mstatus, t0
  ld t0, XSRT_FRAME_EPC(sp)
  csrw mepc, t0

  XSRT_LOAD_REG(1, ra)
  XSRT_LOAD_REG(3, gp)
  XSRT_LOAD_REG(4, tp)
  XSRT_LOAD_REG(5, t0)
  XSRT_LOAD_REG(6, t1)
  XSRT_LOAD_REG(7, t2)
  XSRT_LOAD_REG(8, s0)
  XSRT_LOAD_REG(9, s1)
  XSRT_LOAD_REG(10, a0)
  XSRT_LOAD_REG(11, a1)
  XSRT_LOAD_REG(12, a2)
  XSRT_LOAD_REG(13, a3)
  XSRT_LOAD_REG(14, a4)
  XSRT_LOAD_REG(15, a5)
  XSRT_LOAD_REG(16, a6)
  XSRT_LOAD_REG(17, a7)
  XSRT_LOAD_REG(18, s2)
  XSRT_LOAD_REG(19, s3)
  XSRT_LOAD_REG(20, s4)
  XSRT_LOAD_REG(21, s5)
  XSRT_LOAD_REG(22, s6)
  XSRT_LOAD_REG(23, s7)
  XSRT_LOAD_REG(24, s8)
  XSRT_LOAD_REG(25, s9)
  XSRT_LOAD_REG(26, s10)
  XSRT_LOAD_REG(27, s11)
  XSRT_LOAD_REG(28, t3)
  XSRT_LOAD_REG(29, t4)
  XSRT_LOAD_REG(30, t5)
  XSRT_LOAD_REG(31, t6)

  ld t1, (XSRT_FRAME_GPR_BASE + (2 * XSRT_REGBYTES))(sp)
  mv sp, t1
  mret
