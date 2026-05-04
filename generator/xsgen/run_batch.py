from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
import json
import uuid

from generator.xsgen.emitter import emit_harness
from generator.xsgen.mmu_rule_emitter import mark_mmu_coverage_ledger_ran
from generator.xsgen.model import BuildArtifact, ComposePlan, RunEntry, RunLedger, RunSeedArtifacts, TargetRunResult
from generator.xsgen.run_target import load_run_target
from generator.xsgen.snippet_db import load_snippet_db
from generator.xsgen.suite_loader import build_compose_plan, load_suite
from generator.xsgen.toolchain import artifact_paths_for_run_seed, build_artifacts


@dataclass(frozen=True)
class _PreparedSeedRun:
    seed: int
    plan: ComposePlan
    artifact: BuildArtifact
    run_artifacts: RunSeedArtifacts
    stdout_log_path: Path
    stderr_log_path: Path
    run_meta_path: Path
    wave_path: Path


def _require_non_negative_seed(value: int) -> int:
    if value < 0:
        raise ValueError(f"seed must be non-negative: {value}")
    return value


def normalize_seeds(
    *,
    seed: int | None,
    seeds: str | None,
    seed_range: str | None,
) -> tuple[int, ...]:
    provided = [value is not None for value in (seed, seeds, seed_range)]
    if sum(provided) != 1:
        raise ValueError("exactly one seed selector must be provided")

    if seed is not None:
        return (_require_non_negative_seed(seed),)

    if seeds is not None:
        parts = seeds.split(",")
        if not parts:
            raise ValueError("invalid seed list")
        values: list[int] = []
        seen: set[int] = set()
        for part in parts:
            if not part.strip():
                raise ValueError("invalid seed list contains an empty seed")
            try:
                value = int(part)
            except ValueError as exc:
                raise ValueError(f"invalid seed value: {part}") from exc
            _require_non_negative_seed(value)
            if value in seen:
                raise ValueError(f"duplicate seed value: {value}")
            seen.add(value)
            values.append(value)
        return tuple(values)

    assert seed_range is not None
    bounds = seed_range.split(":")
    if len(bounds) != 2 or not bounds[0] or not bounds[1]:
        raise ValueError(f"invalid seed range: {seed_range}")
    try:
        start = int(bounds[0])
        end = int(bounds[1])
    except ValueError as exc:
        raise ValueError(f"invalid seed range: {seed_range}") from exc
    _require_non_negative_seed(start)
    _require_non_negative_seed(end)
    if end < start:
        raise ValueError(f"invalid seed range: {seed_range}")
    return tuple(range(start, end + 1))


def _default_run_batch_id() -> str:
    return f"batch_{uuid.uuid4().hex[:12]}"


def _ensure_log_files(stdout_log_path: Path, stderr_log_path: Path) -> None:
    stdout_log_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_log_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_log_path.touch(exist_ok=True)
    stderr_log_path.touch(exist_ok=True)


def _entry_payload(entry: RunEntry) -> dict:
    return {
        "suite": entry.suite_name,
        "target": entry.target,
        "run_batch": entry.run_batch,
        "seed": entry.seed,
        "artifact_dir": str(entry.artifact_dir),
        "elf": str(entry.elf_path),
        "bin": str(entry.bin_path),
        "disasm": str(entry.disasm_path) if entry.disasm_path is not None else None,
        "stdout_log": str(entry.stdout_log_path),
        "stderr_log": str(entry.stderr_log_path),
        "run_meta": str(entry.run_meta_path),
        "wave_path": str(entry.wave_path) if entry.wave_path is not None else None,
        "status": entry.status,
        "labels": list(entry.labels),
        "notes": entry.notes,
        "returncode": entry.returncode,
        "finish_code": entry.finish_code,
        "runner_profile": entry.runner_profile,
        "runner_revision": entry.runner_revision,
        "diff_revision": entry.diff_revision,
        "runner_path": entry.runner_path,
        "diff_path": entry.diff_path,
        "mmu_coverage_ledger": (
            str(entry.mmu_coverage_ledger_path)
            if entry.mmu_coverage_ledger_path is not None
            else None
        ),
    }


def _write_run_meta(entry: RunEntry) -> None:
    entry.run_meta_path.write_text(json.dumps(_entry_payload(entry), indent=2, sort_keys=True))


def _mmu_ran_rule_ids(
    *,
    prepared: _PreparedSeedRun,
    target_result: TargetRunResult,
) -> tuple[str, ...]:
    code: int | None
    partial_count: int

    if not prepared.plan.mmu_rule_ids:
        return ()
    if target_result.finish_code == 0 or "good_trap" in target_result.labels:
        return prepared.plan.mmu_rule_ids

    code = target_result.finish_code
    if code is None:
        return ()

    partial_count = code - 64
    if partial_count < 0 or partial_count > len(prepared.plan.mmu_rule_ids):
        return ()
    return prepared.plan.mmu_rule_ids[:partial_count]


def _completed_entry(
    *,
    prepared: _PreparedSeedRun,
    target_result: TargetRunResult,
) -> RunEntry:
    mmu_coverage_ledger_path = (
        prepared.artifact.mmu_coverage_ledger_path
        if prepared.plan.mmu_rule_ids
        else None
    )
    ran_rule_ids = _mmu_ran_rule_ids(prepared=prepared, target_result=target_result)
    semantic_success = (
        target_result.finish_code == 0
        or "good_trap" in target_result.labels
    )
    if (
        mmu_coverage_ledger_path is not None
        and mmu_coverage_ledger_path.is_file()
        and (semantic_success or ran_rule_ids)
    ):
        mark_mmu_coverage_ledger_ran(
            mmu_coverage_ledger_path,
            ran_rule_ids=ran_rule_ids,
        )
    return RunEntry(
        suite_name=prepared.plan.suite_name,
        target=prepared.plan.target,
        run_batch=prepared.run_artifacts.run_batch,
        seed=prepared.seed,
        artifact_dir=prepared.artifact.build_dir,
        elf_path=prepared.artifact.elf_path,
        bin_path=prepared.artifact.bin_path,
        disasm_path=prepared.artifact.disasm_path,
        stdout_log_path=prepared.stdout_log_path,
        stderr_log_path=prepared.stderr_log_path,
        run_meta_path=prepared.run_meta_path,
        wave_path=prepared.wave_path,
        status=target_result.status,
        labels=target_result.labels,
        notes=target_result.notes,
        returncode=target_result.returncode,
        finish_code=target_result.finish_code,
        mmu_coverage_ledger_path=mmu_coverage_ledger_path,
        runner_profile=target_result.runner_profile or prepared.run_artifacts.runner_profile,
        runner_revision=target_result.runner_revision,
        diff_revision=target_result.diff_revision,
        runner_path=target_result.runner_path,
        diff_path=target_result.diff_path,
    )


def _prepare_seed_run(
    *,
    repo_root: Path,
    plan: ComposePlan,
    artifact: BuildArtifact,
    run_batch: str,
    seed: int,
    stdout_log_path: Path,
    stderr_log_path: Path,
    run_meta_path: Path,
    wave_path: Path,
    runner_profile: str | None,
) -> _PreparedSeedRun:
    emit_harness(plan, artifact.generated_suite_path)
    build_artifacts(repo_root, plan, artifact)
    run_artifacts = RunSeedArtifacts(
        suite_name=plan.suite_name,
        target=plan.target,
        seed=seed,
        run_batch=run_batch,
        build_artifact=artifact,
        stdout_log_path=stdout_log_path,
        stderr_log_path=stderr_log_path,
        run_meta_path=run_meta_path,
        wave_path=wave_path,
        runner_profile=runner_profile,
    )
    return _PreparedSeedRun(
        seed=seed,
        plan=plan,
        artifact=artifact,
        run_artifacts=run_artifacts,
        stdout_log_path=stdout_log_path,
        stderr_log_path=stderr_log_path,
        run_meta_path=run_meta_path,
        wave_path=wave_path,
    )


def _error_result(*, notes: str) -> TargetRunResult:
    return TargetRunResult(
        status="error",
        labels=("error",),
        notes=notes,
        returncode=None,
    )


def _prepared_error_entry(*, prepared: _PreparedSeedRun, notes: str) -> RunEntry:
    prepared.stderr_log_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.stderr_log_path.write_text(f"{notes}\n")
    return _completed_entry(
        prepared=prepared,
        target_result=_error_result(notes=notes),
    )


def _execute_prepared_seed(
    *,
    prepared: _PreparedSeedRun,
    target_runner,
    timeout_s: int | None,
) -> RunEntry:
    try:
        target_result = target_runner(artifacts=prepared.run_artifacts, timeout_s=timeout_s)
    except Exception as exc:
        return _prepared_error_entry(prepared=prepared, notes=str(exc))
    return _completed_entry(prepared=prepared, target_result=target_result)


def _write_run_ledger(
    *,
    suite_name: str,
    target: str,
    run_batch: str,
    entries: list[RunEntry],
    ledger_path: Path,
) -> Path:
    ledger = RunLedger(
        suite_name=suite_name,
        target=target,
        run_batch=run_batch,
        entries=tuple(entries),
    )
    payload = {
        "suite": ledger.suite_name,
        "target": ledger.target,
        "run_batch": ledger.run_batch,
        "entries": [_entry_payload(entry) for entry in ledger.entries],
    }
    ledger_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return ledger_path


def run_suite_batch(
    *,
    repo_root: Path,
    suite_path: Path,
    seed_values: tuple[int, ...],
    target_loader=load_run_target,
    run_batch_id: str | None = None,
    timeout_s: int | None = None,
    jobs: int = 1,
    runner_profile: str | None = None,
) -> Path:
    if jobs < 1:
        raise ValueError(f"jobs must be positive: {jobs}")
    snippet_db = load_snippet_db(repo_root)
    base_suite = load_suite(suite_path)
    run_batch = run_batch_id or _default_run_batch_id()
    batch_root = (repo_root / "build" / base_suite.name / "runs" / run_batch).resolve()
    ledger_path = batch_root / "batch_meta.json"
    batch_root.mkdir(parents=True, exist_ok=True)
    target_runner = target_loader(repo_root, base_suite.target)
    prepared_runs: list[_PreparedSeedRun] = []
    entries_by_seed: dict[int, RunEntry] = {}

    for seed in seed_values:
        suite = replace(base_suite, seed=seed)
        plan = build_compose_plan(suite, snippet_db)
        artifact = artifact_paths_for_run_seed(repo_root, plan.suite_name, run_batch, seed)
        stdout_log_path = artifact.build_dir / "stdout.log"
        stderr_log_path = artifact.build_dir / "stderr.log"
        run_meta_path = artifact.build_dir / "run_meta.json"
        wave_path = artifact.build_dir / "lightsss-wave"
        _ensure_log_files(stdout_log_path, stderr_log_path)
        try:
            prepared = _prepare_seed_run(
                repo_root=repo_root,
                plan=plan,
                artifact=artifact,
                run_batch=run_batch,
                seed=seed,
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=wave_path,
                runner_profile=runner_profile,
            )
        except Exception as exc:
            prepared = _PreparedSeedRun(
                seed=seed,
                plan=plan,
                artifact=artifact,
                run_artifacts=RunSeedArtifacts(
                    suite_name=plan.suite_name,
                    target=plan.target,
                    seed=seed,
                    run_batch=run_batch,
                    build_artifact=artifact,
                    stdout_log_path=stdout_log_path,
                    stderr_log_path=stderr_log_path,
                    run_meta_path=run_meta_path,
                    wave_path=wave_path,
                    runner_profile=runner_profile,
                ),
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                run_meta_path=run_meta_path,
                wave_path=wave_path,
            )
            entry = _prepared_error_entry(prepared=prepared, notes=str(exc))
            _write_run_meta(entry)
            entries_by_seed[seed] = entry
            continue

        prepared_runs.append(prepared)

    if jobs == 1:
        for prepared in prepared_runs:
            entry = _execute_prepared_seed(
                prepared=prepared,
                target_runner=target_runner,
                timeout_s=timeout_s,
            )
            _write_run_meta(entry)
            entries_by_seed[entry.seed] = entry
    elif prepared_runs:
        with ThreadPoolExecutor(max_workers=min(jobs, len(prepared_runs))) as executor:
            future_map = {
                executor.submit(
                    _execute_prepared_seed,
                    prepared=prepared,
                    target_runner=target_runner,
                    timeout_s=timeout_s,
                ): prepared.seed
                for prepared in prepared_runs
            }
            for future in as_completed(future_map):
                entry = future.result()
                _write_run_meta(entry)
                entries_by_seed[entry.seed] = entry

    entries = [entries_by_seed[seed] for seed in seed_values]

    return _write_run_ledger(
        suite_name=base_suite.name,
        target=base_suite.target,
        run_batch=run_batch,
        entries=entries,
        ledger_path=ledger_path,
    )
