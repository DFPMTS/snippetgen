from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]

class AMProgramSnippetRuntimeTest(unittest.TestCase):
    def test_xsam_prot_none_is_zero_and_not_a_permission_bit(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include "xsam/am.h"

            int main(void) {
              if (XSAM_PROT_NONE != 0) {
                return 41;
              }
              if ((XSAM_PROT_NONE & (XSAM_PROT_READ | XSAM_PROT_WRITE | XSAM_PROT_EXEC)) != 0) {
                return 42;
              }
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_prot_none_host.c"
            exe_path = Path(tmpdir) / "xsam_prot_none_host"
            harness_path.write_text(harness_c)

            compile_result = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "runtime" / "include"),
                    str(harness_path),
                    "-o",
                    str(exe_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, compile_result.returncode, msg=compile_result.stderr)

            run_result = subprocess.run(
                [str(exe_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, run_result.returncode, msg=run_result.stderr)

    def test_xsam_headers_and_sources_cross_compile(self) -> None:
        smoke_c = textwrap.dedent(
            """
            #include <stddef.h>
            #include <stdint.h>

            #include "xsam/am.h"
            #include "xsam/amdev.h"
            #include "xsam/context.h"
            #include "xsam/vme.h"
            #include "xsam/ioe.h"
            #include "xsam/program_snippet.h"

            static xsam_context_t *demo_handler(xsam_event_t event, xsam_context_t *ctx) {
              ctx->cause = event.cause;
              return ctx;
            }

            static int demo_main(void) {
              xsam_putc('A');
              return 0;
            }

            XSAM_DEFINE_PROGRAM_SNIPPET(snippet_demo_program, "demo_program", demo_main);

            int main(void) {
              xsam_address_space_t as = {0};
              xsam_dev_timer_uptime_t uptime = {0};
              xsam_dev_serial_send_t serial = {.data = 'B'};

              (void)as;
              (void)uptime;
              (void)serial;
              xsam_cte_init(demo_handler);
              xsam_intr_write(1);
              xsam_yield();
              return snippet_demo_program.id != 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "xsam_smoke.c"
            object_path = Path(tmpdir) / "xsam_smoke.o"
            smoke_path.write_text(smoke_c)

            from generator.xsgen import toolchain
            gcc = toolchain.detect_toolchain()["gcc"]
            compile_result = subprocess.run(
                [
                    gcc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    *toolchain.riscv_compile_flags(),
                    "-I",
                    str(ROOT / "runtime" / "include"),
                    "-I",
                    str(ROOT / "snippets" / "include"),
                    "-c",
                    str(smoke_path),
                    "-o",
                    str(object_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, compile_result.returncode, msg=compile_result.stderr)


if __name__ == "__main__":
    unittest.main()
