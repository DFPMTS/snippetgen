from __future__ import annotations

from pathlib import Path
import re

from generator.xsgen.model import SnippetSpec


def descriptor_symbol(snippet_id: str) -> str:
    return f"snippet_{snippet_id}"


def program_entry_symbol(snippet_id: str) -> str:
    return f"xsam_program_entry_{snippet_id}"


def program_wrapper_path(build_dir: Path, snippet_id: str) -> Path:
    return build_dir / f"generated_am_program_{snippet_id}.c"


def _source_defines_entry(source_text: str, entry: str) -> bool:
    source_text = re.sub(r"/\*.*?\*/", "", source_text, flags=re.DOTALL)
    source_text = re.sub(r"//.*", "", source_text)
    pattern = re.compile(
        rf"(^|\n)\s*(?:[A-Za-z_][\w\s\*\(\),]*\s+)?{re.escape(entry)}\s*\([^;{{}}]*\)\s*\{{",
        re.MULTILINE,
    )
    return pattern.search(source_text) is not None


def resolve_program_entry_source(snippet: SnippetSpec) -> Path:
    if snippet.kind != "am_program":
        raise ValueError(f"snippet is not an AM program: {snippet.id}")
    if snippet.entry is None:
        raise ValueError(f"AM program snippet missing entry symbol: {snippet.id}")
    if not snippet.sources:
        raise ValueError(f"AM program snippet has no sources: {snippet.id}")

    matches = [
        source_path
        for source_path in snippet.sources
        if _source_defines_entry(source_path.read_text(), snippet.entry)
    ]
    if not matches:
        raise ValueError(
            f"AM program entry symbol {snippet.entry} not found in sources: {snippet.id}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"AM program entry symbol {snippet.entry} is defined in multiple sources: {snippet.id}"
        )
    return matches[0]


def emit_program_wrapper(snippet: SnippetSpec, build_dir: Path) -> Path:
    entry_symbol = program_entry_symbol(snippet.id)
    output_path = program_wrapper_path(build_dir, snippet.id)
    lines = [
        '#include "xsam/program_snippet.h"',
        "",
        f"extern int {entry_symbol}(void);",
        "",
        (
            f'XSAM_DEFINE_PROGRAM_SNIPPET({descriptor_symbol(snippet.id)}, '
            f'"{snippet.id}", {entry_symbol});'
        ),
        "",
    ]
    output_path.write_text("\n".join(lines))
    return output_path
