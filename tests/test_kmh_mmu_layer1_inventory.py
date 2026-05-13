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

    def test_permission_fault_rules_are_observable_and_suite_selected(self) -> None:
        import yaml
        from generator.xsgen.snippet_db import load_snippet_db
        from generator.xsgen.suite_loader import build_compose_plan, load_suite

        required = {
            "load_read_perm_fault": {"requestor.load", "exception.page_fault", "pte.r", "pte.a"},
            "store_write_perm_fault": {"requestor.store", "exception.page_fault", "pte.w", "pte.d"},
            "hlvx_exec_perm_fault": {"requestor.hlvx", "exception.guest_page_fault", "pte.x", "pte.a"},
            "host_mxr_exec_load_fault": {"requestor.load", "exception.page_fault", "priv.mxr", "pte.x"},
            "host_sum_user_load_fault": {"requestor.load", "exception.page_fault", "priv.sum", "pte.u"},
            "load_accessed_bit_fault": {"requestor.load", "exception.page_fault", "pte.a"},
            "store_dirty_bit_fault": {"requestor.store", "exception.page_fault", "pte.d"},
        }

        for rule_id, tags in required.items():
            with self.subTest(rule=rule_id):
                rule = yaml.safe_load((KMH_RULE_DIR / f"{rule_id}.yaml").read_text())
                expected_result = (
                    "guest_page_fault"
                    if "exception.guest_page_fault" in tags
                    else "page_fault"
                )
                self.assertEqual(expected_result, rule["expect"]["result"])
                self.assertIn("fault_cause_match", rule["observe"])
                self.assertLessEqual(tags, set(rule["coverage_tags"]))
                if rule_id in {"load_read_perm_fault", "store_write_perm_fault", "hlvx_exec_perm_fault"}:
                    self.assertTrue(rule["setup"]["mappings"][0].get("fault"))

        snippet_db = load_snippet_db(ROOT)
        full_plan = build_compose_plan(load_suite(ROOT / "suites" / "kmh_mmu_layer1_full.yaml"), snippet_db)
        host_perm_plan = build_compose_plan(load_suite(ROOT / "suites" / "kmh_mmu_layer1_host_perm.yaml"), snippet_db)
        hyp_plan = build_compose_plan(load_suite(ROOT / "suites" / "kmh_mmu_layer1_hyp.yaml"), snippet_db)

        self.assertLessEqual(set(required), set(full_plan.mmu_rule_ids))
        self.assertLessEqual(set(required) - {"hlvx_exec_perm_fault"}, set(host_perm_plan.mmu_rule_ids))
        self.assertIn("hlvx_exec_perm_fault", hyp_plan.mmu_rule_ids)

    def test_two_stage_fault_rules_keep_stage_fault_classification_explicit(self) -> None:
        import yaml
        from generator.xsgen.snippet_db import load_snippet_db
        from generator.xsgen.suite_loader import build_compose_plan, load_suite

        stage1 = yaml.safe_load((KMH_RULE_DIR / "all_stage_stage1_page_fault.yaml").read_text())
        stage2 = yaml.safe_load((KMH_RULE_DIR / "two_stage_fault.yaml").read_text())
        only_stage2_rules = {
            rule_id: yaml.safe_load((KMH_RULE_DIR / f"{rule_id}.yaml").read_text())
            for rule_id in (
                "only_stage2_hlv_guest_fault",
                "hlvx_exec_perm_fault",
                "only_stage2_hsv_guest_fault",
            )
        }

        self.assertEqual("allStage", stage1["mode"])
        self.assertEqual("page_fault", stage1["expect"]["result"])
        self.assertIn("exception.page_fault", stage1["coverage_tags"])
        self.assertNotIn("exception.guest_page_fault", stage1["coverage_tags"])
        self.assertTrue(any(mapping.get("fault") and mapping.get("stage", "stage1") == "stage1" for mapping in stage1["setup"]["mappings"]))
        self.assertTrue(any(mapping.get("stage") == "stage2" for mapping in stage1["setup"]["mappings"]))

        self.assertEqual("guest_page_fault", stage2["expect"]["result"])
        self.assertIn("exception.guest_page_fault", stage2["coverage_tags"])
        self.assertTrue(any(mapping.get("fault") and mapping.get("stage") == "stage2" for mapping in stage2["setup"]["mappings"]))

        for rule_id, rule in only_stage2_rules.items():
            with self.subTest(rule=rule_id):
                self.assertEqual("onlyStage2", rule["mode"])
                self.assertEqual("guest_page_fault", rule["expect"]["result"])
                self.assertIn("exception.guest_page_fault", rule["coverage_tags"])
                self.assertTrue(any(mapping.get("fault") and mapping.get("stage") == "stage2" for mapping in rule["setup"]["mappings"]))

        snippet_db = load_snippet_db(ROOT)
        hyp_plan = build_compose_plan(load_suite(ROOT / "suites" / "kmh_mmu_layer1_hyp.yaml"), snippet_db)
        self.assertLessEqual(
            {"all_stage_stage1_page_fault", "two_stage_fault", *only_stage2_rules},
            set(hyp_plan.mmu_rule_ids),
        )

    def test_superpage_rules_have_real_superpage_mappings_and_suite_coverage(self) -> None:
        import yaml
        from generator.xsgen.snippet_db import load_snippet_db
        from generator.xsgen.suite_loader import build_compose_plan, load_suite

        superpage_rules = {
            "superpage": "store",
            "superpage_load_hit": "load",
            "only_stage2_superpage_hlv_hit": "hlv",
            "all_stage_superpage_stage2_4k_hit": "hlv",
        }

        for rule_id, requestor in superpage_rules.items():
            with self.subTest(rule=rule_id):
                rule = yaml.safe_load((KMH_RULE_DIR / f"{rule_id}.yaml").read_text())
                self.assertEqual(requestor, rule["requestor"])
                self.assertIn("page.superpage", rule["coverage_tags"])
                self.assertTrue(
                    any(
                        mapping.get("kind") == "superpage" and mapping.get("page_count") == 512
                        for mapping in rule["setup"]["mappings"]
                    )
                )
                if rule_id.startswith("only_stage2"):
                    self.assertEqual("onlyStage2", rule["mode"])
                    self.assertTrue(any(mapping.get("stage") == "stage2" for mapping in rule["setup"]["mappings"]))
                if rule_id.startswith("all_stage"):
                    self.assertEqual("allStage", rule["mode"])
                    self.assertTrue(any(mapping.get("stage", "stage1") == "stage1" and mapping.get("kind") == "superpage" for mapping in rule["setup"]["mappings"]))
                    self.assertTrue(any(mapping.get("stage") == "stage2" and mapping.get("page_count", 1) == 1 for mapping in rule["setup"]["mappings"]))

        snippet_db = load_snippet_db(ROOT)
        full_plan = build_compose_plan(load_suite(ROOT / "suites" / "kmh_mmu_layer1_full.yaml"), snippet_db)
        self.assertLessEqual(set(superpage_rules), set(full_plan.mmu_rule_ids))

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
        stage2 = yaml.safe_load((KMH_RULE_DIR / "only_stage2_vmid_switch.yaml").read_text())

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

        stage2_mappings = stage2["setup"]["mappings"]
        self.assertEqual("onlyStage2", stage2["mode"])
        self.assertIn("switch_hgatp_context", stage2["actions"]["before_trigger"])
        self.assertIn("hfence_gvma", stage2["actions"]["before_trigger"])
        self.assertEqual(
            1,
            len({mapping["va"] for mapping in stage2_mappings}),
            "onlyStage2 VMID switch rule must map the same GPA in old and switched G-stage roots",
        )
        self.assertGreater(
            len({mapping["pa"] for mapping in stage2_mappings}),
            1,
            "onlyStage2 VMID switch rule must distinguish old and switched physical targets",
        )
        self.assertTrue(
            any(mapping.get("context") == "switch" and mapping.get("stage") == "stage2" for mapping in stage2_mappings)
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
