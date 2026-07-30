# Killer Queen: truncated Bose--Hubbard bulk-gap certificates

## Team

| | |
|---|---|
| **Team name** | Killer Queen |
| **Members** | 唐鼎文 (Tang Dingwen); 聂芃 (Nie Peng) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can the thermodynamic state-polynomial hierarchy be extended to occupation-truncated bosons and produce independently checked bulk-gap upper statements and local Mott-diagnostic bounds on three infinite hyperbolic graphs? |
| **Catalog issue** | Addresses #92 — “Certified bulk spectral-gap bounds for truncated Bose-Hubbard models on hyperbolic lattices,” released by Xiangling Xu (Inria Saclay) and Jie Wang (AMSS-CAS). |
| **Track** | `tracks/polyopt/` — selected from the issue's `Method: Semidefinite programming / Noncommutative polynomial optimization` field. |

## Result

The Julia/JuMP hierarchy core and independent exact certificate checker are
implemented and tested. The current submission contains exact-projected
hard-core finite-level gap upper statements, accepted observable bounds, and
explicit `UNKNOWN` rows for every numerical or resource failure. It is a
partial Target 2 campaign, not a claim that the mandatory larger-cutoff and
nested-level grid is complete. Open the self-contained
[`submission/report.html`](submission/report.html) for the professor-facing
result and [`submission/FINAL_REPORT.md`](submission/FINAL_REPORT.md) for its
GitHub-readable counterpart.

## Technical guide

This directory is a reproducible research scaffold for
[quantum.harness issue #92](https://github.com/QuantumBFS/quantum.harness/issues/92).

Read in this order:

1. [`submission/report.html`](submission/report.html): the self-contained,
   professor-facing challenge report. Its curated tables, structured source,
   run summary, and data-provenance manifest live beside it in
   [`submission/`](submission/README.md).
2. [`results/deadline_analysis/CURRENT_HPC_REPORT.html`](results/deadline_analysis/CURRENT_HPC_REPORT.html):
   current SCNet snapshot, including exact-projected thermodynamic gap upper
   statements, accepted observable endpoints, explicitly labeled floating
   calculations, unresolved refinement points, level sizes, and resource failures.
3. [`PHYSICS_TALK.html`](PHYSICS_TALK.html): a professor-style
   many-body physics talk explaining exactly what finite ED, the atomic SDP,
   and the root-local thermodynamic outer test calculate—and what the results mean.
4. [`status.md`](status.md): authoritative checklist for the paper-defined
   `(L,d)` hierarchy, Target 2 model/grid, completed work, missing work, and
   implementation gates.
5. [`report.html`](report.html): detailed, self-contained technical visual report of the
   algorithm, implementation, experiments, audit trail, limitations, and roadmap.
6. [`agent.md`](agent.md): compact agent handoff and decision log containing
   scientific claim rules, durable corrections, blockers, and the next action.
7. [`ALGORITHM.md`](ALGORITHM.md): why the method is a thermodynamic bulk-gap
   **upper-bound** hierarchy rather than a ground-energy SDP.
8. [`SURVEY.md`](SURVEY.md): what current software can and cannot do.
9. [`REPORT.md`](REPORT.md): generated experiments, limitations, and next
   research steps (created after running the study).

The code contains four deliberately separated calculations:

- `julia/` is the paper-defined hierarchy core.  It implements the complete
  state-polynomial index sets in [`LEVEL_SPEC.md`](LEVEL_SPEC.md), exact
  finite-matrix algebra over `Q(sqrt(2),sqrt(3))`, charge blocks, `TS2`, JuMP
  assembly, Clarabel/Mosek solve paths, and independent dual checking.
  `solve_observable(...; exact_certificate=true)` requests a separately
  classified exact lower/upper certificate for a selected bound.

- `atomic_sdp.py` is a tiny, genuine state-polynomial SDP for the \(t=0\),
  single-site, \(U(1)\)-invariant problem. It includes the lifted nonlinear
  variance term and certifies the exact atomic benchmark.
- `rooted_sdp.py` is a custom root-local thermodynamic outer test: root-supported
  excitations, their complete nearest-neighbor Hamiltonian window, exact
  matrix-unit algebra, stationarity, local positivity, and a lifted gap block.
  It has a valid but weak \(U(1)\)-restricted thermodynamic implication, but it
  is not a paper-defined `(L,d)` level or the complete convergent hierarchy.
- `ed.py` computes open finite-patch spectra in fixed particle-number sectors.
  These results validate signs and observables but are **not** thermodynamic
  gap certificates.

## Reproduce

From this directory:

```bash
make setup
make julia-setup
make test
make graphs
make campaign
make study
make rooted-study
make rooted-issue-scan
make final-report
```

Outputs are written to the git-ignored `results/` and `.figures/` directories.
The default study uses exact rooted radius-one patches, so it is small enough
for a laptop. Use `.raw/venv/bin/python scripts/inspect_hypertiling.py --help`
to generate and inspect larger genuine \(\{p,q\}\) tilings before attempting
larger ED runs.

The default open-source solver is Clarabel through CVXPY. The rooted study is
separate because the redundant/singular PSD faces at \(n_{\max}=3\) expose
solver-conditioning limits and can legitimately produce `UNKNOWN`. A floating-point
`infeasible` status is evidence from a numerical solver, not by itself a
machine-checkable proof. The CSV records solver status and residual-related
statistics so later rational/interval validation can be added.

The complete Target-2 production manifest contains 90 mandatory primary gap
endpoints and 1,620 primary observable min/max solves.  A companion manifest
deduplicates these into 38 dry-assembly levels with resumable SCNet runners.
Both are generated, not run, on the laptop.  See
[`hpc/README.md`](hpc/README.md) for the SCNet launch order and resource gates.
A solver-reported infeasibility is classified as
`UNKNOWN` until the Julia checker has exactly projected the dual identities,
used 256-bit Arb intervals for coefficient signs, verified all PSD cones, and
found a positive normalized Farkas margin.
Selected observable rows can likewise preserve a separately labeled exact
lower- or upper-bound certificate.  Singular optima are moved inward with a
small conservative endpoint backoff, and the backed-off exact value—not the
floating optimum—is the certified result.

The pinned upstream reference reproduction is:

```bash
.raw/venv/bin/python scripts/reproduce_reference.py
```

It requires a Mosek license.  On a host without one it writes a durable
`BLOCKED` record instead of substituting Clarabel and calling the result an
upstream reproduction.
