from __future__ import annotations

from collections import Counter
from pathlib import Path
import json


SUMMARY_STATES = (
    "ran",
    "failed_or_blocked",
    "generated_not_run",
    "defined_only",
    "gap",
)
STATE_RANK = {
    "gap": 0,
    "defined_only": 1,
    "generated_not_run": 2,
    "failed_or_blocked": 3,
    "ran": 4,
}
NO_PROFILE = "<no-profile>"


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_batch_meta(payload: dict[str, object]) -> bool:
    return isinstance(payload.get("entries"), list) and "run_batch" in payload


def _is_coverage_ledger(payload: dict[str, object]) -> bool:
    return isinstance(payload.get("coverage_tags"), list) and isinstance(payload.get("rules"), list)


def _semantic_success(entry: dict[str, object] | None) -> bool:
    if entry is None:
        return False
    labels = entry.get("labels", [])
    return (
        entry.get("finish_code") == 0
        or (isinstance(labels, list) and "good_trap" in labels)
    )


def _effective_state(ledger_state: object, *, entry: dict[str, object] | None) -> str:
    state = str(ledger_state)
    if entry is not None and not _semantic_success(entry) and state == "generated_not_run":
        return "failed_or_blocked"
    if state not in STATE_RANK:
        raise ValueError(f"unknown MMU coverage state: {state}")
    return state


def _counter_payload(items: list[dict[str, object]]) -> dict[str, int]:
    counter = Counter(str(item["state"]) for item in items)
    return {state: counter.get(state, 0) for state in SUMMARY_STATES}


def _merge_state(left: str | None, right: str) -> str:
    if left is None:
        return right
    return left if STATE_RANK[left] >= STATE_RANK[right] else right


def _entry_from_ledger(
    *,
    ledger_path: Path,
    ledger: dict[str, object],
    entry: dict[str, object] | None,
    input_path: Path,
) -> dict[str, object]:
    rules: list[dict[str, object]] = []
    tags: list[dict[str, object]] = []

    for raw_rule in ledger.get("rules", []):
        if not isinstance(raw_rule, dict):
            continue
        state = _effective_state(raw_rule.get("state"), entry=entry)
        rules.append(
            {
                "id": raw_rule.get("id"),
                "state": state,
                "ledger_state": raw_rule.get("state"),
                "coverage_tags": list(raw_rule.get("coverage_tags", [])),
            }
        )

    for raw_tag in ledger.get("coverage_tags", []):
        if not isinstance(raw_tag, dict):
            continue
        state = _effective_state(raw_tag.get("state"), entry=entry)
        tags.append(
            {
                "tag": raw_tag.get("tag"),
                "state": state,
                "ledger_state": raw_tag.get("state"),
                "rules": list(raw_tag.get("rules", [])),
            }
        )

    return {
        "input_path": str(input_path),
        "ledger_path": str(ledger_path),
        "suite": (entry or {}).get("suite", ledger.get("suite")),
        "run_batch": (entry or {}).get("run_batch"),
        "seed": (entry or {}).get("seed"),
        "runner_profile": (entry or {}).get("runner_profile"),
        "runner_revision": (entry or {}).get("runner_revision"),
        "diff_revision": (entry or {}).get("diff_revision"),
        "status": (entry or {}).get("status"),
        "labels": list((entry or {}).get("labels", [])),
        "finish_code": (entry or {}).get("finish_code"),
        "notes": (entry or {}).get("notes"),
        "rules": rules,
        "coverage_tags": tags,
        "rule_counts": _counter_payload(rules),
        "tag_counts": _counter_payload(tags),
    }


def _append_aggregate_item(
    aggregate: dict[str, dict[str, object]],
    *,
    key: str,
    label_name: str,
    state: str,
    runner_profile: str | None,
    entry_index: int,
) -> None:
    profile = runner_profile or NO_PROFILE
    item = aggregate.setdefault(
        key,
        {
            label_name: key,
            "state": "gap",
            "states_by_profile": {},
            "entries": [],
        },
    )
    profile_states = item["states_by_profile"]
    assert isinstance(profile_states, dict)
    profile_states[profile] = _merge_state(profile_states.get(profile), state)
    item["state"] = _merge_state(str(item.get("state")), state)
    entries = item["entries"]
    assert isinstance(entries, list)
    if entry_index not in entries:
        entries.append(entry_index)


def summarize_mmu_coverage(paths: list[Path]) -> dict[str, object]:
    entries: list[dict[str, object]] = []

    for raw_path in paths:
        path = raw_path.resolve()
        payload = _load_json(path)
        if _is_batch_meta(payload):
            for raw_entry in payload.get("entries", []):
                if not isinstance(raw_entry, dict):
                    continue
                ledger_value = raw_entry.get("mmu_coverage_ledger")
                if not ledger_value:
                    continue
                ledger_path = Path(str(ledger_value)).resolve()
                if not ledger_path.is_file():
                    raise ValueError(f"{path} references missing MMU coverage ledger: {ledger_path}")
                ledger = _load_json(ledger_path)
                if not _is_coverage_ledger(ledger):
                    raise ValueError(f"{ledger_path} is not an MMU coverage ledger")
                entries.append(
                    _entry_from_ledger(
                        ledger_path=ledger_path,
                        ledger=ledger,
                        entry=raw_entry,
                        input_path=path,
                    )
                )
            continue

        if _is_coverage_ledger(payload):
            entries.append(
                _entry_from_ledger(
                    ledger_path=path,
                    ledger=payload,
                    entry=None,
                    input_path=path,
                )
            )
            continue

        raise ValueError(f"{path} is neither batch_meta.json nor mmu_coverage_ledger.json")

    rule_aggregate: dict[str, dict[str, object]] = {}
    tag_aggregate: dict[str, dict[str, object]] = {}
    for index, entry in enumerate(entries):
        runner_profile = entry.get("runner_profile")
        for rule in entry["rules"]:
            assert isinstance(rule, dict)
            rule_id = rule.get("id")
            if rule_id is None:
                continue
            _append_aggregate_item(
                rule_aggregate,
                key=str(rule_id),
                label_name="id",
                state=str(rule["state"]),
                runner_profile=str(runner_profile) if runner_profile is not None else None,
                entry_index=index,
            )
        for tag in entry["coverage_tags"]:
            assert isinstance(tag, dict)
            tag_name = tag.get("tag")
            if tag_name is None:
                continue
            _append_aggregate_item(
                tag_aggregate,
                key=str(tag_name),
                label_name="tag",
                state=str(tag["state"]),
                runner_profile=str(runner_profile) if runner_profile is not None else None,
                entry_index=index,
            )

    return {
        "inputs": [str(path.resolve()) for path in paths],
        "entries": entries,
        "rules": [rule_aggregate[key] for key in sorted(rule_aggregate)],
        "coverage_tags": [tag_aggregate[key] for key in sorted(tag_aggregate)],
    }


def _format_counts(counts: dict[str, object]) -> str:
    return ", ".join(f"{state}={counts.get(state, 0)}" for state in SUMMARY_STATES)


def format_mmu_coverage_summary_text(summary: dict[str, object]) -> str:
    lines = ["MMU coverage summary"]
    entries = summary.get("entries", [])
    if not isinstance(entries, list) or not entries:
        lines.append("entries: 0")
        return "\n".join(lines)

    lines.append(f"entries: {len(entries)}")
    for index, entry in enumerate(entries):
        assert isinstance(entry, dict)
        profile = entry.get("runner_profile") or NO_PROFILE
        lines.append(
            f"- entry[{index}] suite={entry.get('suite')} profile={profile} "
            f"batch={entry.get('run_batch')} seed={entry.get('seed')} "
            f"status={entry.get('status')} finish_code={entry.get('finish_code')}"
        )
        lines.append(f"  ledger={entry.get('ledger_path')}")
        lines.append(f"  rules: {_format_counts(entry.get('rule_counts', {}))}")
        lines.append(f"  tags: {_format_counts(entry.get('tag_counts', {}))}")

    lines.append("coverage tags:")
    for tag in summary.get("coverage_tags", []):
        assert isinstance(tag, dict)
        states_by_profile = tag.get("states_by_profile", {})
        assert isinstance(states_by_profile, dict)
        profiles = ", ".join(
            f"{profile}={state}"
            for profile, state in sorted(states_by_profile.items())
        )
        lines.append(f"- {tag.get('tag')}: {tag.get('state')} ({profiles})")

    return "\n".join(lines)
