# 昆明湖 v2 vector MMU 下一阶段验证计划

## Goal Description

当前 Kunminghu v2 vector MMU 第一波 smoke 已经覆盖了 `vle8.v` / `vse8.v`
unit-stride 访存、Bare hit、Sv39 host single-stage hit、跨 4K 两页 valid 访问、
基础 load/store page fault 和基础读写权限 fault。它能证明 snippetgen 可以稳定生成
真实 vector memory 指令，并且能在 v2 runner profile 上作为一条 v2-only smoke
回归。

但这还不是 v2 vector 指令 MMU 第一层验证的完整覆盖。下一阶段目标是在不打开第二层
PTW/L2TLB 竞争验证的前提下，把 v2-only vector MMU 从单一 smoke 扩成一组可维护、
可自检、可长期回归的第一层功能型 suite。重点覆盖更多 EEW、更多 vector memory
形态、跨页异常、mask/fault-only-first/`vstart` 基础语义、属性限制，以及少量 H
扩展翻译模式下的 fault 分类。

本计划仍然限定在 Kunminghu v2。Kunminghu v3 不作为本轮 vector evidence；现有
v2/v3 scalar MMU suite 和 v3 smoke/full baseline 继续保持 vector-free。

## Acceptance Criteria

- AC-1: 明确当前覆盖结论和下一阶段边界。
  - Positive Tests (expected to PASS):
    - 文档说明现有 v2 vector smoke 已覆盖 `vle8.v` / `vse8.v`、Bare、Sv39 hit、cross-4K valid 和基础 fault。
    - 文档说明现有覆盖缺口包括 `e16/e32/e64`、masked、strided、indexed、segment、fault-only-first、`vstart`、属性组合和 H 扩展翻译模式。
    - 新计划明确不进入 ITLB/DTLB 并发 miss、PTW/L2TLB 竞争、merged miss、replay 拍点、pipeline kill 等第二层/第三层验证。
    - v3 suite 仍不选择任何 vector MMU case。
  - Negative Tests (expected to FAIL):
    - 文档把当前 smoke 描述成“vector MMU 第一层完整覆盖”时不满足。
    - 把第二层/第三层微架构现象写成本轮自检 pass/fail 目标时不满足。
    - 把 v2 vector evidence 复用成 v3 evidence 时不满足。

- AC-2: 扩展 vector memory helper，覆盖多个 EEW 的 unit-stride load/store。
  - Positive Tests (expected to PASS):
    - helper 支持 `e8/e16/e32/e64` 的 `vsetvli` 或等价 `.word` 编码。
    - helper 支持 `vle8/vle16/vle32/vle64` 和 `vse8/vse16/vse32/vse64` 的最小发射接口。
    - build/disassembly 测试确认最终 ELF 包含多种 vector memory opcode，而不是只包含 `vsetvli` 或现有 `vle8/vse8`。
    - 全局 toolchain ISA 仍保持 `-march=rv64gc`，vector 指令继续用局部 `.word` 或受控 inline asm 发射。
    - scalar host fallback 能保持单元测试可运行，不要求 host compiler 支持 RVV。
  - Negative Tests (expected to FAIL):
    - 新增 helper 需要把全局 build flag 改成 vector ISA 时不满足。
    - 只扩展 C 函数名但最终 ELF 没有对应 vector memory 指令编码时不满足。
    - host fallback 与 RISC-V path 语义明显不一致，导致 host test 误判时不满足。

- AC-3: 建立 v2 vector MMU suite 分层。
  - Positive Tests (expected to PASS):
    - 保留 `suites/kmh_mmu_layer1_v2_vector_smoke.yaml` 作为短路径稳定 smoke。
    - 新增或规划独立 suite，例如 `kmh_mmu_layer1_v2_vector_widths.yaml`、`kmh_mmu_layer1_v2_vector_faults.yaml`、`kmh_mmu_layer1_v2_vector_attr.yaml`、`kmh_mmu_layer1_v2_vector_hyp.yaml`。
    - suite 命名、README 和 run notes 明确 v2-only。
    - inventory 或 suite loader 测试确认 v3 smoke/full baseline 不包含 vector snippets。
    - smoke 不因为扩展 case 变成过大的 grouped regression。
  - Negative Tests (expected to FAIL):
    - 把所有 vector case 都塞进 smoke，导致 smoke 失去快速定位价值时不满足。
    - 新 suite 名称没有 v2/vector 边界，容易被误用于 v3 evidence 时不满足。
    - v3 smoke/full 被动引入 vector snippet 时测试失败。

- AC-4: 覆盖跨页 fault 和权限边界。
  - Positive Tests (expected to PASS):
    - vector load/store 覆盖跨 4K 边界且第二页 invalid 的 page fault。
    - vector load/store 覆盖跨 4K 边界且第二页权限不满足的 page fault 或 access fault。
    - fault case 检查 trap cause、fault address，以及 fault 发生前后可观察数据没有越界污染。
    - 对 store case，检查第一页已允许写入的元素和第二页 fault 后不应写入的元素。
    - 对 load case，检查 fault 后 handler 能恢复到 good trap 或受控结束状态。
  - Negative Tests (expected to FAIL):
    - 地址声称跨页但实际没有跨越 4K 边界时不满足。
    - 只检查“有 trap”，不检查 cause/tval/数据边界时不满足。
    - fault 后 store 对第二页产生非预期写入但测试仍 pass 时不满足。

- AC-5: 覆盖 masked vector load/store 的 MMU 语义。
  - Positive Tests (expected to PASS):
    - masked load 覆盖 masked-on 元素访问 valid 页并返回正确数据。
    - masked store 覆盖 masked-on 元素写入 valid 页并保持 masked-off 元素不变。
    - masked-off 元素落在 invalid 或无权限页时，不应因为 masked-off 元素触发 fault。
    - masked-on 元素落在 invalid 或无权限页时，应触发对应 fault。
    - 自检能区分 mask 语义错误和普通翻译错误。
  - Negative Tests (expected to FAIL):
    - masked-off fault 被错误触发时测试失败。
    - masked-on fault 被吞掉时测试失败。
    - 只检查最终程序返回值，不检查 masked-off 数据保持时不满足。

- AC-6: 覆盖 strided、indexed 和 segment 的基础 MMU hit/fault。
  - Positive Tests (expected to PASS):
    - strided load/store 覆盖正 stride 的 valid hit，并至少覆盖一个 fault 元素。
    - indexed load/store 覆盖 unordered 或 ordered indexed 的 valid hit，并至少覆盖一个 fault 元素。
    - segment load/store 覆盖最小 segment 形态，例如 2-field segment 的 valid hit。
    - 每类 case 都有数据自检和 fault cause/tval 自检。
    - 若编码复杂，先用小而明确的 `.word` helper，不引入全局 assembler 依赖。
  - Negative Tests (expected to FAIL):
    - 只写入 helper 但没有任何 suite 选择该路径时不满足。
    - indexed/segment 的地址计算没有自检，导致访问了错误地址仍 pass 时不满足。
    - fault 元素和预期 fault address 不匹配但测试仍 pass 时不满足。

- AC-7: 覆盖 fault-only-first 和基础 `vstart` 语义。
  - Positive Tests (expected to PASS):
    - fault-only-first load 覆盖第一个元素 valid、后续元素 fault 的受控行为。
    - fault-only-first load 覆盖第一个元素就 fault 的行为。
    - 至少一个 case 读取并检查 `vstart` 或等价可观察恢复状态。
    - `vstart` 非 0 的重入或跳过前缀元素行为有最小自检。
    - 文档明确这些仍是第一层功能语义，不声明覆盖 vector pipeline 内部 micro-op 顺序。
  - Negative Tests (expected to FAIL):
    - fault-only-first 被当作普通 load fault 处理，缺少 first-element 语义检查时不满足。
    - `vstart` case 没有读取或验证可观察状态时不满足。
    - 把 `vstart` 精确拍点或内部 replay 顺序写成本轮目标时不满足。

- AC-8: 覆盖 PMP/PMA/PBMT/NC/MMIO 属性组合。
  - Positive Tests (expected to PASS):
    - vector load/store 覆盖 PMP deny 后的 access fault。
    - vector load/store 覆盖 PMA/MMIO 属性限制下的 fault 或路径分流期望。
    - vector load/store 覆盖 PBMT/NC 相关 PTE 属性，结果与当前 scalar MMU rule 语义一致。
    - 属性 case 明确区分翻译成功后的物理属性限制和页表权限 fault。
    - run notes 记录属性 case 在 v2 runner 上的 pass/fail 分类。
  - Negative Tests (expected to FAIL):
    - 把页表 permission fault 误记成 PMP/PMA fault 时不满足。
    - PBMT/NC case 没有检查当前实现/配置是否支持对应语义时不满足。
    - MMIO case 只依赖任意非法地址，不说明属性来源时不满足。

- AC-9: 覆盖少量 H 扩展翻译模式下的 vector load/store。
  - Positive Tests (expected to PASS):
    - onlyStage1 下 vector load/store 至少有一个 hit 和一个 stage1 fault。
    - onlyStage2 下 vector load/store 至少有一个 hit 或 guest page fault。
    - allStage 下至少覆盖 `GVA -> GPA -> HPA` hit、stage1 page fault、stage2 guest page fault 中的代表 case。
    - H 扩展 case 明确 requestor 是普通 vector load/store，不把 HLV/HSV 与 vector 指令混淆。
    - trap cause 分类与 scalar H MMU rule 的分类保持一致。
  - Negative Tests (expected to FAIL):
    - 用 HLV/HSV case 冒充普通 vector load/store case 时不满足。
    - onlyStage2/allStage 的 fault 分类写错但测试仍 pass 时不满足。
    - H 扩展 setup 未真正启用对应 CSR/context 时不满足。

- AC-10: 建立 vector MMU coverage 汇总，不污染 scalar rule corpus。
  - Positive Tests (expected to PASS):
    - 新增 vector coverage ledger 或等价 JSON/metadata，至少记录 requestor、mode、instruction form、EEW、page boundary、fault、attribute、profile、seed、status。
    - `mmu-coverage-summary` 或单独 summary 能区分 scalar YAML rule coverage 和 vector snippet coverage。
    - README/run notes 给出如何查看 v2 vector MMU coverage 缺口。
    - batch metadata 能追踪 suite、runner profile、runner revision、NEMU revision、seed、finish code、stdout/stderr 和 artifact path。
  - Negative Tests (expected to FAIL):
    - vector snippet 通过后 scalar MMU coverage 被误标为覆盖 vector requestor 时不满足。
    - 没有 target run evidence 却在 summary 中标成 ran/pass 时不满足。
    - coverage tag 粒度粗到无法区分 `e8` 与 `e64`、unit-stride 与 indexed 时不满足。

## Path Boundaries

### Upper Bound (Maximum Scope)

完成一组 v2-only vector MMU 第一层扩展 suite，覆盖：

- `e8/e16/e32/e64`
- unit-stride、masked、strided、indexed、segment、fault-only-first
- Bare、host single-stage、onlyStage1、onlyStage2、allStage 的代表 case
- 跨 4K valid 和跨 4K fault
- load/store page fault、access fault、guest page fault
- `vstart` 基础可观察状态
- PMP/PMA/PBMT/NC/MMIO 属性组合
- vector coverage ledger/summary、README/run notes、host build/disassembly 测试和 v2 target evidence

### Lower Bound (Minimum Scope)

至少完成下一波可以进入回归的核心增量：

- `e16/e32/e64` unit-stride load/store hit。
- 跨页第二页 invalid 的 vector load/store fault。
- masked load/store 的 masked-off fault 抑制和 masked-on fault 触发。
- 独立 `kmh_mmu_layer1_v2_vector_faults.yaml` 或等价 suite。
- build/disassembly 检查确认新增真实 vector memory opcode。
- `kmh-v2/difftest` target evidence 和 run notes。

如果只更新文档、不新增可运行 suite，或者只扩展 helper 但没有目标运行 evidence，不满足下界。

### Allowed Choices

- Can use: 现有 snippetgen suite/snippet/build/run pipeline。
- Can use: 现有 `kmh-v2/difftest` runner profile。
- Can use: 现有 MMU runtime、trap handler、page table helper、PMP/PMA helper。
- Can use: 新增 `snippets/include/xs_vector_mmu.h` helper 接口或拆出 `snippets/vector_mmu/` 源文件。
- Can use: 局部 `.word` 或受控 inline asm 发射 vector 指令。
- Can use: 新增 vector-specific coverage ledger，不强行塞进 scalar YAML MMU rule corpus。
- Cannot use: `bitlesson` 或 `ask-codex`。
- Cannot use: 把 v2 vector suite 当作 v3 evidence。
- Cannot use: 修改全局 toolchain `-march` 影响所有 suite。
- Cannot use: 提交 runner binary、NEMU `.so`、wave 或大型 build artifact。
- Cannot use: 把 PTW/L2TLB 竞争、merged miss、replay 拍点、pipeline kill 作为本轮 pass/fail 验收目标。
- Cannot use: 用 fence 或其他规避手段隐藏目标 bug；若 pass-only 回归需要规避，必须把规避版本和 bug repro 分开。

## Dependencies and Sequence

### Milestones

1. Milestone 1: 覆盖盘点和 suite 分层
   - Phase A: 盘点当前 `kmh_v2_vector_mmu_main` 已覆盖路径和未覆盖指令形态。
   - Phase B: 决定 smoke、widths、faults、attr、hyp 的 suite 边界。
   - Phase C: 确认 v3 vector-free inventory 仍成立。

2. Milestone 2: 扩展 vector helper 和构建检查
   - Phase A: 增加 `e16/e32/e64` 的 `vsetvli` helper。
   - Phase B: 增加 unit-stride load/store 多 EEW helper。
   - Phase C: 增加 disassembly/opcode 检查和 host fallback。

3. Milestone 3: 多 EEW unit-stride hit/fault
   - Phase A: 覆盖 `e16/e32/e64` Bare 或 Sv39 hit。
   - Phase B: 覆盖 `e16/e32/e64` load/store fault。
   - Phase C: 拆出 widths/faults suite 并运行 v2 target evidence。

4. Milestone 4: 跨页 fault 和 masked 语义
   - Phase A: 构造第二页 invalid / no-perm 的跨页 load/store。
   - Phase B: 构造 masked-off fault suppression。
   - Phase C: 构造 masked-on fault trigger。

5. Milestone 5: strided/indexed/segment 基础覆盖
   - Phase A: 实现 strided load/store valid hit 和 fault。
   - Phase B: 实现 indexed load/store valid hit 和 fault。
   - Phase C: 实现最小 segment load/store hit。

6. Milestone 6: fault-only-first 和 `vstart`
   - Phase A: 实现 first-element valid、后续 fault 的 fault-only-first case。
   - Phase B: 实现 first-element fault case。
   - Phase C: 实现 `vstart` 可观察状态检查。

7. Milestone 7: 属性和 H 扩展代表 case
   - Phase A: 添加 PMP/PMA/PBMT/NC/MMIO 属性组合。
   - Phase B: 添加 onlyStage1 / onlyStage2 / allStage 代表 case。
   - Phase C: 对齐 trap cause 分类和 scalar MMU rule 语义。

8. Milestone 8: evidence、coverage 和文档
   - Phase A: 在 `kmh-v2/difftest` 上运行新增 suite。
   - Phase B: 生成或更新 vector MMU coverage summary。
   - Phase C: 更新 README/run notes，记录通过项、失败项和后续 backlog。

## Task Breakdown

Each task must include exactly one routing tag:

| Task ID | Description | Target AC | Tag (`coding`/`analyze`) | Depends On |
|---------|-------------|-----------|----------------------------|------------|
| task1 | 盘点现有 v2 vector MMU smoke 的真实覆盖和缺口，更新 run notes 或 coverage notes。 | AC-1 | analyze | - |
| task2 | 设计 v2 vector MMU suite 分层，保留 smoke，新增 widths/faults/attr/hyp 边界。 | AC-1, AC-3 | coding | task1 |
| task3 | 扩展 vector helper，支持 `e16/e32/e64` 的 `vsetvli` 和 unit-stride load/store。 | AC-2 | coding | task1 |
| task4 | 增加 build/disassembly 测试，确认新增真实 vector memory opcode 且全局 ISA 不变。 | AC-2 | coding | task3 |
| task5 | 实现多 EEW unit-stride hit 和基础 fault case。 | AC-2, AC-3, AC-4 | coding | task2, task3 |
| task6 | 实现跨 4K 第二页 invalid / permission fault 的 vector load/store 自检。 | AC-4 | coding | task5 |
| task7 | 实现 masked load/store 的 masked-off fault suppression 和 masked-on fault trigger。 | AC-5 | coding | task5 |
| task8 | 实现 strided、indexed、segment 的最小 hit/fault case。 | AC-6 | coding | task7 |
| task9 | 实现 fault-only-first 和基础 `vstart` 可观察状态 case。 | AC-7 | coding | task7 |
| task10 | 实现 PMP/PMA/PBMT/NC/MMIO 属性组合 case。 | AC-8 | coding | task5 |
| task11 | 实现 onlyStage1 / onlyStage2 / allStage 的 vector load/store 代表 case。 | AC-9 | coding | task5 |
| task12 | 增加 vector MMU coverage ledger 或 summary 支持，避免污染 scalar rule corpus。 | AC-10 | coding | task2, task5 |
| task13 | 在 `kmh-v2/difftest` 上运行新增 suite，记录 batch evidence 和失败分类。 | AC-3, AC-10 | coding | task6, task7, task8, task9, task10, task11, task12 |
| task14 | 更新 README/run notes，说明运行流程、覆盖缺口、v2-only 边界和 deferred backlog。 | AC-1, AC-10 | coding | task13 |
| task15 | 跑最终 host tests、build、dump-plan、v2 target run 和文档一致性检查。 | AC-1, AC-2, AC-3, AC-10 | coding | task14 |

## Implementation Notes

- 新代码和注释不要包含 `AC-`、`Milestone`、`Phase`、`task` 等计划术语。
- 本计划只生成下一阶段方案；实现建议另开 `kmh-v2-vector-mmu-next` 或类似分支。
- 第一轮实现建议先做 `task2` 到 `task7`，也就是 suite 分层、多 EEW、跨页 fault 和 masked 语义。
- `task8` 到 `task11` 可以分波推进，避免一次性把 vector 编码、H 扩展和属性 case 全部耦合在一起。
- 每新增一种 vector 指令形态，都要有数据自检或 fault 自检，不接受“能跑完就算 pass”。
- 对 bug repro 和 pass-only 回归保持隔离；若某 case 暴露 RTL bug，不要用 fence 或降低压力的方式把同一个 case 改成假 pass。
- v3 继续保持 vector-free，直到有独立 v3 vector 计划和 runner evidence。
