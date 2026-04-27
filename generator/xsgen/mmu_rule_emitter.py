from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from generator.xsgen.mmu_rule_loader import COVERAGE_TAG_TAXONOMY, MMURule, load_mmu_rule_db


MMU_RULE_FLAG_IDENTITY = 1 << 0
MMU_RULE_FLAG_SUPERPAGE = 1 << 1
MMU_RULE_FLAG_FAULT = 1 << 2
MMU_RULE_FLAG_STAGE2 = 1 << 3

PTE_PERM_BITS = {
    "r": "XSAM_MMU_PTE_R",
    "w": "XSAM_MMU_PTE_W",
    "x": "XSAM_MMU_PTE_X",
    "u": "XSAM_MMU_PTE_U",
    "g": "XSAM_MMU_PTE_G",
    "a": "XSAM_MMU_PTE_A",
    "d": "XSAM_MMU_PTE_D",
}
STAGE_VALUES = {"stage1", "stage2"}
MAPPING_KIND_VALUES = {"identity", "alias", "superpage"}
KNOWN_SYMBOLIC_ADDRESSES = {
    "test_page": 0x80020000,
    "test_page_alt": 0x80021000,
    "guest_page": 0x80400000,
    "guest_page_alt": 0x80401000,
}
FAULT_MASK_BY_RESULT_AND_REQUESTOR = {
    ("page_fault", "load"): ("XSAM_MMU_FAULT_LOAD_PAGE", "XSAM_MMU_CAUSE_LOAD_PAGE_FAULT"),
    ("page_fault", "hybrid_load"): ("XSAM_MMU_FAULT_LOAD_PAGE", "XSAM_MMU_CAUSE_LOAD_PAGE_FAULT"),
    ("page_fault", "store"): ("XSAM_MMU_FAULT_STORE_PAGE", "XSAM_MMU_CAUSE_STORE_PAGE_FAULT"),
    ("access_fault", "load"): ("XSAM_MMU_FAULT_LOAD_ACCESS", "XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT"),
    ("access_fault", "hybrid_load"): ("XSAM_MMU_FAULT_LOAD_ACCESS", "XSAM_MMU_CAUSE_LOAD_ACCESS_FAULT"),
    ("access_fault", "store"): ("XSAM_MMU_FAULT_STORE_ACCESS", "XSAM_MMU_CAUSE_STORE_ACCESS_FAULT"),
    ("guest_page_fault", "hlv"): ("XSAM_MMU_FAULT_LOAD_GUEST_PAGE", "XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT"),
    ("guest_page_fault", "hlvx"): ("XSAM_MMU_FAULT_LOAD_GUEST_PAGE", "XSAM_MMU_CAUSE_LOAD_GUEST_PAGE_FAULT"),
    ("guest_page_fault", "hsv"): ("XSAM_MMU_FAULT_STORE_GUEST_PAGE", "XSAM_MMU_CAUSE_STORE_GUEST_PAGE_FAULT"),
}


@dataclass(frozen=True)
class EmittedMMURuleBundle:
    defined_rule_ids: tuple[str, ...]
    selected_rule_ids: tuple[str, ...]
    coverage_tags: tuple[str, ...]


def _c_string(value: str) -> str:
    return json.dumps(value)


def _c_uint(value: int) -> str:
    return f"0x{value:x}ull"


def _rule_symbol(rule: MMURule) -> str:
    return rule.symbol or rule.id


def _resolve_address(value: object, *, mapping_vas: dict[str, int], field_name: str, rule_id: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"MMU rule {rule_id} field '{field_name}' must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value in mapping_vas:
            return mapping_vas[value]
        if value in KNOWN_SYMBOLIC_ADDRESSES:
            return KNOWN_SYMBOLIC_ADDRESSES[value]
    raise ValueError(f"MMU rule {rule_id} field '{field_name}' has unsupported address value: {value}")


def _mapping_flags(mapping: dict[str, object], *, va: int, pa: int, rule_id: str) -> int:
    flags = 0
    kind = mapping.get("kind")
    if kind is not None:
        if kind not in MAPPING_KIND_VALUES:
            raise ValueError(f"MMU rule {rule_id} mapping has unsupported kind: {kind}")
        if kind == "identity":
            flags |= MMU_RULE_FLAG_IDENTITY
        if kind == "superpage":
            flags |= MMU_RULE_FLAG_SUPERPAGE
    elif va == pa:
        flags |= MMU_RULE_FLAG_IDENTITY

    page_count = mapping.get("page_count", 1)
    if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1:
        raise ValueError(f"MMU rule {rule_id} mapping has invalid page_count: {page_count}")
    if page_count > 1:
        flags |= MMU_RULE_FLAG_SUPERPAGE

    fault = mapping.get("fault", False)
    if not isinstance(fault, bool):
        raise ValueError(f"MMU rule {rule_id} mapping has invalid fault flag: {fault}")
    if fault:
        flags |= MMU_RULE_FLAG_FAULT

    stage = mapping.get("stage", "stage1")
    if stage not in STAGE_VALUES:
        raise ValueError(f"MMU rule {rule_id} mapping has unsupported stage: {stage}")
    if stage == "stage2":
        flags |= MMU_RULE_FLAG_STAGE2

    return flags


def _mapping_perm_expr(perms: object, rule_id: str) -> str:
    if not isinstance(perms, list) or not perms:
        raise ValueError(f"MMU rule {rule_id} mapping perms must be a non-empty list")
    bits: list[str] = []
    seen: set[str] = set()
    for perm in perms:
        if perm not in PTE_PERM_BITS:
            raise ValueError(f"MMU rule {rule_id} mapping has unsupported perm: {perm}")
        if perm in seen:
            continue
        seen.add(perm)
        bits.append(PTE_PERM_BITS[perm])
    return " | ".join(bits)


def _emit_string_array(name: str, values: tuple[str, ...], source_lines: list[str]) -> None:
    source_lines.append(f"static const char *const {name}[] = {{")
    for value in values:
        source_lines.append(f"    {_c_string(value)},")
    source_lines.append("};")
    source_lines.append("")


def _emit_mapping_array(rule: MMURule, symbol: str, source_lines: list[str]) -> tuple[dict[str, int], str]:
    raw_mappings = rule.setup.get("mappings", [])
    if raw_mappings is None:
        raw_mappings = []
    if not isinstance(raw_mappings, list):
        raise ValueError(f"MMU rule {rule.id} field 'setup.mappings' must be a list")

    mapping_vas: dict[str, int] = {}
    resolved_mappings: list[dict[str, object]] = []
    for index, raw_mapping in enumerate(raw_mappings):
        if not isinstance(raw_mapping, dict):
            raise ValueError(f"MMU rule {rule.id} mapping #{index} must be a YAML mapping")
        name = raw_mapping.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"MMU rule {rule.id} mapping #{index} missing name")
        if name in mapping_vas:
            raise ValueError(f"MMU rule {rule.id} has duplicate mapping name: {name}")
        va = _resolve_address(raw_mapping.get("va"), mapping_vas=mapping_vas, field_name=f"mappings.{name}.va", rule_id=rule.id)
        mapping_vas[name] = va
        resolved_mappings.append({"name": name, "va": va, "raw": raw_mapping})

    array_name = f"xs_generated_mmu_mappings_{symbol}"
    source_lines.append(f"static const xs_generated_mmu_mapping_t {array_name}[] = {{")
    for mapping in resolved_mappings:
        raw_mapping = mapping["raw"]
        va = int(mapping["va"])
        pa = _resolve_address(raw_mapping.get("pa"), mapping_vas=mapping_vas, field_name=f"mappings.{mapping['name']}.pa", rule_id=rule.id)
        flags = _mapping_flags(raw_mapping, va=va, pa=pa, rule_id=rule.id)
        perm_expr = _mapping_perm_expr(raw_mapping.get("perms"), rule.id)
        page_count = raw_mapping.get("page_count", 1)
        source_lines.extend(
            [
                "    {",
                f"        .name = {_c_string(mapping['name'])},",
                f"        .va = {_c_uint(va)},",
                f"        .pa = {_c_uint(pa)},",
                f"        .prot = {perm_expr},",
                f"        .flags = {flags}u,",
                f"        .page_count = {page_count}u,",
                "    },",
            ]
        )
    source_lines.append("};")
    source_lines.append("")
    return mapping_vas, array_name


def _emit_rule_desc(rule: MMURule, source_lines: list[str]) -> tuple[str, tuple[str, ...]]:
    symbol = _rule_symbol(rule)
    mapping_vas, mapping_array_name = _emit_mapping_array(rule, symbol, source_lines)
    before_actions = tuple(rule.actions.get("before_trigger", ()))
    handler_actions = tuple(rule.actions.get("handler", ()))
    post_actions = tuple(rule.actions.get("post_check", ()))
    observe = tuple(rule.observe)
    coverage_tags = tuple(rule.coverage_tags)

    if before_actions:
        _emit_string_array(f"xs_generated_mmu_before_{symbol}", before_actions, source_lines)
    if handler_actions:
        _emit_string_array(f"xs_generated_mmu_handler_{symbol}", handler_actions, source_lines)
    if post_actions:
        _emit_string_array(f"xs_generated_mmu_post_{symbol}", post_actions, source_lines)
    if observe:
        _emit_string_array(f"xs_generated_mmu_observe_{symbol}", observe, source_lines)
    _emit_string_array(f"xs_generated_mmu_tags_{symbol}", coverage_tags, source_lines)

    result = str(rule.expect["result"])
    mask_name, cause_name = FAULT_MASK_BY_RESULT_AND_REQUESTOR.get(
        (result, rule.requestor),
        ("0", "0"),
    )

    trigger_op = str(rule.trigger.get("op", "load"))
    trigger_addr_value = rule.trigger.get("addr")
    if trigger_addr_value is None:
        if trigger_op == "store_then_load":
            trigger_addr_value = rule.trigger.get("store_va", rule.trigger.get("load_va"))
        else:
            trigger_addr_value = rule.trigger.get("load_va", rule.trigger.get("store_va"))
    if trigger_addr_value is None:
        raise ValueError(f"MMU rule {rule.id} missing trigger address")
    trigger_addr = _resolve_address(
        trigger_addr_value,
        mapping_vas=mapping_vas,
        field_name="trigger.addr",
        rule_id=rule.id,
    )
    secondary_addr = _resolve_address(
        rule.trigger.get("load_va", rule.trigger.get("store_va", trigger_addr)),
        mapping_vas=mapping_vas,
        field_name="trigger.secondary_addr",
        rule_id=rule.id,
    )

    source_lines.extend(
        [
            f"static const xs_generated_mmu_rule_t xs_generated_rule_{symbol} = {{",
            f"    .id = {_c_string(rule.id)},",
            f"    .symbol = {_c_string(symbol)},",
            f"    .requestor = {_c_string(rule.requestor)},",
            f"    .mode = {_c_string(rule.mode)},",
            f"    .expected_result = {_c_string(result)},",
            f"    .trigger_op = {_c_string(trigger_op)},",
            f"    .trigger_addr = {_c_uint(trigger_addr)},",
            f"    .secondary_addr = {_c_uint(secondary_addr)},",
            f"    .fault_mask = {mask_name},",
            f"    .expected_cause = {cause_name},",
            f"    .mapping_count = sizeof({mapping_array_name}) / sizeof({mapping_array_name}[0]),",
            f"    .mappings = {mapping_array_name},",
            (
                f"    .before_action_count = sizeof(xs_generated_mmu_before_{symbol}) / "
                f"sizeof(xs_generated_mmu_before_{symbol}[0]),"
                if before_actions
                else "    .before_action_count = 0u,"
            ),
            (
                f"    .before_actions = xs_generated_mmu_before_{symbol},"
                if before_actions
                else "    .before_actions = 0,"
            ),
            (
                f"    .handler_action_count = sizeof(xs_generated_mmu_handler_{symbol}) / "
                f"sizeof(xs_generated_mmu_handler_{symbol}[0]),"
                if handler_actions
                else "    .handler_action_count = 0u,"
            ),
            (
                f"    .handler_actions = xs_generated_mmu_handler_{symbol},"
                if handler_actions
                else "    .handler_actions = 0,"
            ),
            (
                f"    .post_action_count = sizeof(xs_generated_mmu_post_{symbol}) / "
                f"sizeof(xs_generated_mmu_post_{symbol}[0]),"
                if post_actions
                else "    .post_action_count = 0u,"
            ),
            (
                f"    .post_actions = xs_generated_mmu_post_{symbol},"
                if post_actions
                else "    .post_actions = 0,"
            ),
            (
                f"    .observe_count = sizeof(xs_generated_mmu_observe_{symbol}) / "
                f"sizeof(xs_generated_mmu_observe_{symbol}[0]),"
                if observe
                else "    .observe_count = 0u,"
            ),
            (
                f"    .observe = xs_generated_mmu_observe_{symbol},"
                if observe
                else "    .observe = 0,"
            ),
            f"    .coverage_tag_count = sizeof(xs_generated_mmu_tags_{symbol}) / sizeof(xs_generated_mmu_tags_{symbol}[0]),",
            f"    .coverage_tags = xs_generated_mmu_tags_{symbol},",
            "};",
            "",
        ]
    )
    return symbol, coverage_tags


def build_mmu_coverage_ledger_payload(
    *,
    suite_name: str,
    rule_db: dict[str, MMURule],
    selected_rule_ids: tuple[str, ...],
    ran_rule_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    selected = set(selected_rule_ids)
    ran = set(ran_rule_ids)
    all_rules = tuple(sorted(rule_db))
    defined_tags = {tag for rule in rule_db.values() for tag in rule.coverage_tags}
    selected_tags = {
        tag
        for rule_id in selected_rule_ids
        for tag in rule_db[rule_id].coverage_tags
    }
    ran_tags = {
        tag
        for rule_id in ran_rule_ids
        for tag in rule_db[rule_id].coverage_tags
    }

    rules_payload = []
    for rule_id in all_rules:
        rule = rule_db[rule_id]
        if rule_id in ran:
            state = "ran"
        elif rule_id in selected:
            state = "generated_not_run"
        else:
            state = "defined_only"
        rules_payload.append(
            {
                "id": rule.id,
                "symbol": _rule_symbol(rule),
                "coverage_tags": list(rule.coverage_tags),
                "state": state,
            }
        )

    tag_payload = []
    gap_payload = []
    for tag in COVERAGE_TAG_TAXONOMY:
        if tag in ran_tags:
            state = "ran"
        elif tag in selected_tags:
            state = "generated_not_run"
        elif tag in defined_tags:
            state = "defined_only"
        else:
            state = "gap"
        tag_payload.append(
            {
                "tag": tag,
                "rules": [rule.id for rule in rule_db.values() if tag in rule.coverage_tags],
                "state": state,
            }
        )
        if state == "gap":
            gap_payload.append({"tag": tag, "state": state})

    return {
        "suite": suite_name,
        "selected_rule_ids": list(selected_rule_ids),
        "defined_rule_ids": list(all_rules),
        "rules": rules_payload,
        "coverage_tags": tag_payload,
        "gaps": gap_payload,
    }


def write_mmu_coverage_ledger(
    *,
    path: Path,
    suite_name: str,
    rule_db: dict[str, MMURule],
    selected_rule_ids: tuple[str, ...],
    ran_rule_ids: tuple[str, ...] = (),
) -> Path:
    payload = build_mmu_coverage_ledger_payload(
        suite_name=suite_name,
        rule_db=rule_db,
        selected_rule_ids=selected_rule_ids,
        ran_rule_ids=ran_rule_ids,
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def mark_mmu_coverage_ledger_ran(
    path: Path,
    *,
    ran_rule_ids: tuple[str, ...] | None = None,
) -> Path:
    payload = json.loads(path.read_text())
    if ran_rule_ids is None:
        ran_rule_ids = tuple(payload.get("selected_rule_ids", []))
    rule_lookup = {
        entry["id"]: MMURule(
            id=entry["id"],
            symbol=entry.get("symbol"),
            requestor="load",
            mode="host_single_stage",
            preconditions={},
            setup={},
            actions={},
            trigger={},
            expect={"result": "hit"},
            observe=(),
            coverage_tags=tuple(entry.get("coverage_tags", [])),
        )
        for entry in payload.get("rules", [])
    }
    path.write_text(
        json.dumps(
            build_mmu_coverage_ledger_payload(
                suite_name=str(payload.get("suite", "")),
                rule_db=rule_lookup,
                selected_rule_ids=tuple(payload.get("selected_rule_ids", [])),
                ran_rule_ids=tuple(ran_rule_ids),
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return path


def emit_mmu_rule_artifacts(
    *,
    suite_name: str,
    rule_dir: Path,
    rule_ids: tuple[str, ...],
    header_path: Path,
    source_path: Path,
    coverage_ledger_path: Path,
) -> EmittedMMURuleBundle:
    rule_db = load_mmu_rule_db(rule_dir)
    selected_rules = [rule_db[rule_id] for rule_id in rule_ids]

    seen_symbols: dict[str, str] = {}
    for rule in selected_rules:
        symbol = _rule_symbol(rule)
        previous = seen_symbols.get(symbol)
        if previous is not None:
            raise ValueError(f"MMU rule symbol collision: {previous} and {rule.id} -> {symbol}")
        seen_symbols[symbol] = rule.id

    header_lines = [
        "#ifndef XS_GENERATED_MMU_RULE_H",
        "#define XS_GENERATED_MMU_RULE_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uintptr_t va;",
        "    uintptr_t pa;",
        "    uintptr_t prot;",
        "    uint32_t flags;",
        "    size_t page_count;",
        "} xs_generated_mmu_mapping_t;",
        "",
        "typedef struct {",
        "    const char *id;",
        "    const char *symbol;",
        "    const char *requestor;",
        "    const char *mode;",
        "    const char *expected_result;",
        "    const char *trigger_op;",
        "    uintptr_t trigger_addr;",
        "    uintptr_t secondary_addr;",
        "    uint32_t fault_mask;",
        "    uintptr_t expected_cause;",
        "    size_t mapping_count;",
        "    const xs_generated_mmu_mapping_t *mappings;",
        "    size_t before_action_count;",
        "    const char *const *before_actions;",
        "    size_t handler_action_count;",
        "    const char *const *handler_actions;",
        "    size_t post_action_count;",
        "    const char *const *post_actions;",
        "    size_t observe_count;",
        "    const char *const *observe;",
        "    size_t coverage_tag_count;",
        "    const char *const *coverage_tags;",
        "} xs_generated_mmu_rule_t;",
        "",
        f"enum {{ XS_GENERATED_MMU_FLAG_IDENTITY = {MMU_RULE_FLAG_IDENTITY}u, }};",
        f"enum {{ XS_GENERATED_MMU_FLAG_SUPERPAGE = {MMU_RULE_FLAG_SUPERPAGE}u, }};",
        f"enum {{ XS_GENERATED_MMU_FLAG_FAULT = {MMU_RULE_FLAG_FAULT}u, }};",
        f"enum {{ XS_GENERATED_MMU_FLAG_STAGE2 = {MMU_RULE_FLAG_STAGE2}u, }};",
        "",
        "extern const xs_generated_mmu_rule_t *const xs_generated_mmu_rules[];",
        "extern const size_t xs_generated_mmu_rule_count;",
        "",
        "#endif",
        "",
    ]
    source_lines = [
        '#include "generated_mmu_rule.h"',
        "",
        '#include "xsam/mmu.h"',
        '#include "xsam/mmu_fault.h"',
        "",
    ]

    selected_rule_symbols: list[str] = []
    coverage_tags: set[str] = set()
    for rule in selected_rules:
        symbol, rule_tags = _emit_rule_desc(rule, source_lines)
        selected_rule_symbols.append(symbol)
        coverage_tags.update(rule_tags)

    source_lines.append("const xs_generated_mmu_rule_t *const xs_generated_mmu_rules[] = {")
    for symbol in selected_rule_symbols:
        source_lines.append(f"    &xs_generated_rule_{symbol},")
    source_lines.extend(
        [
            "};",
            "",
            "const size_t xs_generated_mmu_rule_count =",
            "    sizeof(xs_generated_mmu_rules) / sizeof(xs_generated_mmu_rules[0]);",
            "",
        ]
    )

    header_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_ledger_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text("\n".join(header_lines))
    source_path.write_text("\n".join(source_lines))
    write_mmu_coverage_ledger(
        path=coverage_ledger_path,
        suite_name=suite_name,
        rule_db=rule_db,
        selected_rule_ids=rule_ids,
    )

    return EmittedMMURuleBundle(
        defined_rule_ids=tuple(sorted(rule_db)),
        selected_rule_ids=rule_ids,
        coverage_tags=tuple(sorted(coverage_tags)),
    )
