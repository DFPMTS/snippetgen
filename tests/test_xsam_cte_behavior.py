from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class XSAMCTEBehaviorTest(unittest.TestCase):
    def test_cte_timer_trap_translates_into_am_event(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static xsrt_env_t g_env;
            static xsrt_trap_handler_t g_strap;
            static int g_cte_active;
            static int g_seen;
            static int g_last_event;
            static uintptr_t g_last_cause;
            static uintptr_t g_last_ref;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              g_strap = fn;
            }

            void xsrt_timer_set_cte_active(int active) {
              g_cte_active = active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return &g_env;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            static xsam_context_t *on_event(xsam_event_t event, xsam_context_t *ctx) {
              g_seen += 1;
              g_last_event = event.event;
              g_last_cause = event.cause;
              g_last_ref = event.ref;
              ctx->epc += 4u;
              return ctx;
            }

            int main(void) {
              xsrt_trap_frame_t frame = {
                .epc = 0x1000u,
                .cause = 0x8000000000000007ull,
                .tval = 0x55u,
              };

              if (xsam_cte_init(on_event) != 0) {
                return 11;
              }
              if (g_strap == 0 || g_cte_active == 0) {
                return 12;
              }

              g_strap(&frame);

              if (g_seen != 1 || g_last_event != XSAM_EVENT_IRQ_TIMER) {
                return 13;
              }
              if (g_last_cause != 0x8000000000000007ull || g_last_ref != 0x55u) {
                return 14;
              }
              if (frame.epc != 0x1004u) {
                return 15;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_cte_machine_irq_traps_translate_into_am_events(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static xsrt_trap_handler_t g_strap;
            static int g_events[2];
            static int g_event_count;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              g_strap = fn;
            }

            void xsrt_timer_set_cte_active(int active) {
              (void) active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            static xsam_context_t *on_event(xsam_event_t event, xsam_context_t *ctx) {
              g_events[g_event_count++] = event.event;
              return ctx;
            }

            int main(void) {
              xsrt_trap_frame_t software_frame = {
                .epc = 0x1000u,
                .cause = 0x8000000000000003ull,
              };
              xsrt_trap_frame_t external_frame = {
                .epc = 0x2000u,
                .cause = 0x800000000000000bull,
              };

              if (xsam_cte_init(on_event) != 0 || g_strap == 0) {
                return 31;
              }

              g_strap(&software_frame);
              g_strap(&external_frame);

              if (g_event_count != 2) {
                return 32;
              }
              if (g_events[0] != XSAM_EVENT_IRQ_SOFT) {
                return 33;
              }
              if (g_events[1] != XSAM_EVENT_IRQ_IODEV) {
                return 34;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_machine_irq_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_machine_irq_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_cte_context_round_trips_trap_status(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static xsrt_trap_handler_t g_strap;
            static uintptr_t g_seen_status;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              g_strap = fn;
            }

            void xsrt_timer_set_cte_active(int active) {
              (void) active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            static xsam_context_t *on_event(xsam_event_t event, xsam_context_t *ctx) {
              (void) event;
              g_seen_status = ctx->status;
              ctx->status = 0x13579bdfu;
              return ctx;
            }

            int main(void) {
              xsrt_trap_frame_t frame = {
                .epc = 0x1000u,
                .status = 0x2468ace0u,
                .cause = 0x8000000000000007ull,
              };

              if (xsam_cte_init(on_event) != 0 || g_strap == 0) {
                return 41;
              }

              g_strap(&frame);

              if (g_seen_status != 0x2468ace0u) {
                return 42;
              }
              if (frame.status != 0x13579bdfu) {
                return 43;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_status_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_status_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_cte_init_rejects_null_handler_without_installing_strap(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static int g_install_calls;
            static int g_cte_active = -1;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              (void) fn;
              g_install_calls += 1;
            }

            void xsrt_timer_set_cte_active(int active) {
              g_cte_active = active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            int main(void) {
              if (xsam_cte_init(0) == 0) {
                return 51;
              }
              if (g_install_calls != 0) {
                return 52;
              }
              if (g_cte_active != -1) {
                return 53;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_null_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_null_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_cte_init_null_after_success_leaves_existing_handler_active(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static xsrt_trap_handler_t g_strap;
            static int g_install_calls;
            static int g_cte_active = -1;
            static int g_seen;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              g_strap = fn;
              g_install_calls += 1;
            }

            void xsrt_timer_set_cte_active(int active) {
              g_cte_active = active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            static xsam_context_t *on_event(xsam_event_t event, xsam_context_t *ctx) {
              (void) event;
              g_seen += 1;
              ctx->epc += 4u;
              return ctx;
            }

            int main(void) {
              xsrt_trap_frame_t frame = {
                .epc = 0x1000u,
                .cause = 11u,
              };

              if (xsam_cte_init(on_event) != 0 || g_strap == 0 || g_cte_active != 1) {
                return 61;
              }
              if (xsam_cte_init(0) == 0) {
                return 62;
              }
              if (g_install_calls != 1 || g_cte_active != 1) {
                return 63;
              }

              g_strap(&frame);
              if (g_seen != 1 || frame.epc != 0x1008u) {
                return 64;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_null_after_success_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_null_after_success_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_cte_maps_yield_syscall_and_pagefault_events(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static xsrt_trap_handler_t g_strap;
            static int g_events[3];
            static int g_event_count;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              g_strap = fn;
            }

            void xsrt_timer_set_cte_active(int active) {
              (void) active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              (void) cycles;
            }

            void xsrt_disable_stimer(void) {
            }

            static xsam_context_t *on_event(xsam_event_t event, xsam_context_t *ctx) {
              g_events[g_event_count++] = event.event;
              return ctx;
            }

            int main(void) {
              xsrt_trap_frame_t yield_frame = {
                .epc = 0x10u,
                .cause = 11u,
              };
              xsrt_trap_frame_t syscall_frame = {
                .epc = 0x20u,
                .cause = 11u,
              };
              xsrt_trap_frame_t pagefault_frame = {
                .epc = 0x30u,
                .cause = 13u,
                .tval = 0xdeadbeefu,
              };

              yield_frame.gpr[17] = (uint64_t) -1ll;
              syscall_frame.gpr[17] = 0u;

              if (xsam_cte_init(on_event) != 0 || g_strap == 0) {
                return 21;
              }

              g_strap(&yield_frame);
              g_strap(&syscall_frame);
              g_strap(&pagefault_frame);

              if (g_event_count != 3) {
                return 22;
              }
              if (g_events[0] != XSAM_EVENT_YIELD) {
                return 23;
              }
              if (g_events[1] != XSAM_EVENT_SYSCALL) {
                return 24;
              }
              if (g_events[2] != XSAM_EVENT_PAGEFAULT) {
                return 25;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_cte_events_host.c"
            exe_path = Path(tmpdir) / "xsam_cte_events_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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

    def test_intr_write_controls_timer_runtime_hooks(self) -> None:
        harness_c = textwrap.dedent(
            """
            #include <stdint.h>
            #include <stdio.h>

            #include "xsam/am.h"
            #include "xsrt_env.h"
            #include "xsrt_trap.h"

            static int g_enable_calls;
            static int g_disable_calls;
            static int g_periodic_arm_calls;
            static int g_one_shot_arm_calls;
            static uint64_t g_last_delta;

            void xsrt_install_strap(xsrt_trap_handler_t fn) {
              (void) fn;
            }

            void xsrt_timer_set_cte_active(int active) {
              (void) active;
            }

            xsrt_env_t *xsrt_current_env(void) {
              return 0;
            }

            void xsrt_enable_stimer(void) {
              g_enable_calls += 1;
            }

            void xsrt_timer_arm_delta(uint64_t cycles) {
              g_one_shot_arm_calls += 1;
              g_last_delta = cycles;
            }

            void xsrt_timer_arm_periodic_delta(uint64_t cycles) {
              g_periodic_arm_calls += 1;
              g_last_delta = cycles;
            }

            void xsrt_disable_stimer(void) {
              g_disable_calls += 1;
            }

            int main(void) {
              if (xsam_intr_read() != 0) {
                return 31;
              }

              xsam_intr_write(1);
              if (xsam_intr_read() == 0 || g_enable_calls != 1 || g_last_delta == 0u || g_disable_calls != 0) {
                return 32;
              }
              if (g_periodic_arm_calls != 1 || g_one_shot_arm_calls != 0) {
                return 34;
              }

              xsam_intr_write(0);
              if (xsam_intr_read() != 0 || g_disable_calls != 1) {
                return 33;
              }

              puts("ok");
              return 0;
            }
            """
        ).strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            harness_path = Path(tmpdir) / "xsam_intr_write_host.c"
            exe_path = Path(tmpdir) / "xsam_intr_write_host"
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
                    str(ROOT / "runtime" / "src" / "xsam_cte.c"),
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
