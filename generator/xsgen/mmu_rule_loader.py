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
        "switch_satp_context",
        "switch_vsatp_context",
        "switch_hgatp_context",
        "switch_asid_context",
        "switch_vmid_context",
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
    "attr.nc",
    "ctrl.satp",
    "ctrl.sfence",
    "ctrl.hfence_vvma",
    "ctrl.hfence_gvma",
    "ctrl.vsatp",
    "ctrl.hgatp",
    "ctrl.asid",
    "ctrl.vmid",
    "retry.repair_then_reexecute",
    "guest.two_stage",
    "guest.vs_only",
)
COVERAGE_TAG_SET = frozenset(COVERAGE_TAG_TAXONOMY)
REQUIRED_FIELDS = ("id", "requestor", "mode", "expect", "coverage_tags")
PTE_RAW_BITS = frozenset({"v", "r", "w", "x", "u", "g", "a", "d"})
PTE_RAW_VALUE_BITS = {
    "v": 1 << 0,
    "r": 1 << 1,
    "w": 1 << 2,
    "x": 1 << 3,
    "u": 1 << 4,
    "g": 1 << 5,
    "a": 1 << 6,
    "d": 1 << 7,
}
PTE_PBMT_MASK = 0x3 << 61
PTE_PBMT_NC_VALUE = 0x1 << 61
ATTRIBUTE_TAGS = frozenset({"attr.nc", "attr.pma", "attr.pbmt_nc", "attr.mmio"})
MAPPING_CONTEXTS = frozenset({"initial", "switch"})


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


def _mapping_list(setup: dict[str, object], path: Path) -> tuple[dict[str, object], ...]:
    mappings = setup.get("mappings")
    if mappings is None:
        return ()
    if not isinstance(mappings, list):
        raise ValueError(f"{path} field 'setup.mappings' must be a list")
    normalized = []
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise ValueError(f"{path} field 'setup.mappings[{index}]' must be a YAML mapping")
        normalized.append(mapping)
    return tuple(normalized)


def _raw_pte_bits(raw_pte: object, path: Path) -> frozenset[str]:
    if raw_pte is None:
        return frozenset()
    if not isinstance(raw_pte, dict):
        raise ValueError(f"{path} field 'raw_pte' must be a YAML mapping")
    value = raw_pte.get("value")
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path} field 'raw_pte.value' must be a non-negative integer")
        return frozenset(bit for bit, mask in PTE_RAW_VALUE_BITS.items() if (value & mask) != 0)
    bits = raw_pte.get("bits")
    if not isinstance(bits, list) or not bits:
        raise ValueError(f"{path} field 'raw_pte.bits' must be a non-empty list")
    if not all(isinstance(bit, str) and bit for bit in bits):
        raise ValueError(f"{path} field 'raw_pte.bits' contains an invalid bit")
    bit_set = frozenset(bits)
    unknown = sorted(bit_set - PTE_RAW_BITS)
    if unknown:
        raise ValueError(f"{path} field 'raw_pte.bits' contains unsupported bits: {', '.join(unknown)}")
    return bit_set


def _validate_raw_pte(mapping: dict[str, object], result: object, path: Path) -> None:
    raw_pte = mapping.get("raw_pte")
    if raw_pte is None:
        return
    bits = _raw_pte_bits(raw_pte, path)
    if "w" in bits and "r" not in bits:
        if result == "hit":
            raise ValueError(f"{path} illegal raw PTE hit claim: W is set while R is clear")
    if result == "hit" and "v" not in bits:
        raise ValueError(f"{path} illegal raw PTE hit claim: V is clear")


def _setup_attributes(setup: dict[str, object], path: Path) -> dict[str, object]:
    attributes = setup.get("attributes")
    if attributes is None:
        return {}
    if not isinstance(attributes, dict):
        raise ValueError(f"{path} field 'setup.attributes' must be a YAML mapping")
    return dict(attributes)


def _raw_pte_has_pbmt_nc(raw_pte: object) -> bool:
    if not isinstance(raw_pte, dict):
        return False
    if raw_pte.get("pbmt") == "nc":
        return True
    value = raw_pte.get("value")
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (value & PTE_PBMT_MASK) == PTE_PBMT_NC_VALUE
    )


def _has_pbmt_nc(setup: dict[str, object], mappings: tuple[dict[str, object], ...], path: Path) -> bool:
    attributes = _setup_attributes(setup, path)
    if attributes.get("pbmt") == "nc":
        return True
    for mapping in mappings:
        if _raw_pte_has_pbmt_nc(mapping.get("raw_pte")):
            return True
    return False


def _has_pma(setup: dict[str, object], path: Path) -> bool:
    attributes = _setup_attributes(setup, path)
    return attributes.get("pma") in {"io", "mmio"}


def _has_mmio(setup: dict[str, object], path: Path) -> bool:
    attributes = _setup_attributes(setup, path)
    return attributes.get("mmio") is True


def _has_pmp_deny(setup: dict[str, object], path: Path) -> bool:
    pmp = setup.get("pmp")
    if pmp is None:
        return False
    if not isinstance(pmp, dict):
        raise ValueError(f"{path} field 'setup.pmp' must be a YAML mapping")
    return "deny_napot" in pmp


def _validate_attribute_tags(
    *,
    setup: dict[str, object],
    mappings: tuple[dict[str, object], ...],
    observe: tuple[str, ...],
    coverage_tags: tuple[str, ...],
    path: Path,
) -> None:
    tag_set = set(coverage_tags)
    attr_tags = tag_set & ATTRIBUTE_TAGS
    if not attr_tags:
        return
    if "attribute_policy_match" not in observe:
        raise ValueError(f"{path} attribute coverage tag requires attribute_policy_match observe")
    if {"attr.nc", "attr.pbmt_nc"} & tag_set and not _has_pbmt_nc(setup, mappings, path):
        raise ValueError(f"{path} attribute coverage tag requires setup.attributes.pbmt: nc")
    if "attr.pma" in tag_set and not _has_pma(setup, path):
        raise ValueError(f"{path} attribute coverage tag requires setup.attributes.pma: io")
    if "attr.mmio" in tag_set and not _has_mmio(setup, path):
        raise ValueError(f"{path} attribute coverage tag requires setup.attributes.mmio: true")


def _validate_pmp_tag(
    *,
    setup: dict[str, object],
    coverage_tags: tuple[str, ...],
    path: Path,
) -> None:
    if "attr.pmp_deny" not in coverage_tags:
        return
    if not _has_pmp_deny(setup, path):
        raise ValueError(f"{path} attr.pmp_deny coverage tag requires setup.pmp.deny_napot")


def _validate_all_stage(
    *,
    mode: str,
    mappings: tuple[dict[str, object], ...],
    path: Path,
) -> None:
    if mode != "allStage" or not mappings:
        return
    has_stage1 = any(mapping.get("stage", "stage1") == "stage1" for mapping in mappings)
    has_stage2 = any(mapping.get("stage", "stage1") == "stage2" for mapping in mappings)
    if not (has_stage1 and has_stage2):
        raise ValueError(f"{path} allStage rule requires both stage1 and stage2 mappings")


def _validate_mapping_contexts(
    *,
    mode: str,
    mappings: tuple[dict[str, object], ...],
    actions: dict[str, tuple[str, ...]],
    path: Path,
) -> None:
    root_switch_actions = {
        "switch_satp_context",
        "switch_vsatp_context",
        "switch_hgatp_context",
    }
    uses_root_switch_action = any(action in root_switch_actions for phase in actions.values() for action in phase)
    uses_stage1_root_switch = any(
        action in {"switch_satp_context", "switch_vsatp_context"}
        for phase in actions.values()
        for action in phase
    )
    uses_stage2_root_switch = any(
        action == "switch_hgatp_context"
        for phase in actions.values()
        for action in phase
    )
    has_switch_mapping = False
    has_switch_stage1 = False
    has_switch_stage2 = False

    for mapping in mappings:
        context = mapping.get("context", "initial")
        if context not in MAPPING_CONTEXTS:
            raise ValueError(f"{path} unsupported mapping context: {context}")
        if context == "switch":
            has_switch_mapping = True
            if mapping.get("stage", "stage1") == "stage2":
                has_switch_stage2 = True
            else:
                has_switch_stage1 = True

    if uses_root_switch_action and not has_switch_mapping:
        raise ValueError(f"{path} context switch action requires a switch-context mapping")
    if mode == "allStage" and uses_stage1_root_switch and not has_switch_stage1:
        raise ValueError(f"{path} allStage stage1 context switch requires a switch-context stage1 mapping")
    if mode == "allStage" and uses_stage2_root_switch and not has_switch_stage2:
        raise ValueError(f"{path} allStage stage2 context switch requires a switch-context stage2 mapping")


def _validate_retry(
    *,
    expect: dict[str, object],
    actions: dict[str, tuple[str, ...]],
    coverage_tags: tuple[str, ...],
    path: Path,
) -> None:
    retry = expect.get("retry", "none")
    if retry not in {"none", "repair_then_reexecute"}:
        raise ValueError(f"{path} unsupported expect.retry: {retry}")
    if "retry.repair_then_reexecute" in coverage_tags and retry != "repair_then_reexecute":
        raise ValueError(f"{path} retry.repair_then_reexecute tag requires expect.retry")
    if retry == "repair_then_reexecute" and "repair_fault_mapping" not in actions.get("handler", ()):
        raise ValueError(f"{path} repair_then_reexecute requires handler repair_fault_mapping")


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

    setup = _optional_mapping(data.get("setup"), "setup", path)
    actions = _normalize_actions(data.get("actions"), path)
    observe = _optional_string_list(data.get("observe"), "observe", path)
    mappings = _mapping_list(setup, path)

    seen_tags: set[str] = set()
    for tag in coverage_tags:
        if COVERAGE_TAG_RE.fullmatch(tag) is None:
            raise ValueError(f"{path} invalid coverage tag: {tag}")
        if tag not in COVERAGE_TAG_SET:
            raise ValueError(f"{path} unknown coverage tag: {tag}")
        if tag in seen_tags:
            raise ValueError(f"{path} duplicate coverage tag: {tag}")
        seen_tags.add(tag)

    for mapping in mappings:
        _validate_raw_pte(mapping, result, path)
    _validate_attribute_tags(
        setup=setup,
        mappings=mappings,
        observe=observe,
        coverage_tags=coverage_tags,
        path=path,
    )
    _validate_pmp_tag(setup=setup, coverage_tags=coverage_tags, path=path)
    _validate_all_stage(mode=mode, mappings=mappings, path=path)
    _validate_mapping_contexts(mode=mode, mappings=mappings, actions=actions, path=path)
    _validate_retry(expect=expect, actions=actions, coverage_tags=coverage_tags, path=path)

    return MMURule(
        id=rule_id,
        symbol=_normalize_symbol(data.get("symbol"), path),
        requestor=requestor,
        mode=mode,
        preconditions=_optional_mapping(data.get("preconditions"), "preconditions", path),
        setup=setup,
        actions=actions,
        trigger=_optional_mapping(data.get("trigger"), "trigger", path),
        expect=expect,
        observe=observe,
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
