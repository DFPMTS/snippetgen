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
        vector_path: Path | None = None,
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
                    "vector_mmu_coverage": str(vector_path) if vector_path is not None else None,
                }
            ],
        }

    def vector_payload(self, *, state: str) -> dict:
        return {
            "kind": "vector_mmu_coverage",
            "suite": "kmh_mmu_layer1_v2_vector_forms",
            "seed": 241027,
            "state": state,
            "items": [
                {
                    "id": "v2_vector_forms_strided_hit",
                    "requestor": "vector_load_store",
                    "mode": "host_single_stage",
                    "form": "strided",
                    "eew": "e8",
                    "page_boundary": "single_page",
                    "fault": "none",
                    "attribute": "normal",
                    "state": state,
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

    def test_summary_accepts_vector_coverage_directly_and_from_batch(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(root / "vector_mmu_coverage.json", self.vector_payload(state="ran"))
            ledger = self.write_json(root / "mmu_coverage_ledger.json", self.ledger_payload(rule_state="ran", tag_state="ran"))
            batch = self.write_json(
                root / "batch_meta.json",
                self.batch_payload(
                    suite="kmh_mmu_layer1_v2_vector_forms",
                    run_batch="vector_batch",
                    ledger_path=ledger,
                    profile="kmh-v2/difftest",
                    status="ran",
                    labels=["built", "ran", "good_trap"],
                    finish_code=0,
                    vector_path=vector,
                ),
            )

            direct = summarize_mmu_coverage([vector])
            batched = summarize_mmu_coverage([batch])

        self.assertEqual(1, len(direct["vector_entries"]))
        self.assertEqual("strided", direct["vector_mmu"][0]["form"])
        self.assertEqual(2, len(batched["entries"]))
        self.assertEqual("vector_mmu_coverage", batched["entries"][1]["kind"])
        self.assertEqual([0], batched["coverage_tags"][0]["entries"])
        self.assertEqual([1], batched["vector_mmu"][0]["entries"])
        self.assertEqual("vector_mmu_coverage", batched["entries"][batched["vector_mmu"][0]["entries"][0]]["kind"])
        self.assertEqual("kmh-v2/difftest", batched["vector_entries"][0]["runner_profile"])
        self.assertEqual("ran", batched["vector_mmu"][0]["states_by_profile"]["kmh-v2/difftest"])

    def test_summary_counts_vector_only_batch_entries(self) -> None:
        from generator.xsgen.mmu_coverage_summary import (
            format_mmu_coverage_summary_text,
            summarize_mmu_coverage,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(root / "vector_mmu_coverage.json", self.vector_payload(state="ran"))
            batch = self.write_json(
                root / "batch_meta.json",
                {
                    "suite": "kmh_mmu_layer1_v2_vector_forms",
                    "target": "xiangshan-verilator",
                    "run_batch": "vector_batch",
                    "entries": [
                        {
                            "suite": "kmh_mmu_layer1_v2_vector_forms",
                            "target": "xiangshan-verilator",
                            "run_batch": "vector_batch",
                            "seed": 241027,
                            "status": "ran",
                            "labels": ["built", "ran", "good_trap"],
                            "notes": "HIT GOOD TRAP",
                            "finish_code": 0,
                            "runner_profile": "kmh-v2/difftest",
                            "runner_revision": "kmh-v2-xs",
                            "diff_revision": "nemu",
                            "mmu_coverage_ledger": None,
                            "vector_mmu_coverage": str(vector),
                        }
                    ],
                },
            )

            summary = summarize_mmu_coverage([batch])
            text = format_mmu_coverage_summary_text(summary)

        self.assertEqual(1, len(summary["entries"]))
        self.assertEqual(1, len(summary["vector_entries"]))
        self.assertEqual("vector_mmu_coverage", summary["entries"][0]["kind"])
        self.assertIn("entries: 1", text)
        self.assertNotIn("entries: 0", text)
        self.assertIn("vector entries: 1", text)

    def test_summary_preserves_vector_unrun_suffix_on_failed_batch(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(
                root / "vector_mmu_coverage.json",
                {
                    "kind": "vector_mmu_coverage",
                    "suite": "kmh_mmu_layer1_v2_vector_forms",
                    "seed": 241027,
                    "state": "failed_or_blocked",
                    "items": [
                        {
                            "id": "v2_vector_forms_strided_hit",
                            "requestor": "vector_load_store",
                            "mode": "host_single_stage",
                            "form": "strided",
                            "eew": "e64",
                            "page_boundary": "single_page",
                            "fault": "none",
                            "attribute": "normal",
                            "state": "ran",
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
                            "state": "failed_or_blocked",
                        },
                        {
                            "id": "v2_vector_forms_indexed_hit",
                            "requestor": "vector_load_store",
                            "mode": "host_single_stage",
                            "form": "indexed",
                            "eew": "e64",
                            "page_boundary": "single_page",
                            "fault": "none",
                            "attribute": "normal",
                            "state": "generated_not_run",
                        },
                    ],
                },
            )
            batch = self.write_json(
                root / "batch_meta.json",
                {
                    "suite": "kmh_mmu_layer1_v2_vector_forms",
                    "target": "xiangshan-verilator",
                    "run_batch": "vector_batch",
                    "entries": [
                        {
                            "suite": "kmh_mmu_layer1_v2_vector_forms",
                            "target": "xiangshan-verilator",
                            "run_batch": "vector_batch",
                            "seed": 241027,
                            "status": "bad_trap",
                            "labels": ["built", "ran", "bad_trap"],
                            "notes": "Unknown trap code: 43",
                            "finish_code": 43,
                            "runner_profile": "kmh-v2/difftest",
                            "runner_revision": "kmh-v2-xs",
                            "diff_revision": "nemu",
                            "mmu_coverage_ledger": None,
                            "vector_mmu_coverage": str(vector),
                        }
                    ],
                },
            )

            summary = summarize_mmu_coverage([batch])

        states = {
            item["id"]: item["state"]
            for item in summary["vector_entries"][0]["items"]
        }
        self.assertEqual("ran", states["v2_vector_forms_strided_hit"])
        self.assertEqual("failed_or_blocked", states["v2_vector_forms_strided_fault"])
        self.assertEqual("generated_not_run", states["v2_vector_forms_indexed_hit"])

    def test_summary_marks_attempted_vector_timeout_as_blocked(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(root / "vector_mmu_coverage.json", self.vector_payload(state="generated_not_run"))
            batch = self.write_json(
                root / "batch_meta.json",
                {
                    "suite": "kmh_mmu_layer1_v2_vector_forms",
                    "target": "xiangshan-verilator",
                    "run_batch": "vector_timeout",
                    "entries": [
                        {
                            "suite": "kmh_mmu_layer1_v2_vector_forms",
                            "target": "xiangshan-verilator",
                            "run_batch": "vector_timeout",
                            "seed": 241027,
                            "status": "timeout",
                            "labels": ["built", "timeout"],
                            "notes": "timeout after 1800s",
                            "finish_code": None,
                            "runner_profile": "kmh-v2/difftest",
                            "runner_revision": "kmh-v2-xs",
                            "diff_revision": "nemu",
                            "mmu_coverage_ledger": None,
                            "vector_mmu_coverage": str(vector),
                        }
                    ],
                },
            )

            summary = summarize_mmu_coverage([batch])

        self.assertEqual(1, summary["vector_entries"][0]["item_counts"]["failed_or_blocked"])
        self.assertEqual("failed_or_blocked", summary["vector_entries"][0]["items"][0]["state"])
        self.assertEqual("failed_or_blocked", summary["vector_mmu"][0]["states_by_profile"]["kmh-v2/difftest"])

    def test_summary_preserves_setup_failure_before_first_vector_case(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(
                root / "vector_mmu_coverage.json",
                {
                    "kind": "vector_mmu_coverage",
                    "suite": "kmh_mmu_layer1_v2_vector_widths",
                    "seed": 241027,
                    "state": "failed_or_blocked",
                    "items": [
                        {
                            "id": "v2_vector_widths_e8_unit_hit",
                            "requestor": "vector_load_store",
                            "mode": "host_single_stage",
                            "form": "unit_stride",
                            "eew": "e8",
                            "page_boundary": "single_page",
                            "fault": "none",
                            "attribute": "normal",
                            "state": "generated_not_run",
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
                            "state": "generated_not_run",
                        },
                    ],
                },
            )
            batch = self.write_json(
                root / "batch_meta.json",
                {
                    "suite": "kmh_mmu_layer1_v2_vector_widths",
                    "target": "xiangshan-verilator",
                    "run_batch": "setup_failure",
                    "entries": [
                        {
                            "suite": "kmh_mmu_layer1_v2_vector_widths",
                            "target": "xiangshan-verilator",
                            "run_batch": "setup_failure",
                            "seed": 241027,
                            "status": "bad_trap",
                            "labels": ["built", "ran", "bad_trap"],
                            "notes": "Unknown trap code: 21",
                            "finish_code": 21,
                            "runner_profile": "kmh-v2/difftest",
                            "runner_revision": "kmh-v2-xs",
                            "diff_revision": "nemu",
                            "mmu_coverage_ledger": None,
                            "vector_mmu_coverage": str(vector),
                        }
                    ],
                },
            )

            summary = summarize_mmu_coverage([batch])

        self.assertEqual(2, summary["vector_entries"][0]["item_counts"]["generated_not_run"])
        self.assertTrue(all(item["state"] == "generated_not_run" for item in summary["vector_entries"][0]["items"]))
        self.assertEqual("generated_not_run", summary["vector_mmu"][0]["states_by_profile"]["kmh-v2/difftest"])

    def test_summary_keeps_unattempted_vector_infra_failure_unrun(self) -> None:
        from generator.xsgen.mmu_coverage_summary import summarize_mmu_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vector = self.write_json(root / "vector_mmu_coverage.json", self.vector_payload(state="generated_not_run"))
            batch = self.write_json(
                root / "batch_meta.json",
                {
                    "suite": "kmh_mmu_layer1_v2_vector_forms",
                    "target": "xiangshan-verilator",
                    "run_batch": "runner_missing",
                    "entries": [
                        {
                            "suite": "kmh_mmu_layer1_v2_vector_forms",
                            "target": "xiangshan-verilator",
                            "run_batch": "runner_missing",
                            "seed": 241027,
                            "status": "run_infra_fail",
                            "labels": ["run_infra_fail", "runner_missing"],
                            "notes": "runner missing: emu",
                            "finish_code": None,
                            "runner_profile": "kmh-v2/difftest",
                            "runner_revision": "kmh-v2-xs",
                            "diff_revision": "nemu",
                            "mmu_coverage_ledger": None,
                            "vector_mmu_coverage": str(vector),
                        }
                    ],
                },
            )

            summary = summarize_mmu_coverage([batch])

        self.assertEqual("generated_not_run", summary["vector_entries"][0]["items"][0]["state"])
        self.assertEqual("generated_not_run", summary["vector_mmu"][0]["states_by_profile"]["kmh-v2/difftest"])


if __name__ == "__main__":
    unittest.main()
