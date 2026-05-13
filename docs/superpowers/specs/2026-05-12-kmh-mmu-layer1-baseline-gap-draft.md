# 昆明湖 v2/v3 MMU 第一层 baseline 与 gap 推进 draft

## 背景

`snippetgen` 当前已经具备昆明湖 v2/v3 MMU 第一层规则型测试的基础设施：

- `snippets/mmu_rules/kmh_layer1/` 存放第一层 YAML rule。
- `snippets/programs/mmu_rule_runner_main.c` 解释执行 generated MMU rules。
- `generator/xsgen/mmu_rule_loader.py` 与 `generator/xsgen/mmu_rule_emitter.py` 完成规则校验、C artifact 生成和 coverage ledger 生成。
- `suites/kmh_mmu_layer1_*` 已经按 smoke、host permission、attribute/control、H extension、faults、full 进行分组。
- `/nfs/home/liujunqi/XS/artifacts/kmh-runners/manifest.json` 已经登记 `kmh-v2/difftest` 和 `kmh-v3/difftest` runner profile，避免每次切换 XiangShan 分支重新编译。

第一轮基础设施计划已经完成大部分目标。接下来不再扩大到第二层微架构验证，先把现有第一层做成可信 baseline，再补齐仍属于第一层的架构规则 gap。

## 当前判断

当前已有 MMU layer1 规则能覆盖：

- `Bare / host_single_stage / onlyStage1 / onlyStage2 / allStage`
- `load / hybrid_load / store / hlv / hlvx / hsv`
- identity、alias、superpage、raw PTE、PMP deny、PBMT NC、PMA/MMIO witness
- page fault、access fault、guest page fault
- MXR、SUM、satp/asid、vsatp/hgatp/vmid、sfence/hfence、fault repair retry

但当前还需要进一步处理：

- 当前 v2/v3 最新 runner cache 更新后，需要重新跑 smoke 和 group baseline，确认 rule runner、suite、profile、coverage ledger 仍然一致。
- 需要一个可读的 coverage gap 汇总，能按 rule/tag/profile 看 `defined`、`generated`、`ran`、`gap`。
- 需要补第一层里更容易暴露 bug 的架构规则，优先是权限负例、two-stage fault 分类、context/fence 生效性和 superpage 组合。
- 当前已有向量相关测试只覆盖 `vsetvl + interrupt`，不属于 MMU layer1。v3 第一轮继续排除向量。v2 的向量 MMU 规则可以后续单独开 suite，但本轮不作为主线。

## 本轮目标

本轮只推进第一层验证，不开启第二层验证。

优先级：

1. 跑当前 v2/v3 baseline，确认现有 smoke 与 group suites 在最新 cached runner 上的结果。
2. 整理 baseline evidence，包括 suite、profile、seed、batch id、runner revision、NEMU revision、finish code、coverage ledger。
3. 增加 coverage gap 汇总能力，让现有 coverage 不再只能靠手工读 JSON。
4. 补充第一层 rule：
   - 权限负例矩阵：`R=0`、`W=0`、`X=0`、`A=0`、`D=0`、`SUM`、`MXR` 的正负组合。
   - two-stage fault 分类：stage1 page fault、stage2 guest page fault、HLV/HLVX/HSV guest fault。
   - context/fence 生效性：satp/vsatp/hgatp/ASID/VMID 切换后同 VA/GVA/GPA 读到新上下文值。
   - superpage 组合：host superpage load/store、stage2 superpage、allStage 4K/superpage 混合。
5. 更新文档和回归入口，使新增规则、suite、coverage gap、运行证据可长期沉淀。

## 明确不做

本轮不做以下第二层/第三层内容：

- `ITLB miss + DTLB miss` 并发归属验证。
- demand/prefetch 竞争 `PTW / L2TLB`。
- miss 期间 redirect、sfence、satp/vsatp/hgatp 切换的精确 in-flight 时序验证。
- TLBNonBlock 内部 `hit / miss / refill / replay` 拍点。
- merged miss / duplicate suppression 内部策略。
- prefetch drop 的精确内部原因。
- stale response 在具体 pipeline stage 被 kill。
- wave/trace/scoreboard 驱动的 monitor/stress 层。
- v3 向量 MMU case。

这些内容保留为后续 backlog，不在本轮 coverage 中声称已覆盖。

## 成功标准

- v2/v3 smoke baseline 都有新的 batch evidence。
- v2/v3 group suites 至少完成 host permission、attribute/control、H extension、faults 的 baseline 运行或明确记录阻塞原因。
- coverage gap 汇总能展示哪些 tag 已定义、已生成、已运行、仍为空。
- 新增第一层规则都通过 `dump-plan`、`build`、unit tests，并进入合适 suite。
- 新增规则在 v2/v3 上有运行证据，或明确记录为 profile-specific gap。
- 文档说明新增规则流程、baseline 运行流程、coverage gap 阅读方式、第二层 deferred scope。
