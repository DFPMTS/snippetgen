import importlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AMProgramSnippetBuildTest(unittest.TestCase):
    def test_emitter_generates_descriptor_wrapper_for_am_program(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            program_source = Path(tmpdir) / "demo_program.c"
            program_source.write_text("int main(void) { return 0; }\n")

            init_source = ROOT / "snippets" / "core" / "init_basic_env.c"
            finish_source = ROOT / "snippets" / "core" / "finish_check.c"

            plan = model.ComposePlan(
                suite_name="am_program_emit_case",
                target="xiangshan-verilator",
                seed=7,
                snippet_ids=("init_basic_env", "demo_program", "finish_check"),
                snippets=(
                    model.SnippetSpec(
                        id="init_basic_env",
                        kind="proc",
                        lang="c",
                        sources=(init_source.resolve(),),
                    ),
                    model.SnippetSpec(
                        id="demo_program",
                        kind="am_program",
                        lang="c",
                        entry="main",
                        sources=(program_source.resolve(),),
                    ),
                    model.SnippetSpec(
                        id="finish_check",
                        kind="proc",
                        lang="c",
                        sources=(finish_source.resolve(),),
                    ),
                ),
            )
            artifact = toolchain.artifact_paths_for_suite(Path(tmpdir), plan.suite_name)

            emitter.emit_harness(plan, artifact.generated_suite_path)
            harness = artifact.generated_suite_path.read_text()
            wrapper = (artifact.build_dir / "generated_am_program_demo_program.c").read_text()

            self.assertIn('#include "xsam/program_snippet.h"', harness)
            self.assertIn("extern int xsam_program_entry_demo_program(void);", harness)
            self.assertIn("extern const xsrt_snippet_desc_t snippet_demo_program;", harness)
            self.assertNotIn(f'#include "{program_source.resolve()}"', harness)
            self.assertNotIn("#define main xsam_program_entry_demo_program", harness)
            self.assertIn('#include "xsam/program_snippet.h"', wrapper)
            self.assertIn("extern int xsam_program_entry_demo_program(void);", wrapper)
            self.assertIn(
                'XSAM_DEFINE_PROGRAM_SNIPPET(snippet_demo_program, "demo_program", xsam_program_entry_demo_program)',
                wrapper,
            )
            self.assertIn("xsrt_run_snippet(&env, &snippet_init_basic_env);", harness)
            self.assertIn("xsrt_run_snippet(&env, &snippet_demo_program);", harness)
            self.assertIn("xsrt_run_snippet(&env, &snippet_finish_check);", harness)

    def test_build_pipeline_renames_actual_am_program_entry_source_even_when_listed_last(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            program_source = tmp_root / "demo_program.c"
            helper_source = tmp_root / "demo_helper.c"
            helper_source.write_text(
                "\n".join(
                    [
                        "extern int main(void);",
                        "int (*demo_entry_ref)(void) = main;",
                        "int demo_helper(void) { return demo_entry_ref != 0 ? 0 : 1; }",
                    ]
                )
                + "\n"
            )
            program_source.write_text(
                "\n".join(
                    [
                        "extern int demo_helper(void);",
                        "int main(void) {",
                        "  return demo_helper();",
                        "}",
                    ]
                )
                + "\n"
            )

            plan = model.ComposePlan(
                suite_name="am_program_build_case",
                target="xiangshan-verilator",
                seed=11,
                snippet_ids=("init_basic_env", "demo_program", "finish_check"),
                snippets=(
                    model.SnippetSpec(
                        id="init_basic_env",
                        kind="proc",
                        lang="c",
                        sources=((ROOT / "snippets" / "core" / "init_basic_env.c").resolve(),),
                    ),
                    model.SnippetSpec(
                        id="demo_program",
                        kind="am_program",
                        lang="c",
                        entry="main",
                        sources=(helper_source.resolve(), program_source.resolve()),
                    ),
                    model.SnippetSpec(
                        id="finish_check",
                        kind="proc",
                        lang="c",
                        sources=((ROOT / "snippets" / "core" / "finish_check.c").resolve(),),
                    ),
                ),
            )
            artifact = toolchain.artifact_paths_for_suite(tmp_root, plan.suite_name)

            emitter.emit_harness(plan, artifact.generated_suite_path)
            toolchain.build_artifacts(ROOT, plan, artifact)

            self.assertTrue(artifact.elf_path.is_file())
            self.assertTrue(artifact.bin_path.is_file())
            self.assertTrue(artifact.build_manifest_path.is_file())

            manifest = json.loads(artifact.build_manifest_path.read_text())
            compile_commands = manifest["commands"]["compile"]
            compile_sources = [cmd[cmd.index("-c") + 1] for cmd in compile_commands]
            wrapper_source = str((artifact.build_dir / "generated_am_program_demo_program.c").resolve())

            self.assertIn(str(program_source.resolve()), compile_sources)
            self.assertIn(str(helper_source.resolve()), compile_sources)
            self.assertIn(wrapper_source, compile_sources)
            self.assertIn(str(artifact.generated_suite_path), compile_sources)
            self.assertIn(
                str((ROOT / "runtime" / "src" / "xsam_program_snippet.c").resolve()),
                compile_sources,
            )
            program_compile = next(
                cmd for cmd in compile_commands if cmd[cmd.index("-c") + 1] == str(program_source.resolve())
            )
            self.assertIn("-Dmain=xsam_program_entry_demo_program", program_compile)
            helper_compile = next(
                cmd for cmd in compile_commands if cmd[cmd.index("-c") + 1] == str(helper_source.resolve())
            )
            self.assertIn("-Dmain=xsam_program_entry_demo_program", helper_compile)

    def test_build_pipeline_keeps_am_programs_in_separate_translation_units(self) -> None:
        emitter = importlib.import_module("generator.xsgen.emitter")
        model = importlib.import_module("generator.xsgen.model")
        toolchain = importlib.import_module("generator.xsgen.toolchain")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            program_a = tmp_root / "program_a.c"
            program_b = tmp_root / "program_b.c"
            program_a.write_text(
                "\n".join(
                    [
                        "static int helper(void) { return 1; }",
                        "int main(void) {",
                        "  return helper() - 1;",
                        "}",
                    ]
                )
                + "\n"
            )
            program_b.write_text(
                "\n".join(
                    [
                        "static int helper(void) { return 2; }",
                        "int altmain(void) {",
                        "  return helper() - 2;",
                        "}",
                    ]
                )
                + "\n"
            )

            plan = model.ComposePlan(
                suite_name="am_program_separate_tu_case",
                target="xiangshan-verilator",
                seed=13,
                snippet_ids=("init_basic_env", "program_a", "program_b", "finish_check"),
                snippets=(
                    model.SnippetSpec(
                        id="init_basic_env",
                        kind="proc",
                        lang="c",
                        sources=((ROOT / "snippets" / "core" / "init_basic_env.c").resolve(),),
                    ),
                    model.SnippetSpec(
                        id="program_a",
                        kind="am_program",
                        lang="c",
                        entry="main",
                        sources=(program_a.resolve(),),
                    ),
                    model.SnippetSpec(
                        id="program_b",
                        kind="am_program",
                        lang="c",
                        entry="altmain",
                        sources=(program_b.resolve(),),
                    ),
                    model.SnippetSpec(
                        id="finish_check",
                        kind="proc",
                        lang="c",
                        sources=((ROOT / "snippets" / "core" / "finish_check.c").resolve(),),
                    ),
                ),
            )
            artifact = toolchain.artifact_paths_for_suite(tmp_root, plan.suite_name)

            emitter.emit_harness(plan, artifact.generated_suite_path)
            toolchain.build_artifacts(ROOT, plan, artifact)

            self.assertTrue(artifact.elf_path.is_file())
            manifest = json.loads(artifact.build_manifest_path.read_text())
            compile_sources = [
                cmd[cmd.index("-c") + 1]
                for cmd in manifest["commands"]["compile"]
            ]
            self.assertIn(str((artifact.build_dir / "generated_am_program_program_a.c").resolve()), compile_sources)
            self.assertIn(str((artifact.build_dir / "generated_am_program_program_b.c").resolve()), compile_sources)


if __name__ == "__main__":
    unittest.main()
