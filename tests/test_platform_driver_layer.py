from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]

class PlatformDriverLayerTest(unittest.TestCase):
    def test_build_manifest_includes_platform_driver_sources(self) -> None:
        build_dir = ROOT / "build" / "am_hello_main_poc"
        if build_dir.exists():
            import shutil

            shutil.rmtree(build_dir)

        result = subprocess.run(
            ["python3", "generator/cli.py", "build", "suites/am_hello_main_poc.yaml"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

        manifest = json.loads((build_dir / "build_manifest.json").read_text())
        compile_sources = [
            cmd[cmd.index("-c") + 1]
            for cmd in manifest["commands"]["compile"]
        ]

        self.assertIn(str((ROOT / "runtime" / "platform" / "xiangshan" / "xsam_xs_clint.c").resolve()), compile_sources)
        self.assertIn(str((ROOT / "runtime" / "platform" / "xiangshan" / "xsam_xs_plic.c").resolve()), compile_sources)
        self.assertIn(str((ROOT / "runtime" / "platform" / "xiangshan" / "xsam_xs_pma.c").resolve()), compile_sources)
        self.assertIn(str((ROOT / "runtime" / "platform" / "xiangshan" / "xsam_xs_pmp.c").resolve()), compile_sources)
        self.assertIn(str((ROOT / "runtime" / "platform" / "xiangshan" / "xsam_xs_cache.c").resolve()), compile_sources)


if __name__ == "__main__":
    unittest.main()
