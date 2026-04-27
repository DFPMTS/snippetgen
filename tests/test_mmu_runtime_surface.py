from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]

class MMURuntimeSurfaceTest(unittest.TestCase):
    def test_mmu_sources_are_part_of_runtime_build(self) -> None:
        from generator.xsgen import toolchain

        sources = {path.relative_to(ROOT).as_posix() for path in toolchain.runtime_sources(ROOT)}
        for relative_path in (
            "runtime/src/xsam_mmu.c",
            "runtime/src/xsam_mmu_fault.c",
            "runtime/src/xsam_mmu_guest.c",
        ):
            with self.subTest(path=relative_path):
                self.assertIn(relative_path, sources)

    def test_mmu_headers_host_compile(self) -> None:
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("host cc not available")

        sample = textwrap.dedent(
            """
            #include <stdint.h>

            #include "xsam/mmu.h"
            #include "xsam/mmu_fault.h"
            #include "xsam/mmu_guest.h"

            int main(void) {
              xsam_mmu_env_t env;
              xsam_mmu_page_table_t s1;
              xsam_mmu_page_table_t s2;
              xsam_mmu_env_init(&env);
              xsam_mmu_pt_init_sv39(&s1);
              xsam_mmu_pt_init_sv39x4(&s2);
              xsam_mmu_pt_map(&s1, 0x1000u, 0x2000u, XSAM_MMU_PTE_R | XSAM_MMU_PTE_A);
              xsam_mmu_pt_map_raw(&s2, 0x4000u, XSAM_MMU_PTE_V);
              xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
              xsam_mmu_write_satp(xsam_mmu_make_satp_pt(&s1, 1u));
              xsam_mmu_enable_bare();
              (void)xsam_mmu_make_vsatp_pt(&s1, 1u);
              (void)xsam_mmu_make_hgatp_pt(&s2, 2u);
              return env.layout.page_size == XSAM_MMU_PAGE_SIZE ? 0 : 1;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "mmu_header_smoke.c"
            object_path = Path(tmpdir) / "mmu_header_smoke.o"
            source_path.write_text(sample)
            result = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "runtime/include"),
                    "-c",
                    str(source_path),
                    "-o",
                    str(object_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_mmu_rule_runner_identity_maps_runtime_for_two_stage_entries(self) -> None:
        sample = (ROOT / "snippets/programs/mmu_rule_runner_main.c").read_text()

        self.assertIn("XS_RULE_RUNTIME_STAGE2_IDENTITY_SIZE = 0x00400000ull", sample)
        self.assertIn("XS_RULE_RUNTIME_VS_STAGE1_IDENTITY_SIZE = 0x00400000ull", sample)
        self.assertIn("XS_RULE_RUNTIME_STAGE2_IDENTITY_SIZE", sample)
        self.assertIn("XS_RULE_RUNTIME_VS_STAGE1_IDENTITY_SIZE", sample)

    def test_mmu_guest_vs_ecall_returns_to_m_mode_resume_stub(self) -> None:
        guest_c = (ROOT / "runtime/src/xsam_mmu_guest.c").read_text()

        self.assertIn("XSAM_MMU_MSTATUS_MPP_MASK = (uintptr_t)3 << 11", guest_c)
        self.assertIn("XSAM_MMU_MSTATUS_MPP_M = (uintptr_t)3 << 11", guest_c)
        self.assertIn("XSAM_MMU_MSTATUS_MPV_MASK = (uintptr_t)1 << 39", guest_c)
        self.assertIn(
            "frame->status = (frame->status &\n"
            "                   ~(XSAM_MMU_MSTATUS_MPP_MASK | XSAM_MMU_MSTATUS_MPV_MASK)) |\n"
            "                  XSAM_MMU_MSTATUS_MPP_M;",
            guest_c,
        )

    def test_mmu_fault_assert_reports_mask_mismatches(self) -> None:
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("host cc not available")

        sample = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/mmu_fault.h"
            #include "xsrt_trap.h"

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              (void) fn;
            }

            int main(void) {
              xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
              xsam_mmu_record_fault(
                  XSAM_MMU_FAULT_LOAD_PAGE,
                  XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
                  0x1000u,
                  0x2000u);
              if (xsam_mmu_fault_assert(XSAM_MMU_FAULT_LOAD_PAGE) != 0) {
                return 11;
              }

              xsam_mmu_expect_fault(XSAM_MMU_FAULT_LOAD_PAGE);
              xsam_mmu_record_fault(
                  XSAM_MMU_FAULT_LOAD_PAGE,
                  XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
                  0x1000u,
                  0x2000u);
              xsam_mmu_record_fault(
                  XSAM_MMU_FAULT_LOAD_PAGE,
                  XSAM_MMU_CAUSE_LOAD_PAGE_FAULT,
                  0x1004u,
                  0x2000u);
              if (xsam_mmu_fault_assert(XSAM_MMU_FAULT_LOAD_PAGE) == 0) {
                return 12;
              }

              xsam_mmu_expect_fault(XSAM_MMU_FAULT_STORE_PAGE);
              if (xsam_mmu_fault_assert(XSAM_MMU_FAULT_STORE_PAGE) == 0) {
                return 13;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "mmu_fault_assert_host.c"
            exe_path = Path(tmpdir) / "mmu_fault_assert_host"
            source_path.write_text(sample)
            result = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "runtime/include"),
                    str(source_path),
                    str(ROOT / "runtime/src/xsam_mmu_fault.c"),
                    str(ROOT / "runtime/src/xsam_mmu_guest.c"),
                    "-o",
                    str(exe_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

            run_result = subprocess.run(
                [str(exe_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, run_result.returncode, msg=run_result.stderr)
            self.assertIn("ok", run_result.stdout)

    def test_identity_range_rejects_unaligned_inputs_without_hanging(self) -> None:
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("host cc not available")

        sample = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/mmu.h"

            int main(void) {
              xsam_mmu_page_table_t pt;

              xsam_mmu_pt_init_sv39(&pt);
              xsam_mmu_pt_map_identity_range(
                  &pt,
                  0x80000001u,
                  XSAM_MMU_PAGE_SIZE,
                  XSAM_MMU_PTE_R | XSAM_MMU_PTE_X | XSAM_MMU_PTE_A);
              if (xsam_mmu_pt_leaf_ptr(&pt, 0x80000000u) != 0) {
                return 11;
              }

              xsam_mmu_pt_map_identity_range(
                  &pt,
                  0x80001000u,
                  XSAM_MMU_PAGE_SIZE - 1u,
                  XSAM_MMU_PTE_R | XSAM_MMU_PTE_X | XSAM_MMU_PTE_A);
              if (xsam_mmu_pt_leaf_ptr(&pt, 0x80001000u) != 0) {
                return 12;
              }

              xsam_mmu_pt_map_identity_range(
                  &pt,
                  0x80002000u,
                  XSAM_MMU_PAGE_SIZE,
                  XSAM_MMU_PTE_R | XSAM_MMU_PTE_X | XSAM_MMU_PTE_A);
              if (xsam_mmu_pt_leaf_ptr(&pt, 0x80002000u) == 0) {
                return 13;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "mmu_identity_range_guard.c"
            exe_path = Path(tmpdir) / "mmu_identity_range_guard"
            source_path.write_text(sample)
            result = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "runtime/include"),
                    str(source_path),
                    str(ROOT / "runtime/src/xsam_mmu.c"),
                    "-o",
                    str(exe_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)

            run_result = subprocess.run(
                [str(exe_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.assertEqual(0, run_result.returncode, msg=run_result.stderr)
            self.assertIn("ok", run_result.stdout)
