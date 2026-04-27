from pathlib import Path
import json
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MMURuleEmitterTest(unittest.TestCase):
    def write_rule(self, rule_dir: Path, name: str, body: str) -> None:
        rule_dir.mkdir(parents=True, exist_ok=True)
        (rule_dir / name).write_text(textwrap.dedent(body).strip() + "\n")

    def test_emitter_writes_generated_artifacts_and_coverage_states(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            bundle = emit_mmu_rule_artifacts(
                suite_name="mmu_unit_emit",
                rule_dir=ROOT / "snippets" / "mmu_rules" / "pilot",
                rule_ids=("bare_identity", "sv39_alias"),
                header_path=build_dir / "generated_mmu_rule.h",
                source_path=build_dir / "generated_mmu_rule.c",
                coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
            )

            header = (build_dir / "generated_mmu_rule.h").read_text()
            source = (build_dir / "generated_mmu_rule.c").read_text()
            ledger = json.loads((build_dir / "mmu_coverage_ledger.json").read_text())

        self.assertIn("xs_generated_mmu_rule_t", header)
        self.assertIn("xs_generated_rule_bare_identity", source)
        self.assertIn("xs_generated_rule_sv39_alias", source)
        self.assertIn('    .trigger_addr = 0xa00000000ull,', source)
        self.assertIn('    .secondary_addr = 0x900000000ull,', source)
        self.assertEqual(("bare_identity", "load_page_fault", "sfence_remap", "superpage", "sv39_alias", "two_stage_fault"), bundle.defined_rule_ids)
        self.assertEqual(("bare_identity", "sv39_alias"), bundle.selected_rule_ids)
        rules = {entry["id"]: entry["state"] for entry in ledger["rules"]}
        self.assertEqual("generated_not_run", rules["bare_identity"])
        self.assertEqual("generated_not_run", rules["sv39_alias"])
        self.assertEqual("defined_only", rules["superpage"])
        tags = {entry["tag"]: entry["state"] for entry in ledger["coverage_tags"]}
        self.assertEqual("generated_not_run", tags["requestor.load"])
        self.assertEqual("defined_only", tags["requestor.store"])

    def test_emitter_rejects_symbol_collisions(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            rule_dir = Path(tmpdir) / "rules"
            self.write_rule(
                rule_dir,
                "a.yaml",
                """
                id: alpha_rule
                symbol: shared_symbol
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: page_a
                      va: 0x80020000
                      pa: 0x80020000
                      perms: [r, a]
                trigger:
                  op: load
                  addr: page_a
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                """,
            )
            self.write_rule(
                rule_dir,
                "b.yaml",
                """
                id: beta_rule
                symbol: shared_symbol
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: page_b
                      va: 0x80021000
                      pa: 0x80021000
                      perms: [r, a]
                trigger:
                  op: load
                  addr: page_b
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                """,
            )

            with self.assertRaisesRegex(ValueError, "symbol collision"):
                emit_mmu_rule_artifacts(
                    suite_name="mmu_symbol_collision",
                    rule_dir=rule_dir,
                    rule_ids=("alpha_rule", "beta_rule"),
                    header_path=Path(tmpdir) / "generated_mmu_rule.h",
                    source_path=Path(tmpdir) / "generated_mmu_rule.c",
                    coverage_ledger_path=Path(tmpdir) / "mmu_coverage_ledger.json",
                )

    def test_emitter_rejects_rules_without_trigger_address(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            rule_dir = Path(tmpdir) / "rules"
            self.write_rule(
                rule_dir,
                "missing_trigger_addr.yaml",
                """
                id: missing_trigger_addr
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: page_a
                      va: 0x80022000
                      pa: 0x80022000
                      perms: [r, a]
                trigger:
                  op: load
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                """,
            )

            with self.assertRaisesRegex(ValueError, "missing trigger address"):
                emit_mmu_rule_artifacts(
                    suite_name="mmu_missing_trigger_addr",
                    rule_dir=rule_dir,
                    rule_ids=("missing_trigger_addr",),
                    header_path=Path(tmpdir) / "generated_mmu_rule.h",
                    source_path=Path(tmpdir) / "generated_mmu_rule.c",
                    coverage_ledger_path=Path(tmpdir) / "mmu_coverage_ledger.json",
                )
