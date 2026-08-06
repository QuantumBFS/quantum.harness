# Issue #133 Five-New-Problem Campaign Design

## Decision

Publish five genuinely new, small tensor-network problems inside the public
WangTheoPhys capsule.  The historical #124--#128 calibration problems do not
count toward the live campaign.

Each problem is frozen with an exact-integer input and acceptance rule before
the Solver certificate is emitted.  A separate dependency-free Verifier CLI
checks the frozen challenge, the separately materialized gate, and the Solver
certificate in a fresh process.  Every positive receipt is paired with a
deterministically corrupted certificate that the same gate must reject.

## Problems

1. Minimal MPO rank of a frozen operator matrix.
2. Globally optimal contraction of a frozen four-tensor matrix chain.
3. Exact spectral gap of a frozen transfer matrix.
4. Exact Schmidt rank of a frozen bipartite coefficient matrix.
5. Exact gauge equivalence of two frozen bond-dimension-two MPS tensor sets.

## Trust boundary

`human.junkaiwang` is recorded as `human expert supervision` and accepts all
five submission problems and their preregistered gates.  The campaign reports
five human-supervised acceptances and five independently executed exact gate
passes.  QuantumBFS maintainers retain authority over upstream catalog and
tier determination.  No refereed publication is claimed.

## Public artifacts

The campaign directory contains Solver and Verifier sources, a deterministic
runner, direct tests, one JSON file for every challenge/gate/certificate/
negative-control/acceptance/receipt, a campaign manifest, a readable report,
and a SHA-256 file manifest.
