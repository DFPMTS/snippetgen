from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "Makefile",
    "README.md",
]

REQUIRED_DIRECTORIES = [
    "runtime",
    "runtime/include",
    "runtime/src",
    "runtime/arch/riscv64",
    "runtime/platform/xiangshan",
    "snippets",
    "snippets/include",
    "snippets/manifests",
    "snippets/core",
    "snippets/scalar_load_legality",
    "generator",
    "generator/xsgen",
    "suites",
    "build",
    "tests",
]


class RepoLayoutTest(unittest.TestCase):
    def test_required_top_level_files_exist(self) -> None:
        for relative_path in REQUIRED_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_required_directories_exist(self) -> None:
        for relative_path in REQUIRED_DIRECTORIES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_dir())

    def test_release_docs_do_not_embed_machine_specific_absolute_paths(self) -> None:
        docs_to_check = [
            ROOT / "README.md",
            ROOT / "CHANGELOG.md",
            ROOT / "docs" / "README.md",
            ROOT / "docs" / "2026-04-10-xiangshan-emu-workload-howto.md",
            ROOT / "docs" / "2026-04-10-vsetvl-hang-investigation-notes.md",
        ]

        for path in docs_to_check:
            with self.subTest(path=path):
                text = path.read_text()
                self.assertNotIn("/home/dfpmts/", text)


if __name__ == "__main__":
    unittest.main()
