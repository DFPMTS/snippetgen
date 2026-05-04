from pathlib import Path
import json
import re
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MMURuleEmitterTest(unittest.TestCase):
    def write_rule(self, rule_dir: Path, name: str, body: str) -> None:
        rule_dir.mkdir(parents=True, exist_ok=True)
        (rule_dir / name).write_text(textwrap.dedent(body).strip() + "\n")

    def generated_rule_field(self, source: str, rule_id: str, field_name: str) -> str:
        rule_marker = f'.id = "{rule_id}",'
        start = source.find(rule_marker)
        self.assertNotEqual(-1, start, f"generated rule {rule_id} missing")
        end = source.find("\n};", start)
        self.assertNotEqual(-1, end, f"generated rule {rule_id} terminator missing")
        block = source[start:end]
        match = re.search(rf"\.{re.escape(field_name)}\s*=\s*(.*?),", block)
        self.assertIsNotNone(match, f"generated rule {rule_id} missing field {field_name}")
        assert match is not None
        return match.group(1).strip()

    def c_flag_set(self, expr: str) -> set[str]:
        if expr in {"0", "0u", "0ull"}:
            return set()
        return {part.strip() for part in expr.split("|")}

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

    def test_emitter_materializes_raw_pte_privilege_attribute_control_and_retry_fields(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            rule_dir = build_dir / "rules"
            self.write_rule(
                rule_dir,
                "kmh_extended.yaml",
                """
                id: kmh_extended
                requestor: load
                mode: host_single_stage
                preconditions:
                  csr:
                    mxr: true
                    sum: true
                    satp_asid: 7
                setup:
                  pmp:
                    deny_napot:
                      register: 1
                      size: 65536
                      permissions: []
                  attributes:
                    pbmt: nc
                  mappings:
                    - name: raw_leaf
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                      raw_pte:
                        bits: [v, r, a, d]
                        pbmt: nc
                    - name: raw_leaf_switched
                      context: switch
                      va: 0x900000000
                      pa: test_page_alt
                      perms: [r, a, d]
                      raw_pte:
                        bits: [v, r, a, d]
                        pbmt: nc
                actions:
                  before_trigger:
                    - switch_satp_context
                trigger:
                  op: load
                  addr: raw_leaf
                expect:
                  result: access_fault
                  retry: none
                observe:
                  - fault_cause_match
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - exception.access_fault
                  - pte.raw
                  - pte.v
                  - pte.r
                  - pte.a
                  - pte.d
                  - priv.mxr
                  - priv.sum
                  - attr.pmp_deny
                  - attr.pbmt_nc
                  - attr.nc
                  - ctrl.satp
                  - ctrl.asid
                """,
            )

            emit_mmu_rule_artifacts(
                suite_name="kmh_extended_emit",
                rule_dir=rule_dir,
                rule_ids=("kmh_extended",),
                header_path=build_dir / "generated_mmu_rule.h",
                source_path=build_dir / "generated_mmu_rule.c",
                coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
            )

            header = (build_dir / "generated_mmu_rule.h").read_text()
            source = (build_dir / "generated_mmu_rule.c").read_text()

        self.assertIn("raw_pte", header)
        self.assertIn("csr_flags", header)
        self.assertIn("satp_asid", header)
        self.assertIn("pmp_deny", header)
        self.assertIn("attr_flags", header)
        self.assertIn("retry_kind", header)
        self.assertIn("XS_GENERATED_MMU_FLAG_SWITCH_CONTEXT", header)
        self.assertIn(".raw_pte =", source)
        self.assertEqual(
            {"XS_GENERATED_MMU_CSR_MXR", "XS_GENERATED_MMU_CSR_SUM"},
            self.c_flag_set(self.generated_rule_field(source, "kmh_extended", "csr_flags")),
        )
        self.assertEqual("0x7ull", self.generated_rule_field(source, "kmh_extended", "satp_asid"))
        self.assertEqual("1u", self.generated_rule_field(source, "kmh_extended", "pmp_deny"))
        self.assertEqual(
            {"XS_GENERATED_MMU_ATTR_PBMT_NC"},
            self.c_flag_set(self.generated_rule_field(source, "kmh_extended", "attr_flags")),
        )
        self.assertEqual(
            "XS_GENERATED_MMU_RETRY_NONE",
            self.generated_rule_field(source, "kmh_extended", "retry_kind"),
        )

    def test_emitter_keeps_pma_and_mmio_attribute_flags_independent(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            rule_dir = build_dir / "rules"
            self.write_rule(
                rule_dir,
                "pma_only.yaml",
                """
                id: pma_only
                requestor: load
                mode: host_single_stage
                setup:
                  attributes:
                    pma: io
                  mappings:
                    - name: pma_page
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                trigger:
                  op: load
                  addr: pma_page
                expect:
                  result: hit
                observe:
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - attr.pma
                """,
            )
            self.write_rule(
                rule_dir,
                "mmio_only.yaml",
                """
                id: mmio_only
                requestor: load
                mode: host_single_stage
                setup:
                  attributes:
                    mmio: true
                  mappings:
                    - name: mmio_page
                      va: 0x900010000
                      pa: test_page_alt
                      perms: [r, a, d]
                trigger:
                  op: load
                  addr: mmio_page
                expect:
                  result: hit
                observe:
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - attr.mmio
                """,
            )
            self.write_rule(
                rule_dir,
                "pma_mmio.yaml",
                """
                id: pma_mmio
                requestor: load
                mode: host_single_stage
                setup:
                  attributes:
                    pma: io
                    mmio: true
                  mappings:
                    - name: pma_mmio_page
                      va: 0x900020000
                      pa: test_page_alt
                      perms: [r, a, d]
                trigger:
                  op: load
                  addr: pma_mmio_page
                expect:
                  result: hit
                observe:
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - attr.pma
                  - attr.mmio
                """,
            )

            emit_mmu_rule_artifacts(
                suite_name="kmh_attr_independent_emit",
                rule_dir=rule_dir,
                rule_ids=("pma_only", "mmio_only", "pma_mmio"),
                header_path=build_dir / "generated_mmu_rule.h",
                source_path=build_dir / "generated_mmu_rule.c",
                coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
            )

            source = (build_dir / "generated_mmu_rule.c").read_text()

        self.assertEqual(
            {"XS_GENERATED_MMU_ATTR_PMA"},
            self.c_flag_set(self.generated_rule_field(source, "pma_only", "attr_flags")),
        )
        self.assertEqual(
            {"XS_GENERATED_MMU_ATTR_MMIO"},
            self.c_flag_set(self.generated_rule_field(source, "mmio_only", "attr_flags")),
        )
        self.assertEqual(
            {"XS_GENERATED_MMU_ATTR_PMA", "XS_GENERATED_MMU_ATTR_MMIO"},
            self.c_flag_set(self.generated_rule_field(source, "pma_mmio", "attr_flags")),
        )

    def test_emitter_detects_pbmt_nc_encoded_in_raw_pte_value(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            rule_dir = build_dir / "rules"
            self.write_rule(
                rule_dir,
                "raw_value_pbmt_nc.yaml",
                """
                id: raw_value_pbmt_nc
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: raw_leaf
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                      raw_pte:
                        value: 0x20000000000000c3
                trigger:
                  op: load
                  addr: raw_leaf
                expect:
                  result: page_fault
                observe:
                  - fault_cause_match
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - exception.page_fault
                  - pte.raw
                  - attr.nc
                  - attr.pbmt_nc
                """,
            )

            emit_mmu_rule_artifacts(
                suite_name="kmh_raw_value_pbmt_nc_emit",
                rule_dir=rule_dir,
                rule_ids=("raw_value_pbmt_nc",),
                header_path=build_dir / "generated_mmu_rule.h",
                source_path=build_dir / "generated_mmu_rule.c",
                coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
            )

            source = (build_dir / "generated_mmu_rule.c").read_text()

        self.assertIn(".raw_pte = 0x20000000000000c3ull", source)
        self.assertEqual(
            {"XS_GENERATED_MMU_ATTR_PBMT_NC"},
            self.c_flag_set(self.generated_rule_field(source, "raw_value_pbmt_nc", "attr_flags")),
        )

    def test_emitter_generates_repair_then_reexecute_case(self) -> None:
        from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            rule_dir = build_dir / "rules"
            self.write_rule(
                rule_dir,
                "fault_retry.yaml",
                """
                id: fault_retry
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: retry_page
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                      fault: true
                actions:
                  handler:
                    - repair_fault_mapping
                trigger:
                  op: load
                  addr: retry_page
                expect:
                  result: page_fault
                  retry: repair_then_reexecute
                observe:
                  - fault_cause_match
                  - memory_value_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - exception.page_fault
                  - retry.repair_then_reexecute
                """,
            )

            emit_mmu_rule_artifacts(
                suite_name="fault_retry_emit",
                rule_dir=rule_dir,
                rule_ids=("fault_retry",),
                header_path=build_dir / "generated_mmu_rule.h",
                source_path=build_dir / "generated_mmu_rule.c",
                coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
            )

            source = (build_dir / "generated_mmu_rule.c").read_text()

        self.assertEqual(
            "XS_GENERATED_MMU_RETRY_REPAIR_THEN_REEXECUTE",
            self.generated_rule_field(source, "fault_retry", "retry_kind"),
        )
