from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
KMH_RULE_DIR = ROOT / "snippets" / "mmu_rules" / "kmh_layer1"
PILOT_RULE_DIR = ROOT / "snippets" / "mmu_rules" / "pilot"


class KMHMMULayer1InventoryTest(unittest.TestCase):
    def test_kmh_layer1_rule_db_loads_core_axes(self) -> None:
        from generator.xsgen.mmu_rule_loader import load_mmu_rule_db

        rule_db = load_mmu_rule_db(KMH_RULE_DIR)

        self.assertGreater(len(rule_db), 0)
        for rule in rule_db.values():
            with self.subTest(rule=rule.id):
                self.assertTrue(rule.observe, f"{rule.id} must define observe points")
                self.assertNotIn("requestor.itlb", rule.coverage_tags)
                self.assertNotIn("requestor.prefetch", rule.coverage_tags)
                self.assertNotIn(rule.expect["result"], {"miss", "refill", "replay"})

        coverage = {tag for rule in rule_db.values() for tag in rule.coverage_tags}
        for tag in (
            "requestor.load",
            "requestor.hybrid_load",
            "requestor.store",
            "requestor.hlv",
            "requestor.hlvx",
            "requestor.hsv",
            "mode.bare",
            "mode.host_single_stage",
            "mode.onlyStage1",
            "mode.onlyStage2",
            "mode.allStage",
            "exception.page_fault",
            "exception.access_fault",
            "exception.guest_page_fault",
            "pte.raw",
            "priv.mxr",
            "priv.sum",
            "attr.pmp_deny",
            "attr.pma",
            "attr.pbmt_nc",
            "attr.mmio",
            "ctrl.satp",
            "ctrl.sfence",
            "ctrl.vsatp",
            "ctrl.hgatp",
            "ctrl.asid",
            "ctrl.vmid",
            "retry.repair_then_reexecute",
        ):
            with self.subTest(tag=tag):
                self.assertIn(tag, coverage)

    def test_kmh_layer1_suites_resolve_and_keep_v3_vector_free(self) -> None:
        from generator.xsgen.snippet_db import load_snippet_db
        from generator.xsgen.suite_loader import build_compose_plan, load_suite

        snippet_db = load_snippet_db(ROOT)
        suites = {
            "smoke": ROOT / "suites" / "kmh_mmu_layer1_smoke.yaml",
            "host_perm": ROOT / "suites" / "kmh_mmu_layer1_host_perm.yaml",
            "attr_ctrl": ROOT / "suites" / "kmh_mmu_layer1_attr_ctrl.yaml",
            "v2": ROOT / "suites" / "kmh_mmu_layer1_v2_smoke.yaml",
            "v3": ROOT / "suites" / "kmh_mmu_layer1_v3_smoke.yaml",
            "full": ROOT / "suites" / "kmh_mmu_layer1_full.yaml",
        }

        plans = {
            name: build_compose_plan(load_suite(path), snippet_db)
            for name, path in suites.items()
        }

        for name, plan in plans.items():
            with self.subTest(suite=name):
                self.assertGreater(len(plan.mmu_rule_ids), 0)
                self.assertEqual("init_basic_env", plan.snippet_ids[0])
                self.assertIn("mmu_rule_runner_main", plan.snippet_ids)
                self.assertEqual("finish_check", plan.snippet_ids[-1])

        self.assertLess(
            len(plans["v2"].mmu_rule_ids),
            len(plans["full"].mmu_rule_ids),
            "v2 smoke should remain a bounded representative smoke, not a grouped regression",
        )
        self.assertEqual(
            plans["v2"].mmu_rule_ids,
            plans["v3"].mmu_rule_ids,
            "v2/v3 smoke suites must exercise the same non-vector rule set",
        )
        self.assertTrue(set(plans["v2"].mmu_rule_ids).issubset(set(plans["full"].mmu_rule_ids)))
        self.assertFalse(
            any("vector" in rule_id for rule_id in plans["v3"].mmu_rule_ids),
            "v3 layer1 smoke must exclude vector rules in the first wave",
        )

        self.assertLessEqual({"attr.pmp_deny", "attr.pbmt_nc", "attr.pma", "attr.mmio"}, set(plans["attr_ctrl"].mmu_coverage_tags))
        self.assertLessEqual({"priv.mxr", "priv.sum", "exception.page_fault", "exception.access_fault"}, set(plans["host_perm"].mmu_coverage_tags))
        self.assertLessEqual({"mode.onlyStage1", "mode.onlyStage2", "mode.allStage"}, set(plans["full"].mmu_coverage_tags))
        self.assertIn("retry.repair_then_reexecute", plans["full"].mmu_coverage_tags)

    def test_pbmt_rule_marks_reserved_nc_pte_semantics(self) -> None:
        import yaml

        rule = yaml.safe_load((KMH_RULE_DIR / "host_pbmt_nc.yaml").read_text())
        mapping = rule["setup"]["mappings"][0]

        self.assertEqual("page_fault", rule["expect"]["result"])
        self.assertIn("fault_cause_match", rule["observe"])
        self.assertIn("attribute_policy_match", rule["observe"])
        self.assertEqual("nc", rule["setup"]["attributes"]["pbmt"])
        self.assertEqual("nc", mapping["raw_pte"]["pbmt"])
        self.assertIn("attr.nc", rule["coverage_tags"])
        self.assertIn("attr.pbmt_nc", rule["coverage_tags"])

    def test_pma_mmio_rule_targets_runtime_mmio_page(self) -> None:
        import yaml

        rule = yaml.safe_load((KMH_RULE_DIR / "host_pma_mmio_attribute.yaml").read_text())
        mapping = rule["setup"]["mappings"][0]

        self.assertTrue(rule["setup"]["attributes"]["mmio"])
        self.assertEqual(0x3800B000, mapping["pa"])
        self.assertEqual(0x900070FF8, rule["trigger"]["addr"])
        self.assertIn("attribute_policy_match", rule["observe"])
        self.assertIn("attr.pma", rule["coverage_tags"])
        self.assertIn("attr.mmio", rule["coverage_tags"])

    def test_only_stage1_hit_is_not_labeled_identity(self) -> None:
        import yaml

        rule = yaml.safe_load((KMH_RULE_DIR / "only_stage1_load_hit.yaml").read_text())
        mapping = rule["setup"]["mappings"][0]

        self.assertNotEqual(mapping["va"], mapping["pa"])
        self.assertNotIn("page.identity", rule["coverage_tags"])

    def test_context_switch_rules_depend_on_switched_page_table_roots(self) -> None:
        import yaml

        satp = yaml.safe_load((KMH_RULE_DIR / "satp_asid_switch.yaml").read_text())
        guest = yaml.safe_load((KMH_RULE_DIR / "vsatp_hgatp_context_switch.yaml").read_text())

        satp_mappings = satp["setup"]["mappings"]
        self.assertGreaterEqual(len(satp_mappings), 2)
        self.assertTrue(any(mapping.get("context") == "switch" for mapping in satp_mappings))
        self.assertEqual(
            1,
            len({mapping["va"] for mapping in satp_mappings if mapping.get("stage", "stage1") == "stage1"}),
            "satp switch rule must map the same VA in old and switched roots",
        )
        self.assertGreater(
            len({mapping["pa"] for mapping in satp_mappings}),
            1,
            "satp switch rule must distinguish old and switched physical targets",
        )

        guest_mappings = guest["setup"]["mappings"]
        self.assertTrue(
            any(mapping.get("context") == "switch" and mapping.get("stage", "stage1") == "stage1" for mapping in guest_mappings)
        )
        self.assertTrue(
            any(mapping.get("context") == "switch" and mapping.get("stage") == "stage2" for mapping in guest_mappings)
        )

    def test_rule_physical_targets_avoid_runtime_and_page_table_image_area(self) -> None:
        import yaml

        reserved_start = 0x80000000
        reserved_end = 0x80100000
        rule_dirs = (KMH_RULE_DIR, PILOT_RULE_DIR)

        for rule_dir in rule_dirs:
            for path in sorted(rule_dir.glob("*.yaml")):
                rule = yaml.safe_load(path.read_text())
                mappings = rule.get("setup", {}).get("mappings", [])
                for index, mapping in enumerate(mappings):
                    pa = mapping.get("pa")
                    if pa is None:
                        continue
                    with self.subTest(rule_dir=rule_dir.name, rule=path.name, mapping=index):
                        self.assertFalse(
                            reserved_start <= pa < reserved_end,
                            (
                                f"{path.name} mapping {index} uses pa=0x{pa:x}, "
                                "which can collide with generated runtime BSS/page-table objects"
                            ),
                        )
