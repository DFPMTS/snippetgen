# MMU Spec-In Case-Out Interface Draft

## 背景

昆明湖 V2 的验证不能只依赖系统级测试。当前 MMU 相关测试主要在 `XS/xs-env/nexus-am/tests/mmutest` 中，基于 AM/VME 环境编写。现在 `XS/snippetgen` 已经具备 ELF-first 的 snippet 生成、构建、运行和记录能力，需要把 `mmutest` 的测试意图和关键接口迁移到 `snippetgen`。

这次迁移不是简单搬运测试文件，而是要把 `mmutest` 中混在一起的运行时、页表、异常、虚拟化、CSR/fence 和检查逻辑拆成可复用的 `snippetgen` 接口。目标是让后续 MMU 测试能从结构化规则生成小型定向 case，同时保留未来测试微架构场景的扩展点。

## 目标

为 `snippetgen` 设计第一波 MMU 验证接口，服务于“第一层：适合 spec in, case out”的工作。

接口需要满足：

- 能表达规则型 MMU 功能测试，例如翻译模式、PTE 权限、异常类型、属性结果、fence/context 失效。
- 能把 CSR 初始化、页表布局、trap handler、指令片段和自检逻辑从规则生成出来。
- 人类可以用 API/规则快速组合场景，AI 也能根据清晰命名和注释生成可审查的 case。
- 未来可以插入“异常前动作 / 异常点 / handler 内动作 / handler 后检查”，但第一波不实现完整随机化、monitor 或 scoreboard。

## 仓库上下文

现有 `mmutest` 相关路径：

- `xs-env/nexus-am/tests/mmutest/README.md`
- `xs-env/nexus-am/tests/mmutest/include/mmutest.h`
- `xs-env/nexus-am/tests/mmutest/include/mmutest_vme.h`
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme.c`
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_pt.c`
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_fault.c`
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_hyp.c`

现有 `snippetgen` 相关路径：

- `snippetgen/README.md`
- `snippetgen/runtime/include/xsam/am.h`
- `snippetgen/runtime/include/xsam/vme.h`
- `snippetgen/runtime/include/xsam/program_snippet.h`
- `snippetgen/runtime/src/xsam_vme.c`
- `snippetgen/runtime/src/xsam_cte.c`
- `snippetgen/runtime/platform/xiangshan/xsam_xs_platform.h`
- `snippetgen/snippets/programs/nexus_memscan_page_fault_main.c`
- `snippetgen/generator/xsgen/model.py`
- `snippetgen/generator/xsgen/suite_loader.py`
- `snippetgen/generator/xsgen/toolchain.py`

现有 `snippetgen` 已支持：

- `am_program` 类型 snippet。
- suite/manifest 加载。
- deterministic harness 生成。
- ELF/bin/disasm 构建。
- XiangShan `emu` 运行和 run ledger 记录。
- 已有若干从 `nexus-am` 迁移来的 `nexus_memscan_*` 程序。

当前缺口：

- 现有 `xsam/vme.h` 只提供很薄的 AM 兼容面，不足以表达 MMU 验证规则。
- 已迁移的 `nexus_memscan_*` case 把页表、trap、PMP、satp 等逻辑写在单个 C 文件里，不能作为大规模 MMU 规则生成的基础。
- `mmutest` 的接口把多个职责混在 `mmutest_*` 命名空间下，不能直接原样搬到 `snippetgen`。

## 需要拆出的接口组

第一波计划应把 `mmutest` 拆成以下 `snippetgen` 原生模块：

- MMU 环境与布局：
  - runtime 初始化。
  - 受控页分配。
  - kernel/test/guest 地址布局。
  - stage1/stage2 page-table root 生命周期。
- 页表构造：
  - Sv39 / Sv48 / Sv39x4 / Sv48x4 初始化。
  - 普通页、superpage、raw PTE、fault PTE 映射。
  - identity map 和 alias map。
  - PTE 读回和 leaf pointer 修改。
- 控制与上下文：
  - `satp` / `vsatp` / `hgatp` 写入。
  - `ASID` / `VMID` 切换。
  - `sfence.vma` / `hfence.vvma` / `hfence.gvma`。
  - bare mode 切换。
- 异常与观察：
  - trap handler 安装。
  - expected fault arming。
  - observed fault collection。
  - sepc/tval/cause 检查。
  - handler 内动作和返回后检查的扩展点。
- 虚拟化与 H 扩展：
  - VS entry/resume。
  - HLV / HLVX / HSV 指令封装。
  - hypervisor CSR read/write。
- 规则与 coverage：
  - rule schema。
  - rule -> generated C/assembly case。
  - coverage tag。
  - defined/generated/ran/gap 状态统计。

## 第一层规则范围

第一波聚焦规则型场景：

- `Bare` / host 单阶段 / `onlyStage1` / `onlyStage2` / `allStage`。
- `load` / `store` / `HLV` / `HLVX` / `HSV`。
- 普通页 / superpage / alias。
- `V/R/W/X/U/A/D` 位组合。
- page fault / access fault / guest page fault。
- `MXR` / `SUM`。
- `PMP` / `PMA` / `PBMT` / `NC` / `MMIO`。
- `sfence` / `hfence` / `satp` / `vsatp` / `hgatp` / `ASID` / `VMID` 后旧翻译失效。
- 页表修复后重试。

规则条目需要回答：

- 适用 requestor。
- 适用翻译模式。
- 前提条件。
- 预期结果。
- 需要观察什么。
- 对应 coverage item。

## 不在第一波范围内

- 全量迁移 `mmutest` 的所有 case。
- 同页重复 miss、ITLB+DTLB 并发 miss、demand/prefetch 竞争 PTW/L2TLB 的随机扩展。
- 精确到某一拍 replay、内部 buffer 仲裁、老响应在某个 pipeline stage 被 kill 的 monitor/scoreboard。
- waveform-only 或 internal trace-only 的判定基础设施。
- L1/L2 cache 方向的完整验证。

## 第一波代表性 pilot

第一波接口至少要能表达下列代表类型：

- Bare 或基础地址直通。
- Sv39 4K alias load/store。
- superpage。
- page fault 或 access fault。
- `sfence` remap/invalidation。
- VS-only 或 G-only。
- two-stage happy path。
- two-stage fault。
- PBMT/NC/MMIO 或等价属性场景。

这些是接口证明点，不要求第一波完成 `mmutest` 全量迁移。

## 期望计划输出

正式计划需要包含：

- 可执行的 AC-X acceptance criteria。
- 明确路径边界，避免过小只做 one-off port，也避免过大进入随机化和 scoreboard。
- 具体文件目标。
- TDD/验证方式。
- 任务拆分和依赖顺序。
- `coding` / `analyze` 任务路由。

## 当前实现落点

本轮实现把第一波 MMU 规则链路固化为三层：

- `generator/xsgen/mmu_rule_loader.py`
  - 负责 rule schema、mode 规范化、coverage taxonomy 和 action phase 校验。
  - 当前 canonical mode 为 `bare`、`host_single_stage`、`onlyStage1`、`onlyStage2`、`allStage`。
  - 兼容 `only_stage1`、`only_stage2`、`all_stage` 的旧拼写，但 loader 会归一化到 canonical mode。

- `generator/xsgen/mmu_rule_emitter.py`
  - 负责把 rule DB 解析成 `generated_mmu_rule.h`、`generated_mmu_rule.c` 和稳定 JSON coverage ledger。
  - 生成物放在 `build/<suite>/` 或 `build/<suite>/runs/<batch>/seed_<N>/` 下，与现有 build/run artifact 并列。

- `snippets/programs/mmu_rule_runner_main.c`
  - 作为 generic runner 消费 generated rule data。
  - 调用 `xsam_mmu_*` runtime helper，执行 setup、before-trigger、fault handler/post-check，并给出确定性的 pass/fail 返回码。

## Rule Schema

第一波 rule 必填字段：

```yaml
id: load_page_fault
requestor: load
mode: host_single_stage
expect:
  result: page_fault
coverage_tags:
  - requestor.load
  - mode.host_single_stage
  - exception.page_fault
```

可选结构：

```yaml
symbol: load_page_fault_rule
preconditions:
  stage1: sv39
setup:
  mappings:
    - name: fault_page
      va: 0xb00000000
      pa: 0x80022000
      perms: [r, a]
      fault: true
      stage: stage1
      page_count: 1
actions:
  before_trigger:
    - sfence_vma
  handler:
    - repair_fault_mapping
  post_check:
    - record_fault_snapshot
trigger:
  op: load
  addr: fault_page
observe:
  - fault_cause_match
```

约束：

- `symbol` 是可选项，但如果提供，必须是合法 C symbol。
- `actions` 目前只接受 `before_trigger`、`handler`、`post_check` 三个 phase。
- `coverage_tags` 必须来自 loader 内置 taxonomy，未知 tag 会被拒绝。
- suite 里的 `rule_ids` 允许从更大的 rule DB 中选取子集；未选中的 rule 会在 ledger 中保留为 `defined_only`。

## Build And Ledger Flow

MMU suite 仍然走现有 `snippetgen build` / `snippetgen run` pipeline，但多出一层 MMU 生成物：

1. `suite_loader` 读取 `compose.mmu.rule_dir` 和 `compose.mmu.rule_ids`。
2. `toolchain.build_artifacts()` 先调用 MMU emitter，写出：
   - `generated_mmu_rule.h`
   - `generated_mmu_rule.c`
   - `mmu_coverage_ledger.json`
3. `generated_suite.c` 继续由既有 harness emitter 生成，并把 `mmu_rule_runner_main.c` 当作普通 `am_program` wrapper 内联进去。
4. 构建 manifest 额外记录：
   - `mmu.rule_dir`
   - `mmu.resolved_rule_ids`
   - `mmu.defined_rule_ids`
   - `artifacts.generated_mmu_header`
   - `artifacts.generated_mmu_source`
   - `artifacts.mmu_coverage_ledger`
5. `run_batch` 在单 seed 成功执行后，把该 seed 的 MMU coverage ledger 从 `generated_not_run` 升级为 `ran`。

## Coverage Ledger Semantics

MMU coverage ledger 当前同时记录 rule state 和 taxonomy tag state：

- `defined_only`
  - rule 在 DB 中定义了，但当前 suite 没有生成它。
- `generated_not_run`
  - rule 已经被当前 suite 生成，但还没有成功执行。
- `ran`
  - 当前 seed 的 run 已成功执行该 rule。
- `gap`
  - taxonomy 中定义了该 coverage tag，但当前 rule DB 里还没有任何 rule 覆盖到它。

这保证了 “defined / generated / ran / hole” 四个维度在同一个 JSON 里可追踪，而不是靠多个零散文件拼接。

## Authoring Notes

新增 MMU rule 的最小步骤：

1. 在 `snippets/mmu_rules/<group>/` 下新增 YAML rule。
2. 只使用 loader 支持的 requestor、mode、result 和 coverage tags。
3. 如果需要 stage-2 mapping，给 mapping 增加 `stage: stage2`。
4. 如果需要 fault probe，给 mapping 增加 `fault: true`，并在 `expect.result` 中选择 fault 类型。
5. 把新 rule id 加到 suite 的 `compose.mmu.rule_ids`。
6. 运行：
   - `python3 -m unittest tests.test_mmu_rule_loader tests.test_mmu_rule_emitter -v`
   - `python3 generator/cli.py dump-plan suites/mmu_pilot_rules_poc.yaml`

## Local Execution Constraint

当前 repo 的 MMU suite build 依赖能识别 `rv64gcv_zicbop` 的 RISC-V 工具链。本地 host 若只有较旧的 GCC，会在 `runtime/arch/riscv64/start.S` 编译阶段失败，典型报错为：

```text
Error: cannot find default versions of the ISA extension `v'
Error: unknown z ISA extension `zicbop'
```

因此，真实 XiangShan `emu` + NEMU 证据应在具备匹配 toolchain 的 host 上补录；本轮代码已经把 MMU suite/build/run/ledger 的接入点准备好，但不会伪造本地不存在的 real-run 结果。
