from pathlib import Path
import importlib
import json
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AMProgramSnippetRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.run_root = ROOT / "build" / "am_hello_main_poc" / "runs"
        if self.run_root.exists():
            shutil.rmtree(self.run_root)

    def test_run_batch_supports_am_program_suite(self) -> None:
        run_batch = importlib.import_module("generator.xsgen.run_batch")
        model = importlib.import_module("generator.xsgen.model")

        def fake_target_loader(repo_root: Path, target: str):
            self.assertEqual(ROOT, repo_root)
            self.assertEqual("xiangshan-verilator", target)

            def run_target(*, artifacts, timeout_s):
                harness = artifacts.build_artifact.generated_suite_path.read_text()
                self.assertIn("xsam_program_entry_am_hello_main", harness)
                artifacts.stdout_log_path.write_text("am hello ran\n")
                artifacts.stderr_log_path.write_text("")
                return model.TargetRunResult(
                    status="ran",
                    labels=("built", "ran"),
                    notes="am program mock run",
                    returncode=0,
                )

            return run_target

        ledger_path = run_batch.run_suite_batch(
            repo_root=ROOT,
            suite_path=ROOT / "suites" / "am_hello_main_poc.yaml",
            seed_values=(101,),
            target_loader=fake_target_loader,
            run_batch_id="am-program-run",
        )

        self.assertTrue(ledger_path.is_file())

        ledger = json.loads(ledger_path.read_text())
        self.assertEqual("am_hello_main_poc", ledger["suite"])
        self.assertEqual("am-program-run", ledger["run_batch"])
        self.assertEqual(1, len(ledger["entries"]))
        self.assertEqual("ran", ledger["entries"][0]["status"])

        seed_dir = self.run_root / "am-program-run" / "seed_101"
        self.assertTrue((seed_dir / "generated_suite.c").is_file())
        self.assertTrue((seed_dir / "test.elf").is_file())
        self.assertTrue((seed_dir / "test.bin").is_file())
        self.assertTrue((seed_dir / "disasm").is_file())
        self.assertTrue((seed_dir / "build_manifest.json").is_file())
        self.assertTrue((seed_dir / "stdout.log").is_file())
        self.assertTrue((seed_dir / "stderr.log").is_file())
        self.assertTrue((seed_dir / "run_meta.json").is_file())

        manifest = json.loads((seed_dir / "build_manifest.json").read_text())
        compile_sources = [
            cmd[cmd.index("-c") + 1]
            for cmd in manifest["commands"]["compile"]
        ]
        self.assertIn(str((ROOT / "snippets" / "programs" / "am_hello_main.c").resolve()), compile_sources)
        self.assertIn(
            str((seed_dir / "generated_am_program_am_hello_main.c").resolve()),
            compile_sources,
        )
        self.assertIn(str((ROOT / "runtime" / "src" / "xsam_program_snippet.c").resolve()), compile_sources)


if __name__ == "__main__":
    unittest.main()
