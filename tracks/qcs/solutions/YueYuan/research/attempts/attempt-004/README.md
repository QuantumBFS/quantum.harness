# Attempt 004: Hessian-Guided Sim-to-Real Calibration

This is the current full-checklist solution for challenge #113 in the YueYuan
PR. It implements a differentiable quantum-gate model, extracts a model-Hessian
control subspace, and compares low-dimensional closed-loop calibration against
fair noisy black-box baselines.

The short scientific report is [`REPORT.md`](REPORT.md).
The primary judging summary is
[`../../../SUBMISSION.md`](../../../SUBMISSION.md), and the exact
environment and run commands are in [`REPRODUCE.md`](REPRODUCE.md).

## What Is Included

- One-qubit `X` and two-qubit `CZ` targets, with 16 and 48 pulse parameters.
- Piecewise-constant controls, phase-insensitive gate fidelity, and JAX
  differentiation through the final propagator.
- Gradient-based open-loop model optimization.
- Dense Hessian extraction plus Hessian-vector-product cross-checks and
  effective-rank/curvature-concentration diagnostics.
- Strict finite-shot `QueryOnlyDevice` with query and shot accounting.
- Sealed black-box optimizer path that records a query transcript first and
  computes exact audit metrics only in a post-run scorer.
- Pulse-distorted software true-device mode for a more realistic hidden
  mismatch without requiring real hardware.
- Backend-neutral hardware candidate/job/result records, batch artifact export,
  result ingestion, and a dry-run hardware backend that exposes only counts.
- Device-informed adaptive subspace probing: paired finite-shot black-box
  perturbations estimate residual directions when the model Hessian subspace
  stalls.
- Model-only transfer, full-space Nelder-Mead, random-subspace Nelder-Mead,
  Hessian-subspace Nelder-Mead, and adaptive Hessian widening.
- Lightweight invariant/rank probe: one- and two-qubit rows are recomputed from
  the attempt-004 model-Hessian path, and the three-qubit row is labeled as a
  local-chart sanity check.
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
- `device_subspace.py`: black-box paired probing and residual direction
  selection for device-informed adaptive recovery.
- `sealed_black_box.py`: optimizer/scorer separation with a query transcript so
  sealed runners do not receive a true-system object.
- `hardware_adapter.py`: batch hardware boundary, dry-run backend, and
  JSON/CSV/JSONL artifact helpers.
- `optimizers.py`, `baselines.py`: derivative-free closed-loop methods.
- `experiments.py`: sweep orchestration and JSONL output.
- `plotting.py`, `make_figures.py`: figures, summaries, and CSV tables,
  including `spectrum_summary.csv`.
- `run_candidate.py`: compact validator-facing export.
- `run_hardware_dry_run.py`: hardware-style dry run that exports batch
  candidates, pulse payloads, shot-count results, and a summary.
- `run_device_informed_focus.py`: focused hard-mismatch comparison including
  the device-informed adaptive method.
- `run_black_box_holdout.py`: sealed dev/holdout benchmark, including the
  pulse-distortion true-device variant, task-array output mode, and complete
  shard check before Slurm task outputs are combined.
- `invariant_probe.py`, `run_invariant_probe.py`: lightweight `d^2 - 1`
  invariant/rank probe with explicit evidence labels for model-Hessian smoke
  rows versus the three-qubit chart sanity check.
- `slurm/`: conservative array-job scripts for larger CPU/GPU checks.

## Local Setup

Run from the repository root:

```bash
python3 -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt
```

For exact reproduction, use `requirements-lock.txt` and follow
[`REPRODUCE.md`](REPRODUCE.md).

## Fast Verification

These commands are the quickest way to confirm the committed implementation:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_hardware_dry_run.py --out /tmp/yueyuan-attempt004-hardware --shots 256
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_device_informed_focus.py --out /tmp/yueyuan-attempt004-device-informed --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_invariant_probe.py --out /tmp/yueyuan-attempt004-invariant
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py --out /tmp/yueyuan-a004-black-box-holdout --fast
```

The latest verification and sweep evidence recorded in `REPORT.md` was:

- black-box rigor tests: `7 passed`;
- submission reproducibility tests: `10 passed`;
- attempt-004 tests: `46 passed`;
- broader YueYuan attempt tests: `60 passed` in the pinned clean environment;
- validator self-test: `"status": "passed"`;
- fast candidate export: schema version 1, 15 groups;
- hardware dry run: 7 candidates, 1,792 total shots, `real_hardware: false`;
- device-informed fast focus: 10 records, 2 device-informed records;
- invariant probe: 3 rows, including `d=8` local-chart evidence;
- sealed black-box holdout fast run: 10 records, 10 groups, dev and holdout
  splits, `pulse_distortion` true-device variant.
- moderate sealed black-box holdout CPU sweep: 48/48 expected task files, 240
  run records, 120 summary groups, dev and holdout splits, and
  `medium`/`large`/`pulse_distortion` true-device variants.

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

## Device-Informed Adaptive Subspace

`device_subspace.py` adds the method-level recovery mechanism that the fixed and
widen-only Hessian baselines lacked. Around the current best pulse, it samples
paired residual perturbations using only finite-shot black-box responses,
estimates a local curvature proxy, orthonormalizes selected directions against
the model Hessian basis, and charges every probe query and shot to the same
closed-loop budget.

`run_device_informed_focus.py --fast` is a small local smoke comparison on known
hard mismatch cells. It emits `runs.jsonl`, `device_informed_summary.csv`,
`device_informed_recovery.csv`, and `device_informed_recovery.png`. In the fast
run, device-informed probing did not reach the target, but it reduced final
infidelity versus the fixed Hessian, random, and full-space baselines in the two
tested hard cells while recording a 9-query probing overhead. Larger generated
sweeps should be kept under ignored results directories.

## Sealed Black-Box Holdout

`sealed_black_box.py` removes the easiest black-box criticism of the earlier
baseline functions. The sealed optimizers accept only an oracle with `query`,
`query_count`, and `shot_count`, then return a transcript of queried pulses and
noisy finite-shot values. Exact true-device fidelity is computed later by
`score_sealed_run`, after optimization decisions are finished.

`run_black_box_holdout.py --fast` exercises that sealed path on a
`pulse_distortion` software true device. The fast smoke run writes
`runs.jsonl`, `black_box_holdout_summary.csv`, and
`black_box_holdout_success.png`; it produced 10 records and 10 summary groups
across dev and holdout splits. This is a boundary and regression check rather
than a target-reaching claim: all fast pulse-distortion rows missed the `1e-3`
target, while device-informed probing lowered final infidelity in the one-qubit
dev cell and beat fixed/adaptive Hessian in the two-qubit holdout cell.

The moderate CPU Slurm script is
`slurm/black_box_holdout.sbatch`: 48 array tasks, 4 CPUs per task, `%8`
concurrency, 32 CPUs maximum, CPU only. The completed moderate sweep produced
240 method records and 120 summary groups from 48/48 expected shards. Across
the 24 split/system/variant/shot cells, the device-informed sealed method had
mean target-reaching success 0.5625 and median-of-median final infidelity
0.002078, compared with 0.520833 and 0.002162 for widen-only adaptive Hessian,
0.416667 and 0.003515 for fixed Hessian, and 0.1875 with roughly 0.00686
median infidelity for full-space and random-subspace search. Device-informed
probing lowered median final infidelity versus full-space and random in 24/24
cells, versus fixed Hessian in 17/24 cells, and versus widen-only adaptive in
11/24 cells, so it is useful but not uniformly dominant.

## Invariant Rank Probe

`run_invariant_probe.py` writes `invariant_rank_probe.csv` and
`invariant_rank_probe.png`. It records the expected `d^2 - 1` dimensions for
`d=2`, `d=4`, and `d=8`. The one- and two-qubit entries are recomputed from the
attempt-004 model-Hessian path and report the smallest dimension capturing 95%
of curvature plus the curvature captured at the `d^2 - 1` benchmark. The
three-qubit entry is explicitly labeled `local_unitary_chart`, so it is a
dimension-counting sanity check rather than a three-qubit closed-loop
calibration.

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
- Device-informed residual probing, counted probe overhead, focused comparison,
  and recovery summaries are implemented and tested.
- Sealed optimizer/scorer separation, dev/holdout labels, and a
  pulse-distortion true-device variant are implemented, tested, and run through
  a completed moderate CPU holdout sweep.
- Invariant/rank probe covers model-Hessian smoke checks for `d=2` and `d=4`,
  plus a labeled `d=8` local-chart sanity check.
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
