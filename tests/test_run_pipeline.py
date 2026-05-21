from pathlib import Path
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_xiangshan_run_target():
    module_path = ROOT / "targets" / "xiangshan-verilator" / "run_target.py"
    spec = importlib.util.spec_from_file_location("xiangshan_run_target_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.run_root = ROOT / "build" / "vsetvl_interrupt_path_poc" / "runs"
        self.mmu_run_root = ROOT / "build" / "mmu_pilot_rules_poc" / "runs"
        if self.run_root.exists():
            shutil.rmtree(self.run_root)
        if self.mmu_run_root.exists():
            shutil.rmtree(self.mmu_run_root)

    def _vector_coverage_after_target_result(
        self,
        *,
        suite_name: str,
        coverage_items: tuple[dict[str, str], ...],
        finish_code: int | None,
        status: str = "bad_trap",
        labels: tuple[str, ...] = ("built", "ran", "bad_trap"),
        notes: str | None = None,
    ):
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            coverage_path = tmp / "vector_mmu_coverage.json"
            coverage_path.write_text(
                json.dumps(
                    {
                        "kind": "vector_mmu_coverage",
                        "suite": suite_name,
                        "seed": 23,
                        "state": "generated_not_run",
                        "items": [
                            {
                                **item,
                                "state": "generated_not_run",
                            }
                            for item in coverage_items
                        ],
                    }
                )
            )
            artifact = model.BuildArtifact(
                suite_name=suite_name,
                build_dir=tmp,
                generated_suite_path=tmp / "generated_suite.c",
                elf_path=tmp / "test.elf",
                bin_path=tmp / "test.bin",
                disasm_path=tmp / "disasm",
                vector_mmu_coverage_path=coverage_path,
            )
            prepared = run_batch._PreparedSeedRun(
                seed=23,
                plan=model.ComposePlan(
                    suite_name=suite_name,
                    target="xiangshan-verilator",
                    seed=23,
                    snippet_ids=(),
                    snippets=(),
                    vector_mmu_coverage=coverage_items,
                ),
                artifact=artifact,
                run_artifacts=model.RunSeedArtifacts(
                    suite_name=suite_name,
                    target="xiangshan-verilator",
                    seed=23,
                    run_batch="vector-coverage-partial",
                    build_artifact=artifact,
                    stdout_log_path=tmp / "stdout.log",
                    stderr_log_path=tmp / "stderr.log",
                    run_meta_path=tmp / "run_meta.json",
                    wave_path=tmp / "wave",
                ),
                stdout_log_path=tmp / "stdout.log",
                stderr_log_path=tmp / "stderr.log",
                run_meta_path=tmp / "run_meta.json",
                wave_path=tmp / "wave",
            )

            entry = run_batch._completed_entry(
                prepared=prepared,
                target_result=model.TargetRunResult(
                    status=status,
                    labels=labels,
                    notes=notes if notes is not None else f"Unknown trap code: {finish_code}",
                    returncode=0,
                    finish_code=finish_code,
                ),
            )

            vector_coverage = json.loads(coverage_path.read_text())

        return entry, vector_coverage

    def test_normalize_seeds_accepts_single_list_and_range(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")

        self.assertEqual((1234,), run_batch.normalize_seeds(seed=1234, seeds=None, seed_range=None))
        self.assertEqual((1, 2, 3), run_batch.normalize_seeds(seed=None, seeds="1,2,3", seed_range=None))
        self.assertEqual((0, 1, 2, 3), run_batch.normalize_seeds(seed=None, seeds=None, seed_range="0:3"))

    def test_normalize_seeds_rejects_missing_selector_and_invalid_inputs(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")

        with self.assertRaisesRegex(ValueError, "one seed selector"):
            run_batch.normalize_seeds(seed=None, seeds=None, seed_range=None)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            run_batch.normalize_seeds(seed=-1, seeds=None, seed_range=None)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_batch.normalize_seeds(seed=None, seeds="1,2,2", seed_range=None)
        with self.assertRaisesRegex(ValueError, "invalid seed"):
            run_batch.normalize_seeds(seed=None, seeds="1,,3", seed_range=None)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            run_batch.normalize_seeds(seed=None, seeds="-1,2", seed_range=None)
        with self.assertRaisesRegex(ValueError, "invalid seed range"):
            run_batch.normalize_seeds(seed=None, seeds=None, seed_range="3:0")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            run_batch.normalize_seeds(seed=None, seeds=None, seed_range="-1:1")

    def test_default_run_batch_id_is_unique_batch_scoped(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")

        batch_a = run_batch._default_run_batch_id()
        batch_b = run_batch._default_run_batch_id()

        self.assertTrue(batch_a.startswith("batch_"))
        self.assertTrue(batch_b.startswith("batch_"))
        self.assertNotEqual(batch_a, batch_b)

    def test_cli_run_invokes_batch_with_normalized_seeds(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [{"seed": 4, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seeds", "4,5,6"])

        self.assertEqual(0, rc)
        run_mock.assert_called_once()
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml", kwargs["suite_path"])
        self.assertEqual((4, 5, 6), kwargs["seed_values"])
        self.assertIsNone(kwargs["run_batch_id"])
        self.assertEqual(1, kwargs["jobs"])

    def test_cli_run_passes_jobs_to_batch_runner(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [{"seed": 4, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(
                    [
                        "run",
                        "suites/vsetvl_interrupt_path_poc.yaml",
                        "--seeds",
                        "4,5,6",
                        "--jobs",
                        "3",
                    ]
                )

        self.assertEqual(0, rc)
        self.assertEqual(3, run_mock.call_args.kwargs["jobs"])

    def test_cli_run_invokes_batch_with_single_seed_and_range(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [{"seed": 7, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed", "7"])
        self.assertEqual(0, rc)
        self.assertEqual((7,), run_mock.call_args.kwargs["seed_values"])
        self.assertIsNone(run_mock.call_args.kwargs["run_batch_id"])

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [{"seed": 8, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed-range", "8:10"])
        self.assertEqual(0, rc)
        self.assertEqual((8, 9, 10), run_mock.call_args.kwargs["seed_values"])
        self.assertIsNone(run_mock.call_args.kwargs["run_batch_id"])

    def test_cli_run_rejects_non_positive_jobs(self) -> None:
        cli = importlib.import_module("generator.cli")

        with self.assertRaises(SystemExit) as ctx:
            cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed", "7", "--jobs", "0"])

        self.assertEqual("jobs must be positive", str(ctx.exception))

    def test_cli_run_passes_explicit_batch_id(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "batch_meta.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "repro_4658",
                        "entries": [{"seed": 4658, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(
                    [
                        "run",
                        "suites/vsetvl_interrupt_path_poc.yaml",
                        "--seed",
                        "4658",
                        "--batch-id",
                        "repro_4658",
                    ]
                )

        self.assertEqual(0, rc)
        self.assertEqual("repro_4658", run_mock.call_args.kwargs["run_batch_id"])

    def test_cli_run_passes_jobs_and_batch_id_together(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "parallel-demo",
                        "entries": [{"seed": 1, "status": "ran", "labels": ["built", "ran"]}],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                rc = cli.main(
                    [
                        "run",
                        "suites/vsetvl_interrupt_path_poc.yaml",
                        "--seeds",
                        "1,2",
                        "--jobs",
                        "2",
                        "--batch-id",
                        "parallel-demo",
                    ]
                )

        self.assertEqual(0, rc)
        self.assertEqual(2, run_mock.call_args.kwargs["jobs"])
        self.assertEqual("parallel-demo", run_mock.call_args.kwargs["run_batch_id"])

    def test_cli_run_reports_clean_seed_validation_error(self) -> None:
        cli = importlib.import_module("generator.cli")

        with self.assertRaises(SystemExit) as ctx:
            cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seeds", "1,,3"])
        self.assertEqual("invalid seed list contains an empty seed", str(ctx.exception))

    def test_cli_run_rejects_negative_seed_without_emitting_ledger(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path) as run_mock:
                with self.assertRaises(SystemExit) as ctx:
                    cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed", "-1"])

        self.assertIn("non-negative", str(ctx.exception))
        run_mock.assert_not_called()

    def test_cli_run_returns_nonzero_when_batch_has_failure_entries(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [
                            {
                                "seed": 1,
                                "status": "error",
                                "labels": ["error"],
                            }
                        ],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path):
                rc = cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed", "7"])

        self.assertNotEqual(0, rc)

    def test_cli_run_returns_zero_when_all_batch_entries_succeed(self) -> None:
        cli = importlib.import_module("generator.cli")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "run_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "suite": "demo",
                        "target": "xiangshan-verilator",
                        "run_batch": "batch",
                        "entries": [
                            {
                                "seed": 1,
                                "status": "ran",
                                "labels": ["built", "ran"],
                            }
                        ],
                    }
                )
            )
            with mock.patch.object(cli, "run_suite_batch", return_value=ledger_path):
                rc = cli.main(["run", "suites/vsetvl_interrupt_path_poc.yaml", "--seed", "7"])

        self.assertEqual(0, rc)

    def test_xiangshan_runner_falls_back_to_path_when_xs_env_is_absent(self) -> None:
        module = load_xiangshan_run_target()

        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            emu_path = tool_dir / "emu"
            emu_path.write_text("#!/bin/sh\nexit 0\n")
            emu_path.chmod(0o755)

            with mock.patch.dict(
                module.os.environ,
                {
                    "PATH": str(tool_dir),
                    "SNIPPETGEN_XS_ENV_SH": str(tool_dir / "missing-env.sh"),
                },
                clear=True,
            ):
                resolved = module._emu_path(module._xs_env())

        self.assertEqual(emu_path, resolved)

    def test_xiangshan_runner_does_not_infer_machine_specific_xs_env_path(self) -> None:
        module = load_xiangshan_run_target()

        with mock.patch.dict(
            module.os.environ,
            {"PATH": "/usr/bin:/bin"},
            clear=True,
        ):
            env = module._xs_env()

        self.assertNotIn("XS_PROJECT_ROOT", env)
        self.assertNotIn("NOOP_HOME", env)
        self.assertNotIn("NEMU_HOME", env)

    def test_xiangshan_runner_uses_xs_env_paths_and_diff_reference(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 0\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=build_dir / "lightsss-wave",
            )

            captured: dict[str, object] = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["env"] = kwargs["env"]
                kwargs["stdout"].write("HIT GOOD TRAP\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=True,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("ran", result.status)
        self.assertIn("ran", result.labels)
        self.assertIsNone(result.runner_profile)
        self.assertEqual(str(emu_path), result.runner_path)
        self.assertEqual(str(diff_path), result.diff_path)
        command = captured["command"]
        self.assertEqual(str(emu_path), command[0])
        self.assertIn("--diff", command)
        self.assertIn(str(diff_path), command)
        self.assertNotIn("--no-diff", command)
        self.assertIn("--enable-fork", command)
        self.assertIn("-X", command)
        self.assertEqual("10", command[command.index("-X") + 1])
        self.assertIn("--wave-path", command)
        self.assertIn(str(build_dir / "lightsss-wave"), command)
        self.assertNotIn("--dump-wave", command)

    def test_xiangshan_runner_default_budget_covers_mmu_pilot_path(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 0\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=build_dir / "lightsss-wave",
            )

            captured: dict[str, object] = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["timeout"] = kwargs["timeout"]
                kwargs["stdout"].write("HIT GOOD TRAP\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=True,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=None)

        self.assertEqual("ran", result.status)
        command = captured["command"]
        self.assertEqual("120000", command[command.index("-C") + 1])
        self.assertEqual("120000", command[command.index("-I") + 1])
        self.assertEqual(1800, captured["timeout"])

    def test_xiangshan_runner_classifies_limit_exceeded_from_logs(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 0\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
            )

            def fake_run(command, **kwargs):
                kwargs["stdout"].write("Core 0: EXCEEDING CYCLE/INSTR LIMIT at pc = 0x80000000\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("limit_exceeded", result.status)
        self.assertIn("limit_exceeded", result.labels)

    def test_xiangshan_runner_classifies_bad_trap_from_logs(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
            )

            def fake_run(command, **kwargs):
                kwargs["stdout"].write("Core 0: HIT BAD TRAP at pc = 0x8000002c\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 1)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("bad_trap", result.status)
        self.assertIn("bad_trap", result.labels)

    def test_xiangshan_runner_sets_finish_code_one_for_bad_trap(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
            )

            def fake_run(command, **kwargs):
                kwargs["stdout"].write("Core 0: HIT BAD TRAP at pc = 0x8000002c\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 1)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("bad_trap", result.status)
        self.assertEqual(1, result.finish_code)

    def test_xiangshan_runner_classifies_unknown_trap_code_from_logs(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
            )

            def fake_run(command, **kwargs):
                kwargs["stderr"].write("Core 0: Unknown trap code: 27\n")
                kwargs["stderr"].flush()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("bad_trap", result.status)
        self.assertIn("bad_trap", result.labels)
        self.assertEqual("Unknown trap code: 27", result.notes)
        self.assertEqual(27, result.finish_code)

    def test_xiangshan_runner_classifies_abort_from_logs(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=build_dir / "lightsss-wave",
            )

            def fake_run(command, **kwargs):
                kwargs["stdout"].write("Assertion failed at /tmp/Rob.sv:1.\nCore 0: ABORT at pc = 0x80000174\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 1)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("abort", result.status)
        self.assertIn("abort", result.labels)
        self.assertIn("rtl_assert", result.labels)
        self.assertEqual("RTL assertion", result.notes)

    def test_xiangshan_runner_classifies_plain_abort_without_assert_label(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=build_dir / "lightsss-wave",
            )

            def fake_run(command, **kwargs):
                kwargs["stdout"].write("Core 0: ABORT at pc = 0x80000174\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 1)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("abort", result.status)
        self.assertIn("abort", result.labels)
        self.assertNotIn("rtl_assert", result.labels)
        self.assertEqual("ABORT", result.notes)

    def test_xiangshan_runner_plain_abort_does_not_confuse_perf_mismatch_with_difftest(self) -> None:
        module = load_xiangshan_run_target()

        result = module._classify_result(
            stdout_text="The first instruction of core 0 has commited. Difftest enabled.\nCore 0: ABORT at pc = 0x80000174\n",
            stderr_text="[PERF] load_to_load_forward_fail_wakeup_mismatch, 0\n",
            returncode=1,
        )

        self.assertEqual("abort", result.status)
        self.assertIn("abort", result.labels)
        self.assertNotIn("difftest_mismatch", result.labels)

    def test_xiangshan_runner_classifies_difftest_mismatch_from_logs(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xs_env_root = root / "xs-env"
            env_sh = xs_env_root / "env.sh"
            emu_path = xs_env_root / "XiangShan" / "build" / "verilator-compile" / "emu"
            diff_path = xs_env_root / "NEMU" / "build" / "riscv64-nemu-interpreter-so"
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            emu_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            build_dir.mkdir(parents=True, exist_ok=True)

            env_sh.write_text("#!/bin/sh\n")
            emu_path.write_text("#!/bin/sh\nexit 1\n")
            emu_path.chmod(0o755)
            diff_path.write_text("stub diff\n")
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=build_dir / "lightsss-wave",
            )

            def fake_run(command, **kwargs):
                kwargs["stderr"].write("Difftest mismatch: pc expected 0x80000000 actual 0x80000004\n")
                kwargs["stderr"].flush()
                return subprocess.CompletedProcess(command, 1)

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_XS_ENV_SH": str(env_sh)},
                clear=False,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("difftest_mismatch", result.status)
        self.assertIn("difftest_mismatch", result.labels)
        self.assertEqual("difftest mismatch", result.notes)

    def test_xiangshan_runner_prioritizes_failure_markers_over_good_trap(self) -> None:
        module = load_xiangshan_run_target()

        mismatch_result = module._classify_result(
            stdout_text="HIT GOOD TRAP\n",
            stderr_text="Difftest mismatch: pc expected 0x80000000 actual 0x80000004\n",
            returncode=1,
        )
        critical_result = module._classify_result(
            stdout_text="HIT GOOD TRAP\nCore 0 dump: HIT CRITICAL ERROR: please check if software cause a double trap.\n",
            stderr_text="",
            returncode=1,
        )

        self.assertEqual("difftest_mismatch", mismatch_result.status)
        self.assertIn("difftest_mismatch", mismatch_result.labels)
        self.assertEqual("critical_error", critical_result.status)
        self.assertIn("critical_error", critical_result.labels)

    def test_xiangshan_runner_missing_profile_is_run_infra_fail(self) -> None:
        module = load_xiangshan_run_target()

        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_dir = root / "build"
            bin_path = build_dir / "test.bin"
            elf_path = build_dir / "test.elf"
            stdout_log_path = build_dir / "stdout.log"
            stderr_log_path = build_dir / "stderr.log"
            run_meta_path = build_dir / "run_meta.json"

            build_dir.mkdir(parents=True, exist_ok=True)
            bin_path.write_bytes(b"\x00")
            elf_path.write_bytes(b"\x00")
            stdout_log_path.write_text("")
            stderr_log_path.write_text("")

            artifacts = model.RunSeedArtifacts(
                suite_name="demo",
                target="xiangshan-verilator",
                seed=4660,
                run_batch="batch",
                build_artifact=model.BuildArtifact(
                    suite_name="demo",
                    build_dir=build_dir,
                    generated_suite_path=build_dir / "generated_suite.c",
                    elf_path=elf_path,
                    bin_path=bin_path,
                    build_manifest_path=build_dir / "build_manifest.json",
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                runner_profile="missing-profile",
            )

            with mock.patch.dict(
                module.os.environ,
                {"SNIPPETGEN_KMH_RUNNER_MANIFEST": str(root / "missing-manifest.json")},
                clear=True,
            ):
                result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("run_infra_fail", result.status)
        self.assertIn("run_infra_fail", result.labels)
        self.assertIn("runner_profile", result.labels)

    def test_run_batch_writes_seed_isolated_artifacts_and_batch_meta(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            self.assertEqual(ROOT, repo_root)
            self.assertEqual("xiangshan-verilator", target)

            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("fake stdout\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes="",
                    returncode=0,
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(11, 12),
            target_loader=fake_target_loader,
            run_batch_id="test-batch",
        )

        self.assertTrue(ledger_path.is_file())
        ledger = json.loads(ledger_path.read_text())
        batch_root = self.run_root / "test-batch"
        self.assertEqual("vsetvl_interrupt_path_poc", ledger["suite"])
        self.assertEqual("xiangshan-verilator", ledger["target"])
        self.assertEqual("test-batch", ledger["run_batch"])
        self.assertEqual([11, 12], [entry["seed"] for entry in ledger["entries"]])
        self.assertEqual(str(batch_root / "batch_meta.json"), str(ledger_path))
        self.assertFalse((self.run_root / "run_ledger.json").exists())

        for seed in (11, 12):
            seed_dir = batch_root / f"seed_{seed}"
            with self.subTest(seed=seed):
                self.assertTrue((seed_dir / "generated_suite.c").is_file())
                self.assertTrue((seed_dir / "test.elf").is_file())
                self.assertTrue((seed_dir / "test.bin").is_file())
                self.assertTrue((seed_dir / "disasm").is_file())
                self.assertTrue((seed_dir / "stdout.log").is_file())
                self.assertTrue((seed_dir / "stderr.log").is_file())
                self.assertTrue((seed_dir / "run_meta.json").is_file())
                self.assertEqual(
                    str(seed_dir / "lightsss-wave"),
                    ledger["entries"][seed - 11]["wave_path"],
                )
                self.assertEqual(
                    str(seed_dir / "disasm"),
                    ledger["entries"][seed - 11]["disasm"],
                )
                self.assertIsNone(ledger["entries"][seed - 11]["mmu_coverage_ledger"])
                self.assertIsNone(ledger["entries"][seed - 11]["vector_mmu_coverage"])
                run_meta = json.loads((seed_dir / "run_meta.json").read_text())
                self.assertIsNone(run_meta["mmu_coverage_ledger"])
                self.assertIsNone(run_meta["vector_mmu_coverage"])

    def test_run_batch_writes_finish_code_to_run_meta_and_batch_meta(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("")
                artifacts.stderr_log_path.write_text("Core 0: Unknown trap code: 27\n")
                return model.TargetRunResult(
                    status="bad_trap",
                    labels=("built", "ran", "bad_trap"),
                    notes="Unknown trap code: 27",
                    returncode=0,
                    finish_code=27,
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(11,),
            target_loader=fake_target_loader,
            run_batch_id="finish-code-batch",
        )

        ledger = json.loads(ledger_path.read_text())
        seed_dir = self.run_root / "finish-code-batch" / "seed_11"
        run_meta = json.loads((seed_dir / "run_meta.json").read_text())

        self.assertEqual(27, ledger["entries"][0]["finish_code"])
        self.assertEqual(27, run_meta["finish_code"])

    def test_run_batch_preserves_input_seed_order_under_parallel_completion(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")
        completion_order: list[int] = []

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                if artifacts.seed == 11:
                    time.sleep(0.05)
                else:
                    time.sleep(0.01)
                completion_order.append(artifacts.seed)
                artifacts.stdout_log_path.write_text(f"seed {artifacts.seed}\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes="",
                    returncode=0,
                )

            return run_target

        def fake_emit(plan, generated_suite_path):
            generated_suite_path.parent.mkdir(parents=True, exist_ok=True)
            generated_suite_path.write_text("int main(void) { return 0; }\n")

        def fake_build(repo_root, plan, artifact):
            artifact.build_dir.mkdir(parents=True, exist_ok=True)
            artifact.elf_path.write_bytes(b"\x00")
            artifact.bin_path.write_bytes(b"\x00")
            artifact.disasm_path.write_text("")

        with mock.patch.object(run_batch, "emit_harness", side_effect=fake_emit):
            with mock.patch.object(run_batch, "build_artifacts", side_effect=fake_build):
                ledger_path = run_batch.run_suite_batch(
                    repo_root=ROOT,
                    suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
                    seed_values=(11, 12),
                    target_loader=fake_target_loader,
                    run_batch_id="parallel-order",
                    timeout_s=5,
                    jobs=2,
                )

        payload = json.loads(ledger_path.read_text())
        self.assertEqual([12, 11], completion_order)
        self.assertEqual([11, 12], [entry["seed"] for entry in payload["entries"]])

    def test_run_batch_continues_other_runs_when_one_seed_errors(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")
        seen: list[int] = []

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                seen.append(artifacts.seed)
                artifacts.stdout_log_path.write_text("")
                if artifacts.seed == 21:
                    artifacts.stderr_log_path.write_text("simulated run failure\n")
                    raise RuntimeError("simulated run failure")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes="",
                    returncode=0,
                )

            return run_target

        def fake_emit(plan, generated_suite_path):
            generated_suite_path.parent.mkdir(parents=True, exist_ok=True)
            generated_suite_path.write_text("int main(void) { return 0; }\n")

        def fake_build(repo_root, plan, artifact):
            artifact.build_dir.mkdir(parents=True, exist_ok=True)
            artifact.elf_path.write_bytes(b"\x00")
            artifact.bin_path.write_bytes(b"\x00")
            artifact.disasm_path.write_text("")

        with mock.patch.object(run_batch, "emit_harness", side_effect=fake_emit):
            with mock.patch.object(run_batch, "build_artifacts", side_effect=fake_build):
                ledger_path = run_batch.run_suite_batch(
                    repo_root=ROOT,
                    suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
                    seed_values=(21, 22),
                    target_loader=fake_target_loader,
                    run_batch_id="parallel-failure",
                    timeout_s=5,
                    jobs=2,
                )

        payload = json.loads(ledger_path.read_text())
        self.assertEqual([21, 22], sorted(seen))
        self.assertEqual(["run_infra_fail", "ran"], [entry["status"] for entry in payload["entries"]])
        self.assertIn("run_infra_fail", payload["entries"][0]["labels"])

    def test_failed_run_still_writes_meta_and_logs(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("")
                artifacts.stderr_log_path.write_text("simulated failure\n")
                raise RuntimeError("simulated target adapter failure")

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(21,),
            target_loader=fake_target_loader,
            run_batch_id="failing-batch",
        )

        ledger = json.loads(ledger_path.read_text())
        self.assertEqual("run_infra_fail", ledger["entries"][0]["status"])
        self.assertIn("run_infra_fail", ledger["entries"][0]["labels"])

        seed_dir = self.run_root / "failing-batch" / "seed_21"
        self.assertTrue((seed_dir / "stdout.log").is_file())
        self.assertTrue((seed_dir / "stderr.log").is_file())
        self.assertTrue((seed_dir / "run_meta.json").is_file())

    def test_run_batch_classifies_build_prepare_failure_as_build_fail(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                raise AssertionError("target runner should not run after build failure")

            return run_target

        def fake_emit(plan, generated_suite_path):
            generated_suite_path.parent.mkdir(parents=True, exist_ok=True)
            generated_suite_path.write_text("int main(void) { return 0; }\n")

        def fake_build(repo_root, plan, artifact):
            raise RuntimeError("simulated build failure")

        with mock.patch.object(run_batch, "emit_harness", side_effect=fake_emit):
            with mock.patch.object(run_batch, "build_artifacts", side_effect=fake_build):
                ledger_path = run_batch.run_suite_batch(
                    repo_root=ROOT,
                    suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
                    seed_values=(23,),
                    target_loader=fake_target_loader,
                    run_batch_id="build-failure",
                )

        ledger = json.loads(ledger_path.read_text())
        run_meta = json.loads((self.run_root / "build-failure" / "seed_23" / "run_meta.json").read_text())
        self.assertEqual("build_fail", ledger["entries"][0]["status"])
        self.assertIn("build_fail", ledger["entries"][0]["labels"])
        self.assertEqual("build_fail", run_meta["status"])

    def test_run_batch_default_batch_id_avoids_shared_top_level_writes(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("fake stdout\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes="",
                    returncode=0,
                )

            return run_target

        first = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(31,),
            target_loader=fake_target_loader,
        )
        second = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(32,),
            target_loader=fake_target_loader,
        )

        self.assertNotEqual(first, second)
        self.assertEqual("batch_meta.json", first.name)
        self.assertEqual("batch_meta.json", second.name)
        self.assertTrue(first.parent.parent == self.run_root)
        self.assertTrue(second.parent.parent == self.run_root)
        self.assertFalse((self.run_root / "run_ledger.json").exists())

    def test_run_batch_explicit_batch_id_can_be_reused_and_recreates_logs(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")
        call_count = 0

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                nonlocal call_count
                call_count += 1
                artifacts.stdout_log_path.write_text(f"stdout run {call_count}\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes=f"run {call_count}",
                    returncode=0,
                )

            return run_target

        batch_id = "reused-batch"
        first = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(41,),
            target_loader=fake_target_loader,
            run_batch_id=batch_id,
        )

        seed_dir = self.run_root / batch_id / "seed_41"
        self.assertTrue((seed_dir / "stdout.log").is_file())
        (seed_dir / "stdout.log").unlink()

        second = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(41,),
            target_loader=fake_target_loader,
            run_batch_id=batch_id,
        )

        self.assertEqual(first, second)
        self.assertTrue((seed_dir / "stdout.log").is_file())
        self.assertEqual("stdout run 2\n", (seed_dir / "stdout.log").read_text())

        ledger = json.loads(second.read_text())
        run_meta = json.loads((seed_dir / "run_meta.json").read_text())
        self.assertEqual("ran", ledger["entries"][0]["status"])
        self.assertEqual("ran", run_meta["status"])
        self.assertEqual("run 2", ledger["entries"][0]["notes"])
        self.assertEqual("run 2", run_meta["notes"])

    def test_run_batch_marks_mmu_coverage_as_ran_for_successful_seed(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("HIT GOOD TRAP\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran", "good_trap"),
                    notes="HIT GOOD TRAP",
                    returncode=0,
                    finish_code=0,
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "mmu_pilot_rules_poc.yaml",
            seed_values=(17,),
            target_loader=fake_target_loader,
            run_batch_id="mmu-coverage-demo",
        )

        batch_ledger = json.loads(ledger_path.read_text())
        seed_dir = self.mmu_run_root / "mmu-coverage-demo" / "seed_17"
        if batch_ledger["entries"][0]["status"] in {"error", "build_fail"}:
            error_note = batch_ledger["entries"][0]["notes"]
            if (
                "unknown z ISA extension `zicbop'" in error_note
                or "cannot find default versions of the ISA extension `v'" in error_note
            ):
                self.skipTest("installed RISC-V toolchain lacks XiangShan ISA extensions")
        coverage_ledger = json.loads((seed_dir / "mmu_coverage_ledger.json").read_text())
        rule_states = {entry["id"]: entry["state"] for entry in coverage_ledger["rules"]}
        tag_states = {entry["tag"]: entry["state"] for entry in coverage_ledger["coverage_tags"]}

        self.assertEqual("ran", batch_ledger["entries"][0]["status"])
        self.assertTrue(batch_ledger["entries"][0]["mmu_coverage_ledger"].endswith("mmu_coverage_ledger.json"))
        self.assertEqual("ran", rule_states["bare_identity"])
        self.assertEqual("ran", rule_states["two_stage_fault"])
        self.assertEqual("ran", tag_states["guest.two_stage"])
        self.assertEqual("ran", tag_states["requestor.load"])

    def test_run_batch_marks_vector_mmu_coverage_by_target_result(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            def run_target(*, artifacts, timeout_s):
                artifacts.stdout_log_path.write_text("HIT GOOD TRAP\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran", "good_trap"),
                    notes="HIT GOOD TRAP",
                    returncode=0,
                    finish_code=0,
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "kmh_mmu_layer1_v2_vector_forms.yaml",
            seed_values=(17,),
            target_loader=fake_target_loader,
            run_batch_id="vector-coverage-demo",
        )

        batch_ledger = json.loads(ledger_path.read_text())
        seed_dir = ROOT / "build" / "kmh_mmu_layer1_v2_vector_forms" / "runs" / "vector-coverage-demo" / "seed_17"
        if batch_ledger["entries"][0]["status"] in {"error", "build_fail"}:
            error_note = batch_ledger["entries"][0]["notes"]
            if (
                "unknown z ISA extension `zicbop'" in error_note
                or "cannot find default versions of the ISA extension `v'" in error_note
            ):
                self.skipTest("installed RISC-V toolchain lacks XiangShan ISA extensions")
        vector_coverage = json.loads((seed_dir / "vector_mmu_coverage.json").read_text())

        self.assertTrue(batch_ledger["entries"][0]["vector_mmu_coverage"].endswith("vector_mmu_coverage.json"))
        self.assertEqual("ran", vector_coverage["state"])
        self.assertTrue(all(item["state"] == "ran" for item in vector_coverage["items"]))

    def test_run_batch_preserves_partial_vector_mmu_coverage_for_late_failure(self) -> None:
        coverage_items = tuple(
            {
                "id": coverage_id,
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": fail_codes,
            }
            for coverage_id, fail_codes in (
                ("v2_vector_forms_strided_hit", "42"),
                ("v2_vector_forms_strided_fault", "43"),
                ("v2_vector_forms_indexed_hit", "44"),
                ("v2_vector_forms_indexed_fault", "45"),
                ("v2_vector_forms_segment_hit", "46"),
                ("v2_vector_forms_fof_later_fault", "47"),
                ("v2_vector_forms_fof_first_fault", "48"),
                ("v2_vector_forms_vstart_store", "49"),
            )
        )

        entry, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_forms",
            coverage_items=coverage_items,
            finish_code=45,
        )

        item_states = {item["id"]: item["state"] for item in vector_coverage["items"]}
        self.assertEqual("bad_trap", entry.status)
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertEqual("ran", item_states["v2_vector_forms_strided_hit"])
        self.assertEqual("ran", item_states["v2_vector_forms_strided_fault"])
        self.assertEqual("ran", item_states["v2_vector_forms_indexed_hit"])
        self.assertEqual("failed_or_blocked", item_states["v2_vector_forms_indexed_fault"])
        self.assertEqual("generated_not_run", item_states["v2_vector_forms_vstart_store"])

    def test_run_batch_preserves_partial_vector_mmu_coverage_for_noncontiguous_fail_codes(self) -> None:
        coverage_items = tuple(
            {
                "id": coverage_id,
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": fail_codes,
            }
            for coverage_id, fail_codes in (
                ("v2_vector_faults_cross_invalid_load", "32"),
                ("v2_vector_faults_cross_invalid_store", "33"),
                ("v2_vector_faults_cross_no_perm_load", "38"),
                ("v2_vector_faults_cross_no_perm_store", "39"),
                ("v2_vector_faults_masked_off_suppression", "34,35"),
                ("v2_vector_faults_masked_on_trigger", "36,37"),
            )
        )

        _, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_faults",
            coverage_items=coverage_items,
            finish_code=36,
        )

        item_states = {item["id"]: item["state"] for item in vector_coverage["items"]}
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertEqual("ran", item_states["v2_vector_faults_cross_no_perm_store"])
        self.assertEqual("ran", item_states["v2_vector_faults_masked_off_suppression"])
        self.assertEqual("failed_or_blocked", item_states["v2_vector_faults_masked_on_trigger"])

    def test_run_batch_distinguishes_first_failed_vector_item_from_unrun_items(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_forms_strided_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "strided",
                "eew": "e64",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "42",
            },
            {
                "id": "v2_vector_forms_strided_fault",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "strided",
                "eew": "e64",
                "page_boundary": "cross_page",
                "fault": "page_fault",
                "attribute": "normal",
                "fail_codes": "43",
            },
        )

        _, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_forms",
            coverage_items=coverage_items,
            finish_code=42,
        )

        item_states = {item["id"]: item["state"] for item in vector_coverage["items"]}
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertEqual("failed_or_blocked", item_states["v2_vector_forms_strided_hit"])
        self.assertEqual("generated_not_run", item_states["v2_vector_forms_strided_fault"])

    def test_run_batch_keeps_vector_items_unrun_for_setup_failure_before_first_case(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_widths_e8_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "22",
            },
            {
                "id": "v2_vector_widths_e16_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e16",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "23",
            },
        )

        entry, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_widths",
            coverage_items=coverage_items,
            finish_code=21,
        )

        self.assertEqual("bad_trap", entry.status)
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertTrue(all(item["state"] == "generated_not_run" for item in vector_coverage["items"]))

    def test_run_batch_marks_completed_prefix_for_setup_failure_between_cases(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_smoke_bare_unit_e8_hit",
                "requestor": "vector_load_store",
                "mode": "bare",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "11",
            },
            {
                "id": "v2_vector_smoke_sv39_unit_e8_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "13",
            },
            {
                "id": "v2_vector_smoke_sv39_load_page_fault",
                "requestor": "vector_load",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "load_page_fault",
                "attribute": "normal",
                "fail_codes": "15",
            },
        )

        _, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_smoke",
            coverage_items=coverage_items,
            finish_code=12,
        )

        item_states = {item["id"]: item["state"] for item in vector_coverage["items"]}
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertEqual("ran", item_states["v2_vector_smoke_bare_unit_e8_hit"])
        self.assertEqual("generated_not_run", item_states["v2_vector_smoke_sv39_unit_e8_hit"])
        self.assertEqual("generated_not_run", item_states["v2_vector_smoke_sv39_load_page_fault"])

    def test_run_batch_keeps_unstructured_vector_bad_trap_as_blocked(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_widths_e8_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "22",
            },
        )

        _, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_widths",
            coverage_items=coverage_items,
            finish_code=1,
            notes="HIT BAD TRAP",
        )

        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertEqual("failed_or_blocked", vector_coverage["items"][0]["state"])

    def test_run_batch_keeps_vector_items_unrun_for_infra_failure_before_run(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_widths_e8_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "22",
            },
            {
                "id": "v2_vector_widths_e16_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e16",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "23",
            },
        )

        entry, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_widths",
            coverage_items=coverage_items,
            finish_code=None,
            status="run_infra_fail",
            labels=("run_infra_fail", "runner_missing"),
            notes="runner missing: emu",
        )

        self.assertEqual("run_infra_fail", entry.status)
        self.assertEqual("generated_not_run", vector_coverage["state"])
        self.assertTrue(all(item["state"] == "generated_not_run" for item in vector_coverage["items"]))

    def test_run_batch_marks_vector_timeout_as_attempted_blocked(self) -> None:
        coverage_items = (
            {
                "id": "v2_vector_widths_e8_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e8",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "22",
            },
            {
                "id": "v2_vector_widths_e16_unit_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "unit_stride",
                "eew": "e16",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "23",
            },
        )

        entry, vector_coverage = self._vector_coverage_after_target_result(
            suite_name="kmh_mmu_layer1_v2_vector_widths",
            coverage_items=coverage_items,
            finish_code=None,
            status="timeout",
            labels=("built", "timeout"),
            notes="timeout after 1800s",
        )

        self.assertEqual("timeout", entry.status)
        self.assertEqual("failed_or_blocked", vector_coverage["state"])
        self.assertTrue(all(item["state"] == "failed_or_blocked" for item in vector_coverage["items"]))

    def test_completed_entry_drops_missing_vector_coverage_path_for_build_failure(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        coverage_items = (
            {
                "id": "v2_vector_forms_strided_hit",
                "requestor": "vector_load_store",
                "mode": "host_single_stage",
                "form": "strided",
                "eew": "e64",
                "page_boundary": "single_page",
                "fault": "none",
                "attribute": "normal",
                "fail_codes": "42",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            artifact = model.BuildArtifact(
                suite_name="kmh_mmu_layer1_v2_vector_forms",
                build_dir=tmp,
                generated_suite_path=tmp / "generated_suite.c",
                elf_path=tmp / "test.elf",
                bin_path=tmp / "test.bin",
                disasm_path=tmp / "disasm",
                vector_mmu_coverage_path=tmp / "vector_mmu_coverage.json",
            )
            prepared = run_batch._PreparedSeedRun(
                seed=23,
                plan=model.ComposePlan(
                    suite_name="kmh_mmu_layer1_v2_vector_forms",
                    target="xiangshan-verilator",
                    seed=23,
                    snippet_ids=(),
                    snippets=(),
                    vector_mmu_coverage=coverage_items,
                ),
                artifact=artifact,
                run_artifacts=model.RunSeedArtifacts(
                    suite_name="kmh_mmu_layer1_v2_vector_forms",
                    target="xiangshan-verilator",
                    seed=23,
                    run_batch="vector-build-fail",
                    build_artifact=artifact,
                    stdout_log_path=tmp / "stdout.log",
                    stderr_log_path=tmp / "stderr.log",
                    run_meta_path=tmp / "run_meta.json",
                    wave_path=tmp / "wave",
                ),
                stdout_log_path=tmp / "stdout.log",
                stderr_log_path=tmp / "stderr.log",
                run_meta_path=tmp / "run_meta.json",
                wave_path=tmp / "wave",
            )

            entry = run_batch._completed_entry(
                prepared=prepared,
                target_result=model.TargetRunResult(
                    status="build_fail",
                    labels=("build_fail",),
                    notes="compile failed before vector coverage emission",
                    returncode=None,
                    finish_code=None,
                ),
            )

        payload = run_batch._entry_payload(entry)
        self.assertIsNone(entry.vector_mmu_coverage_path)
        self.assertIsNone(payload["vector_mmu_coverage"])

    def test_run_batch_does_not_mark_mmu_coverage_ran_for_non_good_sim_exit(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            coverage_path = tmp / "mmu_coverage_ledger.json"
            coverage_path.write_text(
                json.dumps(
                    {
                        "suite": "mmu_demo",
                        "selected_rule_ids": ["bare_identity"],
                        "defined_rule_ids": ["bare_identity"],
                        "rules": [
                            {
                                "id": "bare_identity",
                                "symbol": "bare_identity",
                                "coverage_tags": ["requestor.load"],
                                "state": "generated_not_run",
                            }
                        ],
                        "coverage_tags": [
                            {
                                "tag": "requestor.load",
                                "rules": ["bare_identity"],
                                "state": "generated_not_run",
                            }
                        ],
                        "gaps": [],
                    }
                )
            )
            artifact = model.BuildArtifact(
                suite_name="mmu_demo",
                build_dir=tmp,
                generated_suite_path=tmp / "generated_suite.c",
                elf_path=tmp / "test.elf",
                bin_path=tmp / "test.bin",
                disasm_path=tmp / "disasm",
                mmu_coverage_ledger_path=coverage_path,
            )
            prepared = run_batch._PreparedSeedRun(
                seed=19,
                plan=model.ComposePlan(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=19,
                    snippet_ids=(),
                    snippets=(),
                ),
                artifact=artifact,
                run_artifacts=model.RunSeedArtifacts(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=19,
                    run_batch="mmu-coverage-sim-exit",
                    build_artifact=artifact,
                    stdout_log_path=tmp / "stdout.log",
                    stderr_log_path=tmp / "stderr.log",
                    run_meta_path=tmp / "run_meta.json",
                    wave_path=tmp / "wave",
                ),
                stdout_log_path=tmp / "stdout.log",
                stderr_log_path=tmp / "stderr.log",
                run_meta_path=tmp / "run_meta.json",
                wave_path=tmp / "wave",
            )

            entry = run_batch._completed_entry(
                prepared=prepared,
                target_result=model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran", "sim_exit"),
                    notes="simulation exit",
                    returncode=0,
                    finish_code=None,
                ),
            )

            coverage_ledger = json.loads(coverage_path.read_text())

        rule_states = {item["id"]: item["state"] for item in coverage_ledger["rules"]}
        self.assertEqual("ran", entry.status)
        self.assertEqual("generated_not_run", rule_states["bare_identity"])

    def test_run_batch_does_not_infer_mmu_progress_from_host_returncode(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            coverage_path = tmp / "mmu_coverage_ledger.json"
            coverage_path.write_text(
                json.dumps(
                    {
                        "suite": "mmu_demo",
                        "selected_rule_ids": ["bare_identity", "sv39_alias"],
                        "defined_rule_ids": ["bare_identity", "sv39_alias"],
                        "rules": [
                            {
                                "id": "bare_identity",
                                "symbol": "bare_identity",
                                "coverage_tags": ["requestor.load", "page.identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "id": "sv39_alias",
                                "symbol": "sv39_alias",
                                "coverage_tags": ["requestor.hlv", "page.alias"],
                                "state": "generated_not_run",
                            },
                        ],
                        "coverage_tags": [
                            {
                                "tag": "requestor.load",
                                "rules": ["bare_identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "page.identity",
                                "rules": ["bare_identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "requestor.hlv",
                                "rules": ["sv39_alias"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "page.alias",
                                "rules": ["sv39_alias"],
                                "state": "generated_not_run",
                            },
                        ],
                        "gaps": [],
                    }
                )
            )
            artifact = model.BuildArtifact(
                suite_name="mmu_demo",
                build_dir=tmp,
                generated_suite_path=tmp / "generated_suite.c",
                elf_path=tmp / "test.elf",
                bin_path=tmp / "test.bin",
                disasm_path=tmp / "disasm",
                mmu_coverage_ledger_path=coverage_path,
            )
            prepared = run_batch._PreparedSeedRun(
                seed=21,
                plan=model.ComposePlan(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=21,
                    snippet_ids=(),
                    snippets=(),
                    mmu_rule_ids=("bare_identity", "sv39_alias"),
                    mmu_defined_rule_ids=("bare_identity", "sv39_alias"),
                    mmu_coverage_tags=("page.alias", "page.identity", "requestor.hlv", "requestor.load"),
                ),
                artifact=artifact,
                run_artifacts=model.RunSeedArtifacts(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=21,
                    run_batch="mmu-coverage-host-error",
                    build_artifact=artifact,
                    stdout_log_path=tmp / "stdout.log",
                    stderr_log_path=tmp / "stderr.log",
                    run_meta_path=tmp / "run_meta.json",
                    wave_path=tmp / "wave",
                ),
                stdout_log_path=tmp / "stdout.log",
                stderr_log_path=tmp / "stderr.log",
                run_meta_path=tmp / "run_meta.json",
                wave_path=tmp / "wave",
            )

            entry = run_batch._completed_entry(
                prepared=prepared,
                target_result=model.TargetRunResult(
                    status="nonzero_exit",
                    labels=("built", "nonzero_exit"),
                    notes="runner exited with code 65",
                    returncode=65,
                    finish_code=None,
                ),
            )

            coverage_ledger = json.loads(coverage_path.read_text())

        rule_states = {item["id"]: item["state"] for item in coverage_ledger["rules"]}
        tag_states = {item["tag"]: item["state"] for item in coverage_ledger["coverage_tags"]}
        self.assertEqual("nonzero_exit", entry.status)
        self.assertEqual("generated_not_run", rule_states["bare_identity"])
        self.assertEqual("generated_not_run", rule_states["sv39_alias"])
        self.assertEqual("generated_not_run", tag_states["requestor.load"])
        self.assertEqual("generated_not_run", tag_states["requestor.hlv"])

    def test_run_batch_marks_only_completed_mmu_rules_for_partial_runner_failure(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            coverage_path = tmp / "mmu_coverage_ledger.json"
            coverage_path.write_text(
                json.dumps(
                    {
                        "suite": "mmu_demo",
                        "selected_rule_ids": ["bare_identity", "sv39_alias"],
                        "defined_rule_ids": ["bare_identity", "sv39_alias"],
                        "rules": [
                            {
                                "id": "bare_identity",
                                "symbol": "bare_identity",
                                "coverage_tags": ["requestor.load", "page.identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "id": "sv39_alias",
                                "symbol": "sv39_alias",
                                "coverage_tags": ["requestor.hlv", "page.alias"],
                                "state": "generated_not_run",
                            },
                        ],
                        "coverage_tags": [
                            {
                                "tag": "requestor.load",
                                "rules": ["bare_identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "page.identity",
                                "rules": ["bare_identity"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "requestor.hlv",
                                "rules": ["sv39_alias"],
                                "state": "generated_not_run",
                            },
                            {
                                "tag": "page.alias",
                                "rules": ["sv39_alias"],
                                "state": "generated_not_run",
                            },
                        ],
                        "gaps": [],
                    }
                )
            )
            artifact = model.BuildArtifact(
                suite_name="mmu_demo",
                build_dir=tmp,
                generated_suite_path=tmp / "generated_suite.c",
                elf_path=tmp / "test.elf",
                bin_path=tmp / "test.bin",
                disasm_path=tmp / "disasm",
                mmu_coverage_ledger_path=coverage_path,
            )
            prepared = run_batch._PreparedSeedRun(
                seed=23,
                plan=model.ComposePlan(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=23,
                    snippet_ids=(),
                    snippets=(),
                    mmu_rule_ids=("bare_identity", "sv39_alias"),
                    mmu_defined_rule_ids=("bare_identity", "sv39_alias"),
                    mmu_coverage_tags=("page.alias", "page.identity", "requestor.hlv", "requestor.load"),
                ),
                artifact=artifact,
                run_artifacts=model.RunSeedArtifacts(
                    suite_name="mmu_demo",
                    target="xiangshan-verilator",
                    seed=23,
                    run_batch="mmu-coverage-partial",
                    build_artifact=artifact,
                    stdout_log_path=tmp / "stdout.log",
                    stderr_log_path=tmp / "stderr.log",
                    run_meta_path=tmp / "run_meta.json",
                    wave_path=tmp / "wave",
                ),
                stdout_log_path=tmp / "stdout.log",
                stderr_log_path=tmp / "stderr.log",
                run_meta_path=tmp / "run_meta.json",
                wave_path=tmp / "wave",
            )

            entry = run_batch._completed_entry(
                prepared=prepared,
                target_result=model.TargetRunResult(
                    status="bad_trap",
                    labels=("built", "bad_trap"),
                    notes="Unknown trap code: 65",
                    returncode=0,
                    finish_code=65,
                ),
            )

            coverage_ledger = json.loads(coverage_path.read_text())

        rule_states = {item["id"]: item["state"] for item in coverage_ledger["rules"]}
        tag_states = {item["tag"]: item["state"] for item in coverage_ledger["coverage_tags"]}
        self.assertEqual("bad_trap", entry.status)
        self.assertEqual("ran", rule_states["bare_identity"])
        self.assertEqual("generated_not_run", rule_states["sv39_alias"])
        self.assertEqual("ran", tag_states["requestor.load"])
        self.assertEqual("generated_not_run", tag_states["requestor.hlv"])


if __name__ == "__main__":
    unittest.main()
