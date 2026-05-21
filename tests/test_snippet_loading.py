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

class SnippetLoadingTest(unittest.TestCase):
    def compile_sources(self, sources: list[Path], *, extra_flags: list[str] | None = None) -> None:
        toolchain = importlib.import_module("generator.xsgen.toolchain")
        flags = extra_flags if extra_flags is not None else toolchain.riscv_compile_flags()
        gcc = toolchain.detect_toolchain()["gcc"]

        with tempfile.TemporaryDirectory() as tmpdir:
            for src_path in sources:
                out_path = Path(tmpdir) / (src_path.stem + ".o")
                result = subprocess.run(
                    [
                        gcc,
                        "-std=c11",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        *flags,
                        "-I",
                        str(ROOT / "runtime/include"),
                        "-I",
                        str(ROOT / "snippets/include"),
                        "-I",
                        str(ROOT / "runtime/platform/xiangshan"),
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

    def test_prefetchw_default_target_addr_stays_outside_default_ram_window(self) -> None:
        header_text = (ROOT / "snippets/include/xs_prefetchw.h").read_text()
        self.assertIn("#define XS_PREFETCHW_TARGET_ADDR", header_text)
        target_match = re.search(r"XS_PREFETCHW_TARGET_ADDR \(\(uint64_t\) 0x([0-9a-fA-F]+)ull\)", header_text)
        self.assertIsNotNone(target_match)
        target = int(target_match.group(1), 16)
        self.assertFalse(0x80000000 <= target < 0xC0000000)

    def test_snippet_sources_compile(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")

        db = snippet_db.load_snippet_db(ROOT)
        sources = sorted({source for snippet in db.values() if snippet.kind == "proc" for source in snippet.sources})
        self.assertGreater(len(sources), 0)
        self.compile_sources(sources)

    def test_prefetchw_sources_compile_without_zicbop_mnemonic_support(self) -> None:
        self.compile_sources(
            [ROOT / "snippets/cbo/prefetchw_tl_denied_fault.c"],
            extra_flags=[
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
            ],
        )

    def test_checked_in_suites_resolve_to_stable_plans(self) -> None:
        snippet_db = importlib.import_module("generator.xsgen.snippet_db")
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        db_first = snippet_db.load_snippet_db(ROOT)
        db_second = snippet_db.load_snippet_db(ROOT)
        self.assertEqual(sorted(db_first.keys()), sorted(db_second.keys()))

        suite_paths = sorted((ROOT / "suites").glob("*.yaml"))
        self.assertGreater(len(suite_paths), 0)
        for suite_path in suite_paths:
            with self.subTest(suite=suite_path.name):
                suite_first = suite_loader.load_suite(suite_path)
                suite_second = suite_loader.load_suite(suite_path)
                self.assertEqual(suite_first, suite_second)

                plan_first = suite_loader.build_compose_plan(suite_first, db_first)
                plan_second = suite_loader.build_compose_plan(suite_second, db_second)
                self.assertEqual(plan_first.snippet_ids, plan_second.snippet_ids)
                self.assertEqual(
                    plan_first.snippet_ids,
                    tuple(snippet.id for snippet in plan_first.snippets),
                )

                if suite_first.run_snippet_ids is not None:
                    self.assertEqual(suite_first.run_snippet_ids, plan_first.run_snippet_ids)
                    self.assertEqual(suite_first.check_snippet_ids, plan_first.check_snippet_ids)
                    self.assertEqual(
                        tuple(dict.fromkeys([*suite_first.run_snippet_ids, *suite_first.check_snippet_ids])),
                        plan_first.snippet_ids,
                    )
                else:
                    self.assertEqual(suite_first.snippet_ids, plan_first.snippet_ids)

                if suite_first.mmu_rule_dir is not None:
                    self.assertIn("mmu_rule_runner_main", plan_first.snippet_ids)
                    self.assertGreater(len(plan_first.mmu_rule_ids), 0)
                    self.assertGreater(len(plan_first.mmu_defined_rule_ids), 0)
                    self.assertGreater(len(plan_first.mmu_coverage_tags), 0)

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

    def test_suite_loader_rejects_invalid_vector_mmu_fail_codes(self) -> None:
        suite_loader = importlib.import_module("generator.xsgen.suite_loader")

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = Path(tmpdir) / "bad_vector_fail_codes.yaml"
            suite_path.write_text(
                textwrap.dedent(
                    """
                    suite: bad_vector_fail_codes
                    target: xiangshan-verilator
                    seed: 9
                    compose:
                      mode: sequence
                      snippets:
                        - init_basic_env
                        - finish_check
                      vector_mmu_coverage:
                        - id: bad_vector_item
                          requestor: vector_load
                          mode: host_single_stage
                          form: unit_stride
                          eew: e8
                          page_boundary: single_page
                          fault: none
                          attribute: normal
                          fail_codes: "42,bad"
                    """
                ).strip()
            )

            with self.assertRaisesRegex(ValueError, "invalid fail_codes"):
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

        self.assertEqual(1, len(plan.mmu_rule_ids))
        self.assertIn("mode.bare", plan.mmu_coverage_tags)
        self.assertIn("requestor.load", plan.mmu_coverage_tags)

        dump_result = subprocess.run(
            ["python3", "generator/cli.py", "dump-plan", "suites/mmu_bare_identity_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, dump_result.returncode, msg=dump_result.stderr)
        payload = json.loads(dump_result.stdout)
        self.assertEqual(list(plan.mmu_rule_ids), payload["mmu"]["resolved_rule_ids"])
        self.assertEqual(list(plan.mmu_coverage_tags), payload["mmu"]["coverage_tags"])
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
