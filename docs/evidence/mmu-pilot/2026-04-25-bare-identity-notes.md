# 2026-04-25 MMU Bare Identity Accepted Evidence

- Date: 2026-04-25
- Suite: `suites/mmu_bare_identity_poc.yaml`
- Rule bundle: `bare_identity`
- Batch ID: `rlcr-round3-mmu-bare-identity`
- Seed: `0`
- Target: `xiangshan-verilator`
- Status: `ran`
- Finish code: `0`
- Observed result: expected `good_trap`

## Command

```bash
env \
  'riscv64-unknown-linux-gnu-gcc'=/usr/bin/riscv64-linux-gnu-gcc \
  'riscv64-unknown-linux-gnu-objcopy'=/usr/bin/riscv64-linux-gnu-objcopy \
  SNIPPETGEN_RISCV_MARCH=rv64gc \
  SNIPPETGEN_RISCV_MABI=lp64d \
  SNIPPETGEN_XS_ENV_SH=/nfs/home/liujunqi/XS/xs-env/env.sh \
  python3 generator/cli.py run suites/mmu_bare_identity_poc.yaml \
    --seed 0 \
    --batch-id rlcr-round3-mmu-bare-identity \
    --timeout-sec 180
```

## Outcome

- `batch_meta.json` recorded `status: ran`, `labels: [built, ran, good_trap]`, and `finish_code: 0`.
- `stdout.log` recorded `HIT GOOD TRAP at pc = 0x80000030`.
- The run used the generated MMU rule path and XiangShan `emu` + NEMU diff flow, so this bundle is accepted AC-5 evidence for a real MMU pilot execution on the local fallback `rv64gc` toolchain path.

## Notes

- This evidence closes the missing "at least one real XiangShan/NEMU pilot bundle" requirement without relying on the rejected 2026-04-24 fallback bundle.
- The broader `mmu_pilot_rules_poc` suite still needs more local runtime budget and remains separate from this accepted minimal bundle.
