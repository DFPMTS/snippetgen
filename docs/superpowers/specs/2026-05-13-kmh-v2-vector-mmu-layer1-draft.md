# 昆明湖 v2 vector MMU layer1 draft

## 背景

上一轮已经把昆明湖 v2/v3 MMU 第一层 scalar baseline 和 gap rule 做完，并
通过 `humanize-rlcr` stop gate。当前 `dev` 上已有：

- `kmh-v2/difftest` 和 `kmh-v3/difftest` runner profile。
- `snippets/mmu_rules/kmh_layer1/` 第一层 MMU rule corpus。
- `suites/kmh_mmu_layer1_*` scalar/H-extension 第一层 suite。
- `mmu-coverage-summary`，可以用 batch metadata 和 coverage ledger 做 rule/tag
  状态汇总。
- 现有 v3 第一波明确 vector-free。
- 现有 `vsetvl_interrupt_*` POC 可以证明 snippetgen 能发出真实 `vsetvl`，但
  还不是 vector memory + MMU 翻译验证。

现在希望进入下一步：只针对昆明湖 v2 加入向量访存指令的 MMU 第一层测试。

## 目标

新增 v2-only vector MMU layer1 验证能力，先做规则型、可自检、可回归的
vector memory + MMU 基础覆盖。这个阶段不把 vector case 混进 v3 baseline，也
不进入第二层/第三层微架构竞争验证。

## 期望覆盖范围

第一波应该优先覆盖最小稳定集：

- v2-only suite，例如 `kmh_mmu_layer1_v2_vector_smoke.yaml`。
- vector enable/runtime 初始化：
  - 能设置 `mstatus.VS`。
  - 能执行 `vsetvli` 或等价 `.word` 编码。
  - 不要求全局 toolchain `-march` 改成 vector-enabled。
- unit-stride vector load/store：
  - `vle8/vle32/vle64` 普通页 hit。
  - `vse8/vse32/vse64` 普通页 hit。
  - Bare mode 地址直通下的 vector load/store。
  - Sv39 host single-stage 下普通页翻译。
- 跨页但两页 valid：
  - vector load 跨 4K 页边界，两页都 valid。
  - vector store 跨 4K 页边界，两页都 valid。
- 基础 fault：
  - vector load page fault。
  - vector store page fault。
  - R/W/A/D 权限负例中至少覆盖 load/store 各一类。
- target evidence：
  - 使用 `--runner-profile kmh-v2/difftest`。
  - batch metadata 必须记录 runner profile、runner revision、NEMU revision、
    seed、batch id、finish code 和 log path。
  - v3 不跑这些 vector suite。

## 暂不覆盖

本轮不要急着覆盖：

- v3 vector。
- demand/prefetch/PTW/L2TLB 竞争、merged miss、replay 拍点等第二层/第三层。
- fault-only-first 精确语义。
- indexed/strided/segment/masked 全组合。
- misalign + vector + fault 的复杂恢复。
- vector 指令内部 pipeline kill 或 `vstart` 精确恢复微架构细节。

这些可以作为后续 backlog。

## 设计倾向

优先不要把 vector memory case 硬塞进现有 YAML MMU rule runner，除非改动很
小。更稳妥的第一步可能是新增 vector MMU snippet 程序：

- 新增 `snippets/vector_mmu/` 下的 C/inline-asm snippet。
- 用 `.word` 或局部 inline asm 发出 vector 指令，避免全局 toolchain 依赖。
- 用现有 runtime 的 page table/PMP/PMA/MMU helper，或者扩展一层小的 vector
  MMU support helper。
- 自检通过 signature 或内存结果比较实现。
- 新增 suite 用普通 snippet composition，不影响现有 MMU rule corpus。

如果后续发现 vector MMU case 很适合纳入 rule schema，再单独规划 schema 扩展，
例如新增 `requestor: vector_load/vector_store`、`vector` 配置段和 coverage
tags。

## 测试与文档要求

- 新增 suite 必须能 `dump-plan` 和 `build`。
- 新增 build/test 应检查最终 ELF 里确实包含 vector memory 指令编码，而不是只
  包含 `vsetvl`。
- inventory 或 loader 测试应确保 v3 suite 继续不选择 vector case。
- README 或 MMU run notes 应说明 v2 vector MMU suite 的运行方法和边界。
- 若目标运行失败，要分类为测试构造问题、runner/reference 问题或 DUT 行为问题。

## 推荐执行顺序

1. 先实现 v2 vector MMU smoke：Bare + Sv39 hit + unit-stride load/store。
2. 再加入跨页 valid case。
3. 再加入基础 page fault 和权限 fault。
4. 最后补文档和 coverage/evidence 汇总。
