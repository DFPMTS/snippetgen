from pathlib import Path
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class BuildPipelineTest(unittest.TestCase):
    def assert_or_skip_for_toolchain(self, result: subprocess.CompletedProcess[str]) -> None:
        if result.returncode == 0:
            return
        stderr = result.stderr or ""
        if (
            "unknown z ISA extension `zicbop'" in stderr
            or "cannot find default versions of the ISA extension `v'" in stderr
        ):
            self.skipTest("installed RISC-V toolchain lacks XiangShan ISA extensions")
        self.assertEqual(0, result.returncode, msg=stderr)

    def compose_plan_for_suite(self, suite_path: str | Path):
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        path = Path(suite_path)
        if not path.is_absolute():
            path = ROOT / path
        suite = suite_loader.load_suite(path)
        return suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))

    def assert_manifest_matches_suite_plan(self, manifest: dict, suite_path: str | Path) -> None:
        plan = self.compose_plan_for_suite(suite_path)
        self.assertEqual(plan.suite_name, manifest["suite"])
        self.assertEqual(list(plan.snippet_ids), manifest["snippet_ids"])
        if plan.run_snippet_ids is not None:
            self.assertEqual(list(plan.run_snippet_ids), manifest["run_snippet_ids"])
            self.assertEqual(list(plan.check_snippet_ids), manifest["check_snippet_ids"])
        if plan.mmu_rule_ids:
            self.assertEqual(list(plan.mmu_rule_ids), manifest["mmu"]["resolved_rule_ids"])
            self.assertEqual(list(plan.mmu_coverage_tags), manifest["mmu"]["coverage_tags"])

    def setUp(self) -> None:
        self.build_dir = ROOT / "build" / "scalar_load_legality_poc"
        self.deferred_check_markers_build_dir = ROOT / "build" / "deferred_check_markers_poc"
        self.vsetvl_build_dir = ROOT / "build" / "vsetvl_interrupt_path_poc"
        self.vsetvl_search_build_dir = ROOT / "build" / "vsetvl_interrupt_search_poc"
        self.interrupt_build_dir = ROOT / "build" / "interrupt_response_poc"
        self.split_store_build_dir = ROOT / "build" / "misaligned_split_store_search_poc"
        self.demo_build_dir = ROOT / "build" / "demo_mark_flag_poc"
        self.prefetchw_build_dir = ROOT / "build" / "prefetchw_tl_denied_fault_poc"
        self.am_program_build_dir = ROOT / "build" / "am_hello_main_poc"
        self.am_timer_program_build_dir = ROOT / "build" / "am_timer_event_poc"
        self.scalar_misalign_load_in_16b_build_dir = ROOT / "build" / "scalar_misalign_load_in_16b_poc"
        self.scalar_misalign_load_cross_16b_build_dir = ROOT / "build" / "scalar_misalign_load_cross_16b_poc"
        self.scalar_misalign_store_in_16b_build_dir = ROOT / "build" / "scalar_misalign_store_in_16b_poc"
        self.scalar_misalign_store_cross_16b_build_dir = ROOT / "build" / "scalar_misalign_store_cross_16b_poc"
        self.scalar_misalign_store_load_overlap_build_dir = ROOT / "build" / "scalar_misalign_store_load_overlap_poc"
        self.scalar_misalign_load_split_build_dir = ROOT / "build" / "scalar_misalign_load_split_templates_poc"
        self.scalar_misalign_store_split_build_dir = ROOT / "build" / "scalar_misalign_store_split_templates_poc"
        self.scalar_misalign_cross_page_build_dir = ROOT / "build" / "scalar_misalign_cross_page_faults_poc"
        self.scalar_misalign_store_forward_overlap_build_dir = ROOT / "build" / "scalar_misalign_store_forward_overlap_poc"
        self.scalar_misalign_store_forward_search_build_dir = ROOT / "build" / "scalar_misalign_store_forward_search_poc"
        self.scalar_misalign_cross_page_search_build_dir = ROOT / "build" / "scalar_misalign_cross_page_fault_search_poc"
        self.scalar_misalign_replay_probe_build_dir = ROOT / "build" / "scalar_misalign_replay_probe_poc"
        self.scalar_misalign_templates_combo_build_dir = ROOT / "build" / "scalar_misalign_templates_combo_poc"
        self.scalar_misalign_fault_forward_combo_build_dir = ROOT / "build" / "scalar_misalign_fault_forward_combo_poc"
        self.scalar_misalign_family_combo_build_dir = ROOT / "build" / "scalar_misalign_family_combo_poc"
        self.generated_random_suite_build_dir = ROOT / "build" / "test_generated_scalar_misalign_full_000"
        self.nexus_cputest_unalign_build_dir = ROOT / "build" / "nexus_cputest_unalign_poc"
        self.nexus_cputest_load_store_build_dir = ROOT / "build" / "nexus_cputest_load_store_poc"
        self.nexus_memscan_access_fault_build_dir = ROOT / "build" / "nexus_memscan_access_fault_poc"
        self.nexus_memscan_fetch_fault_build_dir = ROOT / "build" / "nexus_memscan_fetch_fault_poc"
        self.nexus_memscan_hugepage_access_fault_build_dir = ROOT / "build" / "nexus_memscan_hugepage_access_fault_poc"
        self.nexus_memscan_hugepage_atom_fault_build_dir = ROOT / "build" / "nexus_memscan_hugepage_atom_fault_poc"
        self.nexus_memscan_hugepage_build_dir = ROOT / "build" / "nexus_memscan_hugepage_poc"
        self.nexus_memscan_page_fault_build_dir = ROOT / "build" / "nexus_memscan_page_fault_poc"
        self.mmu_pilot_build_dir = ROOT / "build" / "mmu_pilot_rules_poc"
        self.mmu_bare_identity_build_dir = ROOT / "build" / "mmu_bare_identity_poc"
        self.mmu_missing_rule_build_dir = ROOT / "build" / "mmu_missing_rule"
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        if self.deferred_check_markers_build_dir.exists():
            shutil.rmtree(self.deferred_check_markers_build_dir)
        if self.vsetvl_build_dir.exists():
            shutil.rmtree(self.vsetvl_build_dir)
        if self.vsetvl_search_build_dir.exists():
            shutil.rmtree(self.vsetvl_search_build_dir)
        if self.interrupt_build_dir.exists():
            shutil.rmtree(self.interrupt_build_dir)
        if self.split_store_build_dir.exists():
            shutil.rmtree(self.split_store_build_dir)
        if self.demo_build_dir.exists():
            shutil.rmtree(self.demo_build_dir)
        if self.prefetchw_build_dir.exists():
            shutil.rmtree(self.prefetchw_build_dir)
        if self.am_program_build_dir.exists():
            shutil.rmtree(self.am_program_build_dir)
        if self.am_timer_program_build_dir.exists():
            shutil.rmtree(self.am_timer_program_build_dir)
        if self.scalar_misalign_load_in_16b_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_load_in_16b_build_dir)
        if self.scalar_misalign_load_cross_16b_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_load_cross_16b_build_dir)
        if self.scalar_misalign_store_in_16b_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_in_16b_build_dir)
        if self.scalar_misalign_store_cross_16b_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_cross_16b_build_dir)
        if self.scalar_misalign_store_load_overlap_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_load_overlap_build_dir)
        if self.scalar_misalign_load_split_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_load_split_build_dir)
        if self.scalar_misalign_store_split_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_split_build_dir)
        if self.scalar_misalign_cross_page_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_cross_page_build_dir)
        if self.scalar_misalign_store_forward_overlap_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_forward_overlap_build_dir)
        if self.scalar_misalign_store_forward_search_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_store_forward_search_build_dir)
        if self.scalar_misalign_cross_page_search_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_cross_page_search_build_dir)
        if self.scalar_misalign_replay_probe_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_replay_probe_build_dir)
        if self.scalar_misalign_templates_combo_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_templates_combo_build_dir)
        if self.scalar_misalign_fault_forward_combo_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_fault_forward_combo_build_dir)
        if self.scalar_misalign_family_combo_build_dir.exists():
            shutil.rmtree(self.scalar_misalign_family_combo_build_dir)
        if self.generated_random_suite_build_dir.exists():
            shutil.rmtree(self.generated_random_suite_build_dir)
        if self.nexus_cputest_unalign_build_dir.exists():
            shutil.rmtree(self.nexus_cputest_unalign_build_dir)
        if self.nexus_cputest_load_store_build_dir.exists():
            shutil.rmtree(self.nexus_cputest_load_store_build_dir)
        if self.nexus_memscan_access_fault_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_access_fault_build_dir)
        if self.nexus_memscan_fetch_fault_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_fetch_fault_build_dir)
        if self.nexus_memscan_hugepage_access_fault_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_hugepage_access_fault_build_dir)
        if self.nexus_memscan_hugepage_atom_fault_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_hugepage_atom_fault_build_dir)
        if self.nexus_memscan_hugepage_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_hugepage_build_dir)
        if self.nexus_memscan_page_fault_build_dir.exists():
            shutil.rmtree(self.nexus_memscan_page_fault_build_dir)
        if self.mmu_pilot_build_dir.exists():
            shutil.rmtree(self.mmu_pilot_build_dir)
        if self.mmu_bare_identity_build_dir.exists():
            shutil.rmtree(self.mmu_bare_identity_build_dir)
        if self.mmu_missing_rule_build_dir.exists():
            shutil.rmtree(self.mmu_missing_rule_build_dir)

    def test_emitter_generates_harness_in_suite_order(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/scalar_load_legality_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)

        harness = artifact.generated_suite_path.read_text()
        ordered_symbols = [
            "snippet_init_basic_env",
            "snippet_arm_timer",
            "snippet_unaligned_load",
            "snippet_check_scalar_load_legality",
            "snippet_finish_check",
        ]
        last_index = -1
        for symbol in ordered_symbols:
            current_index = harness.index(symbol)
            self.assertGreater(current_index, last_index)
            last_index = current_index
        self.assertIn("env.seed = 0x1234ull;", harness)

    def test_emitter_generates_two_phase_harness_for_deferred_check_suite(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_suite = Path(tmpdir) / "deferred_check_markers_poc.yaml"
            tmp_suite.write_text(
                textwrap.dedent(
                    """
                    suite: deferred_check_markers_poc
                    target: xiangshan-verilator
                    seed: 99
                    compose:
                      mode: sequence
                      run_snippets:
                        - init_basic_env
                        - arm_timer
                        - finish_check
                      check_snippets:
                        - arm_timer
                        - finish_check
                    """
                ).strip()
            )
            suite = suite_loader.load_suite(tmp_suite)
            plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
            artifact = toolchain.artifact_paths_for_suite(Path(tmpdir), suite.name)
            emitter.emit_harness(plan, artifact.generated_suite_path)
            harness = artifact.generated_suite_path.read_text()

        self.assertIn("xsrt_run_snippet_no_check(&env, &snippet_init_basic_env);", harness)
        self.assertIn("xsrt_run_snippet_no_check(&env, &snippet_arm_timer);", harness)
        self.assertIn("xsrt_run_snippet_no_check(&env, &snippet_finish_check);", harness)
        self.assertIn("xsrt_run_snippet_check_only(&env, &snippet_arm_timer);", harness)
        self.assertIn("xsrt_run_snippet_check_only(&env, &snippet_finish_check);", harness)
        self.assertNotIn("xsrt_run_snippet(&env,", harness)
        self.assertEqual(1, harness.count("extern const xsrt_snippet_desc_t snippet_arm_timer;"))
        self.assertEqual(1, harness.count("extern const xsrt_snippet_desc_t snippet_finish_check;"))

        run_init = harness.index("xsrt_run_snippet_no_check(&env, &snippet_init_basic_env);")
        run_arm_timer = harness.index("xsrt_run_snippet_no_check(&env, &snippet_arm_timer);")
        run_finish = harness.index("xsrt_run_snippet_no_check(&env, &snippet_finish_check);")
        check_arm_timer = harness.index("xsrt_run_snippet_check_only(&env, &snippet_arm_timer);")
        check_finish = harness.index("xsrt_run_snippet_check_only(&env, &snippet_finish_check);")

        self.assertLess(run_init, run_arm_timer)
        self.assertLess(run_arm_timer, run_finish)
        self.assertLess(run_finish, check_arm_timer)
        self.assertLess(check_arm_timer, check_finish)

    def test_emitter_rejects_partial_phase_plan(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")

        plan = model.ComposePlan(
            suite_name="partial_phase_plan",
            target="xiangshan-verilator",
            seed=1,
            snippet_ids=("arm_timer",),
            snippets=(
                model.SnippetSpec(
                    id="arm_timer",
                    kind="proc",
                    lang="c",
                    sources=(),
                ),
            ),
            run_snippet_ids=("arm_timer",),
            check_snippet_ids=None,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_suite.c"
            with self.assertRaisesRegex(
                ValueError,
                "run_snippet_ids and check_snippet_ids must both be set or both be None",
            ):
                emitter.emit_harness(plan, output_path)

    def test_emitter_rejects_am_programs_in_check_phase(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")

        plan = model.ComposePlan(
            suite_name="am_program_check_phase",
            target="xiangshan-verilator",
            seed=1,
            snippet_ids=("init_basic_env", "demo_program"),
            snippets=(
                model.SnippetSpec(
                    id="init_basic_env",
                    kind="proc",
                    lang="c",
                    sources=(),
                ),
                model.SnippetSpec(
                    id="demo_program",
                    kind="am_program",
                    lang="c",
                    sources=(ROOT / "snippets" / "programs" / "am_hello_main.c",),
                    entry="main",
                ),
            ),
            run_snippet_ids=("init_basic_env",),
            check_snippet_ids=("demo_program",),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_suite.c"
            with self.assertRaisesRegex(ValueError, "check_snippets cannot include am_program"):
                emitter.emit_harness(plan, output_path)

    def test_suite_reorder_changes_generated_harness_order(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_suite = Path(tmpdir) / "reordered.yaml"
            tmp_suite.write_text(
                textwrap.dedent(
                    """
                    suite: reordered
                    target: xiangshan-verilator
                    seed: 99
                    compose:
                      mode: sequence
                      snippets:
                        - finish_check
                        - unaligned_load
                        - init_basic_env
                    """
                ).strip()
            )
            suite = suite_loader.load_suite(tmp_suite)
            plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
            artifact = toolchain.artifact_paths_for_suite(Path(tmpdir), suite.name)
            emitter.emit_harness(plan, artifact.generated_suite_path)
            harness = artifact.generated_suite_path.read_text()

            finish_idx = harness.index("snippet_finish_check")
            unaligned_idx = harness.index("snippet_unaligned_load")
            init_idx = harness.index("snippet_init_basic_env")
            self.assertLess(finish_idx, unaligned_idx)
            self.assertLess(unaligned_idx, init_idx)

    def test_emitter_propagates_non_default_suite_seed(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_suite = Path(tmpdir) / "seeded.yaml"
            tmp_suite.write_text(
                textwrap.dedent(
                    """
                    suite: seeded
                    target: xiangshan-verilator
                    seed: 99
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                    """
                ).strip()
            )
            suite = suite_loader.load_suite(tmp_suite)
            plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
            artifact = toolchain.artifact_paths_for_suite(Path(tmpdir), suite.name)
            emitter.emit_harness(plan, artifact.generated_suite_path)
            harness = artifact.generated_suite_path.read_text()

            self.assertIn("xsrt_init(&env);", harness)
            self.assertIn("env.seed = 0x63ull;", harness)
            self.assertLess(harness.index("xsrt_init(&env);"), harness.index("env.seed = 0x63ull;"))
            self.assertLess(harness.index("env.seed = 0x63ull;"), harness.index("xsrt_run_snippet(&env, &snippet_init_basic_env);"))

    def test_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/scalar_load_legality_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.build_dir / "generated_suite.c"
        test_elf = self.build_dir / "test.elf"
        test_bin = self.build_dir / "test.bin"
        disasm = self.build_dir / "disasm"
        build_manifest = self.build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("scalar_load_legality_poc", manifest["suite"])
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])
        self.assertTrue(manifest["commands"]["compile"])
        self.assertTrue(manifest["commands"]["link"])
        self.assertTrue(manifest["commands"]["objcopy"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/scalar_load_legality_poc.yaml")

    def test_deferred_check_suite_build_generates_artifacts_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_suite = Path(tmpdir) / "deferred_check_markers_poc.yaml"
            tmp_suite.write_text(
                textwrap.dedent(
                    """
                    suite: deferred_check_markers_poc
                    target: xiangshan-verilator
                    seed: 99
                    compose:
                      mode: sequence
                      run_snippets:
                        - init_basic_env
                        - arm_timer
                        - finish_check
                      check_snippets:
                        - arm_timer
                        - finish_check
                    """
                ).strip()
            )
            self.assert_proc_check_suite_build(
                suite_path=str(tmp_suite.resolve()),
                build_dir=self.deferred_check_markers_build_dir,
            )

            generated_text = (self.deferred_check_markers_build_dir / "generated_suite.c").read_text()
            self.assertIn("xsrt_run_snippet_no_check(&env, &snippet_arm_timer);", generated_text)
            self.assertIn("xsrt_run_snippet_check_only(&env, &snippet_arm_timer);", generated_text)
            self.assertIn("xsrt_run_snippet_check_only(&env, &snippet_finish_check);", generated_text)
            self.assertNotIn("xsrt_run_snippet(&env,", generated_text)
            self.assertEqual(1, generated_text.count("extern const xsrt_snippet_desc_t snippet_arm_timer;"))

            manifest = json.loads(
                (self.deferred_check_markers_build_dir / "build_manifest.json").read_text()
            )
            self.assert_manifest_matches_suite_plan(manifest, tmp_suite)
            self.assertNotIn("generated_mmu_header", manifest["artifacts"])
            self.assertNotIn("generated_mmu_source", manifest["artifacts"])
            self.assertNotIn("mmu_coverage_ledger", manifest["artifacts"])

    def test_vsetvl_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/vsetvl_interrupt_path_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.vsetvl_build_dir / "generated_suite.c"
        test_elf = self.vsetvl_build_dir / "test.elf"
        test_bin = self.vsetvl_build_dir / "test.bin"
        disasm = self.vsetvl_build_dir / "disasm"
        build_manifest = self.vsetvl_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("vsetvl_interrupt_path_poc", manifest["suite"])
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])
        self.assertTrue(manifest["commands"]["compile"])
        self.assertTrue(manifest["commands"]["link"])
        self.assertTrue(manifest["commands"]["objcopy"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/vsetvl_interrupt_path_poc.yaml")

    def test_interrupt_response_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/interrupt_response_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.interrupt_build_dir / "generated_suite.c"
        test_elf = self.interrupt_build_dir / "test.elf"
        test_bin = self.interrupt_build_dir / "test.bin"
        disasm = self.interrupt_build_dir / "disasm"
        build_manifest = self.interrupt_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("interrupt_response_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/interrupt_response_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])

    def test_vsetvl_search_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/vsetvl_interrupt_search_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.vsetvl_search_build_dir / "generated_suite.c"
        test_elf = self.vsetvl_search_build_dir / "test.elf"
        test_bin = self.vsetvl_search_build_dir / "test.bin"
        disasm = self.vsetvl_search_build_dir / "disasm"
        build_manifest = self.vsetvl_search_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("vsetvl_interrupt_search_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/vsetvl_interrupt_search_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])

    def test_split_store_search_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/misaligned_split_store_search_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.split_store_build_dir / "generated_suite.c"
        test_elf = self.split_store_build_dir / "test.elf"
        test_bin = self.split_store_build_dir / "test.bin"
        disasm = self.split_store_build_dir / "disasm"
        build_manifest = self.split_store_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("misaligned_split_store_search_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/misaligned_split_store_search_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])

    def test_demo_mark_flag_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/demo_mark_flag_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.demo_build_dir / "generated_suite.c"
        test_elf = self.demo_build_dir / "test.elf"
        test_bin = self.demo_build_dir / "test.bin"
        disasm = self.demo_build_dir / "disasm"
        build_manifest = self.demo_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("demo_mark_flag_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/demo_mark_flag_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])

    def test_am_program_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/am_hello_main_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.am_program_build_dir / "generated_suite.c"
        test_elf = self.am_program_build_dir / "test.elf"
        test_bin = self.am_program_build_dir / "test.bin"
        disasm = self.am_program_build_dir / "disasm"
        build_manifest = self.am_program_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("am_hello_main_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/am_hello_main_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])

        generated_text = generated_suite.read_text()
        self.assertIn('#include "xsam/program_snippet.h"', generated_text)
        self.assertIn("xsam_program_entry_am_hello_main", generated_text)

        compile_sources = [
            cmd[cmd.index("-c") + 1]
            for cmd in manifest["commands"]["compile"]
        ]
        self.assertIn(str((ROOT / "snippets" / "programs" / "am_hello_main.c").resolve()), compile_sources)
        self.assertIn(
            str((self.am_program_build_dir / "generated_am_program_am_hello_main.c").resolve()),
            compile_sources,
        )
        self.assertIn(str(generated_suite), compile_sources)
        self.assertIn(str((ROOT / "runtime" / "src" / "xsam_program_snippet.c").resolve()), compile_sources)

    def test_am_timer_program_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/am_timer_event_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.am_timer_program_build_dir / "generated_suite.c"
        test_elf = self.am_timer_program_build_dir / "test.elf"
        test_bin = self.am_timer_program_build_dir / "test.bin"
        disasm = self.am_timer_program_build_dir / "disasm"
        build_manifest = self.am_timer_program_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("am_timer_event_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/am_timer_event_poc.yaml")

        generated_text = generated_suite.read_text()
        self.assertIn("snippet_am_timer_event_main", generated_text)
        self.assertIn("snippet_check_interrupt_response", generated_text)
        self.assertIn("xsam_program_entry_am_timer_event_main", generated_text)

    def test_nexus_cputest_unalign_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_cputest_unalign_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_cputest_unalign_build_dir / "generated_suite.c"
        build_manifest = self.nexus_cputest_unalign_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assertEqual("nexus_cputest_unalign_poc", manifest["suite"])
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_cputest_unalign_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_cputest_unalign_main", generated_suite.read_text())

    def assert_am_program_suite_build(
        self,
        *,
        suite_path: str,
        build_dir: Path,
    ) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", suite_path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = build_dir / "generated_suite.c"
        build_manifest = build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, suite_path)
        snippet_id = next(
            snippet_id
            for snippet_id in manifest["snippet_ids"]
            if snippet_id not in {"init_basic_env", "finish_check"}
        )
        self.assertIn(f"xsam_program_entry_{snippet_id}", generated_suite.read_text())

    def test_scalar_misalign_load_in_16b_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_am_program_suite_build(
            suite_path="suites/scalar_misalign_load_in_16b_poc.yaml",
            build_dir=self.scalar_misalign_load_in_16b_build_dir,
        )

    def test_scalar_misalign_load_cross_16b_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_am_program_suite_build(
            suite_path="suites/scalar_misalign_load_cross_16b_poc.yaml",
            build_dir=self.scalar_misalign_load_cross_16b_build_dir,
        )

    def test_scalar_misalign_store_in_16b_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_am_program_suite_build(
            suite_path="suites/scalar_misalign_store_in_16b_poc.yaml",
            build_dir=self.scalar_misalign_store_in_16b_build_dir,
        )

    def test_scalar_misalign_store_cross_16b_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_am_program_suite_build(
            suite_path="suites/scalar_misalign_store_cross_16b_poc.yaml",
            build_dir=self.scalar_misalign_store_cross_16b_build_dir,
        )

    def test_scalar_misalign_store_load_overlap_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_am_program_suite_build(
            suite_path="suites/scalar_misalign_store_load_overlap_poc.yaml",
            build_dir=self.scalar_misalign_store_load_overlap_build_dir,
        )

    def assert_proc_check_suite_build(
        self,
        *,
        suite_path: str,
        build_dir: Path,
    ) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", suite_path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = build_dir / "generated_suite.c"
        build_manifest = build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, suite_path)

        generated_text = generated_suite.read_text()
        for snippet_id in manifest["snippet_ids"]:
            self.assertIn(f"snippet_{snippet_id}", generated_text)

    def test_scalar_misalign_load_split_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_load_split_templates_poc.yaml",
            build_dir=self.scalar_misalign_load_split_build_dir,
        )

    def test_scalar_misalign_store_split_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_store_split_templates_poc.yaml",
            build_dir=self.scalar_misalign_store_split_build_dir,
        )

    def test_scalar_misalign_cross_page_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_cross_page_faults_poc.yaml",
            build_dir=self.scalar_misalign_cross_page_build_dir,
        )

    def test_scalar_misalign_store_forward_overlap_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_store_forward_overlap_poc.yaml",
            build_dir=self.scalar_misalign_store_forward_overlap_build_dir,
        )

    def test_scalar_misalign_store_forward_search_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_store_forward_search_poc.yaml",
            build_dir=self.scalar_misalign_store_forward_search_build_dir,
        )

    def test_scalar_misalign_cross_page_fault_search_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_cross_page_fault_search_poc.yaml",
            build_dir=self.scalar_misalign_cross_page_search_build_dir,
        )

    def test_scalar_misalign_replay_probe_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_replay_probe_poc.yaml",
            build_dir=self.scalar_misalign_replay_probe_build_dir,
        )

    def test_scalar_misalign_templates_combo_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_templates_combo_poc.yaml",
            build_dir=self.scalar_misalign_templates_combo_build_dir,
        )

    def test_scalar_misalign_fault_forward_combo_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_fault_forward_combo_poc.yaml",
            build_dir=self.scalar_misalign_fault_forward_combo_build_dir,
        )

    def test_scalar_misalign_family_combo_suite_build_generates_artifacts_and_manifest(self) -> None:
        self.assert_proc_check_suite_build(
            suite_path="suites/scalar_misalign_family_combo_poc.yaml",
            build_dir=self.scalar_misalign_family_combo_build_dir,
        )

    def test_generated_scalar_misalign_random_suite_builds(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_root) as tmpdir:
            output_dir = Path(tmpdir) / "generated"
            relative_output_dir = output_dir.relative_to(ROOT)
            generate = subprocess.run(
                [
                    "python3",
                    "generator/cli.py",
                    "generate-suites",
                    "--pool",
                    "scalar_misalign_full",
                    "--count",
                    "1",
                    "--seed",
                    "20260421",
                    "--prefix",
                    "test_generated_scalar_misalign_full",
                    "--output-dir",
                    str(relative_output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, generate.returncode, msg=generate.stderr)
            batch_index = json.loads(Path(generate.stdout.strip()).read_text())
            suite_path = batch_index["suites"][0]["path"]

            result = subprocess.run(
                ["python3", "generator/cli.py", "build", suite_path],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

            build_manifest = self.generated_random_suite_build_dir / "build_manifest.json"
            self.assertTrue(build_manifest.is_file())

            manifest = json.loads(build_manifest.read_text())
            self.assertEqual("test_generated_scalar_misalign_full_000", manifest["suite"])
            self.assertEqual("init_basic_env", manifest["snippet_ids"][0])
            self.assertEqual("finish_check", manifest["snippet_ids"][-1])

    def test_nexus_cputest_load_store_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_cputest_load_store_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_cputest_load_store_build_dir / "generated_suite.c"
        build_manifest = self.nexus_cputest_load_store_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_cputest_load_store_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_cputest_load_store_main", generated_suite.read_text())

    def test_nexus_memscan_access_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_access_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_access_fault_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_access_fault_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_access_fault_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_access_fault_main", generated_suite.read_text())

    def test_nexus_memscan_fetch_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_fetch_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_fetch_fault_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_fetch_fault_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_fetch_fault_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_fetch_fault_main", generated_suite.read_text())

    def test_nexus_memscan_hugepage_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_hugepage_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_hugepage_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_hugepage_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_hugepage_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_hugepage_main", generated_suite.read_text())

    def test_nexus_memscan_hugepage_access_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_hugepage_access_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_hugepage_access_fault_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_hugepage_access_fault_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_hugepage_access_fault_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_hugepage_access_fault_main", generated_suite.read_text())

    def test_nexus_memscan_hugepage_atom_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_hugepage_atom_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_hugepage_atom_fault_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_hugepage_atom_fault_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_hugepage_atom_fault_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_hugepage_atom_fault_main", generated_suite.read_text())

    def test_nexus_memscan_page_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/nexus_memscan_page_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        generated_suite = self.nexus_memscan_page_fault_build_dir / "generated_suite.c"
        build_manifest = self.nexus_memscan_page_fault_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/nexus_memscan_page_fault_poc.yaml")
        self.assertIn("xsam_program_entry_nexus_memscan_page_fault_main", generated_suite.read_text())

    def test_mmu_pilot_suite_build_generates_rule_artifacts_manifest_and_ledger(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/mmu_pilot_rules_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assert_or_skip_for_toolchain(result)

        generated_suite = self.mmu_pilot_build_dir / "generated_suite.c"
        generated_mmu_source = self.mmu_pilot_build_dir / "generated_mmu_rule.c"
        generated_mmu_header = self.mmu_pilot_build_dir / "generated_mmu_rule.h"
        build_manifest = self.mmu_pilot_build_dir / "build_manifest.json"
        coverage_ledger = self.mmu_pilot_build_dir / "mmu_coverage_ledger.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(generated_mmu_source.is_file())
        self.assertTrue(generated_mmu_header.is_file())
        self.assertTrue(build_manifest.is_file())
        self.assertTrue(coverage_ledger.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/mmu_pilot_rules_poc.yaml")
        self.assertIn("two_stage_fault", manifest["mmu"]["resolved_rule_ids"])
        self.assertIn("guest.two_stage", manifest["mmu"]["coverage_tags"])
        self.assertTrue(
            manifest["artifacts"]["generated_mmu_source"].endswith(
                "build/mmu_pilot_rules_poc/generated_mmu_rule.c"
            )
        )
        self.assertIn(str((ROOT / "runtime" / "src" / "xsam_mmu.c").resolve()), manifest["runtime_sources"])
        self.assertIn(str((ROOT / "runtime" / "src" / "xsam_mmu_fault.c").resolve()), manifest["runtime_sources"])
        self.assertIn(str((ROOT / "runtime" / "src" / "xsam_mmu_guest.c").resolve()), manifest["runtime_sources"])
        self.assertIn("xsam_program_entry_mmu_rule_runner_main", generated_suite.read_text())
        self.assertIn("xs_generated_rule_two_stage_fault", generated_mmu_source.read_text())

        ledger = json.loads(coverage_ledger.read_text())
        rule_states = {entry["id"]: entry["state"] for entry in ledger["rules"]}
        self.assertEqual("generated_not_run", rule_states["bare_identity"])
        self.assertEqual("generated_not_run", rule_states["two_stage_fault"])
        tag_states = {entry["tag"]: entry["state"] for entry in ledger["coverage_tags"]}
        self.assertEqual("generated_not_run", tag_states["guest.two_stage"])

    def test_mmu_build_rejects_unknown_rule_ids_before_emitting_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "mmu_missing_rule.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: mmu_missing_rule
                    target: xiangshan-verilator
                    seed: 7
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                        - mmu_rule_runner_main
                        - finish_check
                      mmu:
                        rule_dir: /nfs/home/liujunqi/XS/snippetgen/snippets/mmu_rules/pilot
                        rule_ids:
                          - bare_identity
                          - missing_rule
                    """
                ).strip()
            )
            result = subprocess.run(
                ["python3", "generator/cli.py", "build", str(suite_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown MMU rule id in suite", result.stderr)
        self.assertFalse((self.mmu_missing_rule_build_dir / "build_manifest.json").exists())

    def test_mmu_subset_build_manifest_uses_selected_rule_coverage_tags_only(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/mmu_bare_identity_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assert_or_skip_for_toolchain(result)

        manifest = json.loads((self.mmu_bare_identity_build_dir / "build_manifest.json").read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/mmu_bare_identity_poc.yaml")
        self.assertEqual(manifest["mmu"]["coverage_tags"], manifest["mmu"]["emitted_coverage_tags"])
        self.assertNotIn("guest.two_stage", manifest["mmu"]["coverage_tags"])
        self.assertNotIn("requestor.hlv", manifest["mmu"]["coverage_tags"])

    def test_vsetvl_suite_harness_order_and_final_elf_contains_vsetvl(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/vsetvl_interrupt_path_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)

        harness = artifact.generated_suite_path.read_text()
        ordered_symbols = [
            "snippet_init_basic_env",
            "snippet_arm_timer",
            "snippet_vsetvl_interrupt_path",
            "snippet_check_vsetvl_interrupt_path",
            "snippet_finish_check",
        ]
        last_index = -1
        for symbol in ordered_symbols:
            current_index = harness.index(symbol)
            self.assertGreater(current_index, last_index)
            last_index = current_index

        toolchain.build_artifacts(ROOT, plan, artifact)
        objdump = toolchain.resolve_objdump(toolchain.detect_toolchain())
        start_result = subprocess.run(
            [objdump, "-d", "--disassemble=_start", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, start_result.returncode, msg=start_result.stderr)
        self.assertIn("csrs\tmstatus,", start_result.stdout)

        loop_result = subprocess.run(
            [objdump, "-d", "--disassemble=vsetvl_interrupt_path_run", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, loop_result.returncode, msg=loop_result.stderr)
        self.assertRegex(loop_result.stdout, r"(vsetvl\tzero,zero,zero|0x80007057)")

    def test_runtime_entry_emits_noop_halt_trap_after_main_returns(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/vsetvl_interrupt_path_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)

        objdump = toolchain.resolve_objdump(toolchain.detect_toolchain())
        disasm_result = subprocess.run(
            [objdump, "-d", "--disassemble=_start", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, disasm_result.returncode, msg=disasm_result.stderr)

        instructions = []
        for line in disasm_result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            instructions.append("\t".join(field.strip() for field in fields[2:] if field.strip()))

        call_index = next(
            index for index, instruction in enumerate(instructions)
            if instruction.startswith("call\t") or instruction.startswith("jal\t")
        )
        halt_index = next(
            index for index, instruction in enumerate(instructions)
            if instruction == ".word\t0x0005006b" or instruction.endswith("0x5006b")
        )
        self.assertLess(call_index, halt_index)

    def test_interrupt_runtime_emits_trap_entry_and_timer_enable_sequence(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/interrupt_response_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)

        objdump = toolchain.resolve_objdump(toolchain.detect_toolchain())
        trap_result = subprocess.run(
            [objdump, "-d", "--disassemble=xsrt_trap_entry", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, trap_result.returncode, msg=trap_result.stderr)
        self.assertIn("mret", trap_result.stdout)
        self.assertIn("csrrw", trap_result.stdout)
        self.assertIn("mscratch", trap_result.stdout)

        arm_result = subprocess.run(
            [objdump, "-d", "--disassemble=xsrt_enable_stimer", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, arm_result.returncode, msg=arm_result.stderr)
        instructions = []
        for line in arm_result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            instructions.append("\t".join(field.strip() for field in fields[2:] if field.strip()))

        self.assertTrue(any(instruction.startswith("csrw\tmtvec,") for instruction in instructions))
        self.assertTrue(any(instruction.startswith("csrw\tmscratch,") for instruction in instructions))
        self.assertTrue(any(instruction.startswith("csrs\tmie,") for instruction in instructions))
        self.assertTrue(any(instruction.startswith("csrs\tmstatus,") for instruction in instructions))

    def test_vsetvl_search_suite_final_elf_contains_vsetvl(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/vsetvl_interrupt_search_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)

        objdump = toolchain.resolve_objdump(toolchain.detect_toolchain())
        disasm_result = subprocess.run(
            [objdump, "-d", "--disassemble=vsetvl_interrupt_search_run", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, disasm_result.returncode, msg=disasm_result.stderr)
        self.assertRegex(disasm_result.stdout, r"(vsetvl\tzero,zero,zero|0x80007057)")

    def test_split_store_search_suite_final_elf_contains_split_store_and_aligned_loads(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/misaligned_split_store_search_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)

        disasm_result = subprocess.run(
            [toolchain.resolve_objdump(toolchain.detect_toolchain()), "-d", "--disassemble=misaligned_split_store_search_run", str(artifact.elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, disasm_result.returncode, msg=disasm_result.stderr)
        instructions = []
        for line in disasm_result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            instructions.append("\t".join(field.strip() for field in fields[2:] if field.strip()))

        target_store_count = sum(
            1 for instruction in instructions
            if instruction.startswith("sd\t") and ",0(" in instruction
        )
        detector_load_count = sum(1 for instruction in instructions if instruction.startswith("lwu\t"))
        self.assertGreaterEqual(target_store_count, 17, msg=disasm_result.stdout)
        self.assertGreaterEqual(detector_load_count, 2, msg=disasm_result.stdout)
        self.assertTrue(any(instruction.startswith("lhu\t") for instruction in instructions), msg=disasm_result.stdout)
        self.assertTrue(any(instruction.startswith("lbu\t") for instruction in instructions), msg=disasm_result.stdout)

    def test_build_manifest_uses_xiangshan_linker_script(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/vsetvl_interrupt_path_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        manifest = json.loads((self.vsetvl_build_dir / "build_manifest.json").read_text())
        link_cmd = manifest["commands"]["link"]

        linker_arg = next(
            arg for arg in link_cmd
            if arg.startswith("-Wl,-T")
        )
        self.assertEqual(
            f'-Wl,-T{(ROOT / "runtime" / "platform" / "xiangshan" / "section.ld").resolve()}',
            linker_arg,
        )

    def test_prefetchw_tl_denied_fault_suite_build_generates_artifacts_and_manifest(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/prefetchw_tl_denied_fault_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assert_or_skip_for_toolchain(result)

        generated_suite = self.prefetchw_build_dir / "generated_suite.c"
        test_elf = self.prefetchw_build_dir / "test.elf"
        test_bin = self.prefetchw_build_dir / "test.bin"
        disasm = self.prefetchw_build_dir / "disasm"
        build_manifest = self.prefetchw_build_dir / "build_manifest.json"

        self.assertTrue(generated_suite.is_file())
        self.assertTrue(test_elf.is_file())
        self.assertTrue(test_bin.is_file())
        self.assertTrue(disasm.is_file())
        self.assertTrue(build_manifest.is_file())

        manifest = json.loads(build_manifest.read_text())
        self.assert_manifest_matches_suite_plan(manifest, "suites/prefetchw_tl_denied_fault_poc.yaml")
        self.assertEqual(str(generated_suite), manifest["artifacts"]["generated_suite"])
        self.assertEqual(str(test_elf), manifest["artifacts"]["elf"])
        self.assertEqual(str(test_bin), manifest["artifacts"]["bin"])
        self.assertEqual(str(disasm), manifest["artifacts"]["disasm"])
        self.assertEqual(str(build_manifest), manifest["artifacts"]["build_manifest"])
        self.assertTrue(manifest["commands"]["compile"])
        self.assertTrue(manifest["commands"]["link"])
        self.assertTrue(manifest["commands"]["objcopy"])
        compile_flags = {
            arg
            for command in manifest["commands"]["compile"]
            for arg in command
        }
        self.assertIn("-march=rv64gc", compile_flags)
        self.assertNotIn("-march=rv64gcv_zicbop", compile_flags)
        self.assertIn("0037e013", disasm.read_text())

    def test_prefetchw_tl_denied_fault_suite_final_elf_contains_load_then_prefetch_pair(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/prefetchw_tl_denied_fault_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, suite.name)
        emitter.emit_harness(plan, artifact.generated_suite_path)
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "SNIPPETGEN_RISCV_MARCH": "rv64gcv_zicbop",
                    "SNIPPETGEN_RISCV_MABI": "lp64d",
                },
                clear=False,
            ):
                toolchain.build_artifacts(ROOT, plan, artifact)
        except RuntimeError as exc:
            stderr = str(exc)
            if (
                "unknown z ISA extension `zicbop'" in stderr
                or "cannot find default versions of the ISA extension `v'" in stderr
            ):
                self.skipTest("installed RISC-V toolchain lacks XiangShan ISA extensions")
            raise

        disasm_result = subprocess.run(
            [
                toolchain.resolve_objdump(toolchain.detect_toolchain()),
                "-d",
                "--disassemble=prefetchw_tl_denied_fault_run",
                str(artifact.elf_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, disasm_result.returncode, msg=disasm_result.stderr)
        self.assertRegex(
            disasm_result.stdout,
            r"(?s)\bld\s+\w+,0\((\w+)\).*?\bprefetch\.w\s+0\(\1\)",
        )
        self.assertIn(".word\t0x0005006b", disasm_result.stdout)
        self.assertEqual(1, disasm_result.stdout.count("prefetch.w"))
        self.assertIn("prefetch.w", disasm_result.stdout)
        self.assertNotIn("bnez", disasm_result.stdout)

    def test_cli_build_defaults_to_poc_suite(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "build"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertTrue((ROOT / "build" / "scalar_load_legality_poc" / "build_manifest.json").is_file())

    def test_build_artifact_paths_are_stable(self) -> None:
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        first = toolchain.artifact_paths_for_suite(ROOT, "scalar_load_legality_poc")
        second = toolchain.artifact_paths_for_suite(ROOT, "scalar_load_legality_poc")

        self.assertEqual(first.build_dir, second.build_dir)
        self.assertEqual(first.generated_suite_path, second.generated_suite_path)
        self.assertEqual(first.elf_path, second.elf_path)
        self.assertEqual(first.bin_path, second.bin_path)
        self.assertEqual(first.build_manifest_path, second.build_manifest_path)

    def test_objdump_resolves_from_detected_toolchain_directory(self) -> None:
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            gcc_path = tool_dir / "riscv64-custom-gcc"
            objcopy_path = tool_dir / "riscv64-custom-objcopy"
            objdump_path = tool_dir / "riscv64-custom-objdump"

            for path in (gcc_path, objcopy_path, objdump_path):
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)

            resolved = toolchain.resolve_objdump(
                {
                    "prefix": "riscv64-custom",
                    "gcc": str(gcc_path),
                    "objcopy": str(objcopy_path),
                }
            )

            self.assertEqual(str(objdump_path), resolved)

    def test_compile_flags_allow_local_isa_override(self) -> None:
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with mock.patch.dict(
            os.environ,
            {
                "SNIPPETGEN_RISCV_MARCH": "rv64gc",
                "SNIPPETGEN_RISCV_MABI": "lp64d",
            },
            clear=False,
        ):
            flags = toolchain.riscv_compile_flags()

        self.assertIn("-march=rv64gc", flags)
        self.assertIn("-mabi=lp64d", flags)

    def test_compile_flags_default_to_portable_rv64gc(self) -> None:
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with mock.patch.dict(os.environ, {}, clear=True):
            flags = toolchain.riscv_compile_flags()

        self.assertIn("-march=rv64gc", flags)
        self.assertNotIn("-march=rv64gcv_zicbop", flags)

    def test_local_isa_override_build_keeps_reset_vector_at_pmem_base(self) -> None:
        fallback_gcc = Path("/usr/bin/riscv64-linux-gnu-gcc")
        fallback_objcopy = Path("/usr/bin/riscv64-linux-gnu-objcopy")
        if not fallback_gcc.is_file() or not fallback_objcopy.is_file():
            self.skipTest("local fallback GNU toolchain is unavailable")

        env = dict(os.environ)
        env.update(
            {
                "riscv64-unknown-linux-gnu-gcc": str(fallback_gcc),
                "riscv64-unknown-linux-gnu-objcopy": str(fallback_objcopy),
                "SNIPPETGEN_RISCV_MARCH": "rv64gc",
                "SNIPPETGEN_RISCV_MABI": "lp64d",
            }
        )

        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/am_hello_main_poc.yaml"],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        readelf_result = subprocess.run(
            ["readelf", "-h", "-l", str(self.am_program_build_dir / "test.elf")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, readelf_result.returncode, msg=readelf_result.stderr)
        self.assertIn("Entry point address:               0x80000000", readelf_result.stdout)
        self.assertNotIn(".note.gnu.build-id", readelf_result.stdout)

    def test_missing_descriptor_causes_build_failure(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_descriptor_source = Path(tmpdir) / "broken_snippet.c"
            missing_descriptor_source.write_text("int broken_snippet_helper(void) { return 0; }\n")

            snippet = model.SnippetSpec(
                id="broken_snippet",
                kind="proc",
                lang="c",
                sources=(missing_descriptor_source.resolve(),),
            )
            plan = model.ComposePlan(
                suite_name="missing_descriptor_case",
                target="xiangshan-verilator",
                seed=1,
                snippet_ids=("broken_snippet",),
                snippets=(snippet,),
            )
            artifact = toolchain.artifact_paths_for_suite(ROOT, plan.suite_name)
            emitter.emit_harness(plan, artifact.generated_suite_path)

            with self.assertRaisesRegex(RuntimeError, "undefined reference|unresolved"):
                toolchain.build_artifacts(ROOT, plan, artifact)

    def test_duplicate_snippet_reference_builds_once_per_source(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "duplicate.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: duplicate_snippet_suite
                    target: xiangshan-verilator
                    seed: 5
                    compose:
                      mode: sequence
                      snippets:
                        - arm_timer
                        - arm_timer
                        - finish_check
                    """
                ).strip()
            )
            suite = suite_loader.load_suite(suite_path)
            plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
            artifact = toolchain.artifact_paths_for_suite(ROOT, plan.suite_name)
            emitter.emit_harness(plan, artifact.generated_suite_path)
            toolchain.build_artifacts(ROOT, plan, artifact)

            harness = artifact.generated_suite_path.read_text()
            self.assertEqual(2, harness.count("xsrt_run_snippet(&env, &snippet_arm_timer);"))
            manifest = json.loads(artifact.build_manifest_path.read_text())
            compile_sources = [
                cmd[cmd.index("-c") + 1]
                for cmd in manifest["commands"]["compile"]
            ]
            self.assertEqual(1, compile_sources.count(str((ROOT / "snippets" / "scalar_load_legality" / "arm_timer.c").resolve())))

    def test_missing_compile_input_causes_build_failure(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        missing_source = ROOT / "snippets" / "scalar_load_legality" / "does_not_exist.c"
        snippet = model.SnippetSpec(
            id="missing_source_snippet",
            kind="proc",
            lang="c",
            sources=(missing_source,),
        )
        plan = model.ComposePlan(
            suite_name="missing_source_case",
            target="xiangshan-verilator",
            seed=2,
            snippet_ids=("missing_source_snippet",),
            snippets=(snippet,),
        )
        artifact = toolchain.artifact_paths_for_suite(ROOT, plan.suite_name)
        emitter.emit_harness(plan, artifact.generated_suite_path)

        with self.assertRaisesRegex(RuntimeError, "No such file or directory|cannot find"):
            toolchain.build_artifacts(ROOT, plan, artifact)

    def test_objcopy_failure_is_reported(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/scalar_load_legality_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, "objcopy_failure_case")
        emitter.emit_harness(plan, artifact.generated_suite_path)

        broken_toolchain = dict(toolchain.detect_toolchain())
        broken_toolchain["objcopy"] = "/definitely/not/a/real/objcopy"

        with mock.patch.object(toolchain, "detect_toolchain", return_value=broken_toolchain):
            with self.assertRaisesRegex(RuntimeError, "objcopy"):
                toolchain.build_artifacts(ROOT, plan, artifact)

    def test_failed_rebuild_cleans_stale_outputs(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        emitter = importlib.import_module("generator.xsgen.emitter")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        suite = suite_loader.load_suite(ROOT / "suites/scalar_load_legality_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))
        artifact = toolchain.artifact_paths_for_suite(ROOT, "stale_cleanup_case")

        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)
        self.assertTrue(artifact.elf_path.is_file())
        self.assertTrue(artifact.bin_path.is_file())
        self.assertTrue(artifact.build_manifest_path.is_file())

        artifact.generated_suite_path.write_text("broken harness\n")
        with self.assertRaises(RuntimeError):
            toolchain.build_artifacts(ROOT, plan, artifact)
        self.assertFalse(artifact.elf_path.exists())
        self.assertFalse(artifact.bin_path.exists())
        self.assertFalse(artifact.build_manifest_path.exists())

        emitter.emit_harness(plan, artifact.generated_suite_path)
        toolchain.build_artifacts(ROOT, plan, artifact)
        broken_toolchain = dict(toolchain.detect_toolchain())
        broken_toolchain["objcopy"] = "/definitely/not/a/real/objcopy"

        with mock.patch.object(toolchain, "detect_toolchain", return_value=broken_toolchain):
            with self.assertRaises(RuntimeError):
                toolchain.build_artifacts(ROOT, plan, artifact)
        self.assertFalse(artifact.elf_path.exists())
        self.assertFalse(artifact.bin_path.exists())
        self.assertFalse(artifact.build_manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
