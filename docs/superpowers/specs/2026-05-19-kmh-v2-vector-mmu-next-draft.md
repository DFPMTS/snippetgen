# 昆明湖 v2 vector MMU 下一阶段验证 draft

## 背景

当前 `dev` 上已经有第一波 Kunminghu v2 vector MMU smoke：

- `suites/kmh_mmu_layer1_v2_vector_smoke.yaml`
- `snippets/programs/kmh_v2_vector_mmu_main.c`
- `snippets/include/xs_vector_mmu.h`

这组用例已经证明 snippetgen 可以在不修改全局 `-march=rv64gc` 的前提下，用局部
`.word` 发出真实 vector memory 指令，并在 `kmh-v2/difftest` profile 下覆盖：

- vector state enable
- `vsetvli e8,m1`
- `vle8.v` / `vse8.v` unit-stride load/store
- Bare hit
- Sv39 host single-stage hit
- 跨 4K 但两页 valid 的 hit
- vector load/store page fault
- vector load/store 基础权限 fault

这说明第一波 smoke 有价值，但它还不是 Kunminghu v2 vector 指令 MMU 的完整第一层验证。

## 当前缺口

目前缺口主要集中在 vector 指令形态、跨页异常语义、权限属性组合和可回归组织方式：

- 只覆盖 `e8,m1`，没有覆盖 `e16/e32/e64`。
- 只覆盖 unit-stride，缺少 strided、indexed、segment、masked、mask load/store。
- 没有覆盖 fault-only-first load。
- 没有覆盖 `vstart` 非 0、部分元素完成、异常后恢复或 handler 返回后的重新执行。
- 跨页只覆盖“两页都 valid”，没有覆盖第一页 valid、第二页 fault 的边界异常。
- fault case 目前主要检查 cause/tval，没有系统化记录 fault 发生在 vector 访问的哪类形态。
- 没有把 vector requestor 的 coverage tag 和现有 scalar MMU rule coverage 正式对齐。
- 没有覆盖 vector load/store 与 PMP/PMA/PBMT/NC/MMIO 属性组合。
- 没有覆盖 vector load/store 在 onlyStage1、onlyStage2、allStage 下的最小 H 扩展语义。
- 还没有把 v2 vector suite 拆成 smoke、fault、attr、hyp 等可长期回归的层次。

这些仍然属于第一层功能型验证，可以继续做；暂时不需要进入第二层共享 PTW/L2TLB
竞争、merged miss、replay 拍点、pipeline kill 等微架构验证。

## 下一阶段目标

下一阶段目标是扩展 v2-only vector MMU 第一层覆盖，让它从单个 smoke 变成一组
可维护、可回归、可统计的 suite：

- 保持 v2-only，v3 继续不纳入 vector evidence。
- 仍然以规则型、功能型、自检型 case 为主。
- 覆盖更多 vector memory 指令形态和 EEW。
- 覆盖跨页 fault、mask、fault-only-first、`vstart` 和基础恢复语义。
- 覆盖 PMP/PMA/PBMT/NC/MMIO 与 vector 翻译结果的组合。
- 选择少量 H 扩展翻译模式，验证 vector 访存下的 stage fault 分类。
- 建立 vector MMU coverage ledger 或等价汇总，不污染现有 scalar rule corpus。

## 建议优先级

第一优先级：

- 把 helper 从单一 `e8/m1` 扩展到 `e16/e32/e64`。
- 新增 `vle16/vle32/vle64` 和 `vse16/vse32/vse64` hit/fault 用例。
- 新增跨页第二页 invalid / permission fault 的 vector load/store case。
- 新增 masked load/store，验证 masked-off 元素不触发不该触发的 fault。
- 拆出 `kmh_mmu_layer1_v2_vector_faults.yaml`，避免 smoke 过大。

第二优先级：

- strided load/store。
- indexed load/store。
- segment load/store。
- fault-only-first load。
- `vstart` 非 0 与 fault 后自检。
- PMP/PMA/PBMT/NC/MMIO 属性组合。

第三优先级：

- onlyStage1 / onlyStage2 / allStage 下的 vector load/store 最小 case。
- HLV/HSV 与 vector 指令的边界要谨慎区分：HLV/HSV 是 H 扩展特殊访存语义，不是普通 vector load/store 本身。
- 为后续第二层验证预留 trace/monitor 需求，但不在本轮实现 PTW 竞争类判定。

## 暂不覆盖

本计划不打开第二层/第三层：

- ITLB + DTLB 并发 miss。
- demand/prefetch/PTW/L2TLB 竞争。
- merged miss 内部合并策略。
- replay 精确拍点。
- stale response 在具体 pipeline stage 被 kill。
- vector pipeline 内部 micro-op 顺序验证。

这些后续应由定向模板、monitor、scoreboard 或 waveform 驱动。
