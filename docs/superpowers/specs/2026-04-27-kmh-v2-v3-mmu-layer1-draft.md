# 昆明湖 v2/v3 memblock MMU 第一层测试 draft

## 背景

接下来要测试昆明湖 v2 和 v3 memblock 里面的 MMU 功能。第一阶段先做适合 `spec in, case out` 的规则型测试，在 `snippetgen` 框架里积累可复用测试用例，方便以后做回归测试。

每次昆明湖编译很慢，因此希望先编译出两个 bin，或者按 difftest / 波形配置编译出多个 bin，放到固定路径里复用，避免每次测试都重新编译。

补充约束：v3 第一轮先不管向量指令；v2 可以使用向量指令。

## 验证模块

- `ITLB` 通过 `frontend.io.ptw -> memBlock.ptw` 接入的共享翻译后端。
- 三组 `DTLB requestor`：
  - `dtlb_ld_tlb_ld`：`load + hybrid + L1Prefetcher(stream+stride)`。
  - `dtlb_st_tlb_st`：`store`。
  - `dtlb_prefetch_tlb_prefetch`：`sms + L2-to-L1 tlb_req`。
- `TLBNonBlock` 的 `hit / miss / refill / replay`。
- `PTW / L2TLBWrapper` 的 miss、回灌与共享仲裁。
- `PMP / PMPChecker / PMA / PBMT` 对翻译结果的权限与属性判定。
- `sfence / satp / vsatp / hgatp / hfence / redirect` 对 in-flight 翻译状态的影响。

`L2-to-L1 tlb_req` 表示 L2 侧回到 core 内请求翻译的路径，主要覆盖虚地址侧的预取请求。`PBOP` 物理地址路径不进入 core 侧 L1 DTLB，本阶段不作为任务边界。

`ITLB` 重点放在并发 miss、flush、生效上下文和共享 `PTW / L2TLB` 的请求归属上。

## Requestor 视角

每类 requestor 需要回答四件事：

- 它承担什么角色。
- 它在哪些翻译模式下工作。
- 它会遇到哪些结果。
- 它和共享后端的关键交互是什么。

### ITLB

`ITLB` 负责前端取指地址的翻译请求。它在这份任务里主要覆盖共享后端相关的问题：

- 与 `DTLB` 共享 `PTW / L2TLB` 时，请求和响应归属正确。
- `sfence / satp / vsatp / hgatp / hfence` 后，旧翻译状态失效。
- `ITLB miss + DTLB miss` 并发时，资源竞争和回灌保持稳定。

### Demand requestor

`load`、`hybrid(load side)`、`store` 是主线对象。

- `load` 重点覆盖翻译正确性、`hit / miss / replay`、`pf / af / gpf`、`PMP / PBMT`、`NC / MMIO` 分流，以及异常恢复后的重新执行。
- `hybrid(load side)` 保持和普通 `load` 同等级的翻译与异常覆盖，同时单独观察它自己的请求入口、调度环境和 replay 过程。
- `store` 重点覆盖写权限、`store page fault / store access fault / store guest page fault`、属性分流，以及后续 store 路径是否按正确 memory type 推进。

### Prefetch-side requestor

`prefetch` 类 requestor 正确性重点，是翻译、过滤、丢弃、重试和对主线 demand 路径的影响范围。

- `L1 stream prefetch` 需要覆盖 TLB 翻译、`PMP / PBMT / NC / MMIO` 过滤、miss 后的继续推进，以及与 demand path 的资源竞争。
- `L1 stride prefetch` 需要覆盖与 `stream` 相同的翻译和属性判定，同时保留自己的训练语义和触发条件。
- `sms prefetch` 需要覆盖翻译、属性过滤、`uncache / MMIO / fault` 情况下的停发，以及共享翻译后端的竞争关系。
- `L2-to-L1 tlb_req` 需要覆盖从 L2 回到 core 侧时的翻译、miss/replay、上下文切换后的旧响应失效，以及对 demand path 的影响范围。

## 翻译模式

需要明确每种模式适用的 requestor、成功路径验证目标、失败路径验证目标，以及上下文变化后哪些状态会失效。

- `Bare`：验证地址直通语义、模式切换后的旧翻译失效，以及当前上下文下各类 requestor 的基础行为。
- host 单阶段翻译：验证普通页、superpage、alias、权限位、`PMP / PBMT / NC / MMIO` 与 demand path 的主线行为。
- `onlyStage1`：验证第一阶段翻译语义下的地址收敛、权限判断和 fault 分类。
- `onlyStage2`：验证第二阶段翻译语义下的地址收敛、fault 分类和上下文切换后的状态失效。
- `allStage`：验证 `GVA -> GPA -> HPA` 全链路翻译、stage1 fault、stage2 fault、`guest page fault` 和共享后端一致性。
- `HLV / HLVX / HSV`：验证 H 扩展特殊访存语义下的权限、异常和翻译结果。

同一个 requestor 不要求覆盖所有翻译模式，但每一种正式翻译模式都要明确列出适用对象和验证目标。

## 结果与异常视角

正式覆盖的结果包括：

- `hit`：翻译结果、权限结果和属性结果都可用，后续路径按当前 memory type 推进。
- `miss`：本地 TLB 未命中，请求进入共享后端继续处理。
- `refill`：翻译结果回灌到 TLB 或等待队列中。
- `replay`：请求在 miss 或资源冲突后重新尝试。
- `page fault`：覆盖 `load page fault` 和 `store page fault`。
- `access fault`：覆盖 `load access fault` 和 `store access fault`。
- `guest page fault`：覆盖 H 扩展和两阶段翻译场景下的异常类型。
- `PMP deny / PMA 属性限制`：覆盖翻译成功后由物理属性层产生的限制。
- `PBMT / NC / MMIO / IO`：覆盖最终 memory type 结果以及后续路径分流。
- `stale response drop`：覆盖旧上下文下返回的翻译结果被丢弃。
- `merged miss / duplicate suppression`：覆盖同页并发 miss 的合并和去重。

demand path 和 prefetch path 的验证重点分开：

- demand path 重点看结果类型、异常类型、恢复动作和最终提交语义。
- prefetch path 重点看翻译结果是否允许继续发出预取，以及属性限制下的过滤、丢弃和重试。

## 共享翻译后端与一致性

共享翻译后端里需要持续跟踪的状态包括：

- `ITLB` 和三组 `DTLB requestor`。
- `PTW / L2TLBWrapper`。
- in-flight miss 请求。
- 已经返回但尚未完全消费的翻译结果。
- `TLB entry` 本身。
- requestor 侧等待 replay 的状态。
- prefetch 侧等待继续发出的状态。

会改变翻译语义和状态有效性的控制动作包括：

- `sfence.vma`。
- `satp` 切换。
- `ASID` 切换。
- `vsatp` 切换。
- `hgatp` 切换。
- `VMID` 切换。
- `hfence.vvma`。
- `hfence.gvma`。
- `redirect / flush / rollback`。

验证目标：

- `ITLB` 和 `DTLB` 共享 `PTW / L2TLB` 时，请求和响应归属正确。
- flush 后，旧 `TLB entry` 失效。
- flush 后，在途 miss 请求失效。
- flush 后，已经返回但尚未消费的旧翻译结果失效。
- `satp / vsatp / hgatp / ASID / VMID` 改变后，新请求只使用新上下文下的翻译。
- prefetch requestor 在上下文变化后，旧翻译结果会被丢弃。
- `redirect` 之后，已经失去执行意义的翻译结果不会继续推动后续路径。
- 多个 requestor 命中同一页 miss 时，合并、去重和回灌结果保持一致。

## 复杂组合与边界场景

这一节负责把主轴叠起来看，目标是验证共享翻译后端、翻译模式、异常分类和属性判定在并发与控制交错下仍然保持一致。

- miss、replay 和控制动作交错：`TLB miss` 期间发生 `redirect`、执行 `sfence`、切换 `satp / vsatp / hgatp`，或者请求准备 replay 时上下文已经改变。
- 共享资源竞争：多个 load/store 并发 miss、同页并发 miss、`ITLB miss + DTLB miss`、demand requestor 与 prefetch requestor 同时竞争 `DTLB / PTW / L2TLB`。
- 异常、handler 和页表修改闭环：`pf / af / gpf` 进入 handler、handler 中修改页表并执行 `sfence`、handler 中再次发起 `load / store / AMO`、handler 返回后原指令重新执行。
- 属性与翻译语义叠加：`PBMT = NC`、`MMIO / IO`、`onlyStage2 / allStage`、`HLV / HLVX / HSV` 与 fault、权限和后续路径分流同时出现。

## 分层策略

### 第一层：适合 spec in, case out

第一层基本是规则型，当前优先测试这一层。适合内容包括：

- Bare / 单阶段 / onlyStage1 / onlyStage2 / allStage。
- load / store / HLV / HLVX / HSV。
- 普通页 / superpage / alias。
- V/R/W/X/U/A/D 位组合。
- page fault / access fault / guest page fault。
- MXR / SUM。
- PMP / PMA / PBMT / NC / MMIO。
- sfence / hfence / satp / vsatp / hgatp / ASID / VMID 之后旧翻译失效。
- 页表修复后重试。

自动生成：

- CSR 初始化。
- 页表布局。
- 内存属性配置。
- 指令片段。
- trap handler。
- 期望结果检查。

### 第二层：spec 约束 + 定向模板 + 随机扩展

共享资源和交叉场景仍然可以从 spec 出发，但通常需要场景模板，并在模板内部随机化地址、页大小、时机、requestor 组合。例如：

- 同页重复 miss。
- `ITLB miss + DTLB miss`。
- demand 和 prefetch 竞争 `PTW / L2TLB`。
- miss 期间 `sfence`。
- miss 期间 `redirect`。
- replay 前上下文切换。

### 第三层：monitor / scoreboard / stress 驱动

更偏微架构的问题，例如：

- merged miss 的内部合并策略。
- 哪一拍发 replay。
- 哪个 requestor 先抢到 PTW。
- prefetch 被 drop 的精确内部原因。
- 某个内部 buffer 的时序竞争。
- 某条老响应在什么 pipeline stage 被 kill。

这层仍然可以用生成器制造输入，但判定方式更像 waveform / monitor / internal trace / scoreboard / performance counter / microarchitectural assertion。

## 工作内容

1. 规则库存储。把手册里的 MMU 规则整理成结构化条目，每条条目回答：
   - 这条规则适用于哪个 requestor。
   - 适用于哪种翻译模式。
   - 前提条件是什么。
   - 预期结果是什么。
   - 需要观察什么。
   - 对应哪个 coverage item。

   示例：

   ```yaml
   - requestor: load
   - mode: allStage
   - precondition:
     - stage1 有效
     - stage2_pte.v = 0
     - pmp = allow
   - expect:
     - load_guest_page_fault
   ```

2. 测试生成器。从规则库生成：
   - 汇编测试骨架。
   - 页表初始化代码。
   - CSR 配置。
   - trap handler。
   - signature / 自检逻辑。

3. coverage 对齐。给每条规则打 coverage tag：
   - `requestor.load`。
   - `mode.allStage`。
   - `exception.gpf`。
   - `page.superpage`。
   - `attr.nc`。
   - `ctrl.sfence`。

   统计：
   - 哪些功能点已经有规则。
   - 哪些规则已经生成测试。
   - 哪些测试已经跑过。
   - 哪些 coverage 还空着。

## 当前任务

在 `snippetgen` 下新开 git 分支，为昆明湖 v2/v3 memblock MMU 第一层测试生成测试方案。测试方案需要覆盖：

- 第一层规则型 MMU 功能测试的用例组织。
- 规则库、生成器、coverage ledger 的扩展策略。
- 预编译 bin 的复用路径和 v2/v3、difftest、波形配置矩阵。
- 测试用例沉淀和后续回归方式。
- 与第二层/第三层场景的边界划分，避免第一层任务膨胀。
