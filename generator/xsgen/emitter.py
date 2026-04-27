from __future__ import annotations

from pathlib import Path

from generator.xsgen.model import ComposePlan
from generator.xsgen.program_harness import emit_program_wrapper, program_entry_symbol


def descriptor_symbol(snippet_id: str) -> str:
    return f"snippet_{snippet_id}"


def format_seed_literal(seed: int) -> str:
    return f"0x{seed:x}ull"


def emit_harness(plan: ComposePlan, output_path: Path) -> Path:
    has_run_phase = plan.run_snippet_ids is not None
    has_check_phase = plan.check_snippet_ids is not None

    if has_run_phase != has_check_phase:
        raise ValueError(
            "run_snippet_ids and check_snippet_ids must both be set or both be None"
        )

    snippets_by_id = {snippet.id: snippet for snippet in plan.snippets}
    if has_check_phase:
        check_am_programs = [
            snippet_id
            for snippet_id in plan.check_snippet_ids
            if snippets_by_id.get(snippet_id) is not None
            and snippets_by_id[snippet_id].kind == "am_program"
        ]
        if check_am_programs:
            raise ValueError(
                "check_snippets cannot include am_program snippets: "
                + ", ".join(check_am_programs)
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '#include "xsrt_env.h"',
        '#include "xs_snippet.h"',
        "",
    ]

    emitted_wrappers: set[str] = set()
    for snippet in plan.snippets:
        if snippet.id in emitted_wrappers:
            continue
        if snippet.kind == "am_program":
            if '#include "xsam/program_snippet.h"' not in lines:
                lines.insert(2, '#include "xsam/program_snippet.h"')
            emit_program_wrapper(snippet, output_path.parent)
            lines.extend(
                [
                    f"extern int {program_entry_symbol(snippet.id)}(void);",
                    f"extern const xsrt_snippet_desc_t {descriptor_symbol(snippet.id)};",
                ]
            )
        else:
            lines.append(
                f"extern const xsrt_snippet_desc_t {descriptor_symbol(snippet.id)};"
            )
        emitted_wrappers.add(snippet.id)

    lines.extend(
        [
            "",
            "int main(void) {",
            "  xsrt_env_t env;",
            "  int rc;",
            "",
            "  xsrt_init(&env);",
            f"  env.seed = {format_seed_literal(plan.seed)};",
            "",
        ]
    )

    def emit_phase(snippet_ids: tuple[str, ...], runner: str) -> None:
        for snippet_id in snippet_ids:
            symbol = descriptor_symbol(snippet_id)
            lines.extend(
                [
                    f"  rc = {runner}(&env, &{symbol});",
                    "  if (rc != 0) {",
                    "    xsrt_finish_fail(&env, (unsigned long) rc);",
                    "    return rc;",
                    "  }",
                    "",
                ]
            )

    if has_run_phase and has_check_phase:
        emit_phase(plan.run_snippet_ids, "xsrt_run_snippet_no_check")
        emit_phase(plan.check_snippet_ids, "xsrt_run_snippet_check_only")
    else:
        emit_phase(plan.snippet_ids, "xsrt_run_snippet")

    lines.extend(
        [
            "  xsrt_finish_pass(&env);",
            "  return 0;",
            "}",
            "",
        ]
    )

    output_path.write_text("\n".join(lines))
    return output_path
