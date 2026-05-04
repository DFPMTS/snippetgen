# SnippetGen Dev Checkpoint

Date: 2026-04-17
Branch: `dev`

## Current Status

This branch now has a working `nexus-am`-style single-core baseline inside `snippetgen-demo`.

Completed baseline pieces:

- `xsam` compatibility headers and runtime surface for `TRM`, `CTE`, `VME`, `IOE`, and program-as-snippet entry
- XiangShan/noop platform split with timer, PMP, PMA, PLIC, cache, serial, input, and perf hooks
- generator support for `kind: am_program`
- AM `main()` sample suites for hello/timer paths
- migrated `nexus-am` test slices for:
  - `cputest/unalign`
  - `cputest/load-store`
  - `memscantest` load/store access fault
  - `memscantest` fetch fault
  - first Sv39 page-fault slice
  - first Sv39 hugepage slice
  - hugepage access-fault slice
  - hugepage atom-fault slice
- minimal `prefetchw_tl_denied_fault` workload and checks

## Latest Verified Runs

Recent XiangShan/NEMU `good_trap` batches:

- `real_nexus_memscan_page_fault_8197_fix1`
- `real_nexus_memscan_hugepage_8198_fix1`
- `real_nexus_memscan_hugepage_access_fault_8199_fix1`
- `real_nexus_memscan_hugepage_atom_fault_8200_fix1`

Batch metadata paths:

- `build/nexus_memscan_page_fault_poc/runs/real_nexus_memscan_page_fault_8197_fix1/batch_meta.json`
- `build/nexus_memscan_hugepage_poc/runs/real_nexus_memscan_hugepage_8198_fix1/batch_meta.json`
- `build/nexus_memscan_hugepage_access_fault_poc/runs/real_nexus_memscan_hugepage_access_fault_8199_fix1/batch_meta.json`
- `build/nexus_memscan_hugepage_atom_fault_poc/runs/real_nexus_memscan_hugepage_atom_fault_8200_fix1/batch_meta.json`

## Fresh Regression Command

The current checkpoint was re-verified with:

```bash
python3 -m unittest \
  tests.test_runtime_surface \
  tests.test_xsam_cte_behavior \
  tests.test_platform_driver_layer \
  tests.test_xsam_vme_behavior \
  tests.test_am_program_snippet_runtime \
  tests.test_am_program_snippet_build \
  tests.test_am_program_snippet_run \
  tests.test_build_pipeline.BuildPipelineTest.test_am_program_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_am_timer_program_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_cputest_unalign_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_cputest_load_store_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_access_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_fetch_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_page_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_hugepage_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_hugepage_access_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_nexus_memscan_hugepage_atom_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_prefetchw_tl_denied_fault_suite_build_generates_artifacts_and_manifest \
  tests.test_build_pipeline.BuildPipelineTest.test_prefetchw_tl_denied_fault_suite_final_elf_contains_load_then_prefetch_pair \
  tests.test_snippet_loading.SnippetLoadingTest.test_am_program_files_exist \
  tests.test_snippet_loading.SnippetLoadingTest.test_am_timer_program_files_exist \
  tests.test_snippet_loading.SnippetLoadingTest.test_nexus_cputest_port_files_exist \
  tests.test_snippet_loading.SnippetLoadingTest.test_nexus_memscan_port_files_exist \
  tests.test_snippet_loading.SnippetLoadingTest.test_prefetchw_tl_denied_fault_files_exist \
  tests.test_snippet_loading.SnippetLoadingTest.test_prefetchw_default_target_addr_matches_default_emu_repro_window \
  tests.test_snippet_loading.SnippetLoadingTest.test_prefetchw_minimal_case_has_no_probe_loop_controls \
  tests.test_snippet_loading.SnippetLoadingTest.test_prefetchw_run_bad_traps_immediately_on_wrong_trap_shape \
  tests.test_snippet_loading.SnippetLoadingTest.test_prefetchw_trap_handler_advances_epc_by_instruction_length \
  tests.test_run_pipeline.RunPipelineTest.test_xiangshan_target_builds_expected_command_line
```

Expected/observed result at this checkpoint: `49 tests OK`.

## Next Work

If migration continues, the next target should come from remaining `sv39_test` or `sv39_hp_atom_test` edge cases outside the current minimal baseline set.
