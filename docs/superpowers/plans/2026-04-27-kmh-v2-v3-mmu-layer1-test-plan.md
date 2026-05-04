# 昆明湖 v2/v3 memblock MMU 第一层测试计划

## Goal Description

在 `snippetgen` 里把昆明湖 v2/v3 memblock MMU 的第一层“spec in, case out”测试做成可积累、可构建、可回归的规则库和运行矩阵。第一层聚焦架构规则和功能可观察结果：翻译模式、requestor、页表项权限、异常分类、PMP/PMA/PBMT 属性、CSR/fence 控制失效、页表修复后重试，以及 H 扩展访存语义。

当前仓库已经有第一版 MMU 规则接口：

- `docs/mmu-spec-in-case-out.md` 说明现有 rule 到 generated case 的流程。
- `snippets/mmu_rules/pilot/*.yaml` 已有 6 个 pilot rule。
- `generator/xsgen/mmu_rule_loader.py` 支持 `load`、`hybrid_load`、`store`、`hlv`、`hlvx`、`hsv` 和 `bare`、`host_single_stage`、`onlyStage1`、`onlyStage2`、`allStage`。
- `generator/xsgen/mmu_rule_emitter.py` 已能生成 `generated_mmu_rule.h`、`generated_mmu_rule.c` 和 `mmu_coverage_ledger.json`。
- `suites/mmu_pilot_rules_poc.yaml` 已接入 generic runner。

本计划不重新设计这些基础设施，而是在它们之上扩展昆明湖第一层规则库、suite 分组、coverage taxonomy、runner 二进制缓存和 v2/v3 回归记录。

关于“先编译两个 bin”的解释：这里把慢编译对象视为昆明湖 v2/v3 的 `emu`/runner 二进制和对应 difftest/波形构建配置。`snippetgen` 生成的 workload `test.bin` 仍按 suite 构建，它是规则变更后的测试输入，不应和昆明湖 runner cache 混在一起。

昆明湖 v2/v3 的指令覆盖边界不同：v3 第一轮先不覆盖向量指令相关 case；v2 可以使用向量指令，也可以把向量访存触发的 MMU 行为纳入第一层规则型验证。

## Acceptance Criteria

- AC-1: 建立昆明湖第一层 MMU 规则库存储，并明确第一层和后续 monitor/stress 层的边界。
  - Positive Tests (expected to PASS):
    - 新增 `snippets/mmu_rules/kmh_layer1/`，第一波保持扁平 YAML 文件布局，因为当前 loader 使用 `*.yaml` 读取规则目录。
    - 新增 `snippets/mmu_rules/kmh_layer1/README.md` 或等价 inventory 文档，逐条列出 rule id、requestor、mode、preconditions、expect、observe、coverage tags 和来源规则。
    - 新增 `tests/test_kmh_mmu_layer1_inventory.py`，加载 `kmh_layer1` 规则库并确认 rule id 唯一、必填字段完整、coverage tags 全部属于 taxonomy、每条 rule 都能追溯到一个 coverage item。
    - inventory 明确说明 `ITLB` 并发 miss、prefetch drop 精确原因、merged miss 内部合并策略、replay 拍点、stale response pipeline kill 等属于第二层/第三层，不在第一层自检闭环里声称已覆盖。
  - Negative Tests (expected to FAIL):
    - 缺少 `requestor`、`mode`、`expect`、`observe` 或 `coverage_tags` 的昆明湖第一层 rule 被测试拒绝。
    - 使用 `requestor: itlb`、`requestor: l1_stream_prefetch`、`expect.result: miss`、`expect.result: refill`、`expect.result: replay` 这类当前 generic runner 无法自检的字段时，除非配套 monitor/scoreboard hook，否则不能进入 `kmh_layer1` generated suite。
    - 只写自然语言用例清单、没有 YAML rule 和 coverage tag 的内容不算第一层规则库完成。

- AC-2: 扩展 coverage taxonomy，使第一层 MMU 规则能表达完整的功能维度。
  - Positive Tests (expected to PASS):
    - `mmu_rule_loader.py` 或等价 taxonomy 模块新增并测试以下标签类别：`pte.*`、`priv.mxr`、`priv.sum`、`attr.pmp_deny`、`attr.pma`、`attr.pbmt_nc`、`attr.mmio`、`ctrl.satp`、`ctrl.vsatp`、`ctrl.hgatp`、`ctrl.asid`、`ctrl.vmid`、`retry.repair_then_reexecute`。
    - coverage ledger 能区分 `defined_only`、`generated_not_run`、`ran`、`gap`，并能列出昆明湖第一层仍未覆盖的标签。
    - 新规则至少覆盖这些主轴：`requestor.load`、`requestor.hybrid_load`、`requestor.store`、`requestor.hlv`、`requestor.hlvx`、`requestor.hsv`、`mode.bare`、`mode.host_single_stage`、`mode.onlyStage1`、`mode.onlyStage2`、`mode.allStage`、`exception.page_fault`、`exception.access_fault`、`exception.guest_page_fault`。
  - Negative Tests (expected to FAIL):
    - 未知 tag、重复 tag、格式不是 `category.item` 的 tag 被 loader 拒绝。
    - 规则使用 `attr.nc` 但没有能观测 NC/PBMT/MMIO 分流的 setup 或 observe 字段时，inventory 测试失败。
    - coverage ledger 只统计“生成了多少 rule”，但不能说明哪些 coverage 还是空洞时，测试失败。

- AC-3: 扩展 rule schema 和 emitter，生成第一层所需的 CSR、页表、属性和异常自检代码。
  - Positive Tests (expected to PASS):
    - loader 能表达普通页、superpage、alias、raw PTE 位组合、stage1/stage2 映射、PMP/PMA/PBMT 属性配置、MXR/SUM CSR 前提、`sfence/hfence/satp/vsatp/hgatp` 控制动作和 handler 修复动作。
    - emitter 生成的 C/header artifact 能驱动 generic runner 完成页表初始化、CSR 初始化、触发访存、trap handler 记录、handler 内修复、返回后重试和 signature 自检。
    - 新增 unit tests 覆盖至少一个合法 raw PTE rule、一个 PMP deny access fault rule、一个 PBMT/NC attribute rule、一个 `vsatp/hgatp` 切换 rule、一个 fault handler repair rule。
  - Negative Tests (expected to FAIL):
    - raw PTE 同时设置非法 `R/W/X` 组合但 expect 写成 `hit` 时，loader 或 inventory 测试失败。
    - stage2 mapping 使用 stage1-only 字段、或 `allStage` rule 缺少 stage1/stage2 任一侧 setup 时，测试失败。
    - 每个新 case 都手写完整 C 程序、绕过 rule source、绕过 generated artifact 的实现不满足本 AC。

- AC-4: 建立昆明湖 v2/v3 runner cache 和 profile 选择机制，避免反复编译昆明湖。
  - Positive Tests (expected to PASS):
    - 约定外部 runner cache 路径，例如 `/nfs/home/liujunqi/XS/artifacts/kmh-runners/`，其中至少包含 `kmh-v2/difftest/emu` 和 `kmh-v3/difftest/emu` 两个逻辑 profile；可选增加 `kmh-v2/difftest-wave/emu`、`kmh-v3/difftest-wave/emu`。
    - cache 下维护 `manifest.json`，记录 profile name、昆明湖 git revision、构建命令摘要、是否带 difftest、是否带 wave、`emu` 路径、NEMU reference 路径、生成时间。
    - `snippetgen` 侧新增 profile resolver 或 run wrapper，能把 `kmh-v2/difftest` 解析成 `SNIPPETGEN_XS_EMU`、`SNIPPETGEN_XS_DIFF` 和必要环境变量。
    - unit tests 能在临时目录构造 fake manifest，验证 profile 解析、缺失 runner 报错、缺失 NEMU 报错、profile 名称拼写错误报错。
  - Negative Tests (expected to FAIL):
    - runner cache 里缺少 `emu` 或 manifest 与文件不一致时，不能静默 fallback 到默认 `NOOP_HOME/build/verilator-compile/emu`。
    - v2/v3 profile 指向同一个 runner binary 但 manifest 没有显式声明 alias 时，测试失败。
    - 大体积 runner binary 不应提交进 `snippetgen` git 仓库；只提交 manifest schema、run notes 和必要 wrapper。

- AC-5: 形成昆明湖第一层 suite 分组，并能在 v2/v3 runner profile 上运行和记录证据。
  - Positive Tests (expected to PASS):
    - 新增 suite 分组，例如 `suites/kmh_mmu_layer1_smoke.yaml`、`suites/kmh_mmu_layer1_host_perm.yaml`、`suites/kmh_mmu_layer1_hyp.yaml`、`suites/kmh_mmu_layer1_attr_ctrl.yaml`、`suites/kmh_mmu_layer1_full.yaml`。
    - `python3 generator/cli.py dump-plan <suite>` 显示 resolved rule ids、defined rule ids 和 coverage tags。
    - `python3 generator/cli.py build <suite>` 生成 `test.elf`、`test.bin`、`disasm`、`build_manifest.json`、`generated_mmu_rule.*` 和 `mmu_coverage_ledger.json`。
    - 对 `kmh-v2/difftest` 和 `kmh-v3/difftest` 至少各运行一次 smoke suite，`batch_meta.json` 中 `status: "ran"`、`finish_code: 0` 或 `labels` 包含 `good_trap` 时，coverage ledger 才能从 `generated_not_run` 晋升为 `ran`。
    - v3 suite 分组第一轮排除向量指令规则；v2 suite 分组允许包含向量指令规则，并在 suite 名或 coverage tag 中区分 vector-enabled 结果。
    - 真实运行命令、profile、seed、batch id、runner revision、NEMU revision 和结果写入 `docs/evidence/kmh-mmu-layer1/` 或同等 run notes。
  - Negative Tests (expected to FAIL):
    - host 命令返回 0 但目标结果不是 `good_trap` 或有效 expected fault，不能标记 rule 为 `ran`。
    - 只在一个昆明湖版本跑通，不记录另一个版本为 missing/gap 时，不满足 v2/v3 回归矩阵。
    - 运行使用的 runner profile 没有写入 batch metadata 或 run notes 时，证据不完整。

- AC-6: 第一层规则集覆盖功能主线，但不把第二层/第三层微架构问题混入第一轮交付。
  - Positive Tests (expected to PASS):
    - 第一波规则至少覆盖：Bare identity、host single-stage 4K hit、host superpage、host alias、load page fault、store page fault、load access fault、store access fault、MXR/SUM、PMP deny、PBMT/NC 或 MMIO 属性、`sfence` remap、`satp` switch、`onlyStage1`、`onlyStage2`、`allStage` guest page fault、HLV、HLVX、HSV、fault repair retry。
    - inventory 为 `ITLB miss + DTLB miss`、demand/prefetch 竞争、miss 期间 redirect、merged miss、duplicate suppression、stale response drop 建立 future coverage hole，但不要求第一层 generated case 判定这些内部时序。
    - 若已有硬件 event、性能计数器或 trace hook 可用，可以在第一层 rule 的 `observe` 中记录为辅助观察，但不作为第一层 pass/fail 的唯一依据。
  - Negative Tests (expected to FAIL):
    - 把 prefetch drop、replay 精确拍点、L2-to-L1 tlb_req 旧响应丢弃等 monitor/stress 问题写成第一层普通 YAML rule 且没有可判定 hook 时，inventory 测试失败。
    - suite 名称或 coverage ledger 声称覆盖 `requestor.itlb`、`requestor.prefetch`，但实际只有 load/store/HLV 指令触发时，测试失败。

- AC-7: 建立长期回归沉淀方式，保证新增规则、生成 artifact、运行结果和 coverage gap 可追踪。
  - Positive Tests (expected to PASS):
    - `docs/mmu-spec-in-case-out.md` 或新增 runbook 更新昆明湖第一层添加规则流程、suite 分组、runner cache profile 用法和证据路径。
    - 新增 make target 或脚本，例如 `make kmh-mmu-layer1-build`、`make kmh-mmu-layer1-smoke-v2`、`make kmh-mmu-layer1-smoke-v3`，内部仍调用 `generator/cli.py`，不复制运行逻辑。
    - coverage summary 能输出 rule defined/generated/ran/gap，并能按 v2/v3 profile 分开记录。
    - 回归结果不覆盖历史证据，使用 batch id 或日期目录保留每次运行。
  - Negative Tests (expected to FAIL):
    - 新增规则没有进入任何 suite 时，coverage summary 必须显示 `defined_only`，不能被误认为已生成或已运行。
    - 运行失败、timeout、abort、difftest mismatch、runner missing 都不能被合并成普通 pass。
    - 生成 artifact 被手工修改后作为源文件提交时，repo layout 测试或文档检查应提示不符合流程。

## Path Boundaries

### Upper Bound (Maximum Scope)

完成昆明湖 v2/v3 第一层 MMU 规则库、taxonomy 扩展、schema/emitter 扩展、suite 分组、runner cache profile 机制、v2/v3 difftest smoke 运行证据、可选 wave profile 运行证据、coverage summary 和文档。第一层覆盖所有正式翻译模式和 demand/H-extension requestor 的代表性规则，并明确所有未进入第一层的 ITLB/prefetch/共享后端微架构场景为后续工作。

### Lower Bound (Minimum Scope)

至少完成：

- `kmh_layer1` 规则目录和 inventory。
- 所有正式翻译模式各至少一条可生成规则。
- `load`、`hybrid_load`、`store`、`hlv`、`hlvx`、`hsv` 至少各一条可生成规则或明确 gap。
- `page_fault`、`access_fault`、`guest_page_fault`、`sfence`、`PMP/PMA/PBMT`、fault repair retry 至少各一条规则或明确 gap。
- `kmh-v2/difftest` 和 `kmh-v3/difftest` 两个 runner profile 的 cache manifest。
- 至少一个 smoke suite 在 v2/v3 profile 上跑出可记录结果，失败也要有 batch evidence 和 gap 说明。

只扩展文档、不新增规则库；只生成 workload `test.bin` 但没有昆明湖 runner cache；只跑现有 pilot suite 但不扩展覆盖矩阵，都不满足下界。

### Allowed Choices

- Can use: 现有 YAML rule、`mmu_rule_loader.py`、`mmu_rule_emitter.py`、generic runner、`mmu_coverage_ledger.json`、`generator/cli.py build/run`、`SNIPPETGEN_XS_EMU`、`SNIPPETGEN_XS_DIFF`、batch-scoped run artifacts。
- Can use: 外部 `/nfs/home/liujunqi/XS/artifacts/kmh-runners/` 存放大体积昆明湖 runner binary，repo 里只提交 schema、manifest example、profile resolver 和 run notes。
- Can use: 先用 deterministic seed 和小 suite 做 smoke，再逐步扩展 host permission、H extension、attribute/control suite。
- Cannot use: 把昆明湖 `emu` binary、NEMU shared object 或 wave 大文件提交进 git。
- Cannot use: 每个 MMU case 都手写完整 C 程序来绕过规则库。
- Cannot use: 在第一层声称覆盖无法自检的内部时序现象，例如 merged miss 精确策略、replay 拍点、prefetch drop 内部原因。

## Dependencies and Sequence

### Milestones

1. Milestone 1: 固化规则库存储和 coverage 边界
   - Phase A: 从 RISC-V privileged spec、昆明湖 memblock/MMU 实现约束和现有 pilot rules 提取第一层 rule inventory。
   - Phase B: 新建 `snippets/mmu_rules/kmh_layer1/` 和 inventory 文档。
   - Phase C: 写 inventory/loader 失败测试，先锁住字段完整性、tag taxonomy 和第一层边界。

2. Milestone 2: 扩展 schema、taxonomy 和 emitter
   - Phase A: 扩展 coverage tag taxonomy，补齐 PTE、privilege、attribute、control、retry 类标签。
   - Phase B: 扩展 YAML schema 表达 raw PTE、PMP/PMA/PBMT、CSR 前提、control action 和 handler repair。
   - Phase C: 扩展 emitter/generic runner，让规则能实际生成 CSR 初始化、页表布局、trap handler 和自检逻辑。

3. Milestone 3: 建立第一层 rule corpus 和 suite 分组
   - Phase A: 迁移或新增 smoke、host permission、page shape、fault、attribute/control、H extension 规则。
   - Phase B: 新增 `kmh_mmu_layer1_*` suites，并确认 `dump-plan`、`build` 和 coverage ledger 正常。
   - Phase C: 对现有 pilot rules 做去重或归档，不让 pilot 和正式昆明湖规则库长期分叉。

4. Milestone 4: 建立昆明湖 runner cache
   - Phase A: 编译或登记 `kmh-v2/difftest`、`kmh-v3/difftest` runner profile。
   - Phase B: 可选登记 `kmh-v2/difftest-wave`、`kmh-v3/difftest-wave`。
   - Phase C: 实现 profile resolver/run wrapper，保证运行时显式选择 v2/v3 runner，不依赖默认环境误选。

5. Milestone 5: 运行 v2/v3 smoke 和扩展回归
   - Phase A: 在 v2/v3 difftest profile 上跑 `kmh_mmu_layer1_smoke`。
   - Phase B: 跑 host permission、H extension、attribute/control 分组，记录每组 batch id 和结果。
   - Phase C: 生成 coverage summary，列出 `ran`、`generated_not_run`、`defined_only` 和 `gap`。

6. Milestone 6: 文档化和长期回归接入
   - Phase A: 更新 `docs/mmu-spec-in-case-out.md` 或新增昆明湖 MMU runbook。
   - Phase B: 新增 make target 或脚本入口，沉淀 v2/v3 smoke/full regression 命令。
   - Phase C: 把第一层未覆盖项转成第二层/第三层 backlog，避免后续误认为已经完成。

## Task Breakdown

Each task must include exactly one routing tag:

| Task ID | Description | Target AC | Tag (`coding`/`analyze`) | Depends On |
|---------|-------------|-----------|----------------------------|------------|
| task1 | 盘点现有 `snippetgen` MMU pilot、RISC-V MMU 规则和昆明湖 memblock 关注点，输出第一层 rule inventory 初稿。 | AC-1, AC-6 | coding | - |
| task2 | 新建 `kmh_layer1` 规则目录、inventory 文档和 inventory/loader 失败测试。 | AC-1, AC-2 | coding | task1 |
| task3 | 扩展 coverage taxonomy，补齐 PTE、privilege、attribute、control、retry 标签，并更新 ledger 测试。 | AC-2, AC-7 | coding | task2 |
| task4 | 扩展 rule schema 与 emitter，支持 raw PTE、PMP/PMA/PBMT、CSR 前提、control action、fault repair retry。 | AC-3 | coding | task3 |
| task5 | 新增昆明湖第一层 rule corpus 和 `kmh_mmu_layer1_*` suites，确认 `dump-plan/build` 通过。 | AC-3, AC-5, AC-6 | coding | task4 |
| task6 | 设计并实现 runner cache manifest/profile resolver，接入 v2/v3 difftest runner 选择。 | AC-4 | coding | task5 |
| task7 | 在 v2/v3 runner profile 上运行 smoke/full 分组，沉淀 batch evidence 和 coverage summary。 | AC-5, AC-7 | coding | task6 |
| task8 | 更新 runbook、make target 或脚本入口，并整理第二层/第三层 backlog。 | AC-6, AC-7 | coding | task7 |

## Implementation Notes

- 新代码和注释不要包含 `AC-`、`Milestone`、`Phase`、`task` 这类计划术语；这些只属于计划文档。
- 第一轮实现时先写 loader/inventory/ledger 测试，再扩展 rule schema 和 emitter。
- 规则目录第一波保持扁平结构；如果要改成递归目录，必须先改 loader 测试和 suite resolver。
- 昆明湖 runner cache 不进入 git。repo 内只保存 manifest schema、profile 名称、run wrapper、run notes 和 coverage evidence。
- `miss/refill/replay` 可以作为未来 monitor 观察点或 coverage backlog，但当前 generic runner 不应把它们作为 `expect.result`。
- `ITLB` 和 prefetch 相关需求要保留在 inventory 里，但第一层只覆盖能由当前 workload 和架构可观察结果自检的部分。
- v3 第一轮不把向量指令作为 bug 搜索入口；v2 可以保留向量指令和向量访存用例。
- 每次真实运行都要记录 profile、seed、batch id、runner revision、NEMU revision、suite、coverage ledger 路径和结果分类。
