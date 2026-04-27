# 2026-04-24 MMU Pilot Local Fallback Attempt

这不是可接受的 MMU pilot evidence，只是 2026-04-24 在当前 host 上对 fallback toolchain 的保底探测记录。

## Commands

```bash
env 'riscv64-unknown-linux-gnu-gcc'=/usr/bin/riscv64-linux-gnu-gcc \
    'riscv64-unknown-linux-gnu-objcopy'=/usr/bin/riscv64-linux-gnu-objcopy \
    SNIPPETGEN_RISCV_MARCH=rv64gc \
    SNIPPETGEN_RISCV_MABI=lp64d \
    SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
    SNIPPETGEN_RUN_MAX_CYCLES=200000 \
    SNIPPETGEN_RUN_MAX_INSTR=200000 \
    python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml \
      --seed 7 \
      --batch-id real_mmu_pilot_round2 \
      --timeout-sec 180
```

对照命令：

```bash
env 'riscv64-unknown-linux-gnu-gcc'=/usr/bin/riscv64-linux-gnu-gcc \
    'riscv64-unknown-linux-gnu-objcopy'=/usr/bin/riscv64-linux-gnu-objcopy \
    SNIPPETGEN_RISCV_MARCH=rv64gc \
    SNIPPETGEN_RISCV_MABI=lp64d \
    SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
    SNIPPETGEN_RUN_MAX_CYCLES=200000 \
    SNIPPETGEN_RUN_MAX_INSTR=200000 \
    python3 generator/cli.py run suites/am_hello_main_poc.yaml \
      --seed 7 \
      --batch-id toolchain_probe_am_hello \
      --timeout-sec 180
```

## Observed Result

- `batch_meta.json` / `run_meta.json` 记录为 `status=ran`, `finish_code=0`, `notes=HIT GOOD TRAP`。
- 但 MMU pilot 和 `am_hello_main_poc` 都出现同样的 early-boot 异常：

```text
isa pma check failed, vaddr=0x0000000000000000, paddr=0x0000000000000000
HIT CRITICAL ERROR: please check if software cause a double trap.
HIT GOOD TRAP at pc = 0xe
Core-0 instrCnt = 3
```

## Interpretation

- 这个 fallback toolchain 组合可以把 `snippetgen` suite 编译、链接并交给 `emu` 运行。
- 但它对简单 `am_hello_main_poc` 也只执行了 3 条指令就落入同样的 double-trap / fake-good-trap 模式。
- 因此 `real_mmu_pilot_round2` 不能作为本轮要求的有效 XiangShan/NEMU MMU evidence。
- 真正可接受的 evidence 仍然需要在能原生支持仓库目标 ISA 和平台假设的 host/toolchain 上重新采集。
