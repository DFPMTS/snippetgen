# 2026-04-24 MMU Local Toolchain Blocker

本地 `snippetgen` MMU suite 的真实 build/run 仍然不能作为有效 evidence 交付，原因不是 MMU rule pipeline 缺失，而是当前 host 上没有一套同时满足“可编译仓库默认 ISA”与“可产出可信 XiangShan/NEMU run”这两个条件的工具链组合。

首先，当前 host 上默认可发现的 RISC-V GCC 无法识别仓库默认 ISA 目标：

```text
-march=rv64gcv_zicbop
```

本地直接构建 `suites/mmu_pilot_rules_poc.yaml` 时，报错为：

```text
Error: cannot find default versions of the ISA extension `v'
Error: unknown z ISA extension `zicbop'
```

受影响命令：

```bash
python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml
python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml --seed 17 --batch-id mmu-coverage-demo
```

2026-04-24 进一步做了一个 fallback 尝试：

```bash
env 'riscv64-unknown-linux-gnu-gcc'=/usr/bin/riscv64-linux-gnu-gcc \
    'riscv64-unknown-linux-gnu-objcopy'=/usr/bin/riscv64-linux-gnu-objcopy \
    SNIPPETGEN_RISCV_MARCH=rv64gc \
    SNIPPETGEN_RISCV_MABI=lp64d \
    SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
    python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml --seed 7 --batch-id real_mmu_pilot_round2
```

这个 fallback path 可以完成编译和链接，但它对 MMU pilot 与对照用的 `am_hello_main_poc` 都给出相同的不可接受 boot 行为：

```text
isa pma check failed, vaddr=0x0, paddr=0x0
HIT CRITICAL ERROR: please check if software cause a double trap.
HIT GOOD TRAP at pc = 0xe
Core-0 instrCnt = 3
```

也就是说，这个 fallback toolchain 会在程序真正进入 workload 前就掉进 early-boot double-trap，但 run metadata 仍然被表面上记成 `good_trap`。因此它不能拿来证明 MMU suite 在 XiangShan/NEMU 上真实通过。

相关探测记录已存档到：

- `docs/evidence/mmu-pilot/2026-04-24-local-rv64gc-fallback-batch_meta.json`
- `docs/evidence/mmu-pilot/2026-04-24-local-rv64gc-fallback-run_meta.json`
- `docs/evidence/mmu-pilot/2026-04-24-local-rv64gc-fallback-notes.md`

当前已完成：

- MMU rule loader、emitter、suite integration、generic runner、coverage ledger 接入。
- `dump-plan`、`build manifest`、`run_batch` 的 MMU metadata 和 ledger 路径记录。
- 纯 Python / host compile 级别测试通过。
- 使用 fallback ISA override 的 MMU pilot build 已通过，本地 focused unittest 也通过。
- 已确认 fallback `rv64gc` run 对简单 non-MMU suite 同样存在 boot-level double-trap，因此 blocker 属于 host/toolchain 可信度而不是 MMU runner 语义。

下一步需要在具备可信 XiangShan 目标工具链的 host 上执行：

1. `python3 generator/cli.py build suites/mmu_pilot_rules_poc.yaml`
2. `python3 generator/cli.py run suites/mmu_pilot_rules_poc.yaml --seed <seed> --batch-id <batch>`
3. 将产出的 `batch_meta.json` 复制到 `docs/evidence/mmu-pilot/`
4. 追加一份简短 run notes，记录 suite、batch、seed、finish_code 和 expected outcome
