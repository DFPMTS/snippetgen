from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import json


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNNER_MANIFEST_PATH = REPO_ROOT.parent / "artifacts" / "kmh-runners" / "manifest.json"


@dataclass(frozen=True)
class RunnerProfile:
    name: str
    emu_path: Path
    diff_path: Path
    xiangshan_revision: str
    nemu_revision: str
    build_summary: str
    difftest: bool
    wave: bool
    alias_of: str | None = None


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_string(profile: Mapping[str, object], key: str) -> str:
    value = profile.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"runner profile missing string field: {key}")
    return value


def _profile_path(manifest_path: Path, value: object, key: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"runner profile missing path field: {key}")
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def _load_manifest(manifest_path: Path) -> tuple[Mapping[str, object], tuple[Mapping[str, object], ...]]:
    if not manifest_path.is_file():
        raise ValueError(f"runner manifest missing: {manifest_path}")
    payload = _require_mapping(json.loads(manifest_path.read_text()), str(manifest_path))
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError(f"runner manifest has no profiles: {manifest_path}")
    normalized = tuple(_require_mapping(profile, "runner profile") for profile in profiles)
    return payload, normalized


def _validate_alias_collisions(
    *,
    manifest_path: Path,
    profiles: tuple[Mapping[str, object], ...],
) -> None:
    by_emu: dict[Path, list[str]] = {}
    alias_by_name: dict[str, object] = {}

    for profile in profiles:
        name = _require_string(profile, "name")
        emu = _profile_path(manifest_path, profile.get("emu"), "emu")
        by_emu.setdefault(emu, []).append(name)
        alias_by_name[name] = profile.get("alias_of")

    for names in by_emu.values():
        if len(names) < 2:
            continue
        canonical_names = [name for name in names if alias_by_name.get(name) is None]
        if len(canonical_names) != 1:
            joined = ", ".join(names)
            raise ValueError(f"runner profile alias collision: {joined}")
        canonical = canonical_names[0]
        for name in names:
            if name == canonical:
                continue
            if alias_by_name.get(name) != canonical:
                joined = ", ".join(names)
                raise ValueError(f"runner profile alias collision: {joined}")


def resolve_runner_profile(
    name: str,
    manifest_path: Path | None = None,
) -> RunnerProfile:
    if not name:
        raise ValueError("runner profile name must be non-empty")
    path = (manifest_path or DEFAULT_RUNNER_MANIFEST_PATH).resolve()
    _, profiles = _load_manifest(path)
    _validate_alias_collisions(manifest_path=path, profiles=profiles)

    selected = None
    for profile in profiles:
        if profile.get("name") == name:
            selected = profile
            break
    if selected is None:
        raise ValueError(f"unknown runner profile: {name}")

    emu_path = _profile_path(path, selected.get("emu"), "emu")
    diff_path = _profile_path(path, selected.get("nemu"), "nemu")
    if not emu_path.is_file():
        raise ValueError(f"runner emu missing for profile {name}: {emu_path}")
    if not diff_path.is_file():
        raise ValueError(f"runner NEMU reference missing for profile {name}: {diff_path}")

    alias_of = selected.get("alias_of")
    if alias_of is not None and (not isinstance(alias_of, str) or not alias_of):
        raise ValueError(f"runner profile {name} has invalid alias_of")

    return RunnerProfile(
        name=name,
        emu_path=emu_path,
        diff_path=diff_path,
        xiangshan_revision=_require_string(selected, "xiangshan_revision"),
        nemu_revision=_require_string(selected, "nemu_revision"),
        build_summary=str(selected.get("build_summary", "")),
        difftest=bool(selected.get("difftest", False)),
        wave=bool(selected.get("wave", False)),
        alias_of=alias_of,
    )
