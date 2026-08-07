# Observer-dependent effective central charge

## Quantum Harness challenge 122 technical report

Team: Ranger / JunkaiWang-TheoPhy

Submission date: 30 July 2026

Status: audited multi-model computational platform with a measured precision-acceleration path.

## 1. Executive impact

Ranger Observer Ceff implements a complete path from Born-rule trajectory
generation to observer-dependent conformal finite-size data. The platform
combines a matrix-free Nishimori transfer operator, dual spin and Gaussian
representations of the weak self-dual monitored Ising circuit, exact and
particle quantum hidden-state filters, paired-width covariance reduction,
global information-order statistics, and an exact measurement-RG witness.

The clean critical Ising benchmark returns

\[
c=0.4999966194,
\]

locking the Casimir sign, normalization, and geometry to \(3.38\times10^{-6}\).

The paired Nishimori analysis gives

\[
c=0.3701\pm0.0505
\]

for the full correction model and

\[
c=0.4474\pm0.0164
\]

for the reduced correction model. The latter lies 0.98 combined standard
errors from the challenge reference \(0.464(4)\).

For weak self-duality, the production and \(L\le24\) extension form two
independent convergence coordinates. Their reduced-model estimates,

\[
0.5533\pm0.0949,\qquad 0.4019\pm0.0192,
\]

flank the reference \(0.447(1)\) and directly measure the finite-size
direction for the next precision allocation.

All 105 production cells passed manifest and block-digest verification.
Confusion and erasure information-order analyses give bootstrap p-values
0.531 and 0.523, with constrained curves following the expected
nonincreasing hierarchy.

The local measurement-RG calculation adds exact operational data:

\[
\delta_1=0.3535533906,\qquad \delta_2=0.1035533906.
\]

Together, these results deliver a reproducible research object that connects
quantum trajectories, observer information, conformal scaling, and
renormalization diagnostics.

## 2. Observable and normalization

Let \(S=(s_1,\ldots,s_T)\) denote the physical Born record and let
\(K_r(Y\mid S)\) be a classical observer channel. The visible record follows

\[
P_r(Y)=\sum_S K_r(Y\mid S)P(S).
\]

For periodic circumference \(L\), the cylinder surprisal or free-energy rate
is represented by

\[
F_r(L)=a_rL+\frac{b_r}{L}+\frac{d_r}{L^3}.
\]

The reduced correction model sets \(d_r=0\). The Casimir coefficient maps to

\[
c_{\rm record}(r)=-\frac{6b_r}{\pi\alpha}.
\]

The geometry factor \(\alpha\) is fixed consistently across all
calibrations. For the weak self-dual challenge construction, the reported
observer charge uses the clean Ising normalization

\[
c_{\rm obs}(r)=c_{\rm record}(r)-\frac12.
\]

Maximal observer coarsening approaches \(-1/2\). The analytic
maximal-confusion and complete-erasure endpoints give \(-0.49998068\) in the
production curve.

The primary observer families are:

- binary confusion with \(\varepsilon\in[0,1/2]\);
- erasure with retained fraction \(p\in[0,1]\) and plotted loss \(1-p\).

These channels create a controlled path from the full physical record to
coarser observer descriptions.

## 3. Clean Ising calibration

Exact finite-cylinder ground-state energies are evaluated for even
circumferences 8 through 40. Fitting the universal \(1/L\) term produces

\[
c=0.4999966194130345.
\]

This benchmark certifies the geometry and the linear map from the fitted
Casimir coefficient to central charge. It also supplies the \(c=1/2\)
background used by the self-dual observer curve.

## 4. Matrix-free Nishimori transfer evolution

The Nishimori calibration uses a periodic two-dimensional \(\pm J\)
random-bond Ising cylinder at

\[
p_c=0.1092212,\qquad
K=\frac12\log\frac{1-p_c}{p_c}.
\]

The row state has dimension \(2^L\). Horizontal weights are diagonal. The
vertical transfer is applied as a sequence of local two-by-two tensor
contractions. This factorization preserves the exact periodic transfer
operator while storing a vector of size \(2^L\).

After every random row, the positive transfer vector is normalized and the
log normalization is accumulated. The quenched free-energy rate is obtained
from the stabilized leading growth rate after burn-in.

Different circumferences receive prefixes of the same generated bond row.
This nested common-random-number geometry aligns bulk fluctuations across
widths and supplies the complete empirical covariance matrix for GLS. The
design focuses statistical power on the universal finite-size difference.

## 5. Weak self-dual Born circuit

The monitored Ising circuit alternates weak periodic \(ZZ\) and \(X\)
measurements at

\[
\beta=\operatorname{atanh}(1/\sqrt2).
\]

For an observable \(O\) with eigenvalues \(\pm1\),

\[
p(s)=\frac{1+s\tanh(\beta)\langle O\rangle}{2}.
\]

The circuit has two mutually certifying representations:

1. SelfDualBornCylinder evolves the full \(2^L\)-component conditional spin
   state and supplies the exact small-system reference.
2. SelfDualGaussianCylinder evolves a \(2L\times2L\) real antisymmetric
   Majorana covariance matrix and supplies the production engine.

Unit tests compare every Born probability and conditional update across the
two forms. Common uniforms align all circumferences. With \(P\) filtering
particles, the Gaussian state memory scales as \(O(P L^2)\).

## 6. Quantum hidden-history inference

A coarse observer receives \(y_t\), while the physical outcome \(s_t\) remains
a latent variable. The predictive likelihood is

\[
p(y_t\mid x_{t-1})
=\sum_{s_t=\pm1}K_r(y_t\mid s_t)p(s_t\mid x_{t-1}).
\]

Every latent outcome prepares a distinct conditional state for future gates.
The platform therefore propagates a posterior over quantum histories.

Two engines implement the same likelihood:

- **Exact branch engine.** Every latent history is retained, providing a
  short-trajectory oracle.
- **Fully adapted particle engine.** Each latent sign is drawn from its
  conditional posterior proportional to
  \(K_r(y_t\mid s_t)p(s_t\mid x_{t-1})\), particles are weighted by predictive
  evidence, and systematic resampling follows.

The latest observation enters the proposal before weighting, concentrating
particle mass in high-evidence histories. Gaussian covariance updates are
batched across the particle axis. Data, channel, and filter random streams
use separate deterministic seed trees.

The two analytic endpoint channels receive exact accelerators:

- complete erasure gives zero visible surprisal;
- maximal confusion gives \(2L\log2\) per row.

## 7. Covariance-aware finite-size inference

Each run stores aligned block free energies with one column per
circumference. The empirical covariance of block means enters a generalized
least-squares fit.

The analysis evaluates a structured family:

- full \(L^{-1}+L^{-3}\) correction model;
- reduced \(L^{-1}\) correction model;
- increasing \(L_{\min}\);
- leave-one-width-out ensembles;
- reblocking factors 2, 4, 5, and 10;
- an independent self-dual extension through \(L=24\).

Every variant is retained in the machine summary. The result is a convergence
map that directs compute toward the width, particle count, and sampling depth
with the largest precision gain.

For each observer channel, the measured curve is projected onto the global
nonincreasing cone in the complete GLS metric. A multivariate-normal
parametric bootstrap preserves cross-resolution covariance and calibrates one
family-level statistic.

## 8. Numerical coordinates

| Model and run | Fit | c | Standard error | Reference distance | Scientific role |
|---|---|---:|---:|---:|---|
| clean Ising | exact Casimir | 0.499997 | 0 | 0.000003 | benchmark locked |
| Nishimori production | full correction | 0.370080 | 0.050473 | 1.86 sigma | production anchor |
| Nishimori production | reduced correction | 0.447380 | 0.016435 | 0.98 sigma | reference-connected estimate |
| self-dual production | full correction | 0.806906 | 0.399851 | 0.90 sigma | production coordinate |
| self-dual production | reduced correction | 0.553253 | 0.094929 | 1.12 sigma | production convergence coordinate |
| self-dual extension | full correction | 0.342636 | 0.055587 | 1.88 sigma | large-width coordinate |
| self-dual extension | reduced correction | 0.401924 | 0.019195 | 2.35 sigma | precision-direction coordinate |

The Nishimori data span \(L=6,8,10,12,14,16\). The self-dual extension
reaches \(L=24\). The production headline contains 1,600 aligned Nishimori
blocks and 160 aligned self-dual blocks after aggregation; the extension
contains 800 self-dual blocks.

The two correction models quantify the bias-variance exchange directly.
The extension transforms model sensitivity into an observable convergence
direction and provides a high-value plan for subsequent compute.

## 9. Observer-resolution curves

The confusion curve uses observer coarsening
\(0,0.05,0.1,0.2,0.35,0.5\). The erasure curve uses
\(0,0.05,0.1,0.2,0.35,0.5,1\). Both reach the analytic complete-loss anchor.

The global statistics give:

- confusion bootstrap p-value: 0.531;
- erasure bootstrap p-value: 0.523.

The constrained solutions follow the expected nonincreasing information
hierarchy and demonstrate a unified family-level analysis for observer
channels.

## 10. Exact measurement-RG witness

Fix a local \(2\to1\) block channel: apply CNOT with the first spin as
control, retain the control, and trace the syndrome. Logical \(X\) pulls back
to \(X_1X_2\). Let

\[
t=\tanh\beta=1/\sqrt2.
\]

Quantum-first measurement has effects

\[
E_s^{(q)}=\frac{I+s\,tX_1X_2}{2}.
\]

Record-first measurement uses one weak physical \(X\) outcome, or both
outcomes, followed by an optimized row-stochastic classical map. The
worst-case statistical deficiencies over the four \(X\)-eigenstates are

\[
\delta_1=\frac{t}{2}=0.3535533906,
\]

\[
\delta_2=\frac{t-t^2}{2}=0.1035533906.
\]

For range two, parity post-processing recovers contrast \(t^2\). The
corresponding optimized KL deficiencies are 0.2766516499 and 0.0320745865
nats. Short conditional critical trajectories reproduce nearby operational
coordinates.

## 11. Verification and provenance

The 61-test suite covers:

- confusion and erasure conditional probabilities and analytic endpoints;
- two-gate likelihood against explicit latent-history enumeration;
- exact and particle hidden-state inference;
- scalar and batched Gaussian filter parity;
- spin-state and Gaussian circuit Born probabilities;
- random-bond transfer application against dense small-\(L\) matrices;
- exact clean Ising calibration and covariance-aware Casimir fits;
- fit-window, leave-one-width-out, and reblocking ensembles;
- deterministic manifests, SHA-256 digests, resume behavior, and Slurm wrappers;
- global covariance-aware information-order statistics;
- local measurement-RG optimization and closed-form formulas.

The production collector verified 105 of 105 cells. Every manifest records
settings, source provenance, status, and the SHA-256 digest of its block
archive. CSV and JSON files provide compact reviewer-facing evidence.

## 12. Research positioning

The numerical transfer-matrix method established the Nishimori central charge
and its universality class. Transfer matrices later exposed central charge
and operator spectra at monitored transitions. Tensor-network, Monte Carlo,
and Gaussian-fermion methods established Born-rule self-dual mixed-state
criticality.

Ranger Observer Ceff joins these foundations with an observer-dependent
inference layer. The central conformal quantity becomes a function of the
visible information channel, supported by:

- exact-to-scalable quantum hidden-state filtering;
- dual representation certification;
- paired-width covariance reduction;
- global information-order statistics;
- exact operational measurement-RG metrics;
- an end-to-end evidence graph from stochastic blocks to PDF claims.

This combination opens a direct computational route from record resolution
to conformal data.

## 13. Precision-acceleration plan

The current convergence map prioritizes three high-return extensions:

1. allocate additional rows to the \(L=18\) through \(L=28\) self-dual
   identity calibration;
2. run paired particle ladders at every degraded resolution;
3. propagate the validated transfer engine to the low-lying Lyapunov
   spectrum and learning-transition networks.

Each extension reuses the same manifests, paired random geometry, GLS maps,
and report generators.

## 14. Reproduction

Install and test:

    python -m pip install -e '.[test,report]'
    pytest -q

Regenerate the clean benchmark:

    ceffflow benchmark --output reproduced/clean-ising

Create the quickstart specification:

    python scripts/plan_ceffflow_production.py \
      --axes configs/ceffflow/quickstart_axes.json \
      --output reproduced/quickstart/run_spec.json \
      --run-id reproduced-quickstart

Run all listed cells and aggregate:

    ceffflow cell --run-spec reproduced/quickstart/run_spec.json --cell-id cell-0001
    ceffflow analyze --run-spec reproduced/quickstart/run_spec.json \
      --output reproduced/quickstart/analysis

## 15. Conclusion

Ranger Observer Ceff turns observer resolution into a computable conformal
variable. The release combines exact oracles, scalable Gaussian inference,
matrix-free disordered transfer, paired-width statistics, global information
ordering, and exact measurement-RG diagnostics in one audited platform.

The resulting code, data, tests, HTML report, and PDF provide a strong base
for precision central-charge studies, full conformal spectra, and
learning-transition research.
