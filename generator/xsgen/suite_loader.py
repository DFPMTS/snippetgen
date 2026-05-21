from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import re

import yaml

from generator.xsgen.mmu_rule_loader import load_mmu_rule_db
from generator.xsgen.model import ComposePlan, SnippetSpec, SuiteSpec

SUPPORTED_TARGET = "xiangshan-verilator"
SUITE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def _require_mapping(data: object, path: Path) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _require_string_list(data: object, field_name: str, path: Path) -> tuple[str, ...]:
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} field '{field_name}' must be a non-empty list")
    if not all(isinstance(item, str) and item for item in data):
        raise ValueError(f"{path} field '{field_name}' contains an invalid string entry")
    return tuple(data)


def _resolve_rule_dir(raw_path: object, path: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"{path} field 'compose.mmu.rule_dir' must be a non-empty string")

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.is_dir():
        raise ValueError(f"{path} MMU rule directory does not exist: {raw_path}")
    return candidate


def _load_mmu_section(compose: Mapping[str, object], path: Path) -> tuple[Path | None, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    raw_mmu = compose.get("mmu")
    if raw_mmu is None:
        return None, (), (), ()

    mmu = _require_mapping(raw_mmu, path)
    rule_dir = _resolve_rule_dir(mmu.get("rule_dir"), path)
    rule_ids = _require_string_list(mmu.get("rule_ids"), "compose.mmu.rule_ids", path)
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError(f"{path} field 'compose.mmu.rule_ids' contains duplicates")

    rule_db = load_mmu_rule_db(rule_dir)
    missing = [rule_id for rule_id in rule_ids if rule_id not in rule_db]
    if missing:
        raise ValueError(f"unknown MMU rule id in suite: {missing[0]}")

    coverage_tags = sorted(
        {
            tag
            for rule_id in rule_ids
            for tag in rule_db[rule_id].coverage_tags
        }
    )
    return rule_dir, rule_ids, tuple(sorted(rule_db)), tuple(coverage_tags)


def _load_vector_mmu_coverage(compose: Mapping[str, object], path: Path) -> tuple[dict[str, str], ...]:
    raw_vector = compose.get("vector_mmu_coverage")
    if raw_vector is None:
        return ()
    if not isinstance(raw_vector, list):
        raise ValueError(f"{path} field 'compose.vector_mmu_coverage' must be a list")

    required = {
        "id",
        "requestor",
        "mode",
        "form",
        "eew",
        "page_boundary",
        "fault",
        "attribute",
    }
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(raw_vector):
        item = _require_mapping(raw_item, path)
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(
                f"{path} vector_mmu_coverage[{index}] missing required fields: {', '.join(missing)}"
            )
        normalized_item: dict[str, str] = {}
        for key, value in item.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                raise ValueError(f"{path} vector_mmu_coverage[{index}] contains an invalid entry")
            normalized_item[key] = value
        if "fail_codes" in normalized_item:
            for raw_code in normalized_item["fail_codes"].split(","):
                code = raw_code.strip()
                if not code or not code.isdecimal():
                    raise ValueError(f"{path} vector_mmu_coverage[{index}] has invalid fail_codes")
        coverage_id = normalized_item["id"]
        if coverage_id in seen:
            raise ValueError(f"{path} duplicate vector MMU coverage id: {coverage_id}")
        seen.add(coverage_id)
        normalized.append(normalized_item)
    return tuple(normalized)


def load_suite(path: Path) -> SuiteSpec:
    data = _require_mapping(yaml.safe_load(path.read_text()), path)
    compose = _require_mapping(data.get("compose"), path)

    for field in ("suite", "target", "seed"):
        if field not in data:
            raise ValueError(f"{path} missing required field: {field}")

    suite_name = str(data["suite"])
    if SUITE_NAME_RE.fullmatch(suite_name) is None:
        raise ValueError(f"{path} invalid suite name: {suite_name}")

    raw_seed = data["seed"]
    if isinstance(raw_seed, bool) or not isinstance(raw_seed, int) or raw_seed < 0:
        raise ValueError(f"{path} invalid seed: {raw_seed}")

    target = str(data["target"])
    if target != SUPPORTED_TARGET:
        raise ValueError(f"{path} unsupported target: {target}")

    mode = compose.get("mode")
    if mode != "sequence":
        raise ValueError(f"{path} compose mode '{mode}' is future-only in ELF-first PoC")

    legacy_present = "snippets" in compose
    deferred_present = "run_snippets" in compose or "check_snippets" in compose

    legacy_snippet_ids = compose.get("snippets")
    run_snippet_ids = compose.get("run_snippets")
    check_snippet_ids = compose.get("check_snippets")

    if legacy_present and deferred_present:
        raise ValueError(f"{path} cannot mix compose.snippets with run_snippets/check_snippets")

    mmu_rule_dir, mmu_rule_ids, mmu_defined_rule_ids, mmu_coverage_tags = _load_mmu_section(
        compose,
        path,
    )
    vector_mmu_coverage = _load_vector_mmu_coverage(compose, path)

    if legacy_present:
        if not isinstance(legacy_snippet_ids, list) or not legacy_snippet_ids:
            raise ValueError(f"{path} field 'compose.snippets' must be a non-empty list")
        if not all(isinstance(item, str) and item for item in legacy_snippet_ids):
            raise ValueError(f"{path} field 'compose.snippets' contains an invalid snippet id")
        if mmu_rule_dir is not None and "mmu_rule_runner_main" not in legacy_snippet_ids:
            raise ValueError(f"{path} compose.mmu requires mmu_rule_runner_main in compose.snippets")

        return SuiteSpec(
            name=suite_name,
            target=target,
            seed=raw_seed,
            compose_mode=str(mode),
            snippet_ids=tuple(legacy_snippet_ids),
            mmu_rule_dir=mmu_rule_dir,
            mmu_rule_ids=mmu_rule_ids,
            mmu_defined_rule_ids=mmu_defined_rule_ids,
            mmu_coverage_tags=mmu_coverage_tags,
            vector_mmu_coverage=vector_mmu_coverage,
        )

    if not deferred_present:
        raise ValueError(f"{path} compose section requires snippets or run_snippets/check_snippets")
    if mmu_rule_dir is not None:
        raise ValueError(f"{path} compose.mmu currently requires compose.snippets")
    if not isinstance(run_snippet_ids, list) or not run_snippet_ids:
        raise ValueError(f"{path} field 'compose.run_snippets' must be a non-empty list")
    if not isinstance(check_snippet_ids, list) or not check_snippet_ids:
        raise ValueError(f"{path} field 'compose.check_snippets' must be a non-empty list")
    if not all(isinstance(item, str) and item for item in [*run_snippet_ids, *check_snippet_ids]):
        raise ValueError(f"{path} deferred compose contains an invalid snippet id")

    snippet_ids = tuple(dict.fromkeys([*run_snippet_ids, *check_snippet_ids]))

    return SuiteSpec(
        name=suite_name,
        target=target,
        seed=raw_seed,
        compose_mode=str(mode),
        snippet_ids=snippet_ids,
        run_snippet_ids=tuple(run_snippet_ids),
        check_snippet_ids=tuple(check_snippet_ids),
        vector_mmu_coverage=vector_mmu_coverage,
    )


def build_compose_plan(
    suite: SuiteSpec,
    snippet_db: Mapping[str, SnippetSpec],
) -> ComposePlan:
    resolved_snippets: list[SnippetSpec] = []
    for snippet_id in suite.snippet_ids:
        if snippet_id not in snippet_db:
            raise ValueError(f"unknown snippet id in suite: {snippet_id}")
        resolved_snippets.append(snippet_db[snippet_id])

    return ComposePlan(
        suite_name=suite.name,
        target=suite.target,
        seed=suite.seed,
        snippet_ids=suite.snippet_ids,
        snippets=tuple(resolved_snippets),
        run_snippet_ids=suite.run_snippet_ids,
        check_snippet_ids=suite.check_snippet_ids,
        mmu_rule_dir=suite.mmu_rule_dir,
        mmu_rule_ids=suite.mmu_rule_ids,
        mmu_defined_rule_ids=suite.mmu_defined_rule_ids,
        mmu_coverage_tags=suite.mmu_coverage_tags,
        vector_mmu_coverage=suite.vector_mmu_coverage,
    )
