from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class XSAMVMEBehaviorTest(unittest.TestCase):
    def test_xsam_vme_host_smoke_tracks_mappings(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>
            #include <stdlib.h>

            #include "xsam/am.h"
            #include "xsam/vme.h"

            static void *test_pgalloc(size_t size) {
              void *ptr = calloc(1u, size == 0 ? 1u : size);
              return ptr;
            }

            static void test_pgfree(void *ptr) {
              free(ptr);
            }

            int main(void) {
              xsam_address_space_t as = {0};
              void *pa = 0;
              int prot = 0;
              int kind = -1;
              int level = -1;

              if (xsam_vme_init(test_pgalloc, test_pgfree) != 0) {
                return 11;
              }

              xsam_protect(&as);
              if (as.ptr == 0 || as.pgsize != 4096u) {
                return 12;
              }

              xsam_map(&as, (void *) 0x1000u, (void *) 0x2000u, XSAM_PROT_READ | XSAM_PROT_WRITE);
              xsam_map_fault(&as, (void *) 0x3000u, (void *) 0x4000u, XSAM_PROT_READ);
              xsam_map_rv_hugepage(&as, (void *) 0x200000u, (void *) 0x400000u, XSAM_PROT_READ | XSAM_PROT_EXEC, 1);

              if (xsam_vme_mapping_count(&as) != 3u) {
                return 13;
              }

              if (!xsam_vme_lookup(&as, (void *) 0x1000u, &pa, &prot, &kind, &level)) {
                return 14;
              }
              if ((uintptr_t) pa != 0x2000u || prot != (XSAM_PROT_READ | XSAM_PROT_WRITE) || kind != XSAM_VME_MAP_NORMAL || level != 0) {
                return 15;
              }
              if (!xsam_vme_lookup(&as, (void *) 0x1abcu, &pa, &prot, &kind, &level)) {
                return 151;
              }
              if ((uintptr_t) pa != 0x2abcu || prot != (XSAM_PROT_READ | XSAM_PROT_WRITE) || kind != XSAM_VME_MAP_NORMAL || level != 0) {
                return 152;
              }

              if (!xsam_vme_lookup(&as, (void *) 0x3000u, &pa, &prot, &kind, &level)) {
                return 16;
              }
              if ((uintptr_t) pa != 0x4000u || prot != XSAM_PROT_READ || kind != XSAM_VME_MAP_FAULT || level != 0) {
                return 17;
              }
              if (!xsam_vme_lookup(&as, (void *) 0x3f00u, &pa, &prot, &kind, &level)) {
                return 171;
              }
              if ((uintptr_t) pa != 0x4f00u || prot != XSAM_PROT_READ || kind != XSAM_VME_MAP_FAULT || level != 0) {
                return 172;
              }

              if (!xsam_vme_lookup(&as, (void *) 0x200000u, &pa, &prot, &kind, &level)) {
                return 18;
              }
              if ((uintptr_t) pa != 0x400000u || prot != (XSAM_PROT_READ | XSAM_PROT_EXEC) || kind != XSAM_VME_MAP_HUGEPAGE || level != 1) {
                return 19;
              }
              if (!xsam_vme_lookup(&as, (void *) 0x201234u, &pa, &prot, &kind, &level)) {
                return 191;
              }
              if ((uintptr_t) pa != 0x401234u || prot != (XSAM_PROT_READ | XSAM_PROT_EXEC) || kind != XSAM_VME_MAP_HUGEPAGE || level != 1) {
                return 192;
              }

              xsam_unprotect(&as);
              if (as.ptr != 0 || xsam_vme_mapping_count(&as) != 0u) {
                return 20;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_vme_host.c"
            exe_path = Path(tmpdir) / "xsam_vme_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_vme.c"),
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
            self.assertIn("ok", run_result.stdout)

    def test_xsam_vme_init_rejects_missing_allocators(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdio.h>
            #include <stdlib.h>

            #include "xsam/am.h"
            #include "xsam/vme.h"

            static void *test_pgalloc(size_t size) {
              void *ptr = calloc(1u, size == 0 ? 1u : size);
              return ptr;
            }

            static void test_pgfree(void *ptr) {
              free(ptr);
            }

            int main(void) {
              xsam_address_space_t as = {0};

              if (xsam_vme_init(0, test_pgfree) == 0) {
                return 21;
              }
              xsam_protect(&as);
              if (as.ptr != 0) {
                return 22;
              }

              if (xsam_vme_init(test_pgalloc, 0) == 0) {
                return 23;
              }
              xsam_protect(&as);
              if (as.ptr != 0) {
                return 24;
              }

              if (xsam_vme_init(test_pgalloc, test_pgfree) != 0) {
                return 25;
              }
              xsam_protect(&as);
              if (as.ptr == 0) {
                return 26;
              }
              xsam_unprotect(&as);

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_vme_init_rejects_allocators.c"
            exe_path = Path(tmpdir) / "xsam_vme_init_rejects_allocators"
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
                    str(ROOT / "runtime" / "src" / "xsam_vme.c"),
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
            self.assertIn("ok", run_result.stdout)


if __name__ == "__main__":
    unittest.main()
