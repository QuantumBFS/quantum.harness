# Challenge #113 — model-informed closed-loop gate calibration

This directory contains the implementation for
[Quantum Harness challenge #113](https://github.com/QuantumBFS/quantum.harness/issues/113).
The final submission tests whether model-Hessian directions reduce
finite-shot, query-only calibration cost and how a drift-Hamiltonian
model-device gap changes that result.

## Final deliverable

Open the self-contained report:

- [Final HTML report](final_report/report.html)
- [Structured report source](final_report/report.json)
- [Methods and results](REPORT.md)

The final report deliberately uses only two consolidated figures:

1. the `d²−1` Hessian-rank check and single-qubit query saving;
2. the two-qubit fixed-space failure and triggered adaptive recovery.

The compact report bundle contains the plotted CSV values and a provenance
manifest. Full source run records remain under `tracks/qcs/results/`.

## Headline result

- At model optima, the Hessian ranks are `3=d²−1` for a single-qubit X gate
  and `15=d²−1` for a two-qubit CNOT.
- At single-qubit mismatch `ε=0.3`, the informed `k=3` space succeeds in 15/15
  trials with median 25 queries. Random `k=3` succeeds in 0/15; raw `P=20`
  succeeds in 15/15 with median 126.
- For the CNOT at `ε=0.5`, fixed nominal `k=15` succeeds in only 3/15 trials.
- A finite-shot-certificate-triggered `k=15→20` protocol succeeds in all 45
  held-out CNOT trials across `ε=0.1, 0.3, 0.5`, with median 97, 330, and 330
  queries.

The conclusion is that `d²−1` is the local physical dimension, while the
orientation of those directions in pulse space is model dependent.

## Minimal code path

| File | Role |
|---|---|
| `sim_to_real.py` | Controlled dynamics, mismatch, query-only device |
| `landscapes.py` | Hessian and endpoint-Jacobian subspaces |
| `optimizers.py` | Five-point scans, COBYQA wrapper, finite-shot certificate |
| `run_invariant_check.py` | Rank check for `d=2` and `d=4` |
| `run_single_qubit_closed_loop.py` | Single-qubit reduced-space comparison |
| `run_robust_closed_loop.py` | Two-qubit fixed-space comparison |
| `run_adaptive_hybrid_closed_loop.py` | Triggered `15→20` recovery |
| `render_paper_figures.py` | Generate the two headline figures |

Other files in this solution directory are retained exploratory work and are
not required for the final report. The authoritative final scope is the
[`final_report`](final_report/) bundle.

## Reproduce

Run the completed experiment scripts:

```bash
python3 tracks/qcs/solutions/Fermichen99/run_invariant_check.py
python3 tracks/qcs/solutions/Fermichen99/run_single_qubit_closed_loop.py

python3 tracks/qcs/solutions/Fermichen99/run_robust_closed_loop.py \
  --optimizer cobyqa \
  --output-dir \
  tracks/qcs/results/sim-to-real-robust-closed-loop-cobyqa-v1

python3 tracks/qcs/solutions/Fermichen99/run_adaptive_hybrid_closed_loop.py
python3 tracks/qcs/solutions/Fermichen99/render_paper_figures.py
```

Render the offline report:

```bash
python3 skills/report/render_report.py \
  tracks/qcs/results/sim-to-real-challenge-report-final
```

No commit, push, or pull request is performed by these commands.
