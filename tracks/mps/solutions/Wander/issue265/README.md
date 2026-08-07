# Issue #265 — Certifying Machine-Discovered Burgers Hydrodynamics

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Research question

This submission addresses
[Quantum Harness Issue #265](https://github.com/QuantumBFS/quantum.harness/issues/265):
does the constant-coefficient viscous Burgers equation discovered from a
finite-time Heisenberg-chain trajectory represent an asymptotic hydrodynamic
law, or a highly accurate closure of a particular field, condition, and time
window?

Kharkov et al. learned

\[
\partial_tU+aU\partial_xU=D_{\rm cl}\partial_x^2U,
\qquad
a\approx0.24,
\quad
D_{\rm cl}\approx1.90,
\]

for the normalized high-temperature weak-domain-wall magnetization
\(U=\langle S^z\rangle/\mu\) of the isotropic Heisenberg chain. The central
question is the hydrodynamic scope of this exceptionally accurate fit.

## Answer established so far

The public-trajectory audit establishes Burgers as a quantitative
finite-window benchmark:

| Measurement | Result |
|---|---:|
| Fitted nonlinearity | \(a\simeq0.230\) |
| Fitted classical viscosity | \(D_{\rm cl}\simeq1.97\) |
| Integrated profile relative difference | \(0.167\%\) |
| Width exponent on \(t=80\ldots190\) | \(0.6802\) |
| Moment-diffusivity exponent | \(0.3372\) |
| Width-law amplitude | \(A_W=0.741842\) |
| Burgers tangent ratio | \(A_B/A_W=0.999154\) |

The near-unit tangent ratio supplies an analytical explanation for the fit:
over the measured window, the constant-coefficient Burgers constitutive curve
is almost exactly tangent to the scale-dependent moment diffusivity sampled by
the wall. The learned equation therefore organizes genuine hydrodynamic
structure across the measured window.

The field identity remains essential.  At zero magnetic field, physical
magnetization and its current are odd under spin flip, so an autonomous local
one-field current has odd parity in \(m\). The Burgers current \(am^2/2\) has
even parity. It therefore represents a chiral mode, an orientation-labelled
sector, a finite-background expansion, or a trajectory-conditioned effective
current. The registered field-identification tests distinguish these options.

An open fluctuating theory contributes variance or mode-covariance currents
to the mean equation. This motivates the registered competition among a
scalar closure, opposite-chirality two-Burgers modes, a coupled two-mode open
system, and a later memory/more-mode description.

The complete derivation, literature context, public-data measurements, model
hierarchy, and decision rules are in
[`SCIENTIFIC_CASE.md`](SCIENTIFIC_CASE.md).

## Evidence ladder

The submission separates four levels of evidence:

1. **Exact:** microscopic spin continuity; spin-flip field identification;
   algebraic diagonalization of the equal-coupling two-mode flux.
2. **Controlled:** weak-wall linear response; explicit two-field closure;
   finite-window moment tangency; deterministic rarefaction continuation.
3. **Measured:** public-profile fits, width and moment exponents, synthetic
   coefficient-recovery controls, and numerical backend validation.
4. **Registered:** convergence, cross-condition transfer, joint
   profile/current/response/FCS selection, and sealed future-time prediction.

This structure gives the original machine discovery its full empirical value
and assigns microscopic closure to the multi-condition evidence stage.

## Confirmatory experiment

### Frozen time windows

```text
train:       50 <= t <= 150
validate:   150 <  t <= 200
sealed test: 200 <  t <= 400
```

The JSON contracts store the interval endpoints as `[50,150]`, `[150,200]`,
and `[200,400]`. The executable masks assign each shared boundary to the
earlier stage, creating disjoint scoring sets.

The sealed interval opens once, with explicit human confirmation, after
convergence, Production A, and frozen model selection have created an eligible
scalar or two-mode forecast.

### Registered conditions

The matrix includes:

- amplitudes \(\mu=0.02,0.05,0.10,0.20\), both wall orientations;
- tanh widths \(1,2,4,8\);
- erf, double-wall, Gaussian, and sinusoidal profiles;
- backgrounds \(m_0=\pm0.05\);
- equilibrium, opposite-sign local-pulse response, current,
  connected-correlation, and FCS
  observations;
- \(\Delta=0.8\), \(\Delta=1.2\), and integrability-breaking
  \(\Delta=1,J_2=0.1\) environment controls.

### Convergence ladder

| Level | \(L\) | \(\Delta t\) | \(\chi_{\max}\) | cutoff |
|---|---:|---:|---:|---:|
| coarse | 256 | 0.05 | 256 | \(10^{-8}\) |
| medium | 384 | 0.025 | 512 | \(10^{-10}\) |
| fine | 512 | 0.0125 | 1024 | \(10^{-11}\) |

The frozen medium-to-fine gates are \(<0.2\%\) for the profile relative
\(L^2\) difference and \(<0.3\%\) for the maximum width difference.

### Model hierarchy

The same held-out folds compare:

- shared and condition-specific scalar Burgers;
- the symmetry-aware sector law \(a_i=2\sigma_i g\mu_i\);
- independent opposite-chirality Burgers modes \(u_\pm=m\pm\phi\);
- a coupled two-mode stochastic open system;
- the registered memory or additional-mode interpretation for a richer joint
  observable structure.

Two-mode support requires at least \(30\%\) held-out improvement over the best
scalar competitor, a positive paired-bootstrap \(95\%\) lower bound, exact
symmetry checks, and one parameter set for profiles, currents, responses, and
FCS.  The coupled model additionally requires \(10\%\) improvement over the
independent two-mode manifold and \(\Delta\mathrm{BIC}\ge10\).

## What this PR contributes

- a frozen, machine-readable universality protocol and decision engine;
- the analytical field-identification, nonlinear-averaging, moment-tangent,
  and rarefaction arguments;
- synthetic controls that distinguish effectively constant from
  \(t^{1/3}\)-drifting diffusivity;
- a TeNPy infinite-temperature purification-TEBD backend with magnetization,
  complete current, connected \(C^{zz}\), and transfer FCS;
- dense exact-evolution, spin-flip, continuity, grouped-\(J_2\), and actual
  checkpoint/resume validation;
- source-hash and dataset gates for convergence, Production A, selection,
  authorization, and Production B;
- a 34-condition-per-stage Production-v2 panel and a frozen stochastic solver
  budget of 1,024 screening and at least 2,048 final trajectories;
- a reusable quantum-computing benchmark for certifying machine-discovered
  hydrodynamic equations from profiles and higher-order observables.

## Package map

| Path | Role |
|---|---|
| [`SCIENTIFIC_CASE.md`](SCIENTIFIC_CASE.md) | Long-form scientific argument and literature synthesis |
| [`CURRENT_STATUS.md`](CURRENT_STATUS.md) | Dated execution and evidence ledger |
| [`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md) | Frozen scientific contract |
| [`docs/CLOSED_LOOP_VERDICT.md`](docs/CLOSED_LOOP_VERDICT.md) | Detailed microscopic-to-hydrodynamic audit |
| [`configs/burgers_research_matrix.json`](configs/burgers_research_matrix.json) | Conditions, splits, windows, and numerics |
| [`configs/burgers_decision_rules.json`](configs/burgers_decision_rules.json) | Frozen quantitative thresholds |
| [`results_research_program/manifest.json`](results_research_program/manifest.json) | 74-row base convergence/A/B manifest |
| [`results_research_program/production_manifest_v2.json`](results_research_program/production_manifest_v2.json) | 34-condition-per-stage joint-observable manifest |
| [`results_research_program/two_mode/solver_budget.json`](results_research_program/two_mode/solver_budget.json) | Frozen stochastic convergence and fidelity budget |
| `src/` | Burgers, moment, scalar, two-mode, production, and evidence-gate implementations |
| `scripts/` | Reproducible analysis, validation, bundling, and one-time confirmation entry points |
| `hpc/scnet/` | Pinned Slurm submission and continuation controls |
| `tests/` | Regression and synthetic-selection coverage |

## Reproduce the public checks

From this directory:

```bash
python3 -m compileall -q src scripts hpc tests
python3 -m pytest -q
python3 scripts/validate_tenpy_exact_diagonalization.py
python3 scripts/validate_tenpy_fcs.py
python3 scripts/validate_tenpy_resume.py
```

Tensor-network production uses the pinned remote environment and the Slurm
entry points under `hpc/scnet/`.  Raw production arrays and checkpoints remain
in the registered compute environment. This public package contains source,
compact manifests, decision rules, and validation summaries.

## Research status

```text
public pilot:        finite-window Burgers benchmark established
confirmatory stage:  convergence evidence collection
next decision:       scalar / independent two-Burgers / coupled two-mode / memory
future confirmation: one-time sealed 200 < t <= 400 test
```

The current evidence and archived SCNet records are detailed in
[`CURRENT_STATUS.md`](CURRENT_STATUS.md). The scientific protocol is frozen;
future datasets fill its registered gates, and its hypotheses retain their
preregistered form throughout the analysis.

Addresses #265.
