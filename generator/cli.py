#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from generator.xsgen.snippet_db import load_snippet_db
from generator.xsgen.suite_loader import build_compose_plan, load_suite
from generator.xsgen.emitter import emit_harness
from generator.xsgen.suite_generator import list_suite_pools, load_suite_pool, write_generated_suites
from generator.xsgen.toolchain import artifact_paths_for_suite, build_artifacts
from generator.xsgen.run_batch import normalize_seeds, run_suite_batch


def _run_exit_code(ledger_path: Path) -> int:
    payload = json.loads(ledger_path.read_text())
    entries = payload.get("entries", [])
    if not entries:
        return 1
    success_statuses = {"ran"}
    for entry in entries:
        if entry.get("status") not in success_statuses:
            return 1
    return 0


def cmd_list_snippets(_: argparse.Namespace) -> int:
    snippet_db = load_snippet_db(REPO_ROOT)
    for snippet_id in sorted(snippet_db):
        print(snippet_id)
    return 0


def cmd_list_suite_pools(_: argparse.Namespace) -> int:
    for pool_name in list_suite_pools():
        print(pool_name)
    return 0


def cmd_dump_plan(args: argparse.Namespace) -> int:
    snippet_db = load_snippet_db(REPO_ROOT)
    suite = load_suite(REPO_ROOT / args.suite)
    plan = build_compose_plan(suite, snippet_db)
    artifact = artifact_paths_for_suite(REPO_ROOT, plan.suite_name)
    payload = {
        "suite": plan.suite_name,
        "target": plan.target,
        "seed": plan.seed,
        "snippet_ids": list(plan.snippet_ids),
        "artifacts": {
            "build_dir": str(artifact.build_dir),
            "generated_suite": str(artifact.generated_suite_path),
            "elf": str(artifact.elf_path),
            "bin": str(artifact.bin_path),
            "build_manifest": str(artifact.build_manifest_path),
            "generated_mmu_header": str(artifact.generated_mmu_header_path),
            "generated_mmu_source": str(artifact.generated_mmu_source_path),
            "mmu_coverage_ledger": str(artifact.mmu_coverage_ledger_path),
        },
    }
    if plan.mmu_rule_dir is not None and plan.mmu_rule_ids:
        payload["mmu"] = {
            "rule_dir": str(plan.mmu_rule_dir),
            "resolved_rule_ids": list(plan.mmu_rule_ids),
            "defined_rule_ids": list(plan.mmu_defined_rule_ids),
            "coverage_tags": list(plan.mmu_coverage_tags),
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    suite_path = Path(args.suite) if args.suite is not None else Path("suites/scalar_load_legality_poc.yaml")
    snippet_db = load_snippet_db(REPO_ROOT)
    suite = load_suite(REPO_ROOT / suite_path)
    plan = build_compose_plan(suite, snippet_db)
    artifact = artifact_paths_for_suite(REPO_ROOT, plan.suite_name)
    emit_harness(plan, artifact.generated_suite_path)
    build_artifacts(REPO_ROOT, plan, artifact)
    print(artifact.build_manifest_path)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        seed_values = normalize_seeds(seed=args.seed, seeds=args.seeds, seed_range=args.seed_range)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.jobs < 1:
        raise SystemExit("jobs must be positive")
    ledger_path = run_suite_batch(
        repo_root=REPO_ROOT,
        suite_path=REPO_ROOT / Path(args.suite),
        seed_values=seed_values,
        run_batch_id=args.batch_id,
        timeout_s=args.timeout_sec,
        jobs=args.jobs,
    )
    print(ledger_path)
    return _run_exit_code(ledger_path)


def cmd_generate_suites(args: argparse.Namespace) -> int:
    output_dir = None if args.output_dir is None else Path(args.output_dir)
    run_count = args.run_count
    if run_count is None:
        run_count = load_suite_pool(args.pool).default_run_count
    try:
        index_path = write_generated_suites(
            repo_root=REPO_ROOT,
            pool_name=args.pool,
            suite_count=args.count,
            run_count=run_count,
            generator_seed=args.seed,
            output_dir=output_dir,
            prefix=args.prefix,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(index_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snippetgen")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-snippets")
    list_parser.set_defaults(handler=cmd_list_snippets)

    list_pools_parser = subparsers.add_parser("list-suite-pools")
    list_pools_parser.set_defaults(handler=cmd_list_suite_pools)

    dump_parser = subparsers.add_parser("dump-plan")
    dump_parser.add_argument("suite")
    dump_parser.set_defaults(handler=cmd_dump_plan)

    build_parser_cmd = subparsers.add_parser("build")
    build_parser_cmd.add_argument("suite", nargs="?")
    build_parser_cmd.set_defaults(handler=cmd_build)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("suite")
    seed_group = run_parser.add_mutually_exclusive_group(required=True)
    seed_group.add_argument("--seed", type=int)
    seed_group.add_argument("--seeds")
    seed_group.add_argument("--seed-range")
    run_parser.add_argument("--batch-id")
    run_parser.add_argument("--jobs", type=int, default=1)
    run_parser.add_argument("--timeout-sec", type=int)
    run_parser.set_defaults(handler=cmd_run)

    generate_parser = subparsers.add_parser("generate-suites")
    generate_parser.add_argument("--pool", required=True, choices=list_suite_pools())
    generate_parser.add_argument("--count", type=int, required=True)
    generate_parser.add_argument("--run-count", type=int)
    generate_parser.add_argument("--seed", type=int, required=True)
    generate_parser.add_argument("--output-dir")
    generate_parser.add_argument("--prefix")
    generate_parser.set_defaults(handler=cmd_generate_suites)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
