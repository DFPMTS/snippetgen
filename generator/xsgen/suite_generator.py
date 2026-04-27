from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
import re

import yaml


SUPPORTED_TARGET = "xiangshan-verilator"
SUITE_PREFIX_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class SuitePool:
    name: str
    run_pool: tuple[str, ...]
    check_map: dict[str, str]
    target: str = SUPPORTED_TARGET
    init_snippet: str = "init_basic_env"
    finish_check_snippet: str = "finish_check"
    default_run_count: int = 1
    min_run_count: int = 1


@dataclass(frozen=True)
class GeneratedSuite:
    name: str
    target: str
    seed: int
    run_snippets: tuple[str, ...]
    check_snippets: tuple[str, ...]


SCALAR_MISALIGN_FULL_POOL = SuitePool(
    name="scalar_misalign_full",
    run_pool=(
        "load_split_templates",
        "store_split_templates",
        "store_forward_overlap",
        "cross_page_faults",
        "store_forward_search",
        "cross_page_fault_search",
    ),
    check_map={
        "load_split_templates": "check_load_split_templates",
        "store_split_templates": "check_store_split_templates",
        "store_forward_overlap": "check_store_forward_overlap",
        "cross_page_faults": "check_cross_page_faults",
        "store_forward_search": "check_store_forward_search",
        "cross_page_fault_search": "check_cross_page_fault_search",
    },
    default_run_count=5,
    min_run_count=5,
)

SUITE_POOLS: dict[str, SuitePool] = {
    SCALAR_MISALIGN_FULL_POOL.name: SCALAR_MISALIGN_FULL_POOL,
}


def list_suite_pools() -> tuple[str, ...]:
    return tuple(sorted(SUITE_POOLS))


def load_suite_pool(name: str) -> SuitePool:
    if name not in SUITE_POOLS:
        raise ValueError(f"unknown suite pool: {name}")
    return SUITE_POOLS[name]


def _default_output_dir(repo_root: Path, prefix: str) -> Path:
    return repo_root / "build" / "generated_suites" / prefix


def _default_prefix(pool_name: str) -> str:
    return f"{pool_name}_rand"


def _validate_prefix(prefix: str) -> str:
    if SUITE_PREFIX_RE.fullmatch(prefix) is None:
        raise ValueError(f"invalid suite prefix: {prefix}")
    return prefix


def _portable_path(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo_root.resolve()))
    except ValueError:
        return str(resolved)


def _resolve_output_dir(repo_root: Path, output_dir: Path) -> Path:
    repo_base = repo_root.resolve()
    candidate = output_dir if output_dir.is_absolute() else repo_base / output_dir
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_base)
    except ValueError as exc:
        raise ValueError(f"output_dir must stay within repo: {output_dir}") from exc
    return resolved


def generate_suites(
    *,
    pool: SuitePool,
    suite_count: int,
    run_count: int,
    generator_seed: int,
    prefix: str,
) -> tuple[GeneratedSuite, ...]:
    if suite_count < 1:
        raise ValueError(f"suite_count must be positive: {suite_count}")
    if run_count < 1:
        raise ValueError(f"run_count must be positive: {run_count}")
    if run_count < pool.min_run_count:
        raise ValueError(
            f"run_count {run_count} is below minimum {pool.min_run_count} for {pool.name}"
        )
    if generator_seed < 0:
        raise ValueError(f"generator_seed must be non-negative: {generator_seed}")
    if not pool.run_pool:
        raise ValueError(f"run_pool must not be empty for {pool.name}")
    if len(set(pool.run_pool)) != len(pool.run_pool):
        raise ValueError(f"run_pool contains duplicate snippet ids for {pool.name}")

    rng = random.Random(generator_seed)
    generated: list[GeneratedSuite] = []

    for index in range(suite_count):
        suite_seed = rng.randrange(1, 1 << 31)
        selected_runs: list[str] = []
        while len(selected_runs) < run_count:
            round_runs = list(pool.run_pool)
            rng.shuffle(round_runs)
            remaining = run_count - len(selected_runs)
            selected_runs.extend(round_runs[:remaining])
        selected_checks = [pool.check_map[snippet_id] for snippet_id in selected_runs]
        rng.shuffle(selected_checks)

        generated.append(
            GeneratedSuite(
                name=f"{prefix}_{index:03d}",
                target=pool.target,
                seed=suite_seed,
                run_snippets=(pool.init_snippet, *selected_runs),
                check_snippets=(*selected_checks, pool.finish_check_snippet),
            )
        )

    return tuple(generated)


def suite_yaml_text(suite: GeneratedSuite) -> str:
    payload = {
        "suite": suite.name,
        "target": suite.target,
        "seed": suite.seed,
        "compose": {
            "mode": "sequence",
            "run_snippets": list(suite.run_snippets),
            "check_snippets": list(suite.check_snippets),
        },
    }
    return yaml.safe_dump(payload, sort_keys=False)


def write_generated_suites(
    *,
    repo_root: Path,
    pool_name: str,
    suite_count: int,
    run_count: int,
    generator_seed: int,
    output_dir: Path | None = None,
    prefix: str | None = None,
) -> Path:
    pool = load_suite_pool(pool_name)
    suite_prefix = _validate_prefix(prefix or _default_prefix(pool.name))
    raw_destination = output_dir if output_dir is not None else _default_output_dir(repo_root, suite_prefix)
    destination = _resolve_output_dir(repo_root, raw_destination)
    generated = generate_suites(
        pool=pool,
        suite_count=suite_count,
        run_count=run_count,
        generator_seed=generator_seed,
        prefix=suite_prefix,
    )

    destination.mkdir(parents=True, exist_ok=True)
    index_payload = {
        "pool": pool.name,
        "generator_seed": generator_seed,
        "suite_count": suite_count,
        "run_count": run_count,
        "output_dir": _portable_path(repo_root, destination),
        "suites": [],
    }

    for suite in generated:
        suite_path = destination / f"{suite.name}.yaml"
        suite_path.write_text(suite_yaml_text(suite))
        index_payload["suites"].append(
            {
                "suite": suite.name,
                "path": _portable_path(repo_root, suite_path),
                "seed": suite.seed,
                "run_snippets": list(suite.run_snippets),
                "check_snippets": list(suite.check_snippets),
            }
        )

    index_path = destination / f"{suite_prefix}_batch.json"
    index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True))
    return index_path
