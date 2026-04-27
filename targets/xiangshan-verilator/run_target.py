from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import subprocess

from generator.xsgen.model import TargetRunResult


DEFAULT_MAX_CYCLES = 120000
DEFAULT_MAX_INSTR = 120000
DEFAULT_TIMEOUT_SEC = 1800
DEFAULT_FORK_INTERVAL_SEC = 10
UNKNOWN_TRAP_CODE_RE = re.compile(r"Unknown trap code:\s*(\d+)")


def _xs_env() -> dict[str, str]:
    env = dict(os.environ)

    if "XS_PROJECT_ROOT" in env and "NEMU_HOME" in env and "NOOP_HOME" in env:
        return env

    env_sh_override = env.get("SNIPPETGEN_XS_ENV_SH")
    if not env_sh_override:
        return env

    env_sh = Path(env_sh_override)
    if not env_sh.is_file():
        return env

    xs_project_root = env_sh.resolve().parent
    env["XS_PROJECT_ROOT"] = str(xs_project_root)
    env["NEMU_HOME"] = str(xs_project_root / "NEMU")
    env["AM_HOME"] = str(xs_project_root / "nexus-am")
    env["NOOP_HOME"] = str(xs_project_root / "XiangShan")
    env["DRAMSIM3_HOME"] = str(xs_project_root / "DRAMsim3")
    return env


def _emu_path(env: dict[str, str] | None = None) -> Path | None:
    env = _xs_env() if env is None else env
    override = os.environ.get("SNIPPETGEN_XS_EMU")
    if override:
        return Path(override)

    noop_home = env.get("NOOP_HOME")
    if noop_home:
        candidate = Path(noop_home) / "build" / "verilator-compile" / "emu"
        if candidate.is_file():
            return candidate

    found = shutil.which("emu")
    if found is None:
        return None
    return Path(found)


def _diff_path(env: dict[str, str]) -> Path | None:
    override = os.environ.get("SNIPPETGEN_XS_DIFF")
    if override:
        return Path(override)

    nemu_home = env.get("NEMU_HOME")
    if not nemu_home:
        return None

    candidate = Path(nemu_home) / "build" / "riscv64-nemu-interpreter-so"
    if candidate.is_file():
        return candidate
    return None


def _error_result(*, artifacts, notes: str, labels: tuple[str, ...] = ("error",)) -> TargetRunResult:
    artifacts.stderr_log_path.write_text(f"{notes}\n")
    artifacts.stdout_log_path.write_text("")
    return TargetRunResult(
        status="error",
        labels=labels,
        notes=notes,
        returncode=None,
    )


def _classify_result(*, stdout_text: str, stderr_text: str, returncode: int) -> TargetRunResult:
    merged = f"{stdout_text}\n{stderr_text}"
    unknown_trap_match = UNKNOWN_TRAP_CODE_RE.search(merged)

    if "HIT GOOD TRAP" in merged:
        return TargetRunResult(
            status="ran",
            labels=("built", "ran", "good_trap"),
            notes="HIT GOOD TRAP",
            returncode=returncode,
            finish_code=0,
        )

    if "HIT BAD TRAP" in merged:
        return TargetRunResult(
            status="bad_trap",
            labels=("built", "ran", "bad_trap"),
            notes="HIT BAD TRAP",
            returncode=returncode,
            finish_code=1,
        )

    if unknown_trap_match is not None:
        finish_code = int(unknown_trap_match.group(1))
        return TargetRunResult(
            status="bad_trap",
            labels=("built", "ran", "bad_trap"),
            notes=f"Unknown trap code: {finish_code}",
            returncode=returncode,
            finish_code=finish_code,
        )

    if "ABORT at pc" in merged or "Assertion failed" in merged:
        return TargetRunResult(
            status="abort",
            labels=("built", "ran", "abort"),
            notes="ABORT",
            returncode=returncode,
        )

    if "EXIT at pc" in merged or "The simulation exits normally" in merged:
        return TargetRunResult(
            status="ran",
            labels=("built", "ran", "sim_exit"),
            notes="simulation exit",
            returncode=returncode,
        )

    if "EXCEEDING CYCLE/INSTR LIMIT" in merged or "EXCEEDED MAX CYCLE" in merged:
        return TargetRunResult(
            status="limit_exceeded",
            labels=("built", "ran", "limit_exceeded"),
            notes="EXCEEDING CYCLE/INSTR LIMIT",
            returncode=returncode,
        )

    if returncode == 0:
        return TargetRunResult(
            status="ran",
            labels=("built", "ran"),
            notes="",
            returncode=0,
        )

    return TargetRunResult(
        status="nonzero_exit",
        labels=("built", "ran", "nonzero_exit"),
        notes=f"runner exited with code {returncode}",
        returncode=returncode,
    )


def run_target(*, artifacts, timeout_s: int | None) -> TargetRunResult:
    env = _xs_env()
    emu_path = _emu_path(env)
    diff_path = _diff_path(env)

    if artifacts.build_artifact.bin_path is None or not artifacts.build_artifact.bin_path.is_file():
        return _error_result(artifacts=artifacts, notes="missing bin artifact")

    if emu_path is None:
        return _error_result(
            artifacts=artifacts,
            notes="runner missing: emu",
            labels=("error", "runner_missing"),
        )

    if not emu_path.is_file():
        return _error_result(
            artifacts=artifacts,
            notes=f"runner missing: {emu_path}",
            labels=("error", "runner_missing"),
        )

    if diff_path is None:
        return _error_result(
            artifacts=artifacts,
            notes="runner missing: riscv64-nemu-interpreter-so",
            labels=("error", "runner_missing"),
        )

    if not diff_path.is_file():
        return _error_result(
            artifacts=artifacts,
            notes=f"runner missing: {diff_path}",
            labels=("error", "runner_missing"),
        )

    timeout_value = timeout_s if timeout_s is not None else DEFAULT_TIMEOUT_SEC
    max_cycles = int(os.environ.get("SNIPPETGEN_RUN_MAX_CYCLES", str(DEFAULT_MAX_CYCLES)))
    max_instr = int(os.environ.get("SNIPPETGEN_RUN_MAX_INSTR", str(DEFAULT_MAX_INSTR)))
    fork_interval = int(os.environ.get("SNIPPETGEN_XS_FORK_INTERVAL", str(DEFAULT_FORK_INTERVAL_SEC)))
    command = [
        str(emu_path),
        "-s",
        str(artifacts.seed),
        "-C",
        str(max_cycles),
        "-I",
        str(max_instr),
        "-i",
        str(artifacts.build_artifact.bin_path),
        "--enable-fork",
        "-X",
        str(fork_interval),
        "--wave-path",
        str(artifacts.wave_path),
        "--diff",
        str(diff_path),
        "--force-dump-result",
    ]

    with artifacts.stdout_log_path.open("w") as stdout_file, artifacts.stderr_log_path.open("w") as stderr_file:
        try:
            result = subprocess.run(
                command,
                check=False,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout=timeout_value,
                env=env,
            )
        except subprocess.TimeoutExpired:
            with artifacts.stderr_log_path.open("a") as stderr_append:
                stderr_append.write(f"timeout after {timeout_value}s\n")
            return TargetRunResult(
                status="timeout",
                labels=("built", "timeout"),
                notes=f"timeout after {timeout_value}s",
                returncode=None,
            )

    return _classify_result(
        stdout_text=artifacts.stdout_log_path.read_text(),
        stderr_text=artifacts.stderr_log_path.read_text(),
        returncode=result.returncode,
    )
