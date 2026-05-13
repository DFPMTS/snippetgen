# 昆明湖 v2 vector MMU layer1 验证计划

## Goal Description

在已经完成的昆明湖 v2/v3 scalar MMU layer1 baseline 之上，新增一组
**v2-only** 的 vector memory + MMU 第一层验证。目标是先证明 snippetgen 能稳定
生成、构建、运行和沉淀 Kunminghu v2 的向量访存翻译用例，并覆盖最小但有价值的
架构可见行为：vector enable、unit-stride vector load/store、Bare 和 Sv39
host single-stage 翻译、跨页 valid 访问、基础 page fault 和权限 fault。

本轮不把 vector case 加入 v3 smoke/full baseline，不声称覆盖第二层/第三层的
微架构现象，也不把 prefetch/PTW/L2TLB 竞争、merged miss、replay 拍点、精确
pipeline kill 等内容写成本轮 pass/fail 目标。

当前可复用基础包括：

- `kmh-v2/difftest` cached runner profile。
- 已有 baremetal snippet build/run pipeline。
- 已有 `vsetvl_interrupt_*` POC，可参考其局部 `.word` 发指令方式。
- 已有 MMU runtime、page table helper、trap handler 和 target run metadata。
- 已有 `mmu-coverage-summary` 与 run notes 证据记录方式。

## Acceptance Criteria

- AC-1: 建立 v2-only vector MMU suite 边界。
  - Positive Tests (expected to PASS):
    - 新增 suite 命名明确区分 v2 vector，例如 `suites/kmh_mmu_layer1_v2_vector_smoke.yaml`。
    - 该 suite 只使用 `--runner-profile kmh-v2/difftest` 作为正式 target evidence。
    - 现有 `kmh_mmu_layer1_v3_smoke.yaml`、`kmh_mmu_layer1_full.yaml` 和 v3 baseline 不选择任何 vector MMU case。
    - inventory 测试或 suite 解析测试能证明 v3 仍保持 vector-free。
  - Negative Tests (expected to FAIL):
    - vector MMU case 被加入 v3 smoke/full baseline 时，inventory 测试失败。
    - 文档把 v2 vector evidence 说成 v3 evidence 时，review 或文档检查应判为失败。
    - suite 未显式区分 v2 vector 范围，却被当成通用 v2/v3 baseline 时，计划不满足。

- AC-2: 生成链能构建真实 vector memory 指令。
  - Positive Tests (expected to PASS):
    - 新增 vector MMU snippet 或程序能通过 `dump-plan` 和 `build`。
    - 最终 ELF 反汇编或字节检查能确认存在真实 vector memory 指令编码，例如 unit-stride vector load/store，而不只是 `vsetvl`。
    - 实现不要求全局 toolchain `-march` 改成 vector-enabled；可以使用局部 inline asm 或 `.word` 编码。
    - build manifest 记录 suite、snippet 顺序、ELF、BIN、disasm 和 build 命令。
  - Negative Tests (expected to FAIL):
    - 只有 `vsetvl`，没有 vector load/store 编码时，build-pipeline 测试失败。
    - 全局 toolchain flag 被改成会影响所有 suite 的 vector target 时，review 判为越界。
    - snippet manifest 缺 source、descriptor 或 suite 顺序错误导致 harness 无法调用时，build 失败。

- AC-3: v2 vector MMU smoke 覆盖 Bare 和 Sv39 hit。
  - Positive Tests (expected to PASS):
    - Bare mode 下 vector load 能从直通地址读出预期内存值。
    - Bare mode 下 vector store 能写回预期内存值，并由 scalar checker 验证。
    - Sv39 host single-stage 下 `vle8/vle32/vle64` 至少覆盖一种或多种 element width 的普通页 hit。
    - Sv39 host single-stage 下 `vse8/vse32/vse64` 至少覆盖一种或多种 element width 的普通页 hit。
    - `mstatus.VS`、`vsetvli/vsetvl`、`vl/vtype` 初始化由 runtime 或 snippet 明确完成。
  - Negative Tests (expected to FAIL):
    - 未启用 vector state 就执行 vector 指令，目标运行不能被记录为通过。
    - 结果只检查“程序结束”，不检查 vector load/store 数据正确性时，测试不满足。
    - 地址实际未经过 Sv39 映射却标为 `mode.host_single_stage` 覆盖时，inventory 或 review 失败。

- AC-4: 覆盖跨 4K 页边界但两页 valid 的 vector load/store。
  - Positive Tests (expected to PASS):
    - vector load 从第一页尾部开始，访问跨入第二个 valid 4K 页，并验证读出的元素序列。
    - vector store 从第一页尾部开始，访问跨入第二个 valid 4K 页，并验证两页内存被正确写入。
    - 页表 setup 明确包含两页 valid 映射，且地址选择保证访问真正跨页。
    - coverage 或 run notes 明确标记 `page.cross_4k` 或等价说明。
  - Negative Tests (expected to FAIL):
    - 地址没有实际跨页但文档声称跨页覆盖时，inventory 或自检失败。
    - 只映射第一页、第二页未映射，却 expect hit 时，目标运行应产生 fault 或失败。
    - store 跨页后只检查第一页，不检查第二页写入结果时，测试不满足。

- AC-5: 覆盖基础 vector page fault 和权限 fault。
  - Positive Tests (expected to PASS):
    - vector load page fault 能被 trap handler 捕获并匹配 load page fault cause。
    - vector store page fault 能被 trap handler 捕获并匹配 store/AMO page fault cause。
    - 至少一个 vector load 权限负例覆盖 R/A 等读侧权限或 accessed-bit 行为。
    - 至少一个 vector store 权限负例覆盖 W/D 等写侧权限或 dirty-bit 行为。
    - fault case 能自检 trap cause、fault address 或可观测恢复状态，并能在 handler 后结束为 good trap。
  - Negative Tests (expected to FAIL):
    - fault case 没有检查 trap cause，只靠程序没有崩溃就记 pass 时，测试不满足。
    - vector load fault 被误标成 store fault，或 store fault 被误标成 load fault，测试失败。
    - 需要精确 `vstart` 恢复但没有 runtime 支持时，不能模糊写成已覆盖。

- AC-6: target evidence 和 coverage/run notes 可回归。
  - Positive Tests (expected to PASS):
    - 在 `kmh-v2/difftest` 上运行 v2 vector smoke suite，batch metadata 记录 `runner_profile`、runner revision、NEMU revision、seed、batch id、finish code、stdout/stderr log 和 artifact path。
    - 成功 evidence 必须有 `finish_code: 0` 或 `HIT GOOD TRAP` 等语义成功信号。
    - README 或 run notes 给出 v2 vector MMU suite 的运行命令、推荐 cycle/instruction budget、batch id 命名方式和 evidence 路径。
    - 若 target run timeout、abort、bad trap 或 difftest mismatch，run notes 记录失败分类和下一步归因方向。
  - Negative Tests (expected to FAIL):
    - 没有 target run evidence 却在文档中声称 v2 vector MMU 通过时，计划不满足。
    - batch metadata 缺 runner profile 或 revision 时，evidence 不完整。
    - v2 vector target run 失败但 coverage summary 或文档标成 ran/pass 时，测试失败。

- AC-7: 保留后续 vector 扩展边界和 backlog。
  - Positive Tests (expected to PASS):
    - 文档明确 indexed、strided、segment、masked、fault-only-first、复杂 `vstart` 精确恢复、misalign + cross-page fault、以及第二层/第三层微架构竞争都不属于本轮完成条件。
    - 若实现中新增 coverage tags，taxonomy 能区分 `requestor.vector_load`、`requestor.vector_store`、`page.cross_4k` 或等价语义，且不会误导现有 scalar coverage。
    - 若暂不扩展 MMU rule schema，文档明确 vector MMU 第一波由专用 snippet/suite 承载，不冒充 YAML rule corpus 覆盖。
  - Negative Tests (expected to FAIL):
    - 文档声称覆盖 fault-only-first 或 indexed/segment 全组合，但没有对应 target evidence。
    - 第二层/第三层微架构现象被写成本轮 generic self-check pass/fail case。
    - vector suite 破坏现有 scalar MMU coverage summary 语义或 v2/v3 profile 隔离。

## Path Boundaries

### Upper Bound (Maximum Scope)

完成 v2-only vector MMU smoke 和基础 fault 验证：新增 vector MMU snippet/program、
manifest、suite、必要 runtime helper、host tests、build/disassembly 检查、v2 target
run evidence、README/run notes 更新，以及必要的 coverage 或 evidence 汇总。可以覆盖
Bare、Sv39 host single-stage、unit-stride vector load/store、跨 4K valid 页、基础
page fault 和读写权限 fault。

### Lower Bound (Minimum Scope)

至少完成：

- 一个 v2-only vector MMU smoke suite。
- 能构建真实 vector memory load/store 指令的 artifact。
- Bare 或 Sv39 中至少一种 vector load hit 和 vector store hit 自检。
- v2 target run evidence，记录 `kmh-v2/difftest` runner profile 和 semantic pass。
- 文档明确 v3 不纳入本轮 vector suite。

如果只保留 `vsetvl` path、不发 vector memory 指令，或者只写计划不提供 v2 target
evidence，不满足下界。

### Allowed Choices

- Can use: 现有 snippet manifest/suite/build/run pipeline。
- Can use: `kmh-v2/difftest` cached runner profile。
- Can use: 现有 MMU runtime/page table/trap helper。
- Can use: 局部 inline asm 或 `.word` 发出 vector 指令，避免全局 toolchain 依赖。
- Can use: 新增 `snippets/vector_mmu/`、v2-only suite、host build/disassembly tests、
  docs/run notes。
- Can use: 后续再扩展 MMU rule schema；本轮可以先用专用 vector MMU snippet。
- Cannot use: `kmh-v3/difftest` 作为本轮 vector evidence。
- Cannot use: 把 vector case 加入 v3 smoke/full baseline。
- Cannot use: 修改全局 compiler flags 影响所有 suite。
- Cannot use: 提交 build artifacts、runner binary、NEMU `.so` 或 wave。
- Cannot use: 在本轮声称覆盖 indexed/strided/segment/fault-only-first 全组合或第二层
  微架构竞争。
- Cannot use: `bitlesson` 或 `ask-codex`。

## Dependencies and Sequence

### Milestones

1. Milestone 1: 固化 vector MMU 承载方式
   - Phase A: 盘点现有 `vsetvl_interrupt_*` snippet 的局部 `.word` 发指令方式。
   - Phase B: 决定第一波采用专用 `vector_mmu` snippet/suite，而不是扩展 YAML MMU rule schema。
   - Phase C: 写清 v2-only/v3-free suite 边界和命名。

2. Milestone 2: 建立 vector 指令生成与构建检查
   - Phase A: 新增 vector enable helper 和 vector memory 指令发射 helper。
   - Phase B: 新增最小 vector MMU snippet、manifest 和 smoke suite。
   - Phase C: 添加 build/disassembly 测试，确认最终 ELF 包含 vector memory 指令。

3. Milestone 3: 实现 Bare 和 Sv39 hit 自检
   - Phase A: Bare vector load/store 数据自检。
   - Phase B: Sv39 host single-stage vector load/store 数据自检。
   - Phase C: `dump-plan`、`build` 和 host tests 通过。

4. Milestone 4: 实现跨页 valid 覆盖
   - Phase A: 构造 4K 页边界附近的 vector load case。
   - Phase B: 构造 4K 页边界附近的 vector store case。
   - Phase C: 自检两页数据并记录 run notes。

5. Milestone 5: 实现基础 fault 覆盖
   - Phase A: vector load/store page fault。
   - Phase B: vector load/store 权限 fault。
   - Phase C: trap cause/fault address/恢复状态自检。

6. Milestone 6: v2 target evidence 与文档沉淀
   - Phase A: 在 `kmh-v2/difftest` 上运行 smoke/fault suite。
   - Phase B: 记录 batch metadata、stdout/stderr、run notes 和失败分类。
   - Phase C: 更新 README/MMU runbook，明确 v3 不纳入本轮。

## Task Breakdown

Each task must include exactly one routing tag:

| Task ID | Description | Target AC | Tag (`coding`/`analyze`) | Depends On |
|---------|-------------|-----------|----------------------------|------------|
| task1 | 盘点现有 vector snippet、toolchain 限制和 MMU runtime helper，确认第一波采用专用 vector MMU snippet。 | AC-1, AC-2 | analyze | - |
| task2 | 新增 v2-only vector MMU suite 设计和 inventory 策略，确保 v3 suite 不选择 vector case。 | AC-1, AC-7 | coding | task1 |
| task3 | 实现 vector enable 与 vector memory 指令发射 helper，避免改全局 `-march`。 | AC-2, AC-3 | coding | task1 |
| task4 | 新增最小 vector MMU smoke snippet、manifest 和 suite，并添加 build/disassembly 测试。 | AC-2, AC-3 | coding | task2, task3 |
| task5 | 实现 Bare vector load/store hit 自检。 | AC-3 | coding | task4 |
| task6 | 实现 Sv39 host single-stage vector load/store hit 自检。 | AC-3 | coding | task4 |
| task7 | 实现跨 4K valid 页的 vector load/store 自检。 | AC-4 | coding | task6 |
| task8 | 实现 vector load/store page fault 与权限 fault 自检。 | AC-5 | coding | task6 |
| task9 | 在 `kmh-v2/difftest` 上运行 v2 vector MMU suite，沉淀 batch evidence 并分类失败。 | AC-6 | coding | task5, task6, task7, task8 |
| task10 | 更新 README/MMU run notes，记录 v2 vector MMU 运行流程、evidence 和 deferred backlog。 | AC-6, AC-7 | coding | task9 |
| task11 | 跑最终 host tests、build、v2 target run 和文档一致性检查。 | AC-1, AC-2, AC-6, AC-7 | coding | task10 |

## Implementation Notes

- 新代码和注释不要包含 `AC-`、`Milestone`、`Phase`、`task` 等计划术语。
- 本计划在 `kmh-v2-vector-mmu-layer1-plan` 分支生成；实现建议另开
  `kmh-v2-vector-mmu-layer1` 分支。
- 第一波优先用专用 vector MMU snippet/suite，不急着扩展 YAML MMU rule schema。
- vector 指令优先使用局部 `.word` 或小 helper 发射，避免修改全局 toolchain flags。
- target run 只使用 `--runner-profile kmh-v2/difftest`。
- v3 保持 vector-free；不要把 vector suite 加入 v3 smoke/full baseline。
- 如果 vector fault 暴露失败，先判断是测试构造、runtime、runner/reference 还是 DUT
  行为问题，再决定是否作为 bug evidence 提交。
- 若后续要覆盖 indexed/strided/segment/masked/fault-only-first 或精确 `vstart` 恢复，
  应另开计划或扩展本计划，不在本轮偷塞。
