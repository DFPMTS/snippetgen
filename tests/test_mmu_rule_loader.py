from pathlib import Path
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MMURuleLoaderTest(unittest.TestCase):
    def write_rule(self, tmpdir: str, name: str, body: str) -> Path:
        path = Path(tmpdir) / name
        path.write_text(textwrap.dedent(body).strip() + "\n")
        return path

    def test_valid_mmu_rule_loads_typed_fields(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "sv39_alias.yaml",
                """
                id: sv39_alias
                requestor: load
                mode: host_single_stage
                preconditions:
                  pmp: allow
                  stage1: sv39
                setup:
                  mappings:
                    - name: rw_alias
                      va: 0xa00000000
                      pa: test_page
                      perms: [r, w, a, d]
                    - name: ro_alias
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                actions:
                  before_trigger:
                    - sfence_vma
                trigger:
                  op: store_then_load
                  store_va: rw_alias
                  load_va: ro_alias
                expect:
                  result: hit
                observe:
                  - memory_value_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - page.alias
                """,
            )

            rule = load_mmu_rule(path)

        self.assertEqual("sv39_alias", rule.id)
        self.assertEqual("load", rule.requestor)
        self.assertEqual("host_single_stage", rule.mode)
        self.assertEqual("hit", rule.expect["result"])
        self.assertEqual(("memory_value_match",), rule.observe)
        self.assertEqual(
            ("requestor.load", "mode.host_single_stage", "page.alias"),
            rule.coverage_tags,
        )
        self.assertEqual(("sfence_vma",), tuple(rule.actions["before_trigger"]))

    def test_loader_accepts_checked_in_pilot_rules(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        pilot_dir = ROOT / "snippets" / "mmu_rules" / "pilot"
        rule_paths = sorted(pilot_dir.glob("*.yaml"))

        self.assertGreater(len(rule_paths), 0)
        for path in rule_paths:
            with self.subTest(path=path.name):
                rule = load_mmu_rule(path)
                self.assertEqual(path.stem, rule.id)
                self.assertTrue(rule.coverage_tags)
                self.assertIn(f"mode.{rule.mode}", rule.coverage_tags)

    def test_loader_normalizes_legacy_mode_aliases(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "legacy_mode.yaml",
                """
                id: legacy_mode
                requestor: load
                mode: only_stage1
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.onlyStage1
                """,
            )

            rule = load_mmu_rule(path)

        self.assertEqual("onlyStage1", rule.mode)

    def test_loader_accepts_coverage_tags_for_supported_hybrid_requestors(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            cases = (
                ("hybrid_load", "requestor.hybrid_load", "hit"),
                ("hlvx", "requestor.hlvx", "guest_page_fault"),
                ("hlv", "requestor.hlv", "page_fault"),
                ("hsv", "requestor.hsv", "page_fault"),
            )
            for requestor, tag, result in cases:
                path = self.write_rule(
                    tmpdir,
                    f"{requestor}.yaml",
                    f"""
                    id: {requestor}_coverage
                    requestor: {requestor}
                    mode: host_single_stage
                    expect:
                      result: {result}
                    coverage_tags:
                      - {tag}
                      - mode.host_single_stage
                    """,
                )

                with self.subTest(requestor=requestor):
                    rule = load_mmu_rule(path)
                    self.assertIn(tag, rule.coverage_tags)

    def test_taxonomy_contains_kmh_layer1_required_axes(self) -> None:
        from generator.xsgen.mmu_rule_loader import COVERAGE_TAG_SET

        required_tags = {
            "pte.raw",
            "pte.v",
            "pte.r",
            "pte.w",
            "pte.x",
            "pte.u",
            "pte.a",
            "pte.d",
            "priv.mxr",
            "priv.sum",
            "attr.pmp_deny",
            "attr.pma",
            "attr.pbmt_nc",
            "attr.mmio",
            "ctrl.satp",
            "ctrl.vsatp",
            "ctrl.hgatp",
            "ctrl.asid",
            "ctrl.vmid",
            "retry.repair_then_reexecute",
        }

        self.assertLessEqual(required_tags, COVERAGE_TAG_SET)

    def test_loader_accepts_kmh_schema_extensions(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "schema_extensions.yaml",
                """
                id: schema_extensions
                requestor: hlv
                mode: allStage
                preconditions:
                  csr:
                    mxr: true
                    sum: true
                    satp_asid: 9
                    vsatp_asid: 10
                    hgatp_vmid: 11
                setup:
                  attributes:
                    pbmt: nc
                    pma: io
                    mmio: true
                  mappings:
                    - name: stage1_raw
                      context: switch
                      stage: stage1
                      va: 0x900000000
                      pa: guest_page
                      perms: [r, a, d]
                      raw_pte:
                        bits: [v, r, a, d]
                    - name: stage2_page
                      context: switch
                      stage: stage2
                      va: guest_page
                      pa: test_page
                      perms: [r, w, a, d]
                actions:
                  before_trigger:
                    - switch_vsatp_context
                    - switch_hgatp_context
                  handler:
                    - repair_fault_mapping
                trigger:
                  op: guest_load
                  addr: stage1_raw
                expect:
                  result: hit
                observe:
                  - memory_value_match
                  - attribute_policy_match
                coverage_tags:
                  - requestor.hlv
                  - mode.allStage
                  - pte.raw
                  - pte.v
                  - pte.r
                  - pte.a
                  - pte.d
                  - priv.mxr
                  - priv.sum
                  - attr.pma
                  - attr.pbmt_nc
                  - attr.mmio
                  - ctrl.vsatp
                  - ctrl.hgatp
                  - ctrl.asid
                  - ctrl.vmid
                """,
            )

            rule = load_mmu_rule(path)

        self.assertEqual("nc", rule.setup["attributes"]["pbmt"])
        self.assertEqual(10, rule.preconditions["csr"]["vsatp_asid"])
        self.assertEqual(("switch_vsatp_context", "switch_hgatp_context"), rule.actions["before_trigger"])

    def test_loader_keeps_independent_attribute_tags_runnable(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            pma_path = self.write_rule(
                tmpdir,
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
            nc_path = self.write_rule(
                tmpdir,
                "nc_only.yaml",
                """
                id: nc_only
                requestor: load
                mode: host_single_stage
                setup:
                  attributes:
                    pbmt: nc
                  mappings:
                    - name: nc_page
                      va: 0x900010000
                      pa: test_page_alt
                      perms: [r, a, d]
                trigger:
                  op: load
                  addr: nc_page
                expect:
                  result: hit
                observe:
                  - attribute_policy_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - attr.nc
                """,
            )

            pma_rule = load_mmu_rule(pma_path)
            nc_rule = load_mmu_rule(nc_path)

        self.assertEqual(
            ("requestor.load", "mode.host_single_stage", "attr.pma"),
            pma_rule.coverage_tags,
        )
        self.assertEqual(
            ("requestor.load", "mode.host_single_stage", "attr.nc"),
            nc_rule.coverage_tags,
        )

    def test_loader_rejects_mmio_tag_without_explicit_mmio_attribute(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "mmio_without_mmio_attr.yaml",
                """
                id: mmio_without_mmio_attr
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
                  - attr.mmio
                """,
            )

            with self.assertRaisesRegex(ValueError, "setup.attributes.mmio: true"):
                load_mmu_rule(path)

    def test_loader_accepts_asid_and_vmid_only_actions_without_switch_mappings(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            asid_path = self.write_rule(
                tmpdir,
                "asid_only.yaml",
                """
                id: asid_only
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: asid_page
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                actions:
                  before_trigger:
                    - switch_asid_context
                trigger:
                  op: load
                  addr: asid_page
                expect:
                  result: hit
                observe:
                  - memory_value_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - ctrl.asid
                """,
            )
            vmid_path = self.write_rule(
                tmpdir,
                "vmid_only.yaml",
                """
                id: vmid_only
                requestor: hlv
                mode: allStage
                setup:
                  mappings:
                    - name: stage1_page
                      stage: stage1
                      va: 0x900000000
                      pa: guest_page
                      perms: [r, a, d]
                    - name: stage2_page
                      stage: stage2
                      va: guest_page
                      pa: test_page
                      perms: [r, a, d]
                actions:
                  before_trigger:
                    - switch_vmid_context
                trigger:
                  op: guest_load
                  addr: stage1_page
                expect:
                  result: hit
                observe:
                  - memory_value_match
                coverage_tags:
                  - requestor.hlv
                  - mode.allStage
                  - ctrl.vmid
                """,
            )

            asid_rule = load_mmu_rule(asid_path)
            vmid_rule = load_mmu_rule(vmid_path)

        self.assertEqual(("switch_asid_context",), asid_rule.actions["before_trigger"])
        self.assertEqual(("switch_vmid_context",), vmid_rule.actions["before_trigger"])

    def test_loader_rejects_illegal_raw_pte_hit_claims(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "illegal_raw_pte.yaml",
                """
                id: illegal_raw_pte
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: bad_leaf
                      va: 0x900000000
                      pa: test_page
                      perms: [w, a, d]
                      raw_pte:
                        bits: [v, w, a, d]
                trigger:
                  op: load
                  addr: bad_leaf
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - pte.raw
                  - pte.w
                """,
            )

            with self.assertRaisesRegex(ValueError, "illegal raw PTE"):
                load_mmu_rule(path)

    def test_loader_accepts_raw_pte_value_and_decodes_illegal_leaf_bits(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            valid = self.write_rule(
                tmpdir,
                "raw_value.yaml",
                """
                id: raw_value
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: raw_leaf
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a, d]
                      raw_pte:
                        value: 0x200000c3
                trigger:
                  op: load
                  addr: raw_leaf
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - pte.raw
                """,
            )
            illegal = self.write_rule(
                tmpdir,
                "raw_value_illegal.yaml",
                """
                id: raw_value_illegal
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: raw_leaf
                      va: 0x900001000
                      pa: test_page_alt
                      perms: [w, a, d]
                      raw_pte:
                        value: 0x200004c5
                trigger:
                  op: load
                  addr: raw_leaf
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - pte.raw
                  - pte.w
                """,
            )

            self.assertEqual("raw_value", load_mmu_rule(valid).id)
            with self.assertRaisesRegex(ValueError, "illegal raw PTE"):
                load_mmu_rule(illegal)

    def test_loader_accepts_pbmt_nc_encoded_in_raw_pte_value(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
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

            rule = load_mmu_rule(path)

        self.assertEqual("raw_value_pbmt_nc", rule.id)
        self.assertIn("attr.pbmt_nc", rule.coverage_tags)

    def test_loader_rejects_attribute_tags_without_schema_support(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "attr_without_setup.yaml",
                """
                id: attr_without_setup
                requestor: load
                mode: host_single_stage
                setup:
                  mappings:
                    - name: page
                      va: 0x900000000
                      pa: test_page
                      perms: [r, a]
                trigger:
                  op: load
                  addr: page
                expect:
                  result: hit
                observe:
                  - memory_value_match
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                  - attr.pbmt_nc
                """,
            )

            with self.assertRaisesRegex(ValueError, "attribute coverage tag requires"):
                load_mmu_rule(path)

    def test_loader_rejects_invalid_all_stage_setup(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "invalid_all_stage.yaml",
                """
                id: invalid_all_stage
                requestor: hlv
                mode: allStage
                setup:
                  mappings:
                    - name: stage1_only
                      stage: stage1
                      va: 0x900000000
                      pa: guest_page
                      perms: [r, a, d]
                trigger:
                  op: guest_load
                  addr: stage1_only
                expect:
                  result: hit
                coverage_tags:
                  - requestor.hlv
                  - mode.allStage
                  - guest.two_stage
                """,
            )

            with self.assertRaisesRegex(ValueError, "allStage rule requires both stage1 and stage2"):
                load_mmu_rule(path)

    def test_loader_rejects_missing_required_fields(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "missing_expect.yaml",
                """
                id: missing_expect
                requestor: load
                mode: host_single_stage
                coverage_tags:
                  - requestor.load
                """,
            )

            with self.assertRaisesRegex(ValueError, "missing required fields: expect"):
                load_mmu_rule(path)

    def test_loader_rejects_unknown_requestor_mode_and_result(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "bad_enum.yaml",
                """
                id: bad_enum
                requestor: mystery
                mode: imaginary
                expect:
                  result: impossible
                coverage_tags:
                  - requestor.load
                """,
            )

            with self.assertRaisesRegex(ValueError, "unsupported requestor"):
                load_mmu_rule(path)

    def test_loader_rejects_results_the_runner_cannot_validate(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        unsupported_results = ("miss", "refill", "replay", "stale_response_drop")

        with tempfile.TemporaryDirectory() as tmpdir:
            for result in unsupported_results:
                path = self.write_rule(
                    tmpdir,
                    f"{result}.yaml",
                    f"""
                    id: reject_{result}
                    requestor: load
                    mode: host_single_stage
                    expect:
                      result: {result}
                    coverage_tags:
                      - requestor.load
                      - mode.host_single_stage
                    """,
                )

                with self.subTest(result=result):
                    with self.assertRaisesRegex(ValueError, "unsupported expect.result"):
                        load_mmu_rule(path)

    def test_loader_rejects_requestors_the_runner_does_not_dispatch(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        unsupported_requestors = (
            "itlb",
            "l1_stream_prefetch",
            "l1_stride_prefetch",
            "sms_prefetch",
            "l2_tlb_req",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            for requestor in unsupported_requestors:
                path = self.write_rule(
                    tmpdir,
                    f"{requestor}.yaml",
                    f"""
                    id: reject_{requestor}
                    requestor: {requestor}
                    mode: host_single_stage
                    expect:
                      result: hit
                    coverage_tags:
                      - requestor.load
                    """,
                )

                with self.subTest(requestor=requestor):
                    with self.assertRaisesRegex(ValueError, "unsupported requestor"):
                        load_mmu_rule(path)

    def test_loader_rejects_requestor_result_pairs_the_runner_cannot_validate(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        unsupported_pairs = (
            ("hlvx", "access_fault", "requestor.hlvx", "exception.access_fault"),
            ("load", "guest_page_fault", "requestor.load", "exception.guest_page_fault"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            for requestor, result, requestor_tag, exception_tag in unsupported_pairs:
                path = self.write_rule(
                    tmpdir,
                    f"{requestor}_{result}.yaml",
                    f"""
                    id: reject_{requestor}_{result}
                    requestor: {requestor}
                    mode: host_single_stage
                    expect:
                      result: {result}
                    coverage_tags:
                      - {requestor_tag}
                      - mode.host_single_stage
                      - {exception_tag}
                    """,
                )

                with self.subTest(requestor=requestor, result=result):
                    with self.assertRaisesRegex(ValueError, "unsupported requestor/result pair"):
                        load_mmu_rule(path)

    def test_loader_rejects_malformed_coverage_tags(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "bad_coverage.yaml",
                """
                id: bad_coverage
                requestor: load
                mode: host_single_stage
                expect:
                  result: hit
                coverage_tags:
                  - requestor-load
                """,
            )

            with self.assertRaisesRegex(ValueError, "invalid coverage tag"):
                load_mmu_rule(path)

    def test_loader_rejects_unknown_coverage_tags(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.write_rule(
                tmpdir,
                "unknown_coverage.yaml",
                """
                id: unknown_coverage
                requestor: load
                mode: host_single_stage
                expect:
                  result: hit
                coverage_tags:
                  - unknown.anything
                """,
            )

            with self.assertRaisesRegex(ValueError, "unknown coverage tag"):
                load_mmu_rule(path)

    def test_loader_rejects_unsupported_action_phases_and_invalid_symbols(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_phase = self.write_rule(
                tmpdir,
                "bad_phase.yaml",
                """
                id: bad_phase
                requestor: load
                mode: host_single_stage
                actions:
                  handler_phase:
                    - sfence_vma
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                """,
            )
            with self.assertRaisesRegex(ValueError, "unsupported action phase"):
                load_mmu_rule(bad_phase)

            bad_symbol = self.write_rule(
                tmpdir,
                "bad_symbol.yaml",
                """
                id: bad_symbol
                symbol: invalid-symbol
                requestor: load
                mode: host_single_stage
                expect:
                  result: hit
                coverage_tags:
                  - requestor.load
                  - mode.host_single_stage
                """,
            )
            with self.assertRaisesRegex(ValueError, "invalid MMU rule symbol"):
                load_mmu_rule(bad_symbol)

    def test_rule_db_rejects_duplicate_ids(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule_db

        body = """
        id: duplicate_rule
        requestor: load
        mode: host_single_stage
        expect:
          result: hit
        coverage_tags:
          - requestor.load
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            self.write_rule(tmpdir, "a.yaml", body)
            self.write_rule(tmpdir, "b.yaml", body)

            with self.assertRaisesRegex(ValueError, "duplicate MMU rule id: duplicate_rule"):
                load_mmu_rule_db(Path(tmpdir))
