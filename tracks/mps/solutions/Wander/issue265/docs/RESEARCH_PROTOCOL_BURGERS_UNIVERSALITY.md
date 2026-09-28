# Burgers Universality: Preregistered Confirmation Protocol

**Protocol version:** 1.2

**Freeze date:** 2026-07-30

**Target system:** high-temperature spin transport in the isotropic
Heisenberg chain

**Primary question:** which hydrodynamic field and model class carry the
machine-discovered Burgers structure across conditions, observables, and
future times?

## 1. Registered scientific claims

### H1 — Transferable scalar closure

A single scalar field \(U\) follows

\[
\partial_tU+aU\partial_xU=D\partial_x^2U
\]

with a shared coefficient law across registered wall amplitudes,
orientations, widths, shapes, and backgrounds. The law predicts held-out
profiles, physical currents, local-pulse responses, connected correlations,
and transfer statistics through one coherent observable map.

### H2 — Independent chiral Burgers modes

Two normal modes

\[
u_+=m+\phi,
\qquad
u_-=m-\phi
\]

follow opposite-chirality Burgers flows with shared constitutive parameters.
Their recombination predicts physical magnetization and current while
respecting spin-flip and wall-orientation transformations.

### H3 — Coupled stochastic two-mode hydrodynamics

A coupled two-field open system, with one shared parameter set, predicts the
joint profile, current, response, correlation, and FCS panel. Fluctuation and
mode-covariance currents provide the distinction from the deterministic
independent-mode manifold.

### H4 — Memory or additional hydrodynamic modes

The registered observable panel selects a richer description with temporal
memory or additional slow fields. This outcome specifies the next model class
for a separately frozen extension study.

## 2. Exact field-identification gate

At zero magnetic field, spin flip maps physical magnetization and current as

\[
m\mapsto-m,
\qquad
j_m\mapsto-j_m.
\]

Accordingly, a scalar model written directly for physical \(m\) uses an odd
local constitutive current. A quadratic Burgers current naturally belongs to
a chiral field, an orientation-labelled sector, a background expansion, or a
trajectory-conditioned effective field. The protocol estimates these field
maps explicitly and scores their transformed predictions.

For orientation label \(\sigma_i\) and wall amplitude \(\mu_i\), the
symmetry-aware scalar law is

\[
a_i=2\sigma_i g\mu_i.
\]

The parameter \(g\) is shared across registered conditions. Orientation and
amplitude holdouts test this relation directly.

## 3. Open-system observable map

For a fluctuating mode, ensemble averaging retains the second-moment flux:

\[
\partial_t\bar u
+a\bar u\partial_x\bar u
+\frac{a}{2}\partial_x\operatorname{Var}(u)
=D\partial_x^2\bar u.
\]

For paired fields, mode covariance enters the physical current. The
confirmatory dataset therefore includes mean profiles and the additional
observables that resolve this structure:

- complete-cut current;
- opposite-sign local-pulse response;
- equilibrium connected \(C^{zz}\);
- two-measurement transfer full counting statistics;
- second and fourth cumulants over registered cuts.

## 4. Frozen time partition

```text
training:             50 <= t <= 150
validation:          150 <  t <= 200
sealed confirmation: 200 <  t <= 400
```

The machine-readable interval pairs are `[50,150]`, `[150,200]`, and
`[200,400]`. Executable masks assign shared boundaries to the earlier stage,
creating three disjoint scoring sets.

Training estimates model parameters. Validation performs model selection and
coefficient-transfer tests. Sealed confirmation scores one hash-bound
future-time forecast after explicit human authorization.

## 5. Condition matrix

### Core isotropic panel

- amplitudes \(\mu=0.02,0.05,0.10,0.20\);
- both wall orientations;
- tanh widths \(w=1,2,4,8\);
- erf and double-wall profiles;
- backgrounds \(m_0=\pm0.05\);
- equilibrium states;
- opposite-sign local pulses;
- Gaussian and sinusoidal perturbations for response and mode separation.

### Environment panel

- easy-plane control \(\Delta=0.8\);
- easy-axis control \(\Delta=1.2\);
- integrability-breaking control \(\Delta=1,J_2=0.1\).

The environment panel measures scope and mechanism. The restricted isotropic
claim uses the \(\Delta=1,J_2=0\) rows; the controls provide comparative
transport signatures.

## 6. Numerical convergence

Four representative conditions run at three registered resolutions:

| Level | \(L\) | \(\Delta t\) | \(\chi_{\max}\) | cutoff |
|---|---:|---:|---:|---:|
| coarse | 256 | 0.05 | 256 | \(10^{-8}\) |
| medium | 384 | 0.025 | 512 | \(10^{-10}\) |
| fine | 512 | 0.0125 | 1024 | \(10^{-11}\) |

The accepted resolution satisfies the medium-to-fine gates

\[
\delta_{L^2}<0.002,
\qquad
\delta_W<0.003.
\]

Resolution selection uses these observables before hydrodynamic model scores.
The convergence record binds dataset hashes, source hashes, and the chosen
production settings.

## 7. Production stages

### Production A

Production A evolves the complete registered training and validation panel
through \(t=200\). It produces the data for:

- rolling coefficient estimation;
- condition and orientation transfer;
- current and continuity scoring;
- connected-response prediction;
- FCS and cumulant comparison;
- scalar and two-mode cross-validation;
- frozen model-family selection.

### Production B

Production B evolves the selected registered predictive family through
\(t=400\). The stage is opened once from a previewed, hash-bound transaction.
The record captures the model, parameters, datasets, code, seeds, and human
authorization.

## 8. Model hierarchy

The validation folds compare:

1. Gaussian diffusion with shared \(D_m\);
2. constant-coefficient scalar Burgers;
3. condition-specific scalar Burgers;
4. symmetry-aware scalar Burgers with \(a_i=2\sigma_i g\mu_i\);
5. independent opposite-chirality Burgers modes;
6. coupled stochastic two-mode hydrodynamics;
7. memory or additional hydrodynamic modes.

All predictive classes use the same held-out times, conditions, orientations,
and observable weights.

## 9. Selection thresholds

### Shared scalar transfer

The shared scalar description advances when:

- its held-out score improves over Gaussian diffusion;
- fitted coefficient spread stays within the frozen transfer threshold;
- orientation and amplitude transformations match the registered field map;
- profile and current predictions share one coefficient set.

### Independent chiral modes

The independent two-mode description advances when:

- held-out improvement over the leading scalar competitor reaches at least
  \(30\%\);
- the paired-bootstrap \(95\%\) lower endpoint is positive;
- exact symmetry checks reach their registered tolerance;
- one parameter set predicts profiles, currents, responses, and FCS.

### Coupled stochastic modes

The coupled model advances when:

- it meets the two-mode gates above;
- improvement over the independent manifold reaches at least \(10\%\);
- \(\Delta\mathrm{BIC}\ge10\);
- stochastic convergence reaches the frozen trajectory budget.

The stochastic budget uses 1,024 screening trajectories and at least 2,048
final trajectories. Seed lists and solver tolerances are frozen in
`results_research_program/two_mode/solver_budget.json`.

### Richer hydrodynamic extension

The memory or additional-mode destination is selected by a coherent residual
signature across time and observables. Its selection creates a new
preregistration centered on the identified temporal kernel or additional slow
field.

## 10. Cross-validation and uncertainty

The protocol uses:

- rolling time windows;
- leave-one-condition-out folds;
- leave-one-orientation-out folds;
- 2,000 paired bootstrap replicates;
- 10-time-unit bootstrap blocks;
- frozen observable normalization and weighting;
- coefficient and score confidence intervals;
- source and dataset hash attestation.

These elements make transfer, symmetry, and future prediction separately
measurable.

## 11. Registered readouts

The final report presents:

1. convergence tables for every three-resolution group;
2. rolling \(a(t)\), \(D_{\rm cl}(t)\), \(A_W(t)\), \(A_B(t)\), and
   crossover width \(W_*(t)\);
3. coefficient variation across amplitudes, orientations, widths, shapes, and
   backgrounds;
4. held-out profile and current scores;
5. connected-response and correlation scores;
6. FCS distribution and cumulant scores;
7. bootstrap intervals and model-complexity comparison;
8. the sealed future-time forecast score;
9. the selected field identity and hydrodynamic scope.

## 12. Reproducibility contract

Every decision artifact includes:

- canonical condition and job identifiers;
- code, configuration, and manifest hashes;
- dataset hashes;
- numerical resolution and solver version;
- seeds and stochastic trajectory counts;
- training, validation, and confirmation masks;
- model identity and parameter vector;
- timestamp and authorization record.

The public repository contains source, compact evidence records, frozen
configuration, and validation summaries. Production arrays and checkpoints
reside in the registered compute environment.

## 13. Version ledger

| Date | Version | Refinement | Scope |
|---|---:|---|---|
| 2026-07-28 | 1.0 | initial hypotheses, matrix, splits, thresholds, and quantum backend | confirmatory |
| 2026-07-29 | 1.1 | executable manifest, convergence, cross-condition, two-mode, and one-time confirmation paths | confirmatory |
| 2026-07-30 | 1.2 | Production-B eligibility for every registered predictive family selected in Production A | confirmatory |

## 14. Completion condition

The protocol completes when the converged Production-A record has selected a
registered predictive family or a richer hydrodynamic extension, and the
eligible predictive family has received its one-time \(200<t\le400\)
confirmation score. The resulting statement identifies the field, scope,
observable coverage, and future-time transfer of the machine-discovered
Burgers structure.
