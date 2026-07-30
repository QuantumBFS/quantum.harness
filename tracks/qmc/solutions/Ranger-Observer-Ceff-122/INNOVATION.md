# Innovation statement

## From central-charge extraction to observer-dependent inference

Three established research threads form the starting point:

- Honecker, Picco, and Pujol used numerical transfer matrices to determine the
  Nishimori central charge \(c=0.464(4)\).
- Zabalo et al. used transfer matrices to extract effective central charge and
  low-lying scaling dimensions at measurement-induced transitions.
- Wang et al. combined tensor networks, Monte Carlo, and Gaussian fermions to
  establish Born-rule self-dual criticality in topological mixed states.

Ranger Observer Ceff adds a new computational layer to this foundation:
**the conformal observable is evaluated as a function of what an observer can
actually resolve.**

That extension changes the inference problem. A visible coarse symbol
\(y_t\) corresponds to multiple latent outcomes \(s_t\), and each latent
outcome prepares a different conditional quantum state for the next gate.
The required predictive likelihood is

\[
p(y_t\mid x_{t-1})
=\sum_{s_t=\pm1}K(y_t\mid s_t)p(s_t\mid x_{t-1}).
\]

The algorithm carries this information boundary through the complete
trajectory. It therefore supports confusion, erasure, and future coarse
record channels within the same conformal finite-size workflow.

## Innovation 1: exact-to-scalable hidden-state filtering

Two mutually certifying engines evaluate the coarse-record likelihood:

- An exact branch engine retains every latent history and supplies a
  small-system oracle.
- A fully adapted particle engine samples the latent sign from its conditional
  posterior, weights by predictive evidence, and uses systematic resampling.

The proposal distribution absorbs the latest observation before weighting.
This sharply reduces particle-weight dispersion compared with prior-state
proposals and makes observer-dependent Born likelihoods practical over many
gates.

## Innovation 2: dual physical representations

The self-dual circuit is implemented both as:

- a \(2^L\)-component conditional spin state;
- a \(2L\times2L\) pure-Gaussian Majorana covariance matrix.

Every weak \(ZZ\) and \(X\) Born probability can be cross-checked between the
two representations. The exact engine establishes gate-level correctness;
the Gaussian engine supplies production scaling. With \(P\) filter particles,
the production state memory is \(O(P L^2)\).

## Innovation 3: matrix-free disordered transfer evolution

The periodic \(\pm J\) random-bond Ising row transfer is factored into:

- local two-by-two vertical-bond contractions;
- a diagonal horizontal Boltzmann weight.

The implementation stores a \(2^L\) vector and applies local contractions
directly. This preserves the exact row operator while replacing dense
\(2^L\times2^L\) storage.

## Innovation 4: paired-width stochastic geometry

Every circumference uses a prefix of the same generated bond or measurement
row. This nested common-random-number design:

- aligns stochastic fluctuations across \(L\);
- directly estimates the full covariance of the finite-size curve;
- increases the precision of the universal \(1/L\) coefficient;
- enables one global GLS map from raw blocks to \(c_{\rm eff}\).

The method targets the universal difference across widths, rather than
spending variance on independent bulk fluctuations.

## Innovation 5: model-aware convergence cartography

Each stochastic calibration is analyzed through a structured family:

- \(L^{-1}+L^{-3}\) and \(L^{-1}\) correction models;
- increasing \(L_{\min}\);
- leave-one-width-out ensembles;
- multiple reblocking factors;
- an independent self-dual extension through \(L=24\).

The output is a convergence map rather than a single selected estimate. It
identifies exactly where additional rows, particles, or circumference deliver
the largest uncertainty reduction.

## Innovation 6: global information-order statistics

For confusion and erasure, all resolution points are fitted jointly. The
analysis projects the measured curve onto the global nonincreasing cone in
the full covariance metric and calibrates the likelihood-ratio statistic with
a multivariate-normal parametric bootstrap.

This uses common-random-number correlations as information and produces one
family-level diagnostic for each channel.

## Innovation 7: exact measurement-RG deficiency

The local \(2\to1\) block channel applies a CNOT, keeps the control, and traces
the syndrome. At \(t=\tanh\beta=1/\sqrt2\), optimization over every
row-stochastic classical map gives

\[
\delta_1=\frac{t}{2}=0.3535533906,
\qquad
\delta_2=\frac{t-t^2}{2}=0.1035533906.
\]

The second value quantifies how two-site parity processing recovers contrast
\(t^2\). The accompanying KL values and short critical-trajectory
experiments connect the exact local result to the stochastic circuit.

## Capability comparison

| Layer | Established workflow | Ranger Observer Ceff |
|---|---|---|
| record | fully resolved trajectory | configurable observer channel |
| state inference | physical conditional state | posterior over latent quantum histories |
| correctness oracle | model-specific checks | exact branches plus spin/Gaussian parity |
| width sampling | independent or shared disorder | nested common random numbers with full covariance |
| finite-size output | selected central-charge fit | multi-model convergence map |
| information hierarchy | pointwise curve | global covariance-aware order test |
| measurement-RG | qualitative comparison | optimized TV/KL statistical deficiency |
| evidence | final estimate | manifests, SHA-256 blocks, tests, CSV/JSON, HTML, PDF |

## What becomes possible

The combined architecture supports research questions that sit between
quantum trajectories, information theory, and conformal finite-size scaling:

- effective central charge as a function of observer resolution;
- statistically efficient comparison of multiple information channels;
- exact local measurement-RG diagnostics tied to production trajectories;
- automated allocation of compute toward the dominant uncertainty direction;
- extension to full Lyapunov spectra and learning-transition networks using
  the same evidence pipeline.
