from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


RULE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COVERAGE_TAG_RE = re.compile(r"^[a-z0-9_]+\.[A-Za-z0-9_]+$")

SUPPORTED_REQUESTORS = frozenset(
    {
        "load",
        "hybrid_load",
        "store",
        "hlv",
        "hlvx",
        "hsv",
    }
)
SUPPORTED_MODES = frozenset(
    {
        "bare",
        "host_single_stage",
        "onlyStage1",
        "onlyStage2",
        "allStage",
    }
)
MODE_ALIASES = {
    "only_stage1": "onlyStage1",
    "only_stage2": "onlyStage2",
    "all_stage": "allStage",
}
SUPPORTED_RESULTS = frozenset(
    {
        "hit",
        "page_fault",
        "access_fault",
        "guest_page_fault",
    }
)
SUPPORTED_FAULT_RESULT_REQUESTOR_PAIRS = frozenset(
    {
        ("page_fault", "load"),
        ("page_fault", "hybrid_load"),
        ("page_fault", "store"),
        ("access_fault", "load"),
        ("access_fault", "hybrid_load"),
        ("access_fault", "store"),
        ("guest_page_fault", "hlv"),
        ("guest_page_fault", "hlvx"),
        ("guest_page_fault", "hsv"),
    }
)
SUPPORTED_ACTION_PHASES = frozenset(
    {
        "before_trigger",
        "handler",
        "post_check",
    }
)
SUPPORTED_ACTIONS = frozenset(
    {
        "sfence_vma",
        "hfence_vvma",
        "hfence_gvma",
        "remap_alias",
        "repair_fault_mapping",
        "switch_bare_mode",
        "restore_stage1",
        "enter_vs",
        "record_fault_snapshot",
    }
)
COVERAGE_TAG_TAXONOMY = (
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
    "page.identity",
    "page.alias",
    "page.superpage",
    "exception.page_fault",
    "exception.access_fault",
    "exception.guest_page_fault",
    "ctrl.sfence",
    "ctrl.hfence_vvma",
    "ctrl.hfence_gvma",
    "guest.two_stage",
    "guest.vs_only",
    "attr.nc",
)
COVERAGE_TAG_SET = frozenset(COVERAGE_TAG_TAXONOMY)
REQUIRED_FIELDS = ("id", "requestor", "mode", "expect", "coverage_tags")


@dataclass(frozen=True)
class MMURule:
    id: str
    symbol: str | None
    requestor: str
    mode: str
    preconditions: dict[str, object]
    setup: dict[str, object]
    actions: dict[str, tuple[str, ...]]
    trigger: dict[str, object]
    expect: dict[str, object]
    observe: tuple[str, ...]
    coverage_tags: tuple[str, ...]


def _require_mapping(data: object, path: Path) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _optional_mapping(data: object, field_name: str, path: Path) -> dict[str, object]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} field '{field_name}' must be a YAML mapping")
    return dict(data)


def _optional_string_list(data: object, field_name: str, path: Path) -> tuple[str, ...]:
    if data is None:
        return ()
    if not isinstance(data, list) or not all(isinstance(item, str) and item for item in data):
        raise ValueError(f"{path} field '{field_name}' must be a list of non-empty strings")
    return tuple(data)


def _normalize_mode(mode: object, path: Path) -> str:
    if not isinstance(mode, str) or not mode:
        raise ValueError(f"{path} unsupported mode: {mode}")
    normalized = MODE_ALIASES.get(mode, mode)
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"{path} unsupported mode: {mode}")
    return normalized


def _normalize_actions(data: object, path: Path) -> dict[str, tuple[str, ...]]:
    normalized: dict[str, tuple[str, ...]] = {}
    for phase_name, actions in _optional_mapping(data, "actions", path).items():
        if not isinstance(phase_name, str) or not phase_name:
            raise ValueError(f"{path} field 'actions' contains an invalid phase name")
        if phase_name not in SUPPORTED_ACTION_PHASES:
            raise ValueError(f"{path} unsupported action phase: {phase_name}")
        if not isinstance(actions, list) or not all(isinstance(item, str) and item for item in actions):
            raise ValueError(
                f"{path} field 'actions.{phase_name}' must be a list of non-empty strings"
            )
        for action in actions:
            if action not in SUPPORTED_ACTIONS:
                raise ValueError(f"{path} unsupported action: {action}")
        normalized[phase_name] = tuple(actions)
    return normalized


def _normalize_symbol(symbol: object, path: Path) -> str | None:
    if symbol is None:
        return None
    if not isinstance(symbol, str) or RULE_ID_RE.fullmatch(symbol) is None:
        raise ValueError(f"{path} invalid MMU rule symbol: {symbol}")
    return symbol


def load_mmu_rule(path: Path) -> MMURule:
    data = _require_mapping(yaml.safe_load(path.read_text()), path)
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f"{path} missing required fields: {', '.join(missing)}")

    rule_id = data["id"]
    requestor = data["requestor"]
    raw_mode = data["mode"]
    expect = _optional_mapping(data["expect"], "expect", path)
    coverage_tags = _optional_string_list(data["coverage_tags"], "coverage_tags", path)

    if not isinstance(rule_id, str) or RULE_ID_RE.fullmatch(rule_id) is None:
        raise ValueError(f"{path} invalid MMU rule id: {rule_id}")
    if requestor not in SUPPORTED_REQUESTORS:
        raise ValueError(f"{path} unsupported requestor: {requestor}")
    mode = _normalize_mode(raw_mode, path)
    if "result" not in expect:
        raise ValueError(f"{path} field 'expect' must include result")
    result = expect["result"]
    if result not in SUPPORTED_RESULTS:
        raise ValueError(f"{path} unsupported expect.result: {result}")
    if result != "hit" and (result, requestor) not in SUPPORTED_FAULT_RESULT_REQUESTOR_PAIRS:
        raise ValueError(
            f"{path} unsupported requestor/result pair: {requestor}/{result}"
        )
    if not coverage_tags:
        raise ValueError(f"{path} field 'coverage_tags' must be a non-empty list")

    seen_tags: set[str] = set()
    for tag in coverage_tags:
        if COVERAGE_TAG_RE.fullmatch(tag) is None:
            raise ValueError(f"{path} invalid coverage tag: {tag}")
        if tag not in COVERAGE_TAG_SET:
            raise ValueError(f"{path} unknown coverage tag: {tag}")
        if tag in seen_tags:
            raise ValueError(f"{path} duplicate coverage tag: {tag}")
        seen_tags.add(tag)

    return MMURule(
        id=rule_id,
        symbol=_normalize_symbol(data.get("symbol"), path),
        requestor=requestor,
        mode=mode,
        preconditions=_optional_mapping(data.get("preconditions"), "preconditions", path),
        setup=_optional_mapping(data.get("setup"), "setup", path),
        actions=_normalize_actions(data.get("actions"), path),
        trigger=_optional_mapping(data.get("trigger"), "trigger", path),
        expect=expect,
        observe=_optional_string_list(data.get("observe"), "observe", path),
        coverage_tags=coverage_tags,
    )


def load_mmu_rule_db(rule_dir: Path) -> dict[str, MMURule]:
    rule_db: dict[str, MMURule] = {}

    for path in sorted(rule_dir.glob("*.yaml")):
        rule = load_mmu_rule(path)
        if rule.id in rule_db:
            raise ValueError(f"duplicate MMU rule id: {rule.id}")
        rule_db[rule.id] = rule

    return rule_db
