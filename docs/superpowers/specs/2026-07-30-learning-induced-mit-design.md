# Learning-Induced Metal–Insulator Transition: Exploratory Study Design

**Date:** 2026-07-30  
**Team:** 卧龙凤雏  
**Challenge:** Quantum Harness #122, “Criticality in open quantum matter”  
**Primary reference:** F. Eckstein, B. Han, S. Trebst, and G.-Y. Zhu,
“Learning transitions of topological surface codes,”
[arXiv:2512.19786](https://arxiv.org/abs/2512.19786)  
**Official reference data:** [Zenodo 18001896](https://zenodo.org/records/18001896)

## 1. Objective and claim boundary

The study will continue beyond the three completed central-charge benchmarks
and investigate the open learning-induced Majorana metal–insulator transition.
The physical setting is projective measurement of a surface code in a uniform
basis

\[
\sigma^{\theta,\phi}
=\sin\theta\cos\phi\,X+\sin\theta\sin\phi\,Y+\cos\theta\,Z.
\]

At generic angles, the Born-distributed tensor network fermionizes to a
disordered free-fermion network in symmetry class DIII. Near the \(X\) and
\(Z\) directions it is insulating, while a finite \(Y\) component can produce
a Majorana metal. The transition's critical exponents and conformal data,
including its effective central charge, remain open.

The work is deliberately staged:

1. reproduce the previously reported metal–insulator threshold window on the
   special \(XY\) line;
2. validate a generic-angle Born Gaussian sampler;
3. locate a candidate DIII transition on an off-symmetry-plane cut;
4. estimate the Casimir amplitude and, only if anisotropy calibration is
   stable, an exploratory effective central charge.

The first production campaign has a target runtime of 60 minutes and a hard
limit of 90 minutes. It is a research-grade pilot, not a final high-precision
determination. Any DIII threshold or central charge will be labeled a
candidate value. The report must never present an exploratory interval as a
verified universal constant.

## 2. Chosen architecture

A new standalone package will be created at

`tracks/qmc/solutions/卧龙凤雏/learning-mit/`.

The completed `weak-self-dual` benchmark remains unchanged. The new package
may reuse its verified algorithms and oracle ideas, but it must have its own
configuration, schemas, tests, raw data, analysis, and reports. This prevents
the fixed self-dual benchmark from being silently broadened into a model with
different symmetry, dynamics, and scientific gates.

### 2.1 Rust simulation components

Rust performs every stochastic or state-evolution calculation.

- `angles` converts \((\theta,\phi)\) into the complex gate parameters
  \(J,\phi,J_d,\phi_d\), evaluates the complex Kramers–Wannier map, and rejects
  singular or non-finite parameter choices.
- `gaussian` stores the real Majorana covariance matrix, applies non-unitary
  conditional Gaussian measurements, applies real-orthogonal Gaussian
  rotations, stabilizes the covariance, and computes subsystem entropy.
- `circuit` constructs alternating bond and onsite layers, implements the
  periodic boundary sector, and applies outcome-dependent unitary feedback.
- `observables` accumulates conditional Shannon entropy, entanglement arcs,
  spatial and temporal correlation data, minimum Born probabilities,
  covariance-invariant errors, and block-level statistics.
- `runner` derives independent deterministic stream seeds, schedules angle and
  width jobs, enforces the runtime budget, and atomically writes JSON and CSV.

The random-number generator is pinned to
`rand_xoshiro::Xoshiro256PlusPlus`. Python must not generate physical
trajectories.

### 2.2 Python analysis components

Python reads frozen Rust artifacts and performs only deterministic data
processing:

- schema and manifest validation;
- autocorrelation and effective-sample-size diagnostics;
- trajectory/block bootstrap;
- finite-size crossing analysis;
- area-law, logarithmic, squared-logarithmic, and mixed entanglement-model
  comparison;
- Casimir-amplitude fitting;
- spatial/temporal anisotropy calibration;
- sensitivity analysis;
- bilingual plotting and HTML/PDF report rendering.

The data flow is

\[
(\theta,\phi,L,\mathrm{seed})
\longrightarrow \text{Born Gaussian trajectories}
\longrightarrow \text{block CSV}
\longrightarrow \text{finite-size analysis}
\longrightarrow
\bigl(\phi_c,\;c_{\rm eff}\alpha,\;\alpha,\;c_{\rm eff}^{\rm candidate}\bigr).
\]

## 3. Generic-angle circuit

For a projective physical measurement, the bilayer Born tensor network
factorizes and each layer maps to a monitored free-fermion circuit. The
effective measurement coupling is

\[
J(\theta)=\operatorname{atanh}(\cos\theta),
\]

and the dual complex coupling is

\[
\frac{J_d+i\phi_d}{2}
=-\frac12\log\tanh\frac{J+i\phi}{2}.
\]

The bond and onsite circuit gates are represented schematically by

\[
M_Z=\exp\left[
\frac{Js+i\left(\phi-\pi(1-s)/2\right)}{2}Z_jZ_{j+1}
\right],
\]

\[
M_X=\exp\left[
\frac{J_ds+i\left(\phi_d-\pi(1-s)/2\right)}{2}X_j
\right].
\]

Each gate is implemented as a conditional non-unitary Gaussian measurement
followed by its outcome-dependent Gaussian unitary rotation. The real part
controls the Born probability and covariance measurement update; the
imaginary part is norm-preserving and acts by a real orthogonal transformation
on Majoranas. Gate ordering and signs must be fixed by dense small-system
oracles, not by convention alone.

At the weak self-dual pure-measurement limit, the new implementation must
reduce to the existing sampler step by step. At the \(Y\) point, the gates
must reduce to maximally entangling swap dynamics with volume-law boundary
entanglement. These are required limiting cases.

## 4. Phase-location protocol

### 4.1 Stage A: \(XY\)-line reproduction

The first scan fixes

\[
\theta=\frac{\pi}{2}
\]

and evaluates

\[
\phi/\pi\in\{0.18,0.21,0.24,0.25,0.27,0.30\}.
\]

The \(XY\) line is a special class-D limit, not the target generic DIII
problem. Its purpose is validation: the reference paper reports strong
finite-size effects and places the transition in the approximate window

\[
0.20\pi\lesssim\phi_c\lesssim0.28\pi.
\]

The implementation passes this stage only if the finite-size classification
changes from insulating to metallic inside a statistically compatible
window. Agreement with the paper is a bracket-level gate, not a demand to
reproduce one preferred point estimate.

### 4.2 Stage B: generic DIII cut

The exploratory generic cut fixes

\[
\theta=0.45\pi
\]

and scans

\[
\phi/\pi\in\{0.06,0.10,0.14,0.18,0.22,0.26,0.30,0.34\}.
\]

For nonzero \(\phi\), this cut lies away from the \(XY\), \(XZ\), and \(YZ\)
special planes and therefore probes the generic DIII circuit. The coarse scan
must first demonstrate an insulating endpoint and a metallic endpoint. Only
then may the pipeline refine the intervening bracket. If no bracket is found,
the extra runtime allowance must not be spent blindly increasing samples at
the same angles.

## 5. Observables and interpretation

### 5.1 Boundary entanglement

For each trajectory, the restricted Majorana covariance determines the von
Neumann entropy of boundary intervals. The averaged entanglement arc is fit to

\[
S(l,L)=v\,\mathrm{Page}(l,L)
+\frac{c'}{6}\log^2R
+\frac{c}{6}\log R+a,
\qquad
R=\frac{L}{\pi}\sin\frac{\pi l}{L}.
\]

Interpretation is operational:

- an insulator has area-law behavior, with size-dependent fitted
  \(v,c',c\) trending toward zero;
- a Majorana metal has a persistent squared-logarithmic coefficient
  \(c'>0\);
- a candidate transition displays enhanced logarithmic scaling and a
  finite-size crossing or model-weight transfer;
- the exact \(Y\) point is a ballistic volume-law oracle and is excluded from
  critical fits.

No phase label may be assigned from a single width or a visually smooth curve.

### 5.2 Casimir amplitude

The chain rule for the Born record probability makes the sum of conditional
binary entropies a Rao–Blackwellized estimator of the record Shannon free
energy. Its per-row rate is fit as

\[
\gamma_1(L)
=f_\infty L-\frac{\pi(c_{\rm eff}\alpha)}{6L}
+\frac{a}{L^3}.
\]

The directly observed universal candidate is the product
\(c_{\rm eff}\alpha\). A generic circuit is not assumed spacetime-isotropic.

### 5.3 Anisotropy

The pilot estimates \(\alpha\) by comparing the length scales of spatial and
temporal Majorana correlation functions at the candidate transition.
Calibration is jointly bootstrapped with the Casimir fit and repeated across
correlation windows.

The publication rule is strict:

- always report the raw Casimir amplitude \(c_{\rm eff}\alpha\);
- report \(\alpha\) with its window sensitivity;
- report \(c_{\rm eff}=(c_{\rm eff}\alpha)/\alpha\) only if the anisotropy
  estimate is finite and stable under the predeclared window changes;
- otherwise mark the standalone central charge as unresolved.

The entanglement coefficient named \(c\) in the arc model is a diagnostic and
must not be substituted for the Casimir central charge.

## 6. Runtime budget and adaptive schedule

The runtime limit applies to the production simulation and analysis pipeline
after release compilation and automated tests have passed.

- target production time: 60 minutes;
- ordinary stop for new jobs: minute 55;
- permitted scientific redundancy: 30 additional minutes;
- hard stop for new jobs: minute 85;
- atomic finalization reserve: minutes 85–90.

The initial allocation is:

- 5 minutes for production microbenchmarks and runtime calibration;
- 15 minutes for the \(XY\) reproduction scan;
- 15 minutes for the DIII coarse scan;
- 15 minutes for candidate-bracket refinement and larger widths;
- 5 minutes for exploratory anisotropy calibration;
- 5 minutes for bootstrap, plots, and reports.

The 30-minute reserve may be activated only when:

- a crossing bracket exists but bootstrap precision is insufficient;
- the largest scheduled width is incomplete;
- anisotropy is close to passing its stability gate;
- a required scientific oracle needs a targeted rerun.

The initial coarse widths are

\[
L=8,12,16,24
\]

with four independent streams per point. Candidate refinement targets

\[
L=8,12,16,20,24,28,32
\]

with eight independent streams per point, burn-in \(12L\), measurement depth
\(40L\), and complete trajectory blocks.

The first microbenchmark predicts the remaining cost. If the target grid
cannot fit, work is removed in this order:

1. angles farthest from the crossing;
2. independent streams;
3. measurement depth;
4. largest widths.

At least five widths and one angle on each side of the candidate transition
are required for a candidate central-charge fit. If this minimum is not met,
the run can validate the implementation but cannot publish a DIII central
charge.

## 7. Statistical analysis

Trajectory blocks estimate autocorrelation and effective sample size.
Uncertainties are obtained by hierarchical resampling: blocks within
independent trajectories and trajectories within each \((L,\theta,\phi)\)
condition. The threshold, Casimir amplitude, anisotropy, and derived central
charge are jointly recomputed in every bootstrap replicate.

Sensitivity checks include:

- changing \(L_{\min}\);
- deleting the largest width;
- narrowing and widening the angular bracket;
- including or excluding the leading irrelevant correction;
- changing entanglement interval windows;
- changing spatial and temporal correlation windows;
- comparing area, \(\log R\), \(\log^2R\), and mixed models.

The report must show estimator covariance and fit-window drift. A narrow
conditional fit interval does not override large model-selection drift.

## 8. Verification and negative controls

### 8.1 Mathematical tests

- complex Kramers–Wannier transformations satisfy their defining equations;
- Gaussian rotations are orthogonal and preserve covariance purity;
- inverse rotations recover the input state;
- outcome probabilities lie in \([0,1]\) and sum to one;
- measurement and rotation updates preserve antisymmetry within tolerance;
- subsystem entropy agrees with known paired and maximally entangled states.

### 8.2 Dense small-system oracles

At \(L=2\) and \(L=4\), dense Hilbert-space evolution is compared gate by
gate with the Gaussian implementation for:

- joint Born probabilities;
- conditional probabilities;
- normalized post-measurement states or equivalent covariance observables;
- final subsystem entropies;
- outcome-dependent feedback signs;
- periodic boundary-sector conventions.

### 8.3 Physical limits

- the weak self-dual pure-measurement limit matches the frozen
  `weak-self-dual` implementation;
- the \(X\)-like limit is insulating;
- the \(Y\) point has swap dynamics and volume-law entanglement;
- the \(XY\) threshold is compatible with the reference window;
- generic off-plane angles do not accidentally decompose into the special
  class-D implementation.

### 8.4 Negative control

An IID-sign trajectory mode is available only as a diagnostic. It must yield
results distinguishable from conditional Born sampling. It is never included
in the physical estimator. This control protects against accidentally
simulating an annealed or incorrect replica ensemble.

## 9. Failure handling and result states

All raw files are written atomically. A resumable task ledger records completed
angle/width/stream/block units. Interrupted partial blocks are discarded;
completed blocks remain auditable. Non-finite values, invalid probabilities,
or invariant failures terminate the affected stream with full context and
prevent downstream physical claims.

Each report has exactly one machine-readable status:

- `xy_reproduced_diii_candidate`: the \(XY\) gate passes and a DIII candidate
  passes the minimum bracket and stability requirements;
- `xy_reproduced_diii_inconclusive`: the implementation and \(XY\) gate pass,
  but the DIII data are insufficient or anisotropy remains unresolved;
- `validation_failed`: a mathematical, dense-oracle, sampling, or invariant
  gate fails.

The pipeline must prefer an explicit inconclusive result over extrapolating
past the available sizes.

## 10. Deliverables

Each run creates a timestamped result directory with:

- `manifest.json` containing the Git commit, configuration, seeds, dependency
  versions, runtime ledger, and input hashes;
- `raw/blocks.csv` and any required correlation/entanglement block tables;
- `processed/` tables for phase classification, crossings, Casimir fits,
  anisotropy, bootstrap intervals, and sensitivity results;
- `plots/en/` and `plots/zh/` with numerically identical bilingual figures;
- `report.html` and `report-zh.html`;
- `report.pdf` and `report-zh.pdf`;
- `summary.json` with the result state, claims, estimates, intervals, and every
  gate outcome.

The English and Simplified Chinese reports use one report model and the same
frozen numerical data. They explain the model mapping, Gaussian circuit,
Born sampling, parameter choices, phase diagnostics, finite-size fits,
anisotropy problem, uncertainties, failure modes, and claim boundary.

A short, clearly labeled exploratory chapter may also be added to the existing
three-model integrated report. Its candidate DIII result must not be displayed
at the same verification level as the clean Ising, Nishimori, and weak
self-dual benchmarks.

## 11. Acceptance criteria

The implementation phase is complete when:

1. all Rust and Python automated tests pass;
2. dense and physical-limit oracles pass;
3. the production pipeline respects the 90-minute hard limit;
4. raw results are deterministic under fixed seeds and fully auditable;
5. the \(XY\) reproduction either passes or produces an explicit
   `validation_failed` result;
6. any DIII estimate satisfies the minimum width/bracket requirements and is
   labeled exploratory;
7. HTML and PDF reports exist in both languages and contain identical
   numerical claims;
8. no standalone \(c_{\rm eff}\) is claimed when \(\alpha\) is unresolved.

