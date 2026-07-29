# Challenge 194: long-range q=1 random-cluster model

This directory implements the pinned independent-edge finite-ring model from
QuantumBFS/quantum.harness issue #194. It does not use Gori et al.'s
minimum-image `C/r^(1+sigma)` convention.

## Scope

The validated production engine now supports the physical Pilot phase. Pilot
data are exploratory window-selection data only; they make no transition,
critical-point, critical-exponent, scaling, or universality claim.

## Setup

```bash
uv sync \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  --python 3.12
```

## Verify

```bash
uv run \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  pytest -q
```

The accelerated sampler is accepted only when it agrees with analytic edge
probabilities and exact small-system partition distributions.

## Pilot P0 orchestration

Build the immutable 96-cell run spec on the target compute runtime:

```bash
uv run scripts/run_pilot.py build-spec \
  --validation-report /absolute/validation/report/report.json \
  --output-root /absolute/shared/pilot-p0 \
  --run-spec /absolute/shared/pilot-p0/run_spec.json
```

Inspect pending cells, run one zero-based cell, merge all completed cells, and
verify a downloaded tree:

```bash
uv run scripts/run_pilot.py pending --run-spec /absolute/shared/pilot-p0/run_spec.json
uv run scripts/run_pilot.py run-cell --run-spec /absolute/shared/pilot-p0/run_spec.json --cell-index 0
uv run scripts/run_pilot.py merge --run-spec /absolute/shared/pilot-p0/run_spec.json
uv run scripts/run_pilot.py verify --run-spec /downloaded/pilot-p0/run_spec.json
```

`scripts/pilot_array_slurm.sh` maps Slurm array IDs `1..96` to cell indices
`0..95`, requires one CPU, and isolates the Numba cache per cell. Task 10's
120-second/4-GiB capability gate and Task 11 optimization were explicitly
waived after correctness validation. The benchmark status is
`cancelled-without-capability-report`; this is not a passed performance gate.

## Design and references

- `DESIGN.md` pins the scientific and statistical protocol.
- `PLAN.md` records the test-driven implementation sequence.
- `PILOT_PLAN.md` freezes P0, provenance, resource, restart, and P1 boundaries.
- `references/README.md` records source URLs and SHA256 hashes.
