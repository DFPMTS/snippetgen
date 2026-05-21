from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnippetSpec:
    id: str
    kind: str
    lang: str
    sources: tuple[Path, ...]
    entry: str | None = None


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    target: str
    seed: int
    compose_mode: str
    snippet_ids: tuple[str, ...]
    run_snippet_ids: tuple[str, ...] | None = None
    check_snippet_ids: tuple[str, ...] | None = None
    mmu_rule_dir: Path | None = None
    mmu_rule_ids: tuple[str, ...] = ()
    mmu_defined_rule_ids: tuple[str, ...] = ()
    mmu_coverage_tags: tuple[str, ...] = ()
    vector_mmu_coverage: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class ComposePlan:
    suite_name: str
    target: str
    seed: int
    snippet_ids: tuple[str, ...]
    snippets: tuple[SnippetSpec, ...]
    run_snippet_ids: tuple[str, ...] | None = None
    check_snippet_ids: tuple[str, ...] | None = None
    mmu_rule_dir: Path | None = None
    mmu_rule_ids: tuple[str, ...] = ()
    mmu_defined_rule_ids: tuple[str, ...] = ()
    mmu_coverage_tags: tuple[str, ...] = ()
    vector_mmu_coverage: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class BuildArtifact:
    suite_name: str
    build_dir: Path
    generated_suite_path: Path
    elf_path: Path | None = None
    bin_path: Path | None = None
    disasm_path: Path | None = None
    build_manifest_path: Path | None = None
    generated_mmu_header_path: Path | None = None
    generated_mmu_source_path: Path | None = None
    mmu_coverage_ledger_path: Path | None = None
    vector_mmu_coverage_path: Path | None = None


@dataclass(frozen=True)
class RunSeedArtifacts:
    suite_name: str
    target: str
    seed: int
    run_batch: str
    build_artifact: BuildArtifact
    stdout_log_path: Path
    stderr_log_path: Path
    run_meta_path: Path
    wave_path: Path | None = None
    runner_profile: str | None = None


@dataclass(frozen=True)
class TargetRunResult:
    status: str
    labels: tuple[str, ...]
    notes: str
    returncode: int | None = None
    finish_code: int | None = None
    runner_profile: str | None = None
    runner_revision: str | None = None
    diff_revision: str | None = None
    runner_path: str | None = None
    diff_path: str | None = None


@dataclass(frozen=True)
class RunEntry:
    suite_name: str
    target: str
    run_batch: str
    seed: int
    artifact_dir: Path
    elf_path: Path
    bin_path: Path
    disasm_path: Path | None
    stdout_log_path: Path
    stderr_log_path: Path
    run_meta_path: Path
    wave_path: Path | None
    status: str
    labels: tuple[str, ...]
    notes: str
    returncode: int | None = None
    finish_code: int | None = None
    mmu_coverage_ledger_path: Path | None = None
    vector_mmu_coverage_path: Path | None = None
    runner_profile: str | None = None
    runner_revision: str | None = None
    diff_revision: str | None = None
    runner_path: str | None = None
    diff_path: str | None = None


@dataclass(frozen=True)
class RunLedger:
    suite_name: str
    target: str
    run_batch: str
    entries: tuple[RunEntry, ...]
