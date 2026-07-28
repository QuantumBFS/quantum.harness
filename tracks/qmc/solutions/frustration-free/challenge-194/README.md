# Challenge 194: long-range q=1 random-cluster model

This directory implements the pinned independent-edge finite-ring model from
QuantumBFS/quantum.harness issue #194. It does not use Gori et al.'s
minimum-image `C/r^(1+sigma)` convention.

## Scope

The current Day-0 milestone validates the periodic kernel, canonical edge
classes, deterministic union-find, exact graph enumeration through `L=6`,
an independent quadratic Bernoulli oracle, and a geometric-skipping sampler.
It makes no transition or critical-exponent claim.

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
probabilities and exact small-system partition distributions. Generated
production data do not exist at this milestone.

## Design and references

- `DESIGN.md` pins the scientific and statistical protocol.
- `PLAN.md` records the test-driven implementation sequence.
- `references/README.md` records source URLs and SHA256 hashes.
