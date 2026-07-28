# YueYuan Solution Version Ledger

## Purpose

Keep a human-readable record of known-good solution versions before adding more
research changes. Git stores the exact files; this ledger records what each
version means scientifically, what evidence supported it, and how to compare a
future version against it.

Do not overwrite or revert user changes automatically. If a future version is
worse, create a comparison note first, then either continue from the better
commit or ask before reverting any committed work.

## Current Protected Baselines

### Baseline A: Hardware-Readiness PR State

- Scientific meaning: strongest submitted attempt-004 solution before the
  device-informed subspace research pass.
- Local commit with matching tree: `b109129 Add attempt 004 hardware readiness layer`.
- PR remote head with matching tree: `074ce92c359ecfa8e7c2c060790a54cf760a97c8`.
- PR: <https://github.com/QuantumBFS/quantum.harness/pull/203>
- Approximate challenge rating recorded before further upgrades: `8.7/10`.
- Scope:
  - differentiable one-qubit and two-qubit model;
  - Hessian and HVP diagnostics;
  - strict query-only noisy simulated device;
  - full, random, fixed Hessian, and widen-only adaptive baselines;
  - full CPU sweep and focused adaptive sweep;
  - effective-rank diagnostics;
  - hardware-style dry-run adapter with `real_hardware: false`.
- Fresh verification at that point:
  - hardware tests: `4 passed`;
  - attempt-004 tests: `25 passed`;
  - broader YueYuan attempt tests: `39 passed`;
  - validator self-test: passed;
  - fast candidate export: `15` groups;
  - hardware dry run: `7` candidates, `1,792` shots, `real_hardware: false`;
  - sensitive-marker scan: no hits.

### Baseline B: Device-Informed Design Spec Only

- Scientific meaning: Baseline A plus a committed design document for the next
  research pass. No solution code changed after Baseline A.
- Local commit: `215b7ef Specify device-informed adaptive subspace pass`.
- Added file:
  - `docs/superpowers/specs/2026-07-29-yueyuan-device-informed-adaptive-subspace-design.md`
- Use this as the starting point for the implementation plan.

## Future Version Rule

Before any future research implementation pass:

1. Add a new entry to this ledger with the current commit SHA.
2. Name what is being attempted and why it could improve the challenge score.
3. Record expected success metrics and risk.
4. After implementation, record:
   - new commit SHA;
   - files changed;
   - fresh verification output;
   - whether the challenge rating improved, worsened, or stayed unclear.

## Comparison Checklist

A future version should be considered better than Baseline A only if it preserves
all of these:

- strict query-only device boundary;
- counted query and shot budgets;
- no real-hardware claim unless measured hardware counts are actually present;
- no private account, host, password, key, or credential markers in committed
  files;
- generated results remain ignored by git;
- `Ion.lock` remains unstaged unless the user explicitly asks otherwise;
- attempt-004 and broader YueYuan tests pass;
- validator self-test passes;
- PR report remains honest about failures and limitations.

It should improve at least one of these:

- recovery under medium/large model-device mismatch;
- evidence for useful dimension near `d^2 - 1`;
- device-informed subspace selection beyond fixed widening;
- statistical confidence or clarity of plots/tables;
- hardware-readiness for real measured counts.

## Non-Destructive Recovery Notes

Prefer comparison over deletion. Useful read-only checks:

```bash
git show --stat b109129
git diff b109129..HEAD -- tracks/qcs/solutions/YueYuan docs/superpowers
git diff 215b7ef..HEAD -- tracks/qcs/solutions/YueYuan docs/superpowers
```

If a future branch looks worse, the safest path is to create a new branch from a
known-good commit and continue there. Do not run destructive reset or checkout
commands without explicit approval.

## Version Entries

### 2026-07-29: Before Device-Informed Adaptive Subspace Implementation

- Protected baseline: Baseline A (`b109129`, PR head `074ce92`).
- Current planning baseline: Baseline B (`215b7ef`).
- Pre-implementation ledger checkpoint: `6ac59d6 Record YueYuan solution version ledger`.
- Intended next change:
  - implement black-box device-informed local subspace probing;
  - compare fixed Hessian, widen-only adaptive, and device-informed adaptive
    methods on known mismatch failure cases;
  - then add a software-only invariant/rank probe.
- Main risk:
  - finite-shot probing may spend too many queries to beat widen-only adaptive;
  - if so, the result is still useful negative evidence, but the report must say
    that clearly.

### 2026-07-29: Device-Informed Adaptive Subspace And Invariant Probe

- Implementation commits:
  - `53d5d04 Add device-informed subspace probing`
  - `e8f1b98 Add device-informed adaptive baseline`
  - `62a61e5 Add device-informed focus runner`
  - `6ffc083 Add invariant rank probe`
  - `7a71f78 Derive invariant rows from model Hessians`
- Intended score improvement:
  - closes the fixed-subspace-only weakness by adding counted, finite-shot
    device-informed residual direction probing;
  - adds a software-only `d=2`, `d=4`, `d=8` invariant/rank probe with the
    three-qubit entry labeled as a local unitary-chart sanity check.
- Fresh verification:
  - device-informed subspace tests: `4 passed`;
  - invariant probe tests: `2 passed`;
  - attempt-004 tests: `31 passed`;
  - broader YueYuan attempt tests: `45 passed`;
  - validator self-test: passed;
  - fast candidate export: `15` groups;
  - hardware dry run: `7` candidates, `1,792` shots, `real_hardware: false`;
  - device-informed fast focus: `10` records, `2` device-informed records;
  - invariant probe: `3` rows; `d=2` and `d=4` evidence type
    `attempt_004_model_hessian_smoke`; `d=8` evidence type
    `local_unitary_chart`;
  - private-marker scan: no hits after removing exact scan markers from the
    committed plan text.
- Interpretation:
  - fast device-informed focus did not reach the target in the two hard cells;
  - it lowered final infidelity relative to fixed Hessian, random, and full-space
    baselines in those fast cells while charging 9 probe queries;
  - post-review invariant rows now distinguish actual attempt-004 model-Hessian
    smoke evidence from the synthetic three-qubit local chart;
  - one-qubit `k95=3` and two-qubit `k95=10`; the `d^2 - 1` benchmark captures
    `0.970` and `0.975` of model-Hessian curvature in those rows;
  - this is a method-level improvement and partial/negative recovery result, not
    a real-hardware or target-reaching claim.
