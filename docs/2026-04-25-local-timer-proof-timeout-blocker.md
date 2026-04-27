# 2026-04-25 Local Timer Proof Timeout Blocker

## Summary

On April 25, 2026, the local XiangShan `emu` flow timed out on both:

- [am_timer_event_poc](/nfs/home/liujunqi/XS/snippetgen/suites/am_timer_event_poc.yaml)
- [interrupt_response_poc](/nfs/home/liujunqi/XS/snippetgen/suites/interrupt_response_poc.yaml)

This matters because `interrupt_response_poc` is the older timer proof suite that previously produced `good_trap`, while `am_timer_event_poc` is the new AM-surface suite added to validate the review finding around `xsam_cte_init(...); xsam_intr_write(1);`.

The shared failure mode means the current local target blocker is broader than the new AM suite alone. Host-side/unit evidence still shows the round-4 code fixes landed correctly, but local target-level timer proof is not reliable enough to claim completion.

## Commands

### New AM timer suite

```bash
env SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
  python3 generator/cli.py run suites/am_timer_event_poc.yaml \
  --seed 0 \
  --batch-id rlcr-round4-am-timer-event-v2 \
  --timeout-sec 180
```

Result:

- `status: timeout`
- `notes: timeout after 180s`
- Batch meta: [build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/batch_meta.json](/nfs/home/liujunqi/XS/snippetgen/build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/batch_meta.json)
- Stdout: [build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/seed_0/stdout.log](/nfs/home/liujunqi/XS/snippetgen/build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/seed_0/stdout.log)
- Stderr: [build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/seed_0/stderr.log](/nfs/home/liujunqi/XS/snippetgen/build/am_timer_event_poc/runs/rlcr-round4-am-timer-event-v2/seed_0/stderr.log)

### Historical timer proof suite

```bash
env SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
  python3 generator/cli.py run suites/interrupt_response_poc.yaml \
  --seed 0 \
  --batch-id rlcr-round4-interrupt-response-recheck \
  --timeout-sec 180
```

Result:

- `status: timeout`
- `notes: timeout after 180s`
- Batch meta: [build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/batch_meta.json](/nfs/home/liujunqi/XS/snippetgen/build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/batch_meta.json)
- Stdout: [build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/seed_0/stdout.log](/nfs/home/liujunqi/XS/snippetgen/build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/seed_0/stdout.log)
- Stderr: [build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/seed_0/stderr.log](/nfs/home/liujunqi/XS/snippetgen/build/interrupt_response_poc/runs/rlcr-round4-interrupt-response-recheck/seed_0/stderr.log)

## Common Runtime Shape

Both stdout logs stop after the same early `emu` startup banner:

- `Core  0's Commit SHA is: ad21e8099e, dirty: 0`
- `The reference model is /nfs/home/liujunqi/XS/xs-env/NEMU/build/riscv64-nemu-interpreter-so`
- `[FORK_INFO pid(...)] enable fork debugging...`

Neither run reaches `HIT GOOD TRAP`, `HIT BAD TRAP`, `Unknown trap code`, or a normal `sim_exit` classification before the host-side timeout kills the process.

## What Is Still Proven

The round-4 review fixes still have direct repo-level evidence:

- Portable default ISA is restored by [generator/xsgen/toolchain.py](/nfs/home/liujunqi/XS/snippetgen/generator/xsgen/toolchain.py), and the focused build/runtime unit tests pass with `rv64gc`.
- MMU coverage promotion now depends on semantic success in [generator/xsgen/run_batch.py](/nfs/home/liujunqi/XS/snippetgen/generator/xsgen/run_batch.py), and targeted run-pipeline tests pass.
- `xsam_intr_write()` now drives the real timer hooks in [runtime/src/xsam_cte.c](/nfs/home/liujunqi/XS/snippetgen/runtime/src/xsam_cte.c), and host-level tests in [tests/test_xsam_cte_behavior.py](/nfs/home/liujunqi/XS/snippetgen/tests/test_xsam_cte_behavior.py) and [tests/test_am_program_snippet_runtime.py](/nfs/home/liujunqi/XS/snippetgen/tests/test_am_program_snippet_runtime.py) verify the call path.

## Current Interpretation

The timer proof blocker is currently best treated as a local target-evidence issue, not as proof that the round-4 source changes are wrong.

Reasoning:

- The old timer proof suite now times out alongside the new AM suite.
- The failure mode is a host timeout with no guest trap classification, not a clean functional counterexample.
- Host and focused pipeline tests for the reviewed code paths pass.

Until XiangShan/NEMU local timer runs are stable again, the round can claim code-level fixes and explicit blocker documentation, but not fresh target-level timer success evidence.
