# Attempt 004: Hessian-Guided Sim-to-Real Calibration

This is the current full-checklist solution for challenge #113 in the YueYuan
PR. It implements a differentiable quantum-gate model, extracts a model-Hessian
control subspace, and compares low-dimensional closed-loop calibration against
fair noisy black-box baselines.

The short scientific report is [`REPORT.md`](REPORT.md).

## What Is Included

- One-qubit `X` and two-qubit `CZ` targets, with 16 and 48 pulse parameters.
- Piecewise-constant controls, phase-insensitive gate fidelity, and JAX
  differentiation through the final propagator.
- Gradient-based open-loop model optimization.
- Dense Hessian extraction plus Hessian-vector-product cross-checks and
  effective-rank/curvature-concentration diagnostics.
- Strict finite-shot `QueryOnlyDevice` with query and shot accounting.
- Backend-neutral hardware candidate/job/result records, batch artifact export,
  result ingestion, and a dry-run hardware backend that exposes only counts.
- Model-only transfer, full-space Nelder-Mead, random-subspace Nelder-Mead,
  Hessian-subspace Nelder-Mead, and adaptive Hessian widening.
- Sweeps over search dimension `k`, model-truth gap, shot budget, two system
  sizes, and multiple random seeds.
- Figure generation for the required query, shot, success, failure, and Hessian
  diagnostics.

## Repository Map

- `config.py`: systems, shot budgets, mismatch levels, seeds, and sweep grids.
- `systems.py`, `dynamics.py`, `pulses.py`: model construction and propagation.
- `open_loop.py`: model-only optimization.
- `hessian.py`: dense Hessian, HVP, and eigenspace utilities.
- `device.py`: hidden true-device perturbations and query-only interface.
- `hardware_adapter.py`: batch hardware boundary, dry-run backend, and
  JSON/CSV/JSONL artifact helpers.
- `optimizers.py`, `baselines.py`: derivative-free closed-loop methods.
- `experiments.py`: sweep orchestration and JSONL output.
- `plotting.py`, `make_figures.py`: figures, summaries, and CSV tables,
  including `spectrum_summary.csv`.
- `run_candidate.py`: compact validator-facing export.
- `run_hardware_dry_run.py`: hardware-style dry run that exports batch
  candidates, pulse payloads, shot-count results, and a summary.
- `slurm/`: conservative array-job scripts for larger CPU/GPU checks.

## Local Setup

Run from the repository root:

```bash
python3 -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt
```

## Fast Verification

These commands are the quickest way to confirm the committed implementation:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_hardware_dry_run.py --out /tmp/yueyuan-attempt004-hardware --shots 256
```

The latest local verification recorded in `REPORT.md` was:

- attempt-004 tests: `25 passed`;
- broader YueYuan attempt tests: `39 passed`;
- validator self-test: `"status": "passed"`;
- fast candidate export: schema version 1, 15 groups;
- hardware dry run: 7 candidates, 1,792 total shots, `real_hardware: false`.

## Hardware-Style Dry Run

`run_hardware_dry_run.py` makes the local experiment look like a small hardware
batch without changing the main sweep. It optimizes a short one-qubit model
pulse, extracts the top three Hessian directions, writes a center candidate plus
plus/minus Hessian-direction candidates, submits them through the dry-run batch
backend, and reconstructs objectives only from shot counts.

The command writes five generated files under the requested output directory:

- `batch_manifest.json`: schema, candidate count, shots per candidate, total
  planned shots, objective proxy, and metadata.
- `candidates.csv`: candidate IDs, pulse dimensions, shot plan, and metadata.
- `pulse_payloads.jsonl`: one pulse-parameter payload per candidate.
- `hardware_results.jsonl`: count-style results with job IDs and candidate IDs.
- `hardware_summary.json`: best count-derived objective, query/shot counters,
  Hessian eigenvalues, and `real_hardware: false`.

This path is intended as a swap point for a real lab/cloud backend: a future
hardware run can replace `hardware_results.jsonl` with measured counts while
leaving candidate generation, result ingestion, and objective reconstruction
unchanged. No committed result claims real hardware execution.

## Smoke Results And Figures

The smoke run writes generated artifacts to an ignored results directory:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py --out tracks/qcs/results/YueYuan/attempt-004/smoke --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py --results tracks/qcs/results/YueYuan/attempt-004/smoke
```

The full reported sweep and focused adaptive sweep were run as conservative CPU
array jobs. The committed report records the generated row counts, success
rates, query/shot summaries, and failure-mode analysis. Raw generated results,
figures, logs, `submission.json`, and `report.json` stay under
`tracks/qcs/results/YueYuan/attempt-004/`, which is intentionally ignored by git.

## Checklist Notes

The required boxes from `challenge_113_codex_spec.md` are covered as follows:

- Differentiable model, open-loop optimization, gradients, Hessian/HVP, and
  leading eigenspaces are implemented and tested.
- Effective Hessian dimension is measured from the spectrum and surfaced in
  `spectrum_summary.csv`; the report distinguishes formal numerical rank from
  practical curvature concentration.
- Query-only noisy device, finite-shot noise, counters, and hidden-device
  boundary checks are implemented and tested.
- Hardware-style batch export, count ingestion, dry-run backend, and
  no-real-hardware accounting are implemented and tested.
- Model-only, full-space, random-subspace, Hessian-subspace, and adaptive
  Hessian methods are implemented with shared optimizer family, query budget,
  shots, target, bounds, and seed protocol.
- Search-dimension, model-truth gap, shot-budget, system-size, and seed sweeps
  are implemented; the full CPU sweep completed 144/144 tasks.
- Required figures and machine-readable summary tables are generated by
  `make_figures.py`.
- Failure analysis is explicit: fixed Hessian subspaces fail under harder
  two-qubit mismatch, and adaptive widening partially mitigates but does not
  solve the hardest case.
