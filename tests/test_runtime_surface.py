from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]

RUNTIME_FILES = [
    "runtime/include/xsrt_env.h",
    "runtime/include/xsrt_csr.h",
    "runtime/include/xsrt_trap.h",
    "runtime/include/xsrt_intr.h",
    "runtime/src/xsrt_env.c",
    "runtime/src/xsrt_csr.c",
    "runtime/src/xsrt_trap.c",
    "runtime/src/xsrt_intr.c",
    "runtime/src/xsrt_snippet.c",
    "runtime/platform/xiangshan/xsrt_platform.h",
    "runtime/platform/xiangshan/xsrt_platform.c",
    "runtime/arch/riscv64/start.S",
    "runtime/arch/riscv64/trap.S",
    "snippets/include/xs_snippet.h",
]


class RuntimeSurfaceTest(unittest.TestCase):
    def test_runtime_files_exist(self) -> None:
        for relative_path in RUNTIME_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_runtime_headers_expose_minimal_api(self) -> None:
        env_h = (ROOT / "runtime/include/xsrt_env.h").read_text()
        csr_h = (ROOT / "runtime/include/xsrt_csr.h").read_text()
        trap_h = (ROOT / "runtime/include/xsrt_trap.h").read_text()
        intr_h = (ROOT / "runtime/include/xsrt_intr.h").read_text()
        snippet_h = (ROOT / "snippets/include/xs_snippet.h").read_text()

        self.assertIn("typedef struct {", env_h)
        self.assertIn("uint64_t hartid;", env_h)
        self.assertIn("uint64_t test_id;", env_h)
        self.assertIn("uint64_t snippet_id;", env_h)
        self.assertIn("uint64_t seed;", env_h)
        self.assertIn("uint64_t flags;", env_h)
        self.assertIn("uint64_t finish_code;", env_h)
        self.assertIn("#define XSRT_BAD_TRAP(code)", env_h)
        self.assertIn("void xsrt_init(xsrt_env_t *env);", env_h)
        self.assertIn("void xsrt_finish_pass(xsrt_env_t *env);", env_h)
        self.assertIn("void xsrt_finish_fail(xsrt_env_t *env, uint64_t code);", env_h)

        self.assertIn("uint64_t xsrt_csr_read(uint32_t csr);", csr_h)
        self.assertIn("void xsrt_csr_write(uint32_t csr, uint64_t val);", csr_h)

        self.assertIn("typedef struct xsrt_trap_frame xsrt_trap_frame_t;", trap_h)
        self.assertIn("typedef xsrt_trap_frame_t *(*xsrt_trap_handler_t)(xsrt_trap_frame_t *);", trap_h)
        self.assertIn("void xsrt_install_strap(xsrt_trap_handler_t fn);", trap_h)

        self.assertIn("void xsrt_enable_stimer(void);", intr_h)
        self.assertIn("void xsrt_timer_arm_delta(uint64_t cycles);", intr_h)
        self.assertIn("void xsrt_timer_arm_periodic_delta(uint64_t cycles);", intr_h)

        self.assertIn("typedef struct {", snippet_h)
        self.assertIn("const char *id;", snippet_h)
        self.assertIn("int (*init)(xsrt_env_t *env);", snippet_h)
        self.assertIn("int (*run)(xsrt_env_t *env);", snippet_h)
        self.assertIn("int (*check)(xsrt_env_t *env);", snippet_h)
        self.assertIn("void (*fini)(xsrt_env_t *env);", snippet_h)
        self.assertIn("int xsrt_run_snippet(xsrt_env_t *env, const xsrt_snippet_desc_t *snippet);", snippet_h)
        self.assertIn("int xsrt_run_snippet_no_check(xsrt_env_t *env, const xsrt_snippet_desc_t *snippet);", snippet_h)
        self.assertIn("int xsrt_run_snippet_check_only(xsrt_env_t *env, const xsrt_snippet_desc_t *snippet);", snippet_h)

        start_s = (ROOT / "runtime/arch/riscv64/start.S").read_text()
        self.assertIn("main", start_s)
        self.assertRegex(start_s, r"\b(call|tail)\s+main\b")

    def test_sync_trap_install_initializes_mscratch(self) -> None:
        trap_c = (ROOT / "runtime/src/xsrt_trap.c").read_text()

        self.assertIn("static xsrt_trap_scratch_t g_sync_trap_scratch;", trap_c)
        self.assertIn("void xsrt_reset_mscratch_for_sync_traps(void)", trap_c)
        self.assertIn('csrw mscratch, %0', trap_c)
        self.assertIn("xsrt_reset_mscratch_for_sync_traps();", trap_c)

    def test_sync_trap_install_preserves_active_timer_scratch(self) -> None:
        trap_c = (ROOT / "runtime/src/xsrt_trap.c").read_text()
        intr_h = (ROOT / "runtime/include/xsrt_intr.h").read_text()
        intr_c = (ROOT / "runtime/src/xsrt_intr.c").read_text()

        self.assertIn('#include "xsrt_intr.h"', trap_c)
        self.assertIn("int xsrt_timer_trap_state_active(void);", intr_h)
        self.assertIn("int xsrt_timer_trap_state_active(void)", intr_c)
        self.assertIn("return g_stimer_enabled != 0;", intr_c)
        self.assertIn(
            "if (xsrt_timer_trap_state_active() == 0) {\n"
            "    xsrt_reset_mscratch_for_sync_traps();\n"
            "  }",
            trap_c,
        )

    def test_disabling_stimer_restores_sync_trap_scratch(self) -> None:
        intr_c = (ROOT / "runtime/src/xsrt_intr.c").read_text()

        self.assertIn("xsrt_reset_mscratch_for_sync_traps();", intr_c)

    def test_timer_trap_env_offsets_match_xsrt_env_layout(self) -> None:
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("host cc not available")

        trap_s = (ROOT / "runtime/arch/riscv64/trap.S").read_text()
        probe_c = textwrap.dedent(
            """
            #include <stddef.h>
            #include <stdio.h>

            #include "xsrt_env.h"

            int main(void) {
              printf(
                  "%zu %zu %zu %zu %zu\\n",
                  offsetof(xsrt_env_t, flags),
                  offsetof(xsrt_env_t, finish_code),
                  offsetof(xsrt_env_t, interrupt_count),
                  offsetof(xsrt_env_t, last_trap_cause),
                  offsetof(xsrt_env_t, last_trap_epc));
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            probe_path = Path(tmpdir) / "xsrt_env_offsets.c"
            executable_path = Path(tmpdir) / "xsrt_env_offsets"
            probe_path.write_text(probe_c)

            compile_result = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "runtime/include"),
                    str(probe_path),
                    "-o",
                    str(executable_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, compile_result.returncode, msg=compile_result.stderr)

            run_result = subprocess.run(
                [str(executable_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, run_result.returncode, msg=run_result.stderr)

        offsets = [int(value) for value in run_result.stdout.strip().split()]
        self.assertEqual(5, len(offsets))
        names = (
            "XSRT_ENV_FLAGS",
            "XSRT_ENV_FINISH_CODE",
            "XSRT_ENV_INTERRUPT_COUNT",
            "XSRT_ENV_LAST_TRAP_CAUSE",
            "XSRT_ENV_LAST_TRAP_EPC",
        )
        expected_offsets = dict(zip(names, offsets))

        for macro_name, expected_offset in expected_offsets.items():
            match = re.search(rf"#define {macro_name} (\d+)", trap_s)
            self.assertIsNotNone(match, msg=f"missing {macro_name} in trap.S")
            self.assertEqual(expected_offset, int(match.group(1)), msg=macro_name)

    def test_xsrt_snippet_helpers_execute_expected_sequences(self) -> None:
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("host cc not available")

        smoke_c = textwrap.dedent(
            """
            #include <stdint.h>

            #include "xs_snippet.h"

            static int order[4];
            static int order_count = 0;
            static int check_calls = 0;

            static int mark_init(xsrt_env_t *env) {
              order[order_count++] = 1;
              env->test_id = 7u;
              return 0;
            }

            static int mark_run(xsrt_env_t *env) {
              order[order_count++] = 2;
              env->snippet_id = 99u;
              return 0;
            }

            static int mark_check(xsrt_env_t *env) {
              order[order_count++] = 3;
              check_calls++;
              return env->snippet_id == 99u ? 0 : 11;
            }

            static void mark_fini(xsrt_env_t *env) {
              order[order_count++] = 4;
              env->flags |= 1u;
            }

            int main(void) {
              xsrt_env_t env = {0};
              const xsrt_snippet_desc_t snippet = {
                .id = "smoke",
                .init = mark_init,
                .run = mark_run,
                .check = mark_check,
                .fini = mark_fini,
              };

              if (xsrt_run_snippet(&env, &snippet) != 0) {
                return 21;
              }

              if (order_count != 4) {
                return 22;
              }

              for (int i = 0; i < 4; ++i) {
                if (order[i] != i + 1) {
                  return 23;
                }
              }

              if (check_calls != 1) {
                return 24;
              }

              if ((env.flags & 1u) == 0u || env.test_id != 7u || env.snippet_id != 99u) {
                return 25;
              }

              env = (xsrt_env_t){0};
              order_count = 0;
              check_calls = 0;
              if (xsrt_run_snippet_no_check(&env, &snippet) != 0) {
                return 26;
              }

              if (order_count != 3) {
                return 27;
              }

              if (order[0] != 1 || order[1] != 2 || order[2] != 4) {
                return 28;
              }

              if (check_calls != 0) {
                return 29;
              }

              if ((env.flags & 1u) == 0u || env.test_id != 7u || env.snippet_id != 99u) {
                return 30;
              }

              env = (xsrt_env_t){0};
              env.snippet_id = 99u;
              order_count = 0;
              check_calls = 0;
              if (xsrt_run_snippet_check_only(&env, &snippet) != 0) {
                return 31;
              }

              if (order_count != 1 || order[0] != 3) {
                return 32;
              }

              if (check_calls != 1) {
                return 33;
              }

              if (env.flags != 0u || env.test_id != 0u || env.snippet_id != 99u) {
                return 34;
              }

              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "snippet_runtime_smoke.c"
            executable_path = Path(tmpdir) / "snippet_runtime_smoke"
            smoke_path.write_text(smoke_c)

            compile_result = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-O2",
                    "-I",
                    str(ROOT / "runtime/include"),
                    "-I",
                    str(ROOT / "snippets/include"),
                    str(smoke_path),
                    str(ROOT / "runtime/src/xsrt_snippet.c"),
                    "-o",
                    str(executable_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, compile_result.returncode, msg=compile_result.stderr)

            run_result = subprocess.run(
                [str(executable_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                0,
                run_result.returncode,
                msg=f"stdout:\n{run_result.stdout}\nstderr:\n{run_result.stderr}",
            )

    def test_runtime_c_surfaces_cross_compile(self) -> None:
        smoke_c = textwrap.dedent(
            """
            #include <stdint.h>

            #include "xsrt_env.h"
            #include "xsrt_csr.h"
            #include "xsrt_trap.h"
            #include "xsrt_intr.h"
            #include "xs_snippet.h"

            static int order[4];
            static int order_count = 0;
            static int check_calls = 0;

            static int mark_init(xsrt_env_t *env) {
              order[order_count++] = 1;
              env->test_id = 7;
              return 0;
            }

            static int mark_run(xsrt_env_t *env) {
              order[order_count++] = 2;
              xsrt_csr_write(5u, 99u);
              env->snippet_id = xsrt_csr_read(5u);
              return 0;
            }

            static int mark_check(xsrt_env_t *env) {
              order[order_count++] = 3;
              check_calls++;
              return env->snippet_id == 99u ? 0 : 11;
            }

            static void mark_fini(xsrt_env_t *env) {
              order[order_count++] = 4;
              env->flags |= 1u;
            }

            int main(void) {
              xsrt_env_t env = {0};
              const xsrt_snippet_desc_t snippet = {
                .id = "smoke",
                .init = mark_init,
                .run = mark_run,
                .check = mark_check,
                .fini = mark_fini,
              };

              xsrt_init(&env);
              xsrt_install_strap(0);
              xsrt_enable_stimer();
              xsrt_timer_arm_delta(32u);

              if (xsrt_run_snippet(&env, &snippet) != 0) {
                return 21;
              }

              if (order_count != 4) {
                return 22;
              }

              for (int i = 0; i < 4; ++i) {
                if (order[i] != i + 1) {
                  return 23;
                }
              }

              if ((env.flags & 1u) == 0u || env.test_id != 7u || env.snippet_id != 99u) {
                return 24;
              }

              if (env.finish_code != 0u) {
                return 25;
              }

              xsrt_finish_pass(&env);
              if (env.finish_code != 0u) {
                return 26;
              }

              xsrt_finish_fail(&env, 77u);
              if (env.finish_code != 77u) {
                return 27;
              }

              env = (xsrt_env_t){0};
              order_count = 0;
              check_calls = 0;
              if (xsrt_run_snippet_no_check(&env, &snippet) != 0) {
                return 28;
              }

              if (order_count != 3) {
                return 29;
              }

              if (order[0] != 1 || order[1] != 2 || order[2] != 4) {
                return 30;
              }

              if (check_calls != 0) {
                return 31;
              }

              if ((env.flags & 1u) == 0u || env.test_id != 7u || env.snippet_id != 99u) {
                return 32;
              }

              env = (xsrt_env_t){0};
              env.snippet_id = 99u;
              order_count = 0;
              check_calls = 0;
              if (xsrt_run_snippet_check_only(&env, &snippet) != 0) {
                return 33;
              }

              if (order_count != 1 || order[0] != 3) {
                return 34;
              }

              if (check_calls != 1) {
                return 35;
              }

              if (env.flags != 0u || env.test_id != 0u || env.snippet_id != 99u) {
                return 36;
              }

              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "runtime_smoke.c"
            object_path = Path(tmpdir) / "runtime_smoke.o"
            smoke_path.write_text(smoke_c)

            toolchain = __import__("generator.xsgen.toolchain", fromlist=["detect_toolchain"])
            gcc = toolchain.detect_toolchain()["gcc"]
            compile_cmd = [
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
                "-I",
                str(ROOT / "runtime/platform/xiangshan"),
                "-c",
                str(smoke_path),
                "-o",
                str(object_path),
            ]
            compile_result = subprocess.run(
                compile_cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                0,
                compile_result.returncode,
                msg=compile_result.stderr,
            )

    def test_xiangshan_pmp_uses_numeric_csr_operands_for_extended_pmpcfg(self) -> None:
        source = (ROOT / "runtime/platform/xiangshan/xsam_xs_pmp.c").read_text()

        for index in range(4, 16):
            self.assertNotIn(f"pmpcfg{index}", source)
        self.assertIn("0x3a4", source)
        self.assertIn("0x3af", source)


if __name__ == "__main__":
    unittest.main()
