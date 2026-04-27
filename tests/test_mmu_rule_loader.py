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

    def test_loader_accepts_documented_mode_spellings_and_pilot_rules(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule

        pilot_dir = ROOT / "snippets" / "mmu_rules" / "pilot"
        expected_rules = {
            "bare_identity.yaml": ("bare_identity", "bare"),
            "sv39_alias.yaml": ("sv39_alias", "host_single_stage"),
            "superpage.yaml": ("superpage", "host_single_stage"),
            "sfence_remap.yaml": ("sfence_remap", "host_single_stage"),
            "load_page_fault.yaml": ("load_page_fault", "host_single_stage"),
            "two_stage_fault.yaml": ("two_stage_fault", "allStage"),
        }

        for relative_path, (rule_id, mode) in expected_rules.items():
            with self.subTest(path=relative_path):
                rule = load_mmu_rule(pilot_dir / relative_path)
                self.assertEqual(rule_id, rule.id)
                self.assertEqual(mode, rule.mode)

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
