## Team

| | |
|---|---|
| **Team name** | TDVP4all |
| **Members** | Zhigang Hu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can semidefinite-programming spectral-gap certificates be adapted to the Pauli/projector algebra of blockade-constrained Rydberg chains to produce independently checkable thermodynamic-limit gap or gaplessness windows, beyond existing frustration-free hierarchies? |
| **Catalog issue** | `Addresses #233` — “Certified spectral gaps for blockaded Rydberg chains,” released by Jie Wang and Jin-Guo Liu. |
| **Track** | `tracks/polyopt/` — chosen by the team because the challenge centers on semidefinite hierarchies and noncommutative polynomial optimization, while the issue’s `Method` field is `Other`. |

## Minimal result submitted for review

We implement a sparse Ky Fan SDP hierarchy for the periodic blockaded PXP
chain

\[
H_L(\delta)=\sum_i P_{i-1}X_iP_{i+1}-\delta\sum_i n_i,\qquad
P=(I-Z)/2,\quad n=(I+Z)/2,
\]

with unit Rabi coefficient, \(0=\downarrow\), \(1=\uparrow\), and the
nearest-neighbor blockade \(n_i n_{i+1}=0\), including the wrap bond. The
blockade is represented by localizing constraints. Translation and reflection
are used to reduce the SDP; the reported target remains the
multiplicity-counted global \(E_1-E_0\) in the full constrained Hilbert space.

For \(L=4\), the `global-d2` hierarchy produces an independently checked,
strictly positive lower bound at all 61 detunings
\(\delta=0,0.05,\ldots,3.0\). Every bound satisfies
\(\Delta_{\rm cert}\le\Delta_{\rm ED}\) at the identical point. The largest
absolute ED-minus-certificate deficit is \(5.4030\times10^{-7}\); at
\(\delta=3\),

\[
\Delta_{\rm cert}=0.0933579077612491
<\Delta_{\rm ED}=0.0933580036555446.
\]

The range covers the commonly quoted Ising transition near
\(\delta\simeq1.308\) in this normalization. This finite-\(L\) scan validates
the end-to-end certificate workflow but does **not** locate the thermodynamic
transition, certify a thermodynamic-limit gap, or meet the original
\(N\le20\) success gate.

See [EXPERT_REVIEW.md](EXPERT_REVIEW.md) for the physical interpretation,
selected scan table, exact rational anchor, residual corrections, provenance
hashes, and independent-check commands.

## Contents

- `src/challenge233/sdp/`: exact algebra, localizers, sparse/presolved Ky Fan
  construction, Clarabel bridge, exact dual repair, and independent checkers.
- `src/challenge233/ed/`: sparse QuSpin finite-size oracle and checker.
- `external/1d-basis/`: the trusted user-supplied constrained basis, unchanged.
- `tests/`: standard-library unit and mutation tests for the submitted core.
- `results/`: intentionally untracked; raw solver payloads and certificates
  remain local.

From this directory, run the standard-library test suite with:

```bash
make test
```
