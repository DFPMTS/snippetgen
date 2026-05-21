from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess

from generator.xsgen.mmu_rule_emitter import emit_mmu_rule_artifacts
from generator.xsgen.model import BuildArtifact, ComposePlan, SnippetSpec
from generator.xsgen.program_harness import (
    emit_program_wrapper,
    program_entry_symbol,
    resolve_program_entry_source,
)


def _artifact_paths_for_build_dir(build_dir: Path, suite_name: str) -> BuildArtifact:
    build_dir = build_dir.resolve()
    return BuildArtifact(
        suite_name=suite_name,
        build_dir=build_dir,
        generated_suite_path=build_dir / "generated_suite.c",
        elf_path=build_dir / "test.elf",
        bin_path=build_dir / "test.bin",
        disasm_path=build_dir / "disasm",
        build_manifest_path=build_dir / "build_manifest.json",
        generated_mmu_header_path=build_dir / "generated_mmu_rule.h",
        generated_mmu_source_path=build_dir / "generated_mmu_rule.c",
        mmu_coverage_ledger_path=build_dir / "mmu_coverage_ledger.json",
        vector_mmu_coverage_path=build_dir / "vector_mmu_coverage.json",
    )


def artifact_paths_for_suite(repo_root: Path, suite_name: str) -> BuildArtifact:
    return _artifact_paths_for_build_dir(repo_root / "build" / suite_name, suite_name)


def artifact_paths_for_run_seed(
    repo_root: Path,
    suite_name: str,
    run_batch: str,
    seed: int,
) -> BuildArtifact:
    build_dir = repo_root / "build" / suite_name / "runs" / run_batch / f"seed_{seed}"
    return _artifact_paths_for_build_dir(build_dir, suite_name)


def _find_tool(name: str) -> str | None:
    override = os.environ.get(name)
    if override:
        return override
    return shutil.which(name)


def detect_toolchain() -> dict[str, str]:
    candidates = (
        "riscv64-unknown-linux-gnu",
        "riscv64-unknown-elf",
        "riscv64-linux-gnu",
    )

    for prefix in candidates:
        gcc = _find_tool(f"{prefix}-gcc")
        objcopy = _find_tool(f"{prefix}-objcopy")
        if gcc and objcopy:
            return {"prefix": prefix, "gcc": gcc, "objcopy": objcopy}

    raise RuntimeError("RISC-V cross toolchain not found")


def resolve_objdump(toolchain: dict[str, str]) -> str:
    if "objdump" in toolchain and toolchain["objdump"]:
        return toolchain["objdump"]

    objdump_name = f'{toolchain["prefix"]}-objdump'

    for anchor in ("gcc", "objcopy"):
        candidate = Path(toolchain[anchor]).with_name(objdump_name)
        if candidate.is_file():
            return str(candidate)

    found = _find_tool(objdump_name)
    if found is not None:
        return found

    raise RuntimeError(f"RISC-V objdump not found: {objdump_name}")


def runtime_sources(repo_root: Path) -> list[Path]:
    return [
        repo_root / "runtime" / "arch" / "riscv64" / "start.S",
        repo_root / "runtime" / "arch" / "riscv64" / "trap.S",
        repo_root / "runtime" / "src" / "xsrt_env.c",
        repo_root / "runtime" / "src" / "xsrt_csr.c",
        repo_root / "runtime" / "src" / "xsrt_trap.c",
        repo_root / "runtime" / "src" / "xsrt_intr.c",
        repo_root / "runtime" / "src" / "xsrt_snippet.c",
        repo_root / "runtime" / "src" / "xsam_trm.c",
        repo_root / "runtime" / "src" / "xsam_cte.c",
        repo_root / "runtime" / "src" / "xsam_vme.c",
        repo_root / "runtime" / "src" / "xsam_mmu.c",
        repo_root / "runtime" / "src" / "xsam_mmu_fault.c",
        repo_root / "runtime" / "src" / "xsam_mmu_guest.c",
        repo_root / "runtime" / "src" / "xsam_ioe.c",
        repo_root / "runtime" / "src" / "xsam_program_snippet.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsam_xs_clint.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsam_xs_plic.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsam_xs_pma.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsam_xs_pmp.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsam_xs_cache.c",
        repo_root / "runtime" / "platform" / "xiangshan" / "xsrt_platform.c",
    ]


def runtime_linker_script(repo_root: Path) -> Path:
    return (repo_root / "runtime" / "platform" / "xiangshan" / "section.ld").resolve()


def riscv_compile_flags() -> list[str]:
    march = os.environ.get("SNIPPETGEN_RISCV_MARCH", "rv64gc")
    mabi = os.environ.get("SNIPPETGEN_RISCV_MABI", "lp64d")
    return [
        "-O2",
        f"-march={march}",
        f"-mabi={mabi}",
        "-mcmodel=medany",
        "-ffreestanding",
        "-fno-asynchronous-unwind-tables",
        "-fno-builtin",
        "-fno-stack-protector",
        "-fno-tree-vectorize",
        "-fno-tree-slp-vectorize",
    ]


def unique_plan_sources(plan: ComposePlan) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []

    for snippet in plan.snippets:
        if snippet.kind == "am_program":
            continue
        for source_path in snippet.sources:
            if source_path in seen:
                continue
            seen.add(source_path)
            ordered.append(source_path)

    return ordered


def am_program_snippets(plan: ComposePlan) -> list[SnippetSpec]:
    emitted_snippets: set[str] = set()
    ordered: list[SnippetSpec] = []

    for snippet in plan.snippets:
        if snippet.kind != "am_program" or snippet.id in emitted_snippets:
            continue
        ordered.append(snippet)
        emitted_snippets.add(snippet.id)

    return ordered


def _remove_failed_build_outputs(artifact: BuildArtifact) -> None:
    for path in (
        artifact.elf_path,
        artifact.bin_path,
        artifact.disasm_path,
        artifact.build_manifest_path,
        artifact.mmu_coverage_ledger_path,
        artifact.vector_mmu_coverage_path,
    ):
        if path is not None and path.exists():
            path.unlink()


def build_artifacts(
    repo_root: Path,
    plan: ComposePlan,
    artifact: BuildArtifact,
) -> BuildArtifact:
    compile_flags = riscv_compile_flags()
    include_flags = [
        "-I",
        str((repo_root / "runtime" / "include").resolve()),
        "-I",
        str((repo_root / "snippets" / "include").resolve()),
        "-I",
        str((repo_root / "runtime" / "platform" / "xiangshan").resolve()),
        "-I",
        str(artifact.build_dir.resolve()),
    ]
    toolchain = detect_toolchain()
    object_dir = artifact.build_dir / "obj"
    compile_commands: list[list[str]] = []
    object_paths: list[str] = []
    runtime_source_list = runtime_sources(repo_root)

    artifact.build_dir.mkdir(parents=True, exist_ok=True)
    if object_dir.exists():
        shutil.rmtree(object_dir)
    object_dir.mkdir(parents=True, exist_ok=True)

    for path in (
        artifact.elf_path,
        artifact.bin_path,
        artifact.disasm_path,
        artifact.build_manifest_path,
        artifact.generated_mmu_header_path,
        artifact.generated_mmu_source_path,
        artifact.mmu_coverage_ledger_path,
        artifact.vector_mmu_coverage_path,
    ):
        if path.exists():
            path.unlink()

    mmu_bundle = None
    if plan.mmu_rule_dir is not None and plan.mmu_rule_ids:
        mmu_bundle = emit_mmu_rule_artifacts(
            suite_name=plan.suite_name,
            rule_dir=plan.mmu_rule_dir,
            rule_ids=plan.mmu_rule_ids,
            header_path=artifact.generated_mmu_header_path,
            source_path=artifact.generated_mmu_source_path,
            coverage_ledger_path=artifact.mmu_coverage_ledger_path,
        )

    if plan.vector_mmu_coverage:
        vector_payload = {
            "kind": "vector_mmu_coverage",
            "suite": plan.suite_name,
            "seed": plan.seed,
            "state": "generated_not_run",
            "items": [
                {
                    **item,
                    "state": "generated_not_run",
                }
                for item in plan.vector_mmu_coverage
            ],
        }
        artifact.vector_mmu_coverage_path.write_text(json.dumps(vector_payload, indent=2, sort_keys=True))

    for index, source_path in enumerate(runtime_source_list, start=1):
        object_path = object_dir / f"{index:02d}_{source_path.stem}.o"
        object_dir.mkdir(parents=True, exist_ok=True)
        compile_cmd = [
            toolchain["gcc"],
            *compile_flags,
            *include_flags,
            "-c",
            str(source_path.resolve()),
            "-o",
            str(object_path),
        ]
        compile_result = subprocess.run(
            compile_cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        compile_commands.append(compile_cmd)
        if compile_result.returncode != 0:
            _remove_failed_build_outputs(artifact)
            raise RuntimeError(compile_result.stderr or "RISC-V compile failed")
        object_paths.append(str(object_path))

    source_index = len(object_paths) + 1
    for source_path in unique_plan_sources(plan):
        object_path = object_dir / f"{source_index:02d}_{source_path.stem}.o"
        object_dir.mkdir(parents=True, exist_ok=True)
        compile_cmd = [
            toolchain["gcc"],
            *compile_flags,
            *include_flags,
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ]
        compile_result = subprocess.run(
            compile_cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        compile_commands.append(compile_cmd)
        if compile_result.returncode != 0:
            _remove_failed_build_outputs(artifact)
            raise RuntimeError(compile_result.stderr or "RISC-V compile failed")
        object_paths.append(str(object_path))
        source_index += 1

    for snippet in am_program_snippets(plan):
        for source_path in snippet.sources:
            object_path = object_dir / f"{source_index:02d}_{snippet.id}_{source_path.stem}.o"
            object_dir.mkdir(parents=True, exist_ok=True)
            compile_cmd = [
                toolchain["gcc"],
                *compile_flags,
                *include_flags,
                f"-D{snippet.entry}={program_entry_symbol(snippet.id)}",
                "-c",
                str(source_path.resolve()),
                "-o",
                str(object_path),
            ]
            compile_result = subprocess.run(
                compile_cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            compile_commands.append(compile_cmd)
            if compile_result.returncode != 0:
                _remove_failed_build_outputs(artifact)
                raise RuntimeError(compile_result.stderr or "RISC-V compile failed")
            object_paths.append(str(object_path))
            source_index += 1

        wrapper_source = emit_program_wrapper(snippet, artifact.build_dir)
        wrapper_object = object_dir / f"{source_index:02d}_{wrapper_source.stem}.o"
        wrapper_cmd = [
            toolchain["gcc"],
            *compile_flags,
            *include_flags,
            "-c",
            str(wrapper_source.resolve()),
            "-o",
            str(wrapper_object),
        ]
        wrapper_result = subprocess.run(
            wrapper_cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        compile_commands.append(wrapper_cmd)
        if wrapper_result.returncode != 0:
            _remove_failed_build_outputs(artifact)
            raise RuntimeError(wrapper_result.stderr or "RISC-V compile failed")
        object_paths.append(str(wrapper_object))
        source_index += 1

    if artifact.generated_mmu_source_path is not None and artifact.generated_mmu_source_path.exists():
        generated_mmu_object = object_dir / f"{source_index:02d}_{artifact.generated_mmu_source_path.stem}.o"
        object_dir.mkdir(parents=True, exist_ok=True)
        generated_mmu_cmd = [
            toolchain["gcc"],
            *compile_flags,
            *include_flags,
            "-c",
            str(artifact.generated_mmu_source_path),
            "-o",
            str(generated_mmu_object),
        ]
        generated_mmu_result = subprocess.run(
            generated_mmu_cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        compile_commands.append(generated_mmu_cmd)
        if generated_mmu_result.returncode != 0:
            _remove_failed_build_outputs(artifact)
            raise RuntimeError(generated_mmu_result.stderr or "RISC-V compile failed")
        object_paths.append(str(generated_mmu_object))
        source_index += 1

    generated_object = object_dir / f"{source_index:02d}_{artifact.generated_suite_path.stem}.o"
    object_dir.mkdir(parents=True, exist_ok=True)
    generated_compile_cmd = [
        toolchain["gcc"],
        *compile_flags,
        *include_flags,
        "-c",
        str(artifact.generated_suite_path),
        "-o",
        str(generated_object),
    ]
    generated_compile_result = subprocess.run(
        generated_compile_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    compile_commands.append(generated_compile_cmd)
    if generated_compile_result.returncode != 0:
        _remove_failed_build_outputs(artifact)
        raise RuntimeError(generated_compile_result.stderr or "RISC-V compile failed")
    object_paths.append(str(generated_object))

    link_cmd = [
        toolchain["gcc"],
        *compile_flags,
        "-nostdlib",
        "-nostartfiles",
        "-static",
        "-Wl,--build-id=none",
        f"-Wl,-T{runtime_linker_script(repo_root)}",
        "-o",
        str(artifact.elf_path),
    ]
    link_cmd.extend(object_paths)

    link_result = subprocess.run(
        link_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if link_result.returncode != 0:
        _remove_failed_build_outputs(artifact)
        raise RuntimeError(link_result.stderr or "RISC-V link failed")

    objcopy_cmd = [
        toolchain["objcopy"],
        "-O",
        "binary",
        str(artifact.elf_path),
        str(artifact.bin_path),
    ]
    try:
        objcopy_result = subprocess.run(
            objcopy_cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        _remove_failed_build_outputs(artifact)
        raise RuntimeError(f"objcopy failed: {objcopy_cmd[0]}") from exc
    if objcopy_result.returncode != 0:
        _remove_failed_build_outputs(artifact)
        raise RuntimeError(objcopy_result.stderr or "RISC-V objcopy failed")

    objdump_cmd = [
        resolve_objdump(toolchain),
        "-d",
        str(artifact.elf_path),
    ]
    objdump_result = subprocess.run(
        objdump_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if objdump_result.returncode != 0:
        _remove_failed_build_outputs(artifact)
        raise RuntimeError(objdump_result.stderr or "RISC-V objdump failed")
    artifact.disasm_path.write_text(objdump_result.stdout)

    artifact_payload = {
        "build_dir": str(artifact.build_dir),
        "generated_suite": str(artifact.generated_suite_path),
        "elf": str(artifact.elf_path),
        "bin": str(artifact.bin_path),
        "disasm": str(artifact.disasm_path),
        "build_manifest": str(artifact.build_manifest_path),
    }
    has_mmu_artifacts = plan.mmu_rule_dir is not None and bool(plan.mmu_rule_ids)
    if has_mmu_artifacts:
        artifact_payload.update(
            {
                "generated_mmu_header": str(artifact.generated_mmu_header_path),
                "generated_mmu_source": str(artifact.generated_mmu_source_path),
                "mmu_coverage_ledger": str(artifact.mmu_coverage_ledger_path),
            }
        )
    if plan.vector_mmu_coverage:
        artifact_payload["vector_mmu_coverage"] = str(artifact.vector_mmu_coverage_path)

    manifest_payload = {
        "suite": plan.suite_name,
        "target": plan.target,
        "seed": plan.seed,
        "snippet_ids": list(plan.snippet_ids),
        "sources": [str(source) for snippet in plan.snippets for source in snippet.sources],
        "runtime_sources": [str(source.resolve()) for source in runtime_source_list],
        "artifacts": artifact_payload,
        "commands": {
            "compile": compile_commands,
            "link": link_cmd,
            "objcopy": objcopy_cmd,
            "objdump": objdump_cmd,
        },
    }
    if plan.run_snippet_ids is not None and plan.check_snippet_ids is not None:
        manifest_payload["run_snippet_ids"] = list(plan.run_snippet_ids)
        manifest_payload["check_snippet_ids"] = list(plan.check_snippet_ids)
    if plan.mmu_rule_dir is not None and plan.mmu_rule_ids:
        manifest_payload["mmu"] = {
            "rule_dir": str(plan.mmu_rule_dir),
            "resolved_rule_ids": list(plan.mmu_rule_ids),
            "defined_rule_ids": list(plan.mmu_defined_rule_ids),
            "coverage_tags": list(plan.mmu_coverage_tags),
        }
        if mmu_bundle is not None:
            manifest_payload["mmu"]["emitted_coverage_tags"] = list(mmu_bundle.coverage_tags)
    if plan.vector_mmu_coverage:
        manifest_payload["vector_mmu"] = {
            "coverage_path": str(artifact.vector_mmu_coverage_path),
            "coverage": [dict(item) for item in plan.vector_mmu_coverage],
        }
    artifact.build_manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True))
    return artifact
