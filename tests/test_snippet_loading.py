from pathlib import Path
import importlib
import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROUND2_FILES = [
    "requirements.txt",
    "generator/cli.py",
    "generator/xsgen/model.py",
    "generator/xsgen/snippet_db.py",
    "generator/xsgen/suite_loader.py",
    "snippets/core/init_basic_env.c",
    "snippets/core/finish_check.c",
    "snippets/scalar_load_legality/arm_timer.c",
    "snippets/scalar_load_legality/unaligned_load.c",
    "snippets/scalar_load_legality/check_scalar_load_legality.c",
    "snippets/manifests/init_basic_env.yaml",
    "snippets/manifests/finish_check.yaml",
    "snippets/manifests/arm_timer.yaml",
    "snippets/manifests/unaligned_load.yaml",
    "snippets/manifests/check_scalar_load_legality.yaml",
    "suites/scalar_load_legality_poc.yaml",
]

VSETVL_PATH_FILES = [
    "snippets/vector_interrupt/vsetvl_interrupt_path.c",
    "snippets/vector_interrupt/check_vsetvl_interrupt_path.c",
    "snippets/manifests/vsetvl_interrupt_path.yaml",
    "snippets/manifests/check_vsetvl_interrupt_path.yaml",
    "suites/vsetvl_interrupt_path_poc.yaml",
]

VSETVL_SEARCH_FILES = [
    "snippets/vector_interrupt/vsetvl_interrupt_search.c",
    "snippets/vector_interrupt/check_vsetvl_interrupt_search.c",
    "snippets/manifests/vsetvl_interrupt_search.yaml",
    "snippets/manifests/check_vsetvl_interrupt_search.yaml",
    "suites/vsetvl_interrupt_search_poc.yaml",
]

INTERRUPT_RESPONSE_FILES = [
    "snippets/interrupt/interrupt_response_wait.c",
    "snippets/interrupt/check_interrupt_response.c",
    "snippets/manifests/interrupt_response_wait.yaml",
    "snippets/manifests/check_interrupt_response.yaml",
    "suites/interrupt_response_poc.yaml",
]

SPLIT_STORE_FORWARD_FILES = [
    "snippets/store_forward/misaligned_split_store_search.c",
    "snippets/store_forward/check_misaligned_split_store_search.c",
    "snippets/manifests/misaligned_split_store_search.yaml",
    "snippets/manifests/check_misaligned_split_store_search.yaml",
    "suites/misaligned_split_store_search_poc.yaml",
]

EXAMPLE_FILES = [
    "snippets/examples/demo_mark_flag.c",
    "snippets/examples/check_demo_mark_flag.c",
    "snippets/manifests/demo_mark_flag.yaml",
    "snippets/manifests/check_demo_mark_flag.yaml",
    "suites/demo_mark_flag_poc.yaml",
]

PREFETCHW_FILES = [
    "snippets/include/xs_prefetchw.h",
    "snippets/cbo/prefetchw_tl_denied_fault.c",
    "snippets/cbo/check_prefetchw_tl_denied_fault.c",
    "snippets/manifests/prefetchw_tl_denied_fault.yaml",
    "snippets/manifests/check_prefetchw_tl_denied_fault.yaml",
    "suites/prefetchw_tl_denied_fault_poc.yaml",
]

AM_PROGRAM_FILES = [
    "snippets/programs/am_hello_main.c",
    "snippets/manifests/am_hello_main.yaml",
    "suites/am_hello_main_poc.yaml",
]

AM_TIMER_PROGRAM_FILES = [
    "snippets/programs/am_timer_event_main.c",
    "snippets/manifests/am_timer_event_main.yaml",
    "suites/am_timer_event_poc.yaml",
]

SCALAR_MISALIGN_PHASE1_FILES = [
    "snippets/programs/scalar_misalign_load_in_16b_main.c",
    "snippets/programs/scalar_misalign_load_cross_16b_main.c",
    "snippets/programs/scalar_misalign_store_in_16b_main.c",
    "snippets/programs/scalar_misalign_store_cross_16b_main.c",
    "snippets/programs/scalar_misalign_store_load_overlap_main.c",
    "snippets/manifests/scalar_misalign_load_in_16b_main.yaml",
    "snippets/manifests/scalar_misalign_load_cross_16b_main.yaml",
    "snippets/manifests/scalar_misalign_store_in_16b_main.yaml",
    "snippets/manifests/scalar_misalign_store_cross_16b_main.yaml",
    "snippets/manifests/scalar_misalign_store_load_overlap_main.yaml",
    "suites/scalar_misalign_load_in_16b_poc.yaml",
    "suites/scalar_misalign_load_cross_16b_poc.yaml",
    "suites/scalar_misalign_store_in_16b_poc.yaml",
    "suites/scalar_misalign_store_cross_16b_poc.yaml",
    "suites/scalar_misalign_store_load_overlap_poc.yaml",
]

NEXUS_CPUTEST_PORT_FILES = [
    "snippets/programs/nexus_cputest_unalign_main.c",
    "snippets/programs/nexus_cputest_load_store_main.c",
    "snippets/manifests/nexus_cputest_unalign_main.yaml",
    "snippets/manifests/nexus_cputest_load_store_main.yaml",
    "suites/nexus_cputest_unalign_poc.yaml",
    "suites/nexus_cputest_load_store_poc.yaml",
]

NEXUS_MEMSCAN_PORT_FILES = [
    "snippets/programs/nexus_memscan_access_fault_main.c",
    "snippets/programs/nexus_memscan_fetch_fault_main.c",
    "snippets/programs/nexus_memscan_hugepage_access_fault_main.c",
    "snippets/programs/nexus_memscan_hugepage_atom_fault_main.c",
    "snippets/programs/nexus_memscan_hugepage_main.c",
    "snippets/programs/nexus_memscan_page_fault_main.c",
    "snippets/manifests/nexus_memscan_access_fault_main.yaml",
    "snippets/manifests/nexus_memscan_fetch_fault_main.yaml",
    "snippets/manifests/nexus_memscan_hugepage_access_fault_main.yaml",
    "snippets/manifests/nexus_memscan_hugepage_atom_fault_main.yaml",
    "snippets/manifests/nexus_memscan_hugepage_main.yaml",
    "snippets/manifests/nexus_memscan_page_fault_main.yaml",
    "suites/nexus_memscan_access_fault_poc.yaml",
    "suites/nexus_memscan_fetch_fault_poc.yaml",
    "suites/nexus_memscan_hugepage_access_fault_poc.yaml",
    "suites/nexus_memscan_hugepage_atom_fault_poc.yaml",
    "suites/nexus_memscan_hugepage_poc.yaml",
    "suites/nexus_memscan_page_fault_poc.yaml",
]

SCALAR_MISALIGN_PHASE2_W1_FILES = [
    "snippets/include/xs_scalar_misalign.h",
    "snippets/scalar_misalign/load_split_templates.c",
    "snippets/scalar_misalign/check_load_split_templates.c",
    "snippets/scalar_misalign/store_split_templates.c",
    "snippets/scalar_misalign/check_store_split_templates.c",
    "snippets/scalar_misalign/cross_page_faults.c",
    "snippets/scalar_misalign/check_cross_page_faults.c",
    "snippets/manifests/load_split_templates.yaml",
    "snippets/manifests/check_load_split_templates.yaml",
    "snippets/manifests/store_split_templates.yaml",
    "snippets/manifests/check_store_split_templates.yaml",
    "snippets/manifests/cross_page_faults.yaml",
    "snippets/manifests/check_cross_page_faults.yaml",
    "suites/scalar_misalign_load_split_templates_poc.yaml",
    "suites/scalar_misalign_store_split_templates_poc.yaml",
    "suites/scalar_misalign_cross_page_faults_poc.yaml",
]

SCALAR_MISALIGN_PHASE2_W2_FILES = [
    "snippets/scalar_misalign/store_forward_overlap.c",
    "snippets/scalar_misalign/check_store_forward_overlap.c",
    "snippets/manifests/store_forward_overlap.yaml",
    "snippets/manifests/check_store_forward_overlap.yaml",
    "suites/scalar_misalign_store_forward_overlap_poc.yaml",
]

SCALAR_MISALIGN_PHASE3_FILES = [
    "snippets/scalar_misalign/store_forward_search.c",
    "snippets/scalar_misalign/check_store_forward_search.c",
    "snippets/scalar_misalign/cross_page_fault_search.c",
    "snippets/scalar_misalign/check_cross_page_fault_search.c",
    "snippets/scalar_misalign/replay_probe.c",
    "snippets/scalar_misalign/check_replay_probe.c",
    "snippets/manifests/store_forward_search.yaml",
    "snippets/manifests/check_store_forward_search.yaml",
    "snippets/manifests/cross_page_fault_search.yaml",
    "snippets/manifests/check_cross_page_fault_search.yaml",
    "snippets/manifests/replay_probe.yaml",
    "snippets/manifests/check_replay_probe.yaml",
    "suites/scalar_misalign_store_forward_search_poc.yaml",
    "suites/scalar_misalign_cross_page_fault_search_poc.yaml",
    "suites/scalar_misalign_replay_probe_poc.yaml",
]

SCALAR_MISALIGN_FAMILY_COMBO_FILES = [
    "suites/scalar_misalign_templates_combo_poc.yaml",
    "suites/scalar_misalign_fault_forward_combo_poc.yaml",
    "suites/scalar_misalign_family_combo_poc.yaml",
]

DEFERRED_CHECK_FILES = [
    "snippets/deferred_check/deferred_mark_stage_a.c",
    "snippets/deferred_check/deferred_mark_stage_b.c",
    "snippets/manifests/deferred_mark_stage_a.yaml",
    "snippets/manifests/deferred_mark_stage_b.yaml",
    "suites/deferred_check_markers_poc.yaml",
]


class SnippetLoadingTest(unittest.TestCase):
    def test_round2_files_exist(self) -> None:
        for relative_path in ROUND2_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_vsetvl_path_files_exist(self) -> None:
        for relative_path in VSETVL_PATH_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_vsetvl_search_files_exist(self) -> None:
        for relative_path in VSETVL_SEARCH_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_interrupt_response_files_exist(self) -> None:
        for relative_path in INTERRUPT_RESPONSE_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_split_store_forward_files_exist(self) -> None:
        for relative_path in SPLIT_STORE_FORWARD_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_example_files_exist(self) -> None:
        for relative_path in EXAMPLE_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_prefetchw_tl_denied_fault_files_exist(self) -> None:
        for relative_path in PREFETCHW_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_am_program_files_exist(self) -> None:
        for relative_path in AM_PROGRAM_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_am_timer_program_files_exist(self) -> None:
        for relative_path in AM_TIMER_PROGRAM_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_scalar_misalign_phase1_files_exist(self) -> None:
        for relative_path in SCALAR_MISALIGN_PHASE1_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_nexus_cputest_port_files_exist(self) -> None:
        for relative_path in NEXUS_CPUTEST_PORT_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_nexus_memscan_port_files_exist(self) -> None:
        for relative_path in NEXUS_MEMSCAN_PORT_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_scalar_misalign_phase2_wave1_files_exist(self) -> None:
        for relative_path in SCALAR_MISALIGN_PHASE2_W1_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_scalar_misalign_phase2_wave2_files_exist(self) -> None:
        for relative_path in SCALAR_MISALIGN_PHASE2_W2_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_scalar_misalign_phase3_files_exist(self) -> None:
        for relative_path in SCALAR_MISALIGN_PHASE3_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_scalar_misalign_family_combo_files_exist(self) -> None:
        for relative_path in SCALAR_MISALIGN_FAMILY_COMBO_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_deferred_check_files_exist(self) -> None:
        for relative_path in DEFERRED_CHECK_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_prefetchw_default_target_addr_stays_outside_default_ram_window(self) -> None:
        header_text = (ROOT / "snippets/include/xs_prefetchw.h").read_text()
        self.assertIn("#define XS_PREFETCHW_TARGET_ADDR", header_text)
        target_match = re.search(r"XS_PREFETCHW_TARGET_ADDR \(\(uint64_t\) 0x([0-9a-fA-F]+)ull\)", header_text)
        self.assertIsNotNone(target_match)
        target = int(target_match.group(1), 16)
        self.assertFalse(0x80000000 <= target < 0xC0000000)

    def test_prefetchw_source_uses_raw_encoding_for_default_toolchain(self) -> None:
        source_text = (ROOT / "snippets/cbo/prefetchw_tl_denied_fault.c").read_text()

        self.assertIn(".word 0x0037e013", source_text)
        self.assertNotIn('__asm__ volatile("prefetch.w', source_text)

    def test_prefetchw_minimal_case_has_no_probe_loop_controls(self) -> None:
        header_text = (ROOT / "snippets/include/xs_prefetchw.h").read_text()
        self.assertNotIn("XS_PREFETCHW_PROBE_ROUNDS", header_text)
        self.assertNotIn("XS_PREFETCHW_ISSUES_PER_ROUND", header_text)

    def test_prefetchw_run_bad_traps_immediately_on_wrong_trap_shape(self) -> None:
        source_text = (ROOT / "snippets/cbo/prefetchw_tl_denied_fault.c").read_text()
        self.assertIn("XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_LOAD_NO_TRAP);", source_text)
        self.assertIn("XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_LOAD_BAD_TRAP);", source_text)
        self.assertIn("XSRT_BAD_TRAP(XS_PREFETCHW_FAIL_PREFETCH_TRAP);", source_text)

    def test_prefetchw_trap_handler_advances_epc_by_instruction_length(self) -> None:
        source_text = (ROOT / "snippets/cbo/prefetchw_tl_denied_fault.c").read_text()

        self.assertIn("static uint64_t prefetchw_trap_insn_len(uint64_t epc)", source_text)
        self.assertIn("const uint16_t insn_lo", source_text)
        self.assertIn('((insn_lo & 0x3u) == 0x3u) ? 4u : 2u', source_text)
        self.assertIn("frame->epc += prefetchw_trap_insn_len(frame->epc);", source_text)
        self.assertNotIn("frame->epc += 4u;", source_text)

    def test_snippet_sources_compile(self) -> None:
        snippet_sources = [
            "snippets/core/init_basic_env.c",
            "snippets/core/finish_check.c",
            "snippets/scalar_load_legality/arm_timer.c",
            "snippets/scalar_load_legality/unaligned_load.c",
            "snippets/scalar_load_legality/check_scalar_load_legality.c",
            "snippets/vector_interrupt/vsetvl_interrupt_path.c",
            "snippets/vector_interrupt/check_vsetvl_interrupt_path.c",
            "snippets/vector_interrupt/vsetvl_interrupt_search.c",
            "snippets/vector_interrupt/check_vsetvl_interrupt_search.c",
            "snippets/interrupt/interrupt_response_wait.c",
            "snippets/interrupt/check_interrupt_response.c",
            "snippets/store_forward/misaligned_split_store_search.c",
            "snippets/store_forward/check_misaligned_split_store_search.c",
            "snippets/deferred_check/deferred_mark_stage_a.c",
            "snippets/deferred_check/deferred_mark_stage_b.c",
            "snippets/examples/demo_mark_flag.c",
            "snippets/examples/check_demo_mark_flag.c",
            "snippets/cbo/prefetchw_tl_denied_fault.c",
            "snippets/cbo/check_prefetchw_tl_denied_fault.c",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            toolchain = importlib.import_module("generator.xsgen.toolchain")
            gcc = toolchain.detect_toolchain()["gcc"]
            for relative_path in snippet_sources:
                src_path = ROOT / relative_path
                out_path = Path(tmpdir) / (src_path.stem + ".o")
                result = subprocess.run(
                    [
                        gcc,
                        "-std=c11",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        *toolchain.riscv_compile_flags(),
                        "-I",
                        str(ROOT / "runtime/include"),
                        "-I",
                        str(ROOT / "snippets/include"),
                        "-c",
                        str(src_path),
                        "-o",
                        str(out_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_prefetchw_sources_compile(self) -> None:
        snippet_sources = [
            "snippets/cbo/prefetchw_tl_denied_fault.c",
            "snippets/cbo/check_prefetchw_tl_denied_fault.c",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            toolchain = importlib.import_module("generator.xsgen.toolchain")
            gcc = toolchain.detect_toolchain()["gcc"]
            for relative_path in snippet_sources:
                src_path = ROOT / relative_path
                out_path = Path(tmpdir) / (src_path.stem + ".o")
                result = subprocess.run(
                    [
                        gcc,
                        "-std=c11",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        "-O2",
                        "-march=rv64gc",
                        "-mabi=lp64d",
                        "-mcmodel=medany",
                        "-ffreestanding",
                        "-fno-asynchronous-unwind-tables",
                        "-fno-builtin",
                        "-fno-stack-protector",
                        "-fno-tree-vectorize",
                        "-fno-tree-slp-vectorize",
                        "-I",
                        str(ROOT / "runtime/include"),
                        "-I",
                        str(ROOT / "snippets/include"),
                        "-c",
                        str(src_path),
                        "-o",
                        str(out_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_prefetchw_sources_compile_without_zicbop_mnemonic_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            toolchain = importlib.import_module("generator.xsgen.toolchain")
            gcc = toolchain.detect_toolchain()["gcc"]
            src_path = ROOT / "snippets/cbo/prefetchw_tl_denied_fault.c"
            out_path = Path(tmpdir) / "prefetchw_tl_denied_fault.o"
            result = subprocess.run(
                [
                    gcc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-O2",
                    "-march=rv64gc",
                    "-mabi=lp64d",
                    "-mcmodel=medany",
                    "-ffreestanding",
                    "-fno-asynchronous-unwind-tables",
                    "-fno-builtin",
                    "-fno-stack-protector",
                    "-fno-tree-vectorize",
                    "-fno-tree-slp-vectorize",
                    "-I",
                    str(ROOT / "runtime/include"),
                    "-I",
                    str(ROOT / "snippets/include"),
                    "-c",
                    str(src_path),
                    "-o",
                    str(out_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_deferred_check_sources_compile(self) -> None:
        snippet_sources = [
            "snippets/deferred_check/deferred_mark_stage_a.c",
            "snippets/deferred_check/deferred_mark_stage_b.c",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            toolchain = importlib.import_module("generator.xsgen.toolchain")
            gcc = toolchain.detect_toolchain()["gcc"]
            for relative_path in snippet_sources:
                src_path = ROOT / relative_path
                out_path = Path(tmpdir) / (src_path.stem + ".o")
                result = subprocess.run(
                    [
                        gcc,
                        "-std=c11",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        *toolchain.riscv_compile_flags(),
                        "-I",
                        str(ROOT / "runtime/include"),
                        "-I",
                        str(ROOT / "snippets/include"),
                        "-c",
                        str(src_path),
                        "-o",
                        str(out_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_real_manifest_db_and_suite_produce_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db_first = snippet_db.load_snippet_db(ROOT)
        db_second = snippet_db.load_snippet_db(ROOT)
        self.assertEqual(sorted(db_first.keys()), sorted(db_second.keys()))

        suite = suite_loader.load_suite(ROOT / "suites/scalar_load_legality_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db_first)
        plan_second = suite_loader.build_compose_plan(suite, db_second)

        self.assertEqual(
            ("init_basic_env", "arm_timer", "unaligned_load", "check_scalar_load_legality", "finish_check"),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_vsetvl_path_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/vsetvl_interrupt_path_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "arm_timer",
                "vsetvl_interrupt_path",
                "check_vsetvl_interrupt_path",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_vsetvl_search_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/vsetvl_interrupt_search_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "vsetvl_interrupt_search",
                "check_vsetvl_interrupt_search",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_interrupt_response_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/interrupt_response_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "arm_timer",
                "interrupt_response_wait",
                "check_interrupt_response",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_split_store_forward_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/misaligned_split_store_search_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "misaligned_split_store_search",
                "check_misaligned_split_store_search",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_load_split_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_load_split_templates_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "load_split_templates",
                "check_load_split_templates",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_store_split_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_store_split_templates_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "store_split_templates",
                "check_store_split_templates",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_cross_page_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_cross_page_faults_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "cross_page_faults",
                "check_cross_page_faults",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_store_forward_overlap_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_store_forward_overlap_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "store_forward_overlap",
                "check_store_forward_overlap",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_store_forward_search_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_store_forward_search_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "store_forward_search",
                "check_store_forward_search",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_cross_page_fault_search_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_cross_page_fault_search_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "cross_page_fault_search",
                "check_cross_page_fault_search",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_replay_probe_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_replay_probe_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "replay_probe",
                "check_replay_probe",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_templates_combo_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_templates_combo_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            ("init_basic_env", "load_split_templates", "store_split_templates"),
            plan_first.run_snippet_ids,
        )
        self.assertEqual(
            ("check_load_split_templates", "check_store_split_templates", "finish_check"),
            plan_first.check_snippet_ids,
        )
        self.assertEqual(
            (
                "init_basic_env",
                "load_split_templates",
                "store_split_templates",
                "check_load_split_templates",
                "check_store_split_templates",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_fault_forward_combo_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_fault_forward_combo_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            ("init_basic_env", "store_forward_overlap", "cross_page_faults"),
            plan_first.run_snippet_ids,
        )
        self.assertEqual(
            ("check_store_forward_overlap", "check_cross_page_faults", "finish_check"),
            plan_first.check_snippet_ids,
        )
        self.assertEqual(
            (
                "init_basic_env",
                "store_forward_overlap",
                "cross_page_faults",
                "check_store_forward_overlap",
                "check_cross_page_faults",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_scalar_misalign_family_combo_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/scalar_misalign_family_combo_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "load_split_templates",
                "store_split_templates",
                "store_forward_overlap",
                "cross_page_faults",
            ),
            plan_first.run_snippet_ids,
        )
        self.assertEqual(
            (
                "check_load_split_templates",
                "check_store_split_templates",
                "check_store_forward_overlap",
                "check_cross_page_faults",
                "finish_check",
            ),
            plan_first.check_snippet_ids,
        )
        self.assertEqual(
            (
                "init_basic_env",
                "load_split_templates",
                "store_split_templates",
                "store_forward_overlap",
                "cross_page_faults",
                "check_load_split_templates",
                "check_store_split_templates",
                "check_store_forward_overlap",
                "check_cross_page_faults",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_deferred_check_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/deferred_check_markers_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            ("init_basic_env", "deferred_mark_stage_a", "deferred_mark_stage_b"),
            plan_first.run_snippet_ids,
        )
        self.assertEqual(
            ("deferred_mark_stage_a", "deferred_mark_stage_b", "finish_check"),
            plan_first.check_snippet_ids,
        )
        self.assertEqual(
            ("init_basic_env", "deferred_mark_stage_a", "deferred_mark_stage_b", "finish_check"),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_demo_mark_flag_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/demo_mark_flag_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "demo_mark_flag",
                "check_demo_mark_flag",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_prefetchw_tl_denied_fault_suite_produces_deterministic_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)
        suite = suite_loader.load_suite(ROOT / "suites/prefetchw_tl_denied_fault_poc.yaml")
        plan_first = suite_loader.build_compose_plan(suite, db)
        plan_second = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            (
                "init_basic_env",
                "prefetchw_tl_denied_fault",
                "check_prefetchw_tl_denied_fault",
                "finish_check",
            ),
            plan_first.snippet_ids,
        )
        self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)

    def test_manifest_loader_rejects_missing_fields_and_stream_kind(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            source_path = tmp_root / "demo.c"
            source_path.write_text("int demo(void) { return 0; }\n")

            missing_fields_manifest = tmp_root / "missing.yaml"
            missing_fields_manifest.write_text(
                textwrap.dedent(
                    """
                    id: demo
                    kind: proc
                    """
                ).strip()
            )

            stream_manifest = tmp_root / "stream.yaml"
            stream_manifest.write_text(
                textwrap.dedent(
                    """
                    id: demo
                    kind: stream
                    lang: c
                    sources:
                      - demo.c
                    """
                ).strip()
            )

            with self.assertRaises(ValueError):
                snippet_db.load_manifest(missing_fields_manifest, tmp_root)

            with self.assertRaisesRegex(ValueError, "not implemented in ELF-first PoC"):
                snippet_db.load_manifest(stream_manifest, tmp_root)

    def test_manifest_loader_accepts_am_program_with_main_entry(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            source_path = tmp_root / "demo_main.c"
            source_path.write_text("int main(void) { return 0; }\n")

            manifest_path = tmp_root / "demo_program.yaml"
            manifest_path.write_text(
                textwrap.dedent(
                    """
                    id: demo_program
                    kind: am_program
                    lang: c
                    entry: main
                    sources:
                      - demo_main.c
                    """
                ).strip()
            )

            snippet = snippet_db.load_manifest(manifest_path, tmp_root)

            self.assertEqual("demo_program", snippet.id)
            self.assertEqual("am_program", snippet.kind)
            self.assertEqual("c", snippet.lang)
            self.assertEqual("main", snippet.entry)
            self.assertEqual((source_path.resolve(),), snippet.sources)

    def test_manifest_loader_rejects_unsupported_lang(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            source_path = tmp_root / "demo.c"
            source_path.write_text("int demo(void) { return 0; }\n")

            bad_lang_manifest = tmp_root / "bad_lang.yaml"
            bad_lang_manifest.write_text(
                textwrap.dedent(
                    """
                    id: demo
                    kind: proc
                    lang: rust
                    sources:
                      - demo.c
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "unsupported snippet language"):
                snippet_db.load_manifest(bad_lang_manifest, tmp_root)

    def test_manifest_loader_rejects_invalid_snippet_id(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            source_path = tmp_root / "demo.c"
            source_path.write_text("int demo(void) { return 0; }\n")

            bad_id_manifest = tmp_root / "bad_id.yaml"
            bad_id_manifest.write_text(
                textwrap.dedent(
                    """
                    id: bad-id
                    kind: proc
                    lang: c
                    sources:
                      - demo.c
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "invalid snippet id"):
                snippet_db.load_manifest(bad_id_manifest, tmp_root)

    def test_suite_loader_rejects_future_only_modes_and_unknown_snippets(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            future_mode_suite = tmp_root / "future.yaml"
            future_mode_suite.write_text(
                textwrap.dedent(
                    """
                    suite: bad_future
                    target: xiangshan-verilator
                    seed: 1
                    compose:
                      mode: weighted-mix
                      snippets:
                        - init_basic_env
                    """
                ).strip()
            )
            with self.assertRaises(ValueError):
                suite_loader.load_suite(future_mode_suite)
            with self.assertRaisesRegex(ValueError, "future-only"):
                suite_loader.load_suite(future_mode_suite)

            real_db = snippet_db.load_snippet_db(ROOT)
            unknown_snippet_suite = tmp_root / "unknown.yaml"
            unknown_snippet_suite.write_text(
                textwrap.dedent(
                    """
                    suite: unknown_snippet
                    target: xiangshan-verilator
                    seed: 2
                    compose:
                      mode: sequence
                      snippets:
                        - does_not_exist
                    """
                ).strip()
            )
            suite = suite_loader.load_suite(unknown_snippet_suite)
            with self.assertRaises(ValueError):
                suite_loader.build_compose_plan(suite, real_db)

    def test_suite_loader_rejects_unsupported_target(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_target_suite = Path(tmpdir) / "bad_target.yaml"
            bad_target_suite.write_text(
                textwrap.dedent(
                    """
                    suite: bad_target
                    target: totally-unsupported
                    seed: 3
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "unsupported target"):
                suite_loader.load_suite(bad_target_suite)

    def test_suite_loader_rejects_invalid_suite_name(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_suite_name = Path(tmpdir) / "bad_suite_name.yaml"
            bad_suite_name.write_text(
                textwrap.dedent(
                    """
                    suite: ../escaped_out
                    target: xiangshan-verilator
                    seed: 4
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "invalid suite name"):
                suite_loader.load_suite(bad_suite_name)

    def test_suite_loader_rejects_non_integer_or_negative_seed(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            cases = {
                "negative": "-1",
                "float": "1.5",
                "boolean": "true",
            }
            for name, raw_seed in cases.items():
                suite_path = tmp_root / f"{name}.yaml"
                suite_path.write_text(
                    textwrap.dedent(
                        f"""
                        suite: {name}
                        target: xiangshan-verilator
                        seed: {raw_seed}
                        compose:
                          mode: sequence
                          snippets:
                            - init_basic_env
                        """
                    ).strip()
                )
                with self.subTest(seed_case=name):
                    with self.assertRaisesRegex(ValueError, "invalid seed"):
                        suite_loader.load_suite(suite_path)

    def test_suite_loader_accepts_deferred_check_schema(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "deferred.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: deferred_suite
                    target: xiangshan-verilator
                    seed: 9
                    compose:
                      mode: sequence
                      run_snippets:
                        - init_basic_env
                        - arm_timer
                        - unaligned_load
                      check_snippets:
                        - unaligned_load
                        - finish_check
                    """
                ).strip()
            )

            suite = suite_loader.load_suite(suite_path)

        self.assertEqual(
            ("init_basic_env", "arm_timer", "unaligned_load"),
            suite.run_snippet_ids,
        )
        self.assertEqual(
            ("unaligned_load", "finish_check"),
            suite.check_snippet_ids,
        )
        self.assertEqual(
            ("init_basic_env", "arm_timer", "unaligned_load", "finish_check"),
            suite.snippet_ids,
        )

    def test_suite_loader_rejects_mixed_legacy_and_deferred_schema(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "mixed.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: mixed_suite
                    target: xiangshan-verilator
                    seed: 9
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                      run_snippets:
                        - arm_timer
                      check_snippets:
                        - finish_check
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "cannot mix"):
                suite_loader.load_suite(suite_path)

    def test_suite_loader_rejects_mixed_schema_when_other_side_is_yaml_null(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            cases = {
                "legacy_null_with_deferred": """
                    suite: mixed_null_legacy
                    target: xiangshan-verilator
                    seed: 9
                    compose:
                      mode: sequence
                      snippets: null
                      run_snippets:
                        - init_basic_env
                      check_snippets:
                        - finish_check
                """,
                "deferred_null_with_legacy": """
                    suite: mixed_null_deferred
                    target: xiangshan-verilator
                    seed: 9
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                      run_snippets: null
                      check_snippets:
                        - finish_check
                """,
            }

            for name, raw_yaml in cases.items():
                suite_path = tmp_root / f"{name}.yaml"
                suite_path.write_text(textwrap.dedent(raw_yaml).strip())
                with self.subTest(case=name):
                    with self.assertRaisesRegex(ValueError, "cannot mix"):
                        suite_loader.load_suite(suite_path)

    def test_build_compose_plan_preserves_deferred_phase_order(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db = snippet_db.load_snippet_db(ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "deferred_plan.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: deferred_plan
                    target: xiangshan-verilator
                    seed: 11
                    compose:
                      mode: sequence
                      run_snippets:
                        - init_basic_env
                        - arm_timer
                        - unaligned_load
                      check_snippets:
                        - unaligned_load
                        - arm_timer
                        - finish_check
                    """
                ).strip()
            )

            suite = suite_loader.load_suite(suite_path)

        plan = suite_loader.build_compose_plan(suite, db)

        self.assertEqual(
            ("init_basic_env", "arm_timer", "unaligned_load"),
            plan.run_snippet_ids,
        )
        self.assertEqual(
            ("unaligned_load", "arm_timer", "finish_check"),
            plan.check_snippet_ids,
        )
        self.assertEqual(
            ("init_basic_env", "arm_timer", "unaligned_load", "finish_check"),
            plan.snippet_ids,
        )

    def test_cli_dump_plan_and_list_snippets(self) -> None:
        list_result = subprocess.run(
            ["python3", "generator/cli.py", "list-snippets"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, list_result.returncode, msg=list_result.stderr)
        self.assertIn("init_basic_env", list_result.stdout)
        self.assertIn("finish_check", list_result.stdout)

        dump_result = subprocess.run(
            ["python3", "generator/cli.py", "dump-plan", "suites/scalar_load_legality_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, dump_result.returncode, msg=dump_result.stderr)
        plan = json.loads(dump_result.stdout)
        self.assertEqual("scalar_load_legality_poc", plan["suite"])
        self.assertEqual(
            ["init_basic_env", "arm_timer", "unaligned_load", "check_scalar_load_legality", "finish_check"],
            plan["snippet_ids"],
        )
        self.assertTrue(plan["artifacts"]["build_dir"].endswith("build/scalar_load_legality_poc"))
        self.assertTrue(plan["artifacts"]["generated_suite"].endswith("build/scalar_load_legality_poc/generated_suite.c"))
        self.assertTrue(plan["artifacts"]["elf"].endswith("build/scalar_load_legality_poc/test.elf"))
        self.assertTrue(plan["artifacts"]["bin"].endswith("build/scalar_load_legality_poc/test.bin"))
        self.assertTrue(plan["artifacts"]["build_manifest"].endswith("build/scalar_load_legality_poc/build_manifest.json"))

    def test_mmu_suite_loads_rule_metadata_and_dump_plan(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        suite = suite_loader.load_suite(ROOT / "suites/mmu_pilot_rules_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))

        self.assertEqual(
            ("bare_identity", "sv39_alias", "superpage", "sfence_remap", "load_page_fault", "two_stage_fault"),
            plan.mmu_rule_ids,
        )
        self.assertIn("requestor.hlv", plan.mmu_coverage_tags)
        self.assertTrue(str(plan.mmu_rule_dir).endswith("snippets/mmu_rules/pilot"))

        dump_result = subprocess.run(
            ["python3", "generator/cli.py", "dump-plan", "suites/mmu_pilot_rules_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, dump_result.returncode, msg=dump_result.stderr)
        payload = json.loads(dump_result.stdout)
        self.assertEqual("mmu_pilot_rules_poc", payload["suite"])
        self.assertEqual(list(plan.mmu_rule_ids), payload["mmu"]["resolved_rule_ids"])
        self.assertTrue(
            payload["artifacts"]["generated_mmu_source"].endswith(
                "build/mmu_pilot_rules_poc/generated_mmu_rule.c"
            )
        )

    def test_suite_loader_rejects_mmu_metadata_without_mmu_runner(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "mmu_without_runner.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    f"""
                    suite: mmu_without_runner
                    target: xiangshan-verilator
                    seed: 17
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                        - finish_check
                      mmu:
                        rule_dir: {ROOT / "snippets" / "mmu_rules" / "pilot"}
                        rule_ids:
                          - bare_identity
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "compose.mmu requires mmu_rule_runner_main"):
                suite_loader.load_suite(suite_path)

    def test_mmu_subset_suite_coverage_tags_follow_selected_rules_only(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        suite = suite_loader.load_suite(ROOT / "suites/mmu_bare_identity_poc.yaml")
        plan = suite_loader.build_compose_plan(suite, snippet_db.load_snippet_db(ROOT))

        self.assertEqual(("bare_identity",), plan.mmu_rule_ids)
        self.assertEqual(("mode.bare", "page.identity", "requestor.load"), plan.mmu_coverage_tags)

        dump_result = subprocess.run(
            ["python3", "generator/cli.py", "dump-plan", "suites/mmu_bare_identity_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, dump_result.returncode, msg=dump_result.stderr)
        payload = json.loads(dump_result.stdout)
        self.assertEqual(["bare_identity"], payload["mmu"]["resolved_rule_ids"])
        self.assertEqual(["mode.bare", "page.identity", "requestor.load"], payload["mmu"]["coverage_tags"])
        self.assertNotIn("guest.two_stage", payload["mmu"]["coverage_tags"])
        self.assertNotIn("requestor.hlv", payload["mmu"]["coverage_tags"])

    def test_cli_lists_built_in_suite_pools(self) -> None:
        result = subprocess.run(
            ["python3", "generator/cli.py", "list-suite-pools"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertIn("scalar_misalign_full", result.stdout)

    def test_generate_suites_writes_deferred_suite_files_and_batch_index(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_root) as tmpdir:
            output_dir = Path(tmpdir) / "generated"
            relative_output_dir = output_dir.relative_to(ROOT)
            result = subprocess.run(
                [
                    "python3",
                    "generator/cli.py",
                    "generate-suites",
                    "--pool",
                    "scalar_misalign_full",
                    "--count",
                    "2",
                    "--seed",
                    "20260421",
                    "--prefix",
                    "scalar_misalign_full_rand",
                    "--output-dir",
                    str(relative_output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

            index_path = Path(result.stdout.strip())
            self.assertTrue(index_path.is_file())

            payload = json.loads(index_path.read_text())
            self.assertEqual("scalar_misalign_full", payload["pool"])
            self.assertEqual(2, payload["suite_count"])
            self.assertEqual(5, payload["run_count"])
            self.assertEqual(2, len(payload["suites"]))
            self.assertEqual(str(output_dir.resolve()), str((ROOT / payload["output_dir"]).resolve()))

            db = snippet_db.load_snippet_db(ROOT)
            valid_run_ids = {
                "load_split_templates",
                "store_split_templates",
                "store_forward_overlap",
                "cross_page_faults",
                "store_forward_search",
                "cross_page_fault_search",
            }
            valid_check_ids = {
                "check_load_split_templates",
                "check_store_split_templates",
                "check_store_forward_overlap",
                "check_cross_page_faults",
                "check_store_forward_search",
                "check_cross_page_fault_search",
            }

            for index, suite_entry in enumerate(payload["suites"]):
                suite_path = Path(suite_entry["path"])
                if not suite_path.is_absolute():
                    suite_path = ROOT / suite_path
                self.assertTrue(suite_path.is_file())
                suite = suite_loader.load_suite(suite_path)
                plan = suite_loader.build_compose_plan(suite, db)
                self.assertEqual(f"scalar_misalign_full_rand_{index:03d}", suite.name)
                self.assertEqual("init_basic_env", plan.run_snippet_ids[0])
                self.assertEqual("finish_check", plan.check_snippet_ids[-1])
                self.assertEqual(6, len(plan.run_snippet_ids))
                self.assertEqual(6, len(plan.check_snippet_ids))
                self.assertEqual(5, len(set(plan.run_snippet_ids[1:])))
                self.assertEqual(5, len(set(plan.check_snippet_ids[:-1])))
                self.assertTrue(set(plan.run_snippet_ids[1:]).issubset(valid_run_ids))
                self.assertTrue(set(plan.check_snippet_ids[:-1]).issubset(valid_check_ids))
                self.assertGreater(len(plan.run_snippet_ids) + len(plan.check_snippet_ids), 10)

    def test_generate_suites_reports_clean_validation_error(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "generator/cli.py",
                "generate-suites",
                "--pool",
                "scalar_misalign_full",
                "--count",
                "0",
                "--run-count",
                "99",
                "--seed",
                "7",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("suite_count must be positive", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_generate_suites_rejects_too_small_run_count_for_scalar_misalign_full(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "generator/cli.py",
                "generate-suites",
                "--pool",
                "scalar_misalign_full",
                "--count",
                "1",
                "--run-count",
                "4",
                "--seed",
                "7",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("run_count 4 is below minimum 5", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_generate_suites_allows_run_count_above_unique_pool_size_by_repeating_pool(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "generator/cli.py",
                "generate-suites",
                "--pool",
                "scalar_misalign_full",
                "--count",
                "1",
                "--run-count",
                "7",
                "--seed",
                "7",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, msg=result.stderr)
        index_path = Path(result.stdout.strip())
        payload = json.loads(index_path.read_text())
        suite_path = ROOT / payload["suites"][0]["path"]
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        plan = suite_loader.build_compose_plan(
            suite_loader.load_suite(suite_path),
            snippet_db.load_snippet_db(ROOT),
        )

        self.assertEqual(8, len(plan.run_snippet_ids))
        self.assertEqual(7, len(plan.run_snippet_ids[1:]))
        self.assertLess(len(set(plan.run_snippet_ids[1:])), len(plan.run_snippet_ids[1:]))

    def test_generate_suites_rejects_invalid_prefix_without_traceback(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "generator/cli.py",
                "generate-suites",
                "--pool",
                "scalar_misalign_full",
                "--count",
                "1",
                "--run-count",
                "5",
                "--seed",
                "7",
                "--prefix",
                "../escape",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid suite prefix", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_generate_suites_rejects_output_dir_outside_repo_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as outside_dir:
            result = subprocess.run(
                [
                    "python3",
                    "generator/cli.py",
                    "generate-suites",
                    "--pool",
                    "scalar_misalign_full",
                    "--count",
                    "1",
                    "--run-count",
                    "5",
                    "--seed",
                    "7",
                    "--prefix",
                    "outsidecheck",
                    "--output-dir",
                    outside_dir,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("output_dir must stay within repo", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_generate_suites_resolves_relative_output_dir_from_repo_root_even_outside_cwd(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_root) as tmpdir:
            output_dir = Path(tmpdir) / "generated"
            relative_output_dir = output_dir.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as outside_cwd:
                result = subprocess.run(
                    [
                        "python3",
                        str(ROOT / "generator/cli.py"),
                        "generate-suites",
                        "--pool",
                        "scalar_misalign_full",
                        "--count",
                        "1",
                        "--run-count",
                        "5",
                        "--seed",
                        "20260421",
                        "--prefix",
                        "cwdcheck",
                        "--output-dir",
                        str(relative_output_dir),
                    ],
                    cwd=outside_cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                )

            self.assertEqual(0, result.returncode, msg=result.stderr)
            index_path = Path(result.stdout.strip())
            self.assertEqual(str((output_dir / "cwdcheck_batch.json").resolve()), str(index_path.resolve()))

            payload = json.loads(index_path.read_text())
            self.assertEqual(str(output_dir.resolve()), str((ROOT / payload["output_dir"]).resolve()))

    def test_generate_suites_reports_output_dir_write_failure_without_traceback(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_root) as tmpdir:
            output_file = Path(tmpdir) / "occupied"
            output_file.write_text("occupied\n")
            result = subprocess.run(
                [
                    "python3",
                    "generator/cli.py",
                    "generate-suites",
                    "--pool",
                    "scalar_misalign_full",
                    "--count",
                    "1",
                    "--run-count",
                    "5",
                    "--seed",
                    "7",
                    "--prefix",
                    "writefail",
                    "--output-dir",
                    str(output_file.relative_to(ROOT)),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("File exists", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unaligned_load_riscv_path_uses_real_word_load(self) -> None:
        source = (ROOT / "snippets/scalar_load_legality/unaligned_load.c").read_text()
        self.assertIn('"lw %0, 0(%1)"', source)

    def test_vsetvl_search_source_arms_periodic_timer_before_dense_loop(self) -> None:
        source = (ROOT / "snippets/vector_interrupt/vsetvl_interrupt_search.c").read_text()
        helper = (ROOT / "snippets/include/xs_vsetvl_interrupt_path.h").read_text()

        self.assertEqual(1, source.count("xsrt_enable_stimer();"))
        self.assertEqual(1, source.count("xsrt_timer_arm_periodic_delta("))
        self.assertIn("#define XS_VSETVL_X1()", source)
        self.assertIn("#define XS_VSETVL_X2()", source)
        self.assertIn("#define XS_VSETVL_X4()", source)
        self.assertIn("#define XS_VSETVL_X8()", source)
        self.assertIn("XS_VSETVL_X8();", source)
        self.assertIn("xs_vsetvl_emit_zero_zero_zero()", source)
        self.assertIn("0x80007057", helper)
        self.assertIn('iterations = 256u + (unsigned long) ((env->seed >> 4) & 0x7fu);', source)
        self.assertIn('xsrt_timer_arm_periodic_delta(8u + (uint64_t) ((env->seed >> 13) & 0x7u));', source)
        self.assertNotIn("__riscv", source)

    def test_vsetvl_path_source_uses_raw_vsetvl_helper_without_local_arch_toggle(self) -> None:
        source = (ROOT / "snippets/vector_interrupt/vsetvl_interrupt_path.c").read_text()
        helper = (ROOT / "snippets/include/xs_vsetvl_interrupt_path.h").read_text()

        self.assertIn("xs_vsetvl_emit_zero_zero_zero();", source)
        self.assertIn("vsetvl zero, zero, zero", helper)
        self.assertIn(".word 0x80007057", helper)
        self.assertNotIn("__riscv", source)

    def test_runtime_entry_source_sets_fs_and_vs(self) -> None:
        source = (ROOT / "runtime/arch/riscv64/start.S").read_text()

        self.assertIn("MSTATUS_VS", source)
        self.assertIn("MSTATUS_FS", source)
        self.assertIn("csrs mstatus", source)

    def test_split_store_search_source_loads_high_half_first_for_diagnosis(self) -> None:
        source = (ROOT / "snippets/store_forward/misaligned_split_store_search.c").read_text()

        self.assertIn("\"lwu %0, 0(%3)", source)
        self.assertIn("\"lhu %1, 4(%3)", source)
        self.assertIn("\"lbu %2, 6(%3)", source)
        self.assertLess(source.index("\"lwu %0, 0(%3)"), source.index("\"lhu %1, 4(%3)"))
        self.assertLess(source.index("\"lhu %1, 4(%3)"), source.index("\"lbu %2, 6(%3)"))
        self.assertIn("xsrt_csr_write(12u, probe0_word32);", source)
        self.assertIn("xsrt_csr_write(13u, probe0_half16);", source)
        self.assertIn("xsrt_csr_write(14u, probe0_byte8);", source)

    def test_scalar_misalign_load_split_source_uses_seed_driven_rounds_and_summary(self) -> None:
        source = (ROOT / "snippets/scalar_misalign/load_split_templates.c").read_text()
        check = (ROOT / "snippets/scalar_misalign/check_load_split_templates.c").read_text()

        self.assertIn("xs_scalar_misalign_load_rounds", source)
        self.assertIn("xs_scalar_misalign_load_rotation", source)
        self.assertIn("xs_scalar_misalign_load_bank_seed", source)
        self.assertIn("env->seed", source)
        self.assertIn("xs_scalar_misalign_expected_load_summary", check)
        self.assertIn("env->seed", check)
        self.assertNotIn("XS_SCALAR_MISALIGN_CSR_TEMPLATE_COUNT", check)

    def test_scalar_misalign_store_split_source_uses_seed_driven_rounds_and_summary(self) -> None:
        source = (ROOT / "snippets/scalar_misalign/store_split_templates.c").read_text()
        check = (ROOT / "snippets/scalar_misalign/check_store_split_templates.c").read_text()

        self.assertIn("xs_scalar_misalign_store_rounds", source)
        self.assertIn("xs_scalar_misalign_store_rotation", source)
        self.assertIn("xs_scalar_misalign_store_bank_seed", source)
        self.assertIn("env->seed", source)
        self.assertIn("xs_scalar_misalign_expected_store_summary", check)
        self.assertIn("env->seed", check)
        self.assertNotIn("XS_SCALAR_MISALIGN_CSR_TEMPLATE_COUNT", check)

    def test_scalar_misalign_store_forward_overlap_source_uses_seed_driven_rounds_and_values(self) -> None:
        source = (ROOT / "snippets/scalar_misalign/store_forward_overlap.c").read_text()
        check = (ROOT / "snippets/scalar_misalign/check_store_forward_overlap.c").read_text()

        self.assertIn("xs_scalar_misalign_forward_rounds", source)
        self.assertIn("xs_scalar_misalign_target_value", source)
        self.assertIn("xs_scalar_misalign_forward_skid", source)
        self.assertIn("env->seed", source)
        self.assertIn("xs_scalar_misalign_expected_forward_summary", check)
        self.assertIn("xs_scalar_misalign_expected_target_value", check)

    def test_scalar_misalign_cross_page_source_uses_seed_driven_rounds_and_offsets(self) -> None:
        source = (ROOT / "snippets/scalar_misalign/cross_page_faults.c").read_text()
        check = (ROOT / "snippets/scalar_misalign/check_cross_page_faults.c").read_text()

        self.assertIn("xs_scalar_misalign_cross_rounds", source)
        self.assertIn("xs_scalar_misalign_load_offsets", source)
        self.assertIn("xs_scalar_misalign_store_offsets", source)
        self.assertIn("env->seed", source)
        self.assertIn("xs_scalar_misalign_expected_cross_summary", check)
        self.assertIn("env->seed", check)

    def test_declared_python_dependency(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text()
        self.assertIn("PyYAML", requirements)

    def test_cli_build_generates_real_artifacts(self) -> None:
        result = subprocess.run(
            ["make", "build"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
