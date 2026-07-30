# 格格巫 — Challenge 121 final submission

## Team

| | |
|---|---|
| **Team name** | 格格巫 |
| **Members** | Bei Qiao (乔北), Zongyue Liu (刘宗岳), Kexiang Mao (毛柯翔) |
| **Contribution policy** | Joint team result; contributions are not partitioned by member. |

## Challenge

| Row | |
|---|---|
| **Challenge** | Construct physically interacting fermion models whose determinantal-QMC weights are provably nonnegative at arbitrary auxiliary-field depth, and delimit failed extensions with exact certificates. |
| **Catalog issue** | Addresses [#121 — Sign-problem-free hunter](https://github.com/QuantumBFS/quantum.harness/issues/121), released by Lei Wang. |
| **Track** | `qmc`, following the challenge issue. |

## Final reviewer entry point

Challenge 121 is maintained in a dedicated public repository, separate from
Challenge 15:

- [English final report at immutable commit `3a20980`](https://github.com/Joe-Nor/gegewu-challenge-121-sign-free-hunter/blob/3a20980b352afb95cd05a3f5f321ca4585d81abc/FINAL_SUBMISSION_REPORT.md)
- [Static HTML report](https://github.com/Joe-Nor/gegewu-challenge-121-sign-free-hunter/blob/3a20980b352afb95cd05a3f5f321ca4585d81abc/FINAL_SUBMISSION_REPORT.html)
- [Clean-checkout reproduction guide](https://github.com/Joe-Nor/gegewu-challenge-121-sign-free-hunter/blob/3a20980b352afb95cd05a3f5f321ca4585d81abc/REPRODUCIBILITY.md)
- [Machine-readable final manifest](https://github.com/Joe-Nor/gegewu-challenge-121-sign-free-hunter/blob/3a20980b352afb95cd05a3f5f321ca4585d81abc/experiments/FINAL_SUBMISSION_V1.json)
- [Source repository](https://github.com/Joe-Nor/gegewu-challenge-121-sign-free-hunter)

The report derives the interacting Hamiltonian, Trotter/HS construction,
determinant weight, and configuration-wise sign theorem for three primary
models: the 2D totally-nonnegative tensor lift, exterior-representation lift,
and conjugate-tensor lift. It also records DQMC/exact-Trotter/ED checks of
particle number and energy at several chemical potentials, plus the exact
PGL(2,7) local HS theorem and its conventional-hopping no-go boundary.

## Reproduction

From a clean checkout of the dedicated repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
.venv/bin/python validate_final_submission.py --focused-tests
```

The final local acceptance run reported:

```text
103 passed, 21 subtests passed
status: pass
2D-TN: 90,003 stored small-system determinant evaluations,
       336,000 stored 4×4 local ratios
exterior: 132,003 stored chain determinants + 3,000 independent fields
conjugate tensor: 220,005 stored chain determinants + 5,000 independent fields
negative evaluated weights: 0
zero evaluated weights: 0
PGL closure: 336 states, 50 fields, 16,800 transitions
```

The finite numerical checks validate the implementations and estimators.
Arbitrary-size and arbitrary-depth sign claims come from the analytic proofs,
not from these sample counts. Candidate-registry states and novelty boundaries
are stated explicitly in the English report.
