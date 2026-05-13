# 昆明湖 v2/v3 MMU 第一层 baseline 与 gap 推进计划

## Goal Description

在 `snippetgen` 当前已有 MMU layer1 基础设施之上，先把昆明湖 v2/v3 第一层规则型验证做成可信 baseline，再补齐仍属于第一层的架构规则 gap。本轮工作不进入第二层并发 miss、PTW/L2TLB 竞争、replay 时序、prefetch drop、stale response pipeline kill 等微架构 monitor/stress 验证。

当前基础设施已经存在：

- `snippets/mmu_rules/kmh_layer1/` 存放昆明湖第一层 YAML rule。
- `snippets/programs/mmu_rule_runner_main.c` 执行 generated MMU rule。
- `generator/xsgen/mmu_rule_loader.py` 与 `generator/xsgen/mmu_rule_emitter.py` 负责 schema 校验、C artifact 生成和 coverage ledger 生成。
- `suites/kmh_mmu_layer1_*` 已经按 smoke、host permission、attribute/control、H extension、faults、full 分组。
- `/nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json` 登记 `kmh-v2/difftest` 和 `kmh-v3/difftest` runner profile。

本轮重点是：

- 用最新 cached v2/v3 runner 重新跑 smoke/group baseline。
- 形成可读的 baseline evidence 和 coverage gap 汇总。
- 只补第一层可由当前 workload 自检的架构规则：权限负例、two-stage fault 分类、context/fence 生效性、superpage 组合。
- 保持 v3 第一轮 vector-free；v2 vector MMU suite 不进入本轮主线。

## Acceptance Criteria

- AC-1: 当前 v2/v3 MMU layer1 baseline 被重新验证并沉淀证据。
  - Positive Tests (expected to PASS):
    - 在 `kmh-v2/difftest` 与 `kmh-v3/difftest` 上分别运行 `suites/kmh_mmu_layer1_v2_smoke.yaml` 和 `suites/kmh_mmu_layer1_v3_smoke.yaml`，batch metadata 记录 `runner_profile`、runner revision、NEMU revision、seed、batch id、finish code 和 log path。
    - 在 v2/v3 上分别运行 `kmh_mmu_layer1_host_perm.yaml`、`kmh_mmu_layer1_attr_ctrl.yaml`、`kmh_mmu_layer1_hyp.yaml`、`kmh_mmu_layer1_faults.yaml`，成功时 coverage ledger 中对应 selected rule 进入 `ran`。
    - 若某个 group 因 timeout、abort、difftest mismatch、runner missing 或真实 bad trap 失败，run notes 必须记录 suite、profile、batch id、失败分类、stdout/stderr 路径和下一步归因方向。
    - baseline run 使用 cached runner profile，不依赖默认 `SNIPPETGEN_XS_EMU` 或当前 shell 下的 XiangShan branch。
  - Negative Tests (expected to FAIL):
    - 目标运行没有 `good_trap`、`finish_code: 0` 或等价成功状态时，不能把 rule 标记为 `ran`。
    - batch metadata 缺少 `runner_profile`、runner revision 或 NEMU revision 时，baseline evidence 不完整。
    - 只跑 v2 或只跑 v3，但文档声称完成 v2/v3 baseline，视为失败。

- AC-2: coverage gap 能以人可读方式汇总。
  - Positive Tests (expected to PASS):
    - 新增或扩展 coverage summary 入口，能读取 `mmu_coverage_ledger.json` 和 batch metadata，输出每个 coverage tag 的 `defined`、`selected/generated`、`ran`、`gap` 状态。
    - summary 能按 suite 和 profile 区分 v2/v3 运行结果，避免把 v2 的 `ran` 误当成 v3 的 `ran`。
    - summary 能列出 rule 级别状态：`defined_only`、`generated_not_run`、`ran`、`failed_or_blocked`。
    - summary 输出能直接定位 ledger path、suite、batch id 和 seed。
  - Negative Tests (expected to FAIL):
    - 未进入任何 suite 的新增 rule 不能被显示为已生成或已运行。
    - 某个 coverage tag 只在 rule database 里存在，但没有 selected suite 或没有成功 target run，不能显示为完成。
    - v2/v3 profile 的 coverage 结果被合并成单列且无法区分版本时，测试失败。

- AC-3: 补齐第一层权限负例规则。
  - Positive Tests (expected to PASS):
    - 新增 load 权限负例：`R=0` 或 raw PTE 缺少读权限时产生 load page fault，observe 包含 `fault_cause_match`。
    - 新增 store 权限负例：`W=0` 或 `D=0` 时产生 store page fault，observe 包含 `fault_cause_match`。
    - 新增 HLVX 权限负例：`X=0` 时产生 load guest page fault 或对应 H 扩展 fault 分类，observe 包含 `fault_cause_match`。
    - 新增 `A=0` 相关负例，明确在当前 core 行为下预期是 page fault 或由实现置位；若实现策略不明确，规则进入 documented gap 而不是模糊 pass。
    - 现有 `MXR`、`SUM` 正例之外，补充至少一个对应负例或明确记录当前 runner 无法稳定自检的原因。
    - 每条新增 rule 都有 coverage tags，例如 `pte.r`、`pte.w`、`pte.x`、`pte.a`、`pte.d`、`priv.mxr`、`priv.sum`、`exception.page_fault` 或 `exception.guest_page_fault`。
  - Negative Tests (expected to FAIL):
    - raw PTE 写成非法 `W=1,R=0` 却 expect `hit` 时，loader 或 inventory 测试必须拒绝。
    - 权限负例没有 `fault_cause_match` observe，不能进入正式 suite。
    - rule id、coverage tags 或 expected result 与实际 requestor/fault 类型不一致时，unit test 或 single-case run 失败。

- AC-4: 补齐第一层 two-stage fault 分类规则。
  - Positive Tests (expected to PASS):
    - 新增 `allStage` 下 stage1 fault case，预期普通 page fault，不误判为 guest page fault。
    - 新增 `allStage` 下 stage2 fault case，预期 guest page fault，并覆盖 load guest page fault。
    - 新增 `onlyStage2` 下 HLV guest fault、HLVX guest fault、HSV guest fault 中至少两类；若已有规则覆盖其中一类，新增规则需覆盖剩余类别或明确 gap。
    - 每条 rule 都能通过 `dump-plan`、`build` 和 single-case run，失败时记录是否为测试构造问题还是 DUT 行为问题。
  - Negative Tests (expected to FAIL):
    - `allStage` rule 缺少 stage1 或 stage2 mapping 时，loader/inventory 测试失败。
    - HLV/HLVX/HSV 的 fault expectation 与 loader 支持的 requestor/result pair 不匹配时，测试失败。
    - stage1 fault 被 coverage 标成 `exception.guest_page_fault` 或 stage2 fault 被标成普通 `exception.page_fault` 时，inventory 测试失败。

- AC-5: 补齐第一层 context/fence 生效性规则。
  - Positive Tests (expected to PASS):
    - 新增或强化 satp/ASID context switch case，同一 VA 在切换后读到 switch mapping 的物理值。
    - 新增或强化 vsatp/hgatp/VMID context switch case，同一 GVA/GPA 在切换后读到 switch mapping 的物理值。
    - 新增 sfence/hfence remap 生效 case，修改页表后执行对应 fence，再观察新映射值。
    - coverage tags 覆盖 `ctrl.satp`、`ctrl.asid`、`ctrl.vsatp`、`ctrl.hgatp`、`ctrl.vmid`、`ctrl.sfence`、`ctrl.hfence_vvma`、`ctrl.hfence_gvma` 中本轮涉及的项。
  - Negative Tests (expected to FAIL):
    - context switch action 没有配套 `context: switch` mapping 时，loader/inventory 测试失败。
    - rule 只执行 fence 但没有可观测的新旧映射差异，不能作为 context/fence 生效性覆盖。
    - 旧上下文 stale in-flight response 的微架构 kill 被写成本轮第一层 pass/fail 规则时，inventory 应将其挡回 backlog。

- AC-6: 补齐第一层 superpage 组合规则。
  - Positive Tests (expected to PASS):
    - 新增 host single-stage superpage load 和 store 代表性规则，覆盖 `page.superpage` 与 load/store 两类 requestor。
    - 新增 stage2 superpage 规则，覆盖 H 扩展 requestor 通过 G-stage superpage 的 hit 或 fault。
    - 新增 allStage superpage/4K 混合规则：stage1 superpage + stage2 4K，或 stage1 4K + stage2 superpage，至少覆盖一种组合。
    - superpage 规则的地址、page_count、对齐和权限配置由 loader/emitter 校验或由 unit test 覆盖。
  - Negative Tests (expected to FAIL):
    - superpage rule 的 VA/PA 不满足对齐要求但 expect `hit` 时，build/run 不能静默通过。
    - `page.superpage` tag 对应的 rule 实际只映射 4K page 时，inventory 测试失败。
    - stage2 superpage rule 没有 H 扩展 requestor 或 allStage/onlyStage2 mode 时，不能计入 stage2 superpage 覆盖。

- AC-7: 文档和回归入口反映新的 baseline/gap 流程。
  - Positive Tests (expected to PASS):
    - README 或 MMU runbook 说明如何运行 v2/v3 smoke、group baseline、coverage summary 和 single-case 调试。
    - 文档明确本轮不覆盖第二层/第三层微架构场景，并把这些场景列为 deferred backlog。
    - 新增规则流程说明包含：添加 YAML、添加 single-case suite、跑 `dump-plan`、跑 `build`、跑 v2/v3 single-case、再加入 group/full suite。
    - 若新增 make target 或脚本入口，它必须调用现有 `generator/cli.py` 和 runner profile 机制，不复制运行逻辑。
  - Negative Tests (expected to FAIL):
    - 文档声称覆盖 ITLB/DTLB 并发 miss、prefetch drop、merged miss、replay 拍点，但没有 monitor/scoreboard evidence 时，文档检查应指出 scope claim 不成立。
    - runbook 没有说明 v3 vector-free 策略，或把 v2 vector MMU suite 混进 v3 baseline，视为不满足本 AC。
    - 新增规则没有进入任何 suite，coverage summary 必须显示为 `defined_only` 或 gap，不能被文档标成完成。

## Path Boundaries

### Upper Bound (Maximum Scope)

完成 v2/v3 最新 cached runner 的 MMU layer1 smoke 与 group baseline，新增 coverage summary，补齐第一层权限负例、two-stage fault 分类、context/fence 生效性、superpage 组合规则，更新 suite、runbook、evidence 和必要单元测试。所有新增规则必须能通过 `dump-plan`、`build`，并在 v2/v3 上有 target run evidence 或明确 profile-specific gap。

### Lower Bound (Minimum Scope)

至少完成：

- v2/v3 smoke baseline evidence。
- v2/v3 host permission、attribute/control、H extension、faults group baseline evidence，或者明确失败阻塞记录。
- coverage gap summary 的最小可用版本。
- 每类新增规则至少一条：权限负例、two-stage fault 分类、context/fence 生效性、superpage 组合。
- 文档明确第二层验证不在本轮范围。

只写计划不跑 baseline、只跑 baseline 不输出 gap、只新增 rule 但不进入 suite、或只在 v2/v3 其中一个版本验证且不记录另一个版本状态，都不满足下界。

### Allowed Choices

- Can use: 现有 `mmu_rule_loader.py`、`mmu_rule_emitter.py`、`mmu_rule_runner_main.c`、`mmu_coverage_ledger.json`、`generator/cli.py dump-plan/build/run`、runner profile manifest、batch metadata。
- Can use: 新增 coverage summary Python 模块、CLI 子命令、make target 或脚本入口。
- Can use: single-case suite 先调通，再加入 group suite 和 full suite。
- Can use: 文档记录 profile-specific gap，例如某规则 v2 通过但 v3 因已知 vector-free 或实现差异暂不运行。
- Cannot use: `bitlesson` 或 `ask-codex`。
- Cannot use: 把 Kunminghu `emu`、NEMU `.so`、wave 大文件提交进 git。
- Cannot use: 在本轮第一层计划里声称覆盖第二层/第三层微架构现象。
- Cannot use: 把 v2 vector MMU case 混进 v3 smoke/full baseline。

## Dependencies and Sequence

### Milestones

1. Milestone 1: 固化当前 baseline
   - Phase A: 跑 host unit tests，确认 loader/emitter/runner profile 基础仍然通过。
   - Phase B: 跑 v2/v3 smoke baseline。
   - Phase C: 跑 v2/v3 group baseline，并记录 evidence。

2. Milestone 2: 建立 coverage gap summary
   - Phase A: 盘点当前 `mmu_coverage_ledger.json` schema 和 batch metadata。
   - Phase B: 实现 summary 输出，支持 suite/profile/tag/rule 维度。
   - Phase C: 为 summary 添加 unit tests 和文档示例。

3. Milestone 3: 补权限负例规则
   - Phase A: 设计并新增 load/store/HLVX 权限负例 YAML。
   - Phase B: 增加 single-case suites 并运行 `dump-plan/build`。
   - Phase C: v2/v3 single-case 通过后加入 host permission 或 hyp group。

4. Milestone 4: 补 two-stage fault 分类规则
   - Phase A: 新增 allStage stage1 fault 与 stage2 guest fault。
   - Phase B: 新增 onlyStage2 HLV/HLVX/HSV guest fault 的缺口规则。
   - Phase C: v2/v3 single-case 和 group run 验证。

5. Milestone 5: 补 context/fence 与 superpage 规则
   - Phase A: 新增或强化 satp/vsatp/hgatp/ASID/VMID 切换可观察规则。
   - Phase B: 新增 sfence/hfence remap 生效规则。
   - Phase C: 新增 host/stage2/allStage superpage 组合规则。

6. Milestone 6: 文档化和回归沉淀
   - Phase A: 更新 README 或 MMU runbook。
   - Phase B: 更新 suite 清单和 coverage gap 示例。
   - Phase C: 记录第二层 deferred backlog，避免 scope claim 混淆。

## Task Breakdown

Each task must include exactly one routing tag:

| Task ID | Description | Target AC | Tag (`coding`/`analyze`) | Depends On |
|---------|-------------|-----------|----------------------------|------------|
| task1 | 运行 host unit tests，并在 v2/v3 cached runner 上跑 smoke baseline，记录 batch evidence。 | AC-1 | coding | - |
| task2 | 运行 v2/v3 group baseline，包括 host permission、attribute/control、H extension、faults，并整理失败分类。 | AC-1 | coding | task1 |
| task3 | 设计 coverage summary 输出格式，盘点 ledger 与 batch metadata 字段。 | AC-2 | analyze | task2 |
| task4 | 实现 coverage summary 入口和单元测试，支持 suite/profile/tag/rule 状态汇总。 | AC-2 | coding | task3 |
| task5 | 新增权限负例 rules、single-case suites 和 loader/inventory/emitter 测试。 | AC-3 | coding | task4 |
| task6 | 在 v2/v3 上验证权限负例 single-case，并合入合适 group/full suite。 | AC-3 | coding | task5 |
| task7 | 新增 two-stage fault 分类 rules、single-case suites 和必要测试。 | AC-4 | coding | task4 |
| task8 | 在 v2/v3 上验证 two-stage fault single-case，并合入 hyp/fault/full suite。 | AC-4 | coding | task7 |
| task9 | 新增 context/fence 生效性 rules，并验证新旧映射值差异可观测。 | AC-5 | coding | task4 |
| task10 | 新增 superpage 组合 rules，并验证 host/stage2/allStage 覆盖。 | AC-6 | coding | task4 |
| task11 | 更新 README/MMU runbook、suite 清单、coverage gap 示例和第二层 deferred backlog。 | AC-7 | coding | task6, task8, task9, task10 |
| task12 | 跑最终 v2/v3 group 或 full regression，确认 coverage summary 与文档一致。 | AC-1, AC-2, AC-7 | coding | task11 |

## Implementation Notes

- 新代码和注释不要包含 `AC-`、`Milestone`、`Phase`、`task` 这类计划术语；这些只属于计划文档。
- 本轮计划在新分支 `kmh-mmu-layer1-baseline-gap-plan` 上生成，后续实现可以在同一分支继续或从该分支切实现分支。
- 新增规则优先采用 single-case suite 调试，避免 group suite 失败时定位困难。
- target run 使用 `--runner-profile kmh-v2/difftest` 和 `--runner-profile kmh-v3/difftest`，不要依赖默认 runner 环境。
- `SNIPPETGEN_RUN_MAX_CYCLES` 和 `SNIPPETGEN_RUN_MAX_INSTR` 需要按 smoke/group/full 分别设置，避免长 suite 被默认 120000 限制误杀。
- v3 第一轮保持 vector-free；如果以后加 v2 vector MMU，必须独立 suite，不进入本轮 v3 baseline。
- 第二层/第三层问题只进入 backlog，不写成当前 generic rule runner 可判定的 pass/fail。
- 如果新增 rule 暴露失败，先判断是 rule 构造问题、runtime runner 问题、difftest/reference 问题还是 DUT 行为问题，再决定是否提交为 bug evidence。
