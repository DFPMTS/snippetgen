from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock


class MMUCoverageSummaryTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def ledger_payload(self, *, rule_state: str, tag_state: str) -> dict:
        return {
            "suite": "kmh_mmu_layer1_demo",
            "selected_rule_ids": ["bare_identity"],
            "defined_rule_ids": ["bare_identity", "superpage"],
            "rules": [
                {
                    "id": "bare_identity",
                    "symbol": "bare_identity",
                    "coverage_tags": ["requestor.load", "mode.bare"],
                    "state": rule_state,
                },
                {
                    "id": "superpage",
                    "symbol": "superpage",
                    "coverage_tags": ["requestor.store", "page.superpage"],
                    "state": "defined_only",
                },
            ],
            "coverage_tags": [
                {
                    "tag": "requestor.load",
                    "rules": ["bare_identity"],
                    "state": tag_state,
                },
                {
                    "tag": "requestor.store",
                    "rules": ["superpage"],
                    "state": "defined_only",
                },
                {
                    "tag": "page.superpage",
                    "rules": ["superpage"],
                    "state": "defined_only",
                },
                {
                    "tag": "attr.mmio",
                    "rules": [],
                    "state": "gap",
                },
            ],
            "gaps": [{"tag": "attr.mmio", "state": "gap"}],
        }

    def batch_payload(
        self,
        *,
        suite: str,
        run_batch: str,
        ledger_path: Path,
        profile: str,
        status: str,
        labels: list[str],
        finish_code: int | None,
    ) -> dict:
        return {
            "suite": suite,
            "target": "xiangshan-verilator",
            "run_batch": run_batch,
            "entries": [
                {
                    "suite": suite,
                    "target": "xiangshan-verilator",
                    "run_batch": run_batch,
                    "seed": 241027,
                    "status": status,
                    "labels": labels,
                    "notes": status,
                    "finish_code": finish_code,
                    "runner_profile": profile,
                    "runner_revision": f"{profile}-xs",
                    "diff_revision": "nemu",
                    "mmu_coverage_ledger": str(ledger_path),
                }
            ],
        }

    def test_summary_keeps_profiles_separate_and_counts_success(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            v2_ledger = self.write_json(root / "v2" / "mmu_coverage_ledger.json", self.ledger_payload(rule_state="ran", tag_state="ran"))
            v3_ledger = self.write_json(root / "v3" / "mmu_coverage_ledger.json", self.ledger_payload(rule_state="generated_not_run", tag_state="generated_not_run"))
            v2_batch = self.write_json(
                root / "v2" / "batch_meta.json",
                self.batch_payload(
                    suite="kmh_mmu_layer1_v2_smoke",
                    run_batch="v2_batch",
                    ledger_path=v2_ledger,
                    profile="kmh-v2/difftest",
                    status="ran",
                    labels=["built", "ran", "good_trap"],
                    finish_code=0,
                ),
            )
            v3_batch = self.write_json(
                root / "v3" / "batch_meta.json",
                self.batch_payload(
                    suite="kmh_mmu_layer1_v3_smoke",
                    run_batch="v3_batch",
                    ledger_path=v3_ledger,
                    profile="kmh-v3/difftest",
                    status="timeout",
                    labels=["built", "timeout"],
                    finish_code=None,
                ),
            )

            summary = summarize_mmu_coverage([v2_batch, v3_batch])

        load_tag = {
            entry["tag"]: entry
            for entry in summary["coverage_tags"]
        }["requestor.load"]
        self.assertEqual("ran", load_tag["states_by_profile"]["kmh-v2/difftest"])
        self.assertEqual("failed_or_blocked", load_tag["states_by_profile"]["kmh-v3/difftest"])
        self.assertEqual("ran", load_tag["state"])
        self.assertEqual(2, len(summary["entries"]))
        self.assertEqual(1, summary["entries"][1]["tag_counts"]["failed_or_blocked"])

    def test_summary_accepts_direct_coverage_ledger(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = self.write_json(
                Path(tmpdir) / "mmu_coverage_ledger.json",
                self.ledger_payload(rule_state="generated_not_run", tag_state="generated_not_run"),
            )
            summary = summarize_mmu_coverage([ledger])

        self.assertEqual(1, len(summary["entries"]))
        self.assertEqual("<no-profile>", summary["coverage_tags"][0]["states_by_profile"].popitem()[0])

    def test_cli_prints_text_summary_and_json_summary(self) -> None:
        from generator import cli

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ledger = self.write_json(root / "mmu_coverage_ledger.json", self.ledger_payload(rule_state="ran", tag_state="ran"))
            batch = self.write_json(
                root / "batch_meta.json",
                self.batch_payload(
                    suite="kmh_mmu_layer1_v2_smoke",
                    run_batch="v2_batch",
                    ledger_path=ledger,
                    profile="kmh-v2/difftest",
                    status="ran",
                    labels=["built", "ran", "good_trap"],
                    finish_code=0,
                ),
            )
            with mock.patch("builtins.print") as print_mock:
                rc = cli.main(["mmu-coverage-summary", str(batch)])
            self.assertEqual(0, rc)
            printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn("MMU coverage summary", printed)
            self.assertIn("kmh-v2/difftest", printed)

            with mock.patch("builtins.print") as print_mock:
                rc = cli.main(["mmu-coverage-summary", str(batch), "--json"])
            self.assertEqual(0, rc)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual("kmh-v2/difftest", payload["entries"][0]["runner_profile"])

    def test_summary_rejects_missing_ledger_reference(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch = self.write_json(
                root / "batch_meta.json",
                self.batch_payload(
                    suite="kmh_mmu_layer1_v3_smoke",
                    run_batch="missing",
                    ledger_path=root / "missing.json",
                    profile="kmh-v3/difftest",
                    status="timeout",
                    labels=["built", "timeout"],
                    finish_code=None,
                ),
            )
            with self.assertRaisesRegex(ValueError, "missing MMU coverage ledger"):
                summarize_mmu_coverage([batch])


if __name__ == "__main__":
    unittest.main()
