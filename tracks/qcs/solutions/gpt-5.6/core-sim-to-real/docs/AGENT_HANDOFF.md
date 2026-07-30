# Agent handoff — core sim-to-real direction

Read this file first, then `FINAL_REPORT.md`, `ATTEMPT50_PROTOCOL.md`, and
`ATTEMPT49_REPORT.md`.

## One-minute state

- Challenge: `QuantumBFS/quantum.harness#113`.
- Public team repository: `thy10817/Sim-to-real-simulation`.
- Official branch: `challenge/other-sim-to-real-quantum-gates`.
- Benchmark: synthetic dimension-4 CNOT, 40 controls, nominal Hessian rank 15.
- Formal evidence: Attempt 49, preregistered before 24 fresh truth cells were
  opened; 288/288 runs completed and six/six gates passed.
- Final audit: Attempt 50, independent simulator-free reconstruction, 18/18
  checks passed.
- Core issue deliverable: Attempt 51, queries-to-target versus dimension from
  sealed evidence, 11/11 checks passed.
- Gap/invariant deliverable: Attempt 52, simulator-free verification of
  development failure curves and the conditional `d=2,3,4` rank invariant,
  22/22 checks passed.
- Canonical entry point: `run_challenge.py --mwe` or `--full`.
- Scientific state: frozen. Do not tune against Attempt-49 truths.

## Headline result

The frozen model-informed `k=15` method achieved 90.625% success, versus 25%
for completed model-informed `k=40` and 0% for raw-coordinate `k=40`.
Family-stratified empirical truth-cell bootstrap intervals are
[81.25%, 97.92%], [12.50%, 37.50%], and [0%, 0%], respectively. The final
interval is degenerate because every observed raw-`k=40` truth cell and every
resample has zero success; it is not a strict confidence interval asserting
zero population success probability.

`k=15` uses 39.76% of the deterministic full query cap and 39.05% of the full
shot cap of the `k=40` methods. The formal claim is bounded to this frozen
synthetic CNOT benchmark.

The fresh restricted-mean post-hoc queries-to-target values are 48.76 for
`k=15`, 160.63 for completed model-informed `k=40`, and 166 for raw `k=40`.
Failures are charged the complete method cap; this is not an online stopping
rule.

## What an agent may do

- Run the static Attempt-50 audit.
- Run `--mwe` or the public `--full` replay into a new output directory.
- Inspect and improve explanatory documentation without changing scientific
  numbers or claim boundaries.
- Compare teammate outputs with this direction at the level of mechanisms,
  interfaces, and limitations.
- Prepare a clean, explicit-path official-repository sync.

## What an agent must not do

- Modify or rerun the immutable Attempt-49 formal result in place.
- Call a public replay a second independent confirmation.
- Tune `k`, gates, methods, seeds, or mismatch strengths on Attempt-49 truths.
- Claim online queries-to-target, universal cross-dimension scaling, cesium
  fidelity, or hardware validation.
- Edit, stage, move, format, or delete the protected
  `neural_schrodinger.ipynb`.
- Use `git add .` or `git add -A` in the official repository.
- Modify teammate directories such as `reproduce/` or `robustness/`.

## Reproduction

```bash
python core-sim-to-real/code/attempt50_result_audit.py --verify-only
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
python core-sim-to-real/run_challenge.py --mwe
python core-sim-to-real/run_challenge.py --full
python -m unittest core-sim-to-real/tests/test_final_contract.py
```

The MWE is a development-truth software check with full ledgers. The full mode
is a public-seed replay whose summary must exactly equal archived Attempt 49.

## Retained negative results and audit notes

- The proposed online early-stop certificate failed; headline cost is the
  deterministic full cap.
- The unconditional `rank(H)=d^2-1` statement is rejected. The supported
  cross-size statement is conditional local equality of accessible endpoint
  and Hessian ranks.
- Attempt 28 could not identify a cross-dimension resource advantage because
  raw warm starts had zero restricted cost at its frozen epsilon.
- The frozen platform residual sketch reached the target in 0/4 seeds on both
  positive scenarios; no finite-shot platform claim was authorized.
- Attempt 49 retains compact ledger closure plus hashes rather than full rows.
- Drift-only control-map norm metadata describes an unapplied candidate map;
  the actual applied control-map perturbation is zero.

## Exact next sequence

1. Complete and record clean-clone acceptance.
2. Push the final public package only after fetching and confirming no teammate
   conflict.
3. Read the teammate `reproduce/` and `robustness/` handoffs; integrate claims
   narratively without forcing the three directions into one algorithm.
4. On the agreed submission day, use a clean official worktree and copy only
   the entries in `submission_allowlist.txt` under
   `tracks/other/solutions/QL1F/`; follow `OFFICIAL_SYNC_PLAN.md`.
5. Stage explicit paths, verify the protected notebook hash, run MWE/tests,
   render the offline report, then update the existing PR.
