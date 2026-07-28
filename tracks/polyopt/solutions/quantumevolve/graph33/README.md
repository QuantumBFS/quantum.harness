# Challenge #232 — Table-4 graph 33

This is the first real (non-control) target for team `quantumevolve`.
It studies

`β(G) = sup_ρ Σ_i ⟨A_i⟩_ρ²`

for seven Hermitian unitary observables whose anti-commutation graph is graph
33 in Table 4 of arXiv:2310.00612.  The known constructive lower bound is
`α(G)=2`.

The immutable evaluator starts from every square-free state-polynomial basis
word through degree 2.  A candidate may add at most 16 degree-3/4 subsets.
The verifier reconstructs the moment matrix and all algebraic identifications
from the fixed graph, then minimizes the certified numerical upper bound.
This makes basis selection evolvable without allowing candidate code to alter
the graph, objective, commutation relations, or score.

Numerical SDP bounds are discovery evidence only.  A result is not promoted as
a challenge solution until its dual is rationalized and the resulting SOHS
identity is checked exactly.

## Local calibration

The OmniEvolve environment needs CVXPY and Clarabel:

```text
uv pip install --python challenges/omnievolve/.venv/Scripts/python.exe cvxpy clarabel
challenges/omnievolve/.venv/Scripts/python.exe -m pytest tracks/polyopt/solutions/quantumevolve/graph33 -q
```

## Evolution

From `challenges/omnievolve`, with the repository root on `PYTHONPATH`:

```text
omnievolve run ../../tracks/polyopt/solutions/quantumevolve/graph33/initial_code.py \
  -e tracks.polyopt.solutions.quantumevolve.graph33.evaluator:Graph33BasisEvaluator \
  -c ../../tracks/polyopt/solutions/quantumevolve/graph33/config.toml \
  --trusted --no-self-evolve --gens 20 --seed 232
```

## Exported generation-9 certificate

The best 20-generation basis gives the numerical SDP upper bound
`2.0001719333682058`.  The committed exact certificate deliberately uses the
slightly looser rational upper bound `20003/10000 = 2.0003` so that every
coefficient identity and positive-semidefinite check can be performed with
exact rational arithmetic.

```text
challenges/omnievolve/.venv/Scripts/python.exe \
  tracks/polyopt/solutions/quantumevolve/graph33/verify_dual_certificate.py \
  tracks/polyopt/solutions/quantumevolve/graph33/certificates/dual_certificate_exact.json
```

The verifier checks 225 affine coefficient constraints and proves positivity
of the 45-by-45 Gram matrix through 45 strictly positive exact LDL pivots.
`certificates/dual_certificate_numeric.json` retains the floating solver output
for diagnostics; it is not itself the proof.
