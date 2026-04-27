# SnippetGen MMU Spec-In Case-Out 接口计划

## Goal Description

把 `XS/xs-env/nexus-am/tests/mmutest` 中已经沉淀的 MMU 测试能力迁移为 `XS/snippetgen` 原生接口，使第一层“spec in, case out”验证能够通过结构化规则生成小型、可重复、可自检的 MMU case。

本计划的核心不是全量搬运 `mmutest`，而是把旧接口中的运行时初始化、页表构造、CSR/fence 控制、异常观察、虚拟化进入和 coverage 记录拆成可组合模块。第一波完成后，功能型 MMU 测试可以由规则描述生成 case；后续微架构测试也能在同一接口上插入异常前动作、异常点、handler 内动作和 handler 后检查。

## Acceptance Criteria

Following TDD philosophy, each criterion includes positive and negative tests for deterministic verification.

- AC-1: `snippetgen` 提供 MMU 专用运行时接口层，替代 pilot case 中的 `mmutest_*` 依赖和一文件内联页表/trap 样板。
  - Positive Tests (expected to PASS):
    - 新增 `tests/test_mmu_runtime_surface.py`，检查 `runtime/include/xsam/mmu.h`、`runtime/include/xsam/mmu_fault.h`、`runtime/include/xsam/mmu_guest.h` 及对应 `.c` 文件存在。
    - host-side 或 cross-compile smoke test 能包含新 MMU headers，并编译调用 page-table init、map、raw PTE、fault arming、`sfence`、`hfence`、guest helper 的最小 API。
    - 至少一个 pilot MMU suite 通过现有 `generator/cli.py build` 构建，并在 build manifest 中包含新 MMU runtime sources。
  - Negative Tests (expected to FAIL):
    - 新增或迁移的 pilot MMU 程序如果直接 include `mmutest.h` 或 `mmutest_vme.h`，仓库测试失败。
    - 如果公共接口缺少 stage1/stage2 page-table builder、fault observe 或 fence/control helper，runtime surface 测试失败。

- AC-2: 第一层 MMU rule schema 能表达 requestor、翻译模式、前提条件、触发动作、预期结果、观测点和 coverage tags。
  - Positive Tests (expected to PASS):
    - 新增 `tests/test_mmu_rule_loader.py`，可加载合法规则，例如 `bare_identity`、`sv39_alias`、`superpage`、`sfence_remap`、`load_page_fault`、`two_stage_fault`。
    - typed model 至少包含 `id`、`requestor`、`mode`、`preconditions`、`setup`、`trigger`、`expect`、`observe`、`coverage_tags`。
    - schema 支持显式阶段字段，用来表达 setup、before-trigger action、trigger、handler action、post-check 或等价结构。
  - Negative Tests (expected to FAIL):
    - 缺少 `requestor`、`mode`、`expect` 或 `coverage_tags` 的 rule 被 loader 拒绝。
    - 不支持的 requestor/mode/result、重复 rule ID、未知 coverage tag 或非法 symbol name 被 loader 拒绝。

- AC-3: `snippetgen` 能从合法 MMU rule 生成可构建的 case artifact，并继续复用现有 manifest/suite/build/run pipeline。
  - Positive Tests (expected to PASS):
    - 新增 `generator/xsgen/mmu_rule_loader.py` 和 `generator/xsgen/mmu_rule_emitter.py` 或等价模块。
    - 构建 pilot MMU suite 时，在 `build/<suite>/` 下生成 rule 派生的 C/header artifact，例如 `generated_mmu_rule.c`、`generated_mmu_rule.h` 或等价文件。
    - `snippets/programs/mmu_rule_runner_main.c` 或等价 generic runner 能消费生成数据，调用 MMU runtime API，并返回确定性 pass/fail code。
    - `tests/test_build_pipeline.py` 能验证 pilot suite 生成 ELF/bin/disasm，并在 manifest/ledger 中记录 resolved rule IDs。
  - Negative Tests (expected to FAIL):
    - suite 引用不存在的 rule ID 时 build 前失败。
    - rule 生成的 C symbol 非法或与已有 symbol 冲突时，emitter 测试失败。
    - 需要每个新 MMU rule 都手写独立完整 C 程序的实现不满足本 AC。

- AC-4: coverage 记录能区分 rule 已定义、case 已生成、case 已运行和 coverage hole。
  - Positive Tests (expected to PASS):
    - 每条 pilot rule 带 coverage tags，例如 `requestor.load`、`requestor.store`、`mode.host_single_stage`、`mode.allStage`、`exception.gpf`、`page.superpage`、`attr.nc`、`ctrl.sfence`。
    - 构建或运行后生成稳定 JSON ledger，能列出 `defined`、`generated`、`ran`、`gap` 状态。
    - 测试能读取 ledger 并确认 coverage tag 与 rule/case/run 状态对齐。
  - Negative Tests (expected to FAIL):
    - 没有 coverage tags 的 rule 被拒绝。
    - ledger 不能区分 `defined_only`、`generated_not_run`、`ran` 时测试失败。
    - coverage tag 格式不符合 `category.item` 时测试失败。

- AC-5: 第一波 pilot case 证明接口能覆盖功能验证主线，并保留微架构场景组合扩展点。
  - Positive Tests (expected to PASS):
    - pilot set 至少覆盖以下类型中的五类：Bare 或地址直通、Sv39 4K alias、superpage、page/access fault、`sfence` remap、VS-only/G-only、two-stage happy path、two-stage fault、PBMT/NC/MMIO 属性场景。
    - 至少一个 pilot bundle 能在 XiangShan `emu` + NEMU diff 流程中运行到 expected good trap 或 expected fault 结果。
    - 至少一个 pilot rule 使用 handler action 或 post-check 阶段，证明接口能表达“异常点 / handler 内动作 / handler 后检查”的组合。
  - Negative Tests (expected to FAIL):
    - pilot set 如果只覆盖 host single-stage happy path，不满足 AC。
    - pilot case 如果把页表构造、trap handler、CSR/fence 操作全部重新内联在 case 文件里而不走新接口，不满足 AC。

## Path Boundaries

Path boundaries define the acceptable range of implementation quality and choices.

### Upper Bound (Maximum Scope)

完成一个可扩展的 `snippetgen` 原生 MMU 第一层接口：包含 runtime MMU API、rule schema、rule loader、rule emitter、generic runner、coverage ledger、5 到 8 个代表性 pilot rules/suites、unit/build regression，以及至少一个真实 XiangShan/NEMU run 记录。文档说明如何继续添加第一层 MMU 规则，并明确第二层随机模板和第三层 monitor/scoreboard 后续再做。

### Lower Bound (Minimum Scope)

至少完成可复用 runtime MMU API、严格 rule loader、generic runner 或等价生成路径、coverage tag/ledger 基础能力，并用 4 个左右 pilot rules 证明接口能覆盖基础翻译、异常、控制失效和 guest/two-stage 中至少一种。只迁移几个 one-off C 程序、没有规则库、没有 coverage 对齐、没有公共 MMU 接口，不满足下界。

### Allowed Choices

- Can use: 现有 `am_program` harness、YAML rule、Python typed loader、build-time C/header emission、JSON ledger、`xsam_xs_platform.h` 中的 XiangShan 平台 helper。
- Can use: generic runner + generated data 的方式表达规则，也可以用 generated full C case，但必须保留规则源和 coverage ledger。
- Cannot use: 直接把 `mmutest_*` namespace 原样复制到 `snippetgen`；每个 case 继续手写完整页表/trap/CSR 样板；第一波引入随机时序模板、waveform-only monitor 或 scoreboard-heavy 微架构检查。

> **Note on Deterministic Designs**: 第一波设计固定在 `snippetgen` 现有 build/run pipeline 上，不重新设计外层运行框架。自由度主要在 MMU runtime API 的边界、rule schema 细节和 generated artifact 的组织方式。

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only. These are conceptual suggestions, not prescriptive requirements.

### Conceptual Approach

建议把旧 `mmutest` 接口按职责拆成三个层次。

第一层是 runtime API：

```c
xsam_mmu_env_init(...);
xsam_mmu_pt_init_sv39(...);
xsam_mmu_pt_init_sv39x4(...);
xsam_mmu_pt_map(...);
xsam_mmu_pt_map_raw(...);
xsam_mmu_expect_fault(...);
xsam_mmu_fault_assert(...);
xsam_mmu_write_satp(...);
xsam_mmu_write_vsatp(...);
xsam_mmu_write_hgatp(...);
xsam_mmu_sfence_vma(...);
xsam_mmu_hfence_vvma(...);
xsam_mmu_hfence_gvma(...);
xsam_mmu_enter_vs(...);
```

第二层是 rule schema：

```yaml
id: sv39_alias_load_store
requestor: load
mode: host_single_stage
preconditions:
  pmp: allow
setup:
  mappings:
    - name: rw_alias
      va: 0xa00000000
      pa: test_page
      perms: [r, w, a, d]
    - name: ro_alias
      va: 0x900000000
      pa: test_page
      perms: [r, a, d]
trigger:
  op: store_then_load
  store_va: rw_alias
  load_va: ro_alias
expect:
  result: hit
observe:
  - memory_value_match
coverage_tags:
  - requestor.load
  - mode.host_single_stage
  - page.alias
```

第三层是 generated runner：

- loader 校验 rule。
- emitter 生成静态 rule data 或 case-specific C helper。
- `mmu_rule_runner_main.c` 根据 generated data 调用 runtime API。
- build manifest 和 coverage ledger 记录 rule IDs、coverage tags 和状态。

### Relevant References

- `xs-env/nexus-am/tests/mmutest/include/mmutest_vme.h` - 旧接口总览。
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_pt.c` - 页表 helper 的主要来源。
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_fault.c` - fault arming/observe 的主要来源。
- `xs-env/nexus-am/tests/mmutest/src/support/mmutest_vme_hyp.c` - H 扩展、VS entry、CSR/fence 的主要来源。
- `snippetgen/runtime/include/xsam/vme.h` - 当前 VME surface，后续不应继续承载过多 MMU 专用语义。
- `snippetgen/snippets/programs/nexus_memscan_page_fault_main.c` - 当前 one-off MMU-like port，可作为反例和迁移参考。
- `snippetgen/generator/xsgen/model.py` - typed model 扩展点。
- `snippetgen/generator/xsgen/suite_loader.py` - suite schema 外层应尽量保持兼容。
- `snippetgen/tests/test_am_program_snippet_runtime.py` - runtime surface 测试模式参考。

## Dependencies and Sequence

### Milestones

1. Milestone 1: 固化接口边界和测试保护网
   - Phase A: 盘点 `mmutest_vme.h` 和 support sources，把 API 分为 environment、page table、control/context、fault observe、guest/hyp、coverage/rule。
   - Phase B: 写失败测试，锁定新 headers/sources、禁止 pilot 直接 include 旧 `mmutest`、定义 rule loader 的必填字段。

2. Milestone 2: 实现 MMU runtime API
   - Phase A: 实现 page-table builder、mapping、raw PTE、identity/alias/superpage helper。
   - Phase B: 实现 fault observation、CSR/fence、guest/HLV/HSV helper。
   - Phase C: 确认新 runtime source 被 `toolchain.py` 或现有 build source collection 纳入。

3. Milestone 3: 实现 rule schema、loader 和 emitter
   - Phase A: 新增 typed rule model 和 YAML loader。
   - Phase B: 新增 rule validation，包括 requestor/mode/result/coverage tag。
   - Phase C: 新增 generated C/header artifact 或等价 generated source。

4. Milestone 4: 接入 generic runner 和 pilot suites
   - Phase A: 新增 `mmu_rule_runner_main.c` 和 manifest。
   - Phase B: 新增 pilot rules/suites，覆盖基础翻译、fault、control invalidation、guest/two-stage、属性场景。
   - Phase C: 运行 unit/build tests 和至少一个真实 XiangShan/NEMU pilot run。

5. Milestone 5: coverage ledger 和文档
   - Phase A: 生成 JSON ledger，记录 rule defined/generated/ran/gap。
   - Phase B: 更新文档，说明如何添加第一层 MMU rule，以及哪些第二层/第三层内容不属于当前接口第一波。

## Task Breakdown

Each task must include exactly one routing tag:
- `coding`: implemented by Claude
- `analyze`: executed via Codex (`/humanize:ask-codex`)

| Task ID | Description | Target AC | Tag (`coding`/`analyze`) | Depends On |
|---------|-------------|-----------|----------------------------|------------|
| task1 | 盘点 `mmutest` API 和现有 `snippetgen` MMU-like ports，输出接口分组和 pilot 类型清单。 | AC-1, AC-5 | analyze | - |
| task2 | 添加失败测试，锁定 MMU runtime surface、禁止旧 `mmutest` include、定义 rule loader 必填字段。 | AC-1, AC-2 | coding | task1 |
| task3 | 实现 `xsam/mmu*.h` 与 `xsam_mmu*.c` runtime API，包括页表、fault、control、guest helper。 | AC-1 | coding | task2 |
| task4 | 实现 `mmu_rule_loader.py`、typed model 和 schema validation。 | AC-2, AC-4 | coding | task1 |
| task5 | 实现 `mmu_rule_emitter.py` 和 generated artifact 接入现有 build pipeline。 | AC-3 | coding | task3, task4 |
| task6 | 实现 generic MMU runner、pilot rules、pilot suites 和 build regression。 | AC-3, AC-5 | coding | task5 |
| task7 | 实现 coverage ledger，更新 docs，并记录至少一个 real-run evidence。 | AC-4, AC-5 | coding | task6 |

## Claude-Codex Deliberation

### Agreements

- 第一波必须是 `snippetgen` 原生接口，不应把 `mmutest_*` 直接平移。
- 现有 `am_program` pipeline 足够作为第一波外层执行框架。
- 第一波只做规则型 `spec in, case out`，不做随机扩展和内部 scoreboard。
- coverage 需要从一开始进入规则库，否则后面很难说明“科学地证明没有 bug”。

### Resolved Disagreements

- Direct port vs interface extraction: 选择 interface extraction。原因是 direct port 可以短期跑更多 case，但会继续复制页表/trap/CSR 样板，不能支撑规则库和 coverage 对齐。
- Full generated C case vs generic runner plus generated data: 首选 generic runner plus generated data，但允许 generated C helper。约束是规则源必须保留，coverage ledger 必须能反查 rule。

### Convergence Status

- Final Status: `partially_converged`

## Pending User Decisions

- DEC-1: 第一波 pilot 数量是否固定为 5 类还是扩展到 8 类。
  - Claude Position: 先做 5 类，保证接口闭环和真实运行证据。
  - Codex Position: 可以扩展到 8 类，但不要阻塞 runtime/rule/coverage 基础设施落地。
  - Tradeoff Summary: 5 类风险低、交付快；8 类覆盖更完整，但容易把第一波拖成 case 迁移工程。
  - Decision Status: `PENDING`

## Implementation Notes

### Code Style Requirements

- Implementation code and comments must NOT contain plan-specific terminology such as `AC-`, `Milestone`, `Step`, `Phase`, or similar workflow markers。
- 新代码使用领域命名，例如 `xsam_mmu_*`、`xs_mmu_rule_*`、`page_table`、`fault_state`、`translation_mode`，不要使用计划文档术语。
- 旧 `mmutest` 语义可以参考，但不要保留 `mmutest_*` 作为 `snippetgen` 公共 API。

### Execution Notes

- 第一轮开发时先写测试再实现接口，避免 plan 退化成文档。
- 每个 pilot rule 都要能说明对应 coverage tag，而不是只说明“跑过了”。
- 真实 XiangShan/NEMU run 可以只覆盖一个 pilot bundle，但必须把命令、batch id 和结果写入 docs/evidence 或 run notes。
