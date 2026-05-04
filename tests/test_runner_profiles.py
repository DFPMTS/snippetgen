from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RunnerProfileTest(unittest.TestCase):
    def write_manifest(self, root: Path, profiles: list[dict[str, object]]) -> Path:
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "profiles": profiles,
                },
                indent=2,
            )
        )
        return manifest_path

    def write_runner_files(self, root: Path, profile_root: str) -> tuple[Path, Path]:
        emu = root / profile_root / "emu"
        diff = root / profile_root / "riscv64-nemu-interpreter-so"
        emu.parent.mkdir(parents=True, exist_ok=True)
        diff.parent.mkdir(parents=True, exist_ok=True)
        emu.write_text("#!/bin/sh\nexit 0\n")
        emu.chmod(0o755)
        diff.write_text("stub diff\n")
        return emu, diff

    def profile_entry(self, name: str, emu: Path, diff: Path, **extra: object) -> dict[str, object]:
        entry: dict[str, object] = {
            "name": name,
            "xiangshan_revision": f"{name}-xs-rev",
            "nemu_revision": f"{name}-nemu-rev",
            "build_summary": "unit-test profile",
            "difftest": True,
            "wave": False,
            "emu": str(emu),
            "nemu": str(diff),
        }
        entry.update(extra)
        return entry

    def test_resolves_kmh_v2_and_v3_profiles_from_manifest(self) -> None:
        from generator.xsgen.runner_profiles import resolve_runner_profile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            v2_emu, v2_diff = self.write_runner_files(root, "kmh-v2/difftest")
            v3_emu, v3_diff = self.write_runner_files(root, "kmh-v3/difftest")
            manifest = self.write_manifest(
                root,
                [
                    self.profile_entry("kmh-v2/difftest", v2_emu, v2_diff),
                    self.profile_entry("kmh-v3/difftest", v3_emu, v3_diff),
                ],
            )

            v2 = resolve_runner_profile("kmh-v2/difftest", manifest)
            v3 = resolve_runner_profile("kmh-v3/difftest", manifest)

        self.assertEqual("kmh-v2/difftest", v2.name)
        self.assertEqual(v2_emu, v2.emu_path)
        self.assertEqual(v2_diff, v2.diff_path)
        self.assertEqual("kmh-v3/difftest", v3.name)
        self.assertEqual(v3_emu, v3.emu_path)
        self.assertEqual(v3_diff, v3.diff_path)

    def test_default_manifest_path_is_workspace_relative(self) -> None:
        from generator.xsgen.runner_profiles import DEFAULT_RUNNER_MANIFEST_PATH

        self.assertEqual(
            ROOT.parent / "artifacts" / "kmh-runners" / "manifest.json",
            DEFAULT_RUNNER_MANIFEST_PATH,
        )

    def test_rejects_missing_manifest_bad_profile_missing_files_and_alias_collision(self) -> None:
        from generator.xsgen.runner_profiles import resolve_runner_profile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            v2_emu, v2_diff = self.write_runner_files(root, "kmh-v2/difftest")
            missing = root / "missing.json"

            with self.assertRaisesRegex(ValueError, "runner manifest missing"):
                resolve_runner_profile("kmh-v2/difftest", missing)

            manifest = self.write_manifest(root, [self.profile_entry("kmh-v2/difftest", v2_emu, v2_diff)])
            with self.assertRaisesRegex(ValueError, "unknown runner profile"):
                resolve_runner_profile("kmh-v3/difftest", manifest)

            bad_manifest = self.write_manifest(
                root,
                [
                    self.profile_entry(
                        "kmh-v3/difftest",
                        root / "kmh-v3" / "difftest" / "missing-emu",
                        v2_diff,
                    )
                ],
            )
            with self.assertRaisesRegex(ValueError, "runner emu missing"):
                resolve_runner_profile("kmh-v3/difftest", bad_manifest)

            collision_manifest = self.write_manifest(
                root,
                [
                    self.profile_entry("kmh-v2/difftest", v2_emu, v2_diff),
                    self.profile_entry("kmh-v3/difftest", v2_emu, v2_diff),
                ],
            )
            with self.assertRaisesRegex(ValueError, "runner profile alias collision"):
                resolve_runner_profile("kmh-v2/difftest", collision_manifest)

            alias_manifest = self.write_manifest(
                root,
                [
                    self.profile_entry("kmh-v2/difftest", v2_emu, v2_diff),
                    self.profile_entry("kmh-v3/difftest", v2_emu, v2_diff, alias_of="kmh-v2/difftest"),
                ],
            )
            resolved = resolve_runner_profile("kmh-v3/difftest", alias_manifest)

        self.assertEqual("kmh-v3/difftest", resolved.name)
        self.assertEqual("kmh-v2/difftest", resolved.alias_of)

    def test_alias_collision_validation_is_independent_of_manifest_order(self) -> None:
        from generator.xsgen.runner_profiles import resolve_runner_profile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            v2_emu, v2_diff = self.write_runner_files(root, "kmh-v2/difftest")
            manifest = self.write_manifest(
                root,
                [
                    self.profile_entry(
                        "kmh-v3/difftest",
                        v2_emu,
                        v2_diff,
                        alias_of="kmh-v2/difftest",
                    ),
                    self.profile_entry("kmh-v2/difftest", v2_emu, v2_diff),
                ],
            )

            resolved = resolve_runner_profile("kmh-v3/difftest", manifest)

        self.assertEqual("kmh-v3/difftest", resolved.name)
        self.assertEqual("kmh-v2/difftest", resolved.alias_of)

    def test_cli_run_passes_runner_profile_to_batch_runner(self) -> None:
        cli = __import__("generator.cli", fromlist=["main"])

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "batch_meta.json"
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
                        "--seed",
                        "4",
                        "--runner-profile",
                        "kmh-v3/difftest",
                    ]
                )

        self.assertEqual(0, rc)
        self.assertEqual("kmh-v3/difftest", run_mock.call_args.kwargs["runner_profile"])

    def test_xiangshan_target_uses_explicit_profile_without_default_fallback(self) -> None:
        module_path = ROOT / "targets" / "xiangshan-verilator" / "run_target.py"
        spec = importlib.util.spec_from_file_location("xiangshan_profile_run_target_test", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)

        model = __import__("generator.xsgen.model", fromlist=["RunSeedArtifacts"])

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_emu, profile_diff = self.write_runner_files(root, "kmh-v3/difftest")
            fallback_emu, _ = self.write_runner_files(root, "xs-env/XiangShan/build/verilator-compile")
            manifest = self.write_manifest(
                root,
                [self.profile_entry("kmh-v3/difftest", profile_emu, profile_diff)],
            )
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
                wave_path=build_dir / "lightsss-wave",
                runner_profile="kmh-v3/difftest",
            )
            captured: dict[str, object] = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                kwargs["stdout"].write("HIT GOOD TRAP\n")
                kwargs["stdout"].flush()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                module.os.environ,
                {
                    "SNIPPETGEN_KMH_RUNNER_MANIFEST": str(manifest),
                    "NOOP_HOME": str(fallback_emu.parents[2]),
                    "PATH": str(fallback_emu.parent),
                },
                clear=True,
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    result = module.run_target(artifacts=artifacts, timeout_s=5)

        self.assertEqual("ran", result.status)
        self.assertEqual(str(profile_emu), captured["command"][0])
        self.assertEqual("kmh-v3/difftest", result.runner_profile)
        self.assertEqual(str(profile_emu), result.runner_path)
        self.assertEqual(str(profile_diff), result.diff_path)
        self.assertNotEqual(str(fallback_emu), captured["command"][0])

    def test_run_batch_records_runner_profile_metadata(self) -> None:
        run_batch = __import__("generator.xsgen.run_batch", fromlist=["run_suite_batch"])
        model = __import__("generator.xsgen.model", fromlist=["TargetRunResult"])

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
                    runner_profile=artifacts.runner_profile,
                    runner_revision="xs-rev-test",
                    diff_revision="nemu-rev-test",
                    runner_path="/tmp/kmh/emu",
                    diff_path="/tmp/kmh/nemu.so",
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "vsetvl_interrupt_path_poc.yaml",
            seed_values=(101,),
            target_loader=fake_target_loader,
            run_batch_id="runner-profile-meta",
            runner_profile="kmh-v2/difftest",
        )
        ledger = json.loads(ledger_path.read_text())
        run_meta = json.loads((ledger_path.parent / "seed_101" / "run_meta.json").read_text())

        self.assertEqual("kmh-v2/difftest", ledger["entries"][0]["runner_profile"])
        self.assertEqual("xs-rev-test", ledger["entries"][0]["runner_revision"])
        self.assertEqual("nemu-rev-test", run_meta["diff_revision"])
        self.assertEqual("/tmp/kmh/emu", run_meta["runner_path"])
