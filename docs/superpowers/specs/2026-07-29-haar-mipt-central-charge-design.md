# Haar-Circuit MIPT Effective-Central-Charge Design

## Objective

Reproduce the effective central charge of the Born-weighted measurement-induced
phase transition in a generic one-dimensional Haar random circuit.  Use exact
state vectors, matrix-free local gates, and sequential Born sampling.  The
first deliverable measures only the entropy density of the measurement record
and extracts `c_eff`; locating the transition, computing subleading Lyapunov
exponents, MPS truncation, and dual-unitary circuits are out of scope.

The literature targets are

\[
p_c=0.168(5),\qquad \alpha=0.81(9),\qquad c_{\mathrm{eff}}=0.25(3).
\]

The production point is fixed to `p = 0.168`.  Its literature uncertainty is
recorded as an unpropagated systematic because this reproduction does not scan
or refit the transition.

## Circuit and time-step conventions

The system is an even-length periodic chain of qubits with

`L = 8, 10, 12, 14, 16, 18`.

Every two-qubit gate is an independent draw from the Haar measure on `U(4)`.
The gate geometry alternates between

- even layers: `(0,1), (2,3), ..., (L-2,L-1)`;
- odd layers: `(1,2), (3,4), ..., (L-1,0)`.

One time step is one such non-overlapping gate layer followed immediately by a
measurement layer.  Thus an even layer and an odd layer each have their own
independent measurement layer; they are not grouped before measuring.  At
every site in each measurement layer, a projective measurement in the `Z`
basis is attempted independently with probability `p = 0.168`.

For every trajectory, discard `4*L` time steps as equilibration and record the
next `24*L` time steps.  These conventions match the generic-Haar calculation
of arXiv:2107.03393.

## Initial-state ensembles

The paper's boundary-effect cancellation is retained by simulating two initial
state families separately:

1. a global Haar-random state in the `2**L`-dimensional Hilbert space;
2. a random product state whose individual qubits are independently Haar
   distributed on the Bloch sphere.

Each family receives independent trajectories and equal statistical weight in
the final free-energy density.  Means and bootstrap samples are formed within
each family before the two estimates are averaged, so a sample-count
imbalance cannot change their intended one-half weights.

## Matrix-free exact-state evolution

The wavefunction is a normalized `complex128` vector of length `2**L`.  No
`2**L`-by-`2**L` circuit or transfer matrix is formed.

A two-qubit gate is applied by reshaping the state into qubit axes, bringing
the target axes together, multiplying the local four-component index by the
`4 x 4` gate, and restoring the original ordering.  The periodic gate
`(L-1,0)` uses the same path and is checked independently in tests.

Haar gates are generated from a complex Ginibre `4 x 4` matrix using QR
decomposition with diagonal phase correction.  Tests require both unitarity
and invariance of the generated distribution under a fixed left unitary at
the level of low moments.

At a measured site, compute

\[
q_0=\lVert P_0\psi\rVert^2,\qquad
q_1=\lVert P_1\psi\rVert^2,
\]

sample `m` from `(q_0, q_1)`, accumulate `-log(q_m)` during the recording
window, project onto outcome `m`, and divide by `sqrt(q_m)`.  Sites selected
in one measurement layer are processed in ascending order.  Since the `Z`
projectors commute, sequential conditional sampling produces the correct
joint Born distribution while avoiding construction of a many-site
projector.

Probabilities are clipped only for roundoff after verifying that their
unclipped values lie within a small numerical tolerance of `[0,1]`.  A sampled
outcome with probability below the positive floating-point threshold is a
hard error, not silently repaired.

At `L = 18`, one state occupies 4 MiB.  A worker is required to keep no more
than three state-sized complex buffers, so state storage remains below roughly
12 MiB per worker; runtime, rather than memory, is the limiting resource.

## Measurement-record free energy

For trajectory `s`, define the recorded Shannon cost

\[
F_s=-\sum_{j\in\mathrm{record}}\log q_{m_j}.
\]

Its raw free-energy-density estimator is

\[
\widetilde f_{L,s}=\frac{F_s}{24L^2},
\]

because the recording time is `24*L`.  The primary per-trajectory output is
`F_s`; the density is recomputed during analysis to keep the normalization
auditable.  The cumulative record cost is also sampled once per time step so
the ensemble-mean curve can verify linear growth throughout the recording
window.  This curve is diagnostic; the endpoint rate above is the primary
estimator.

For each width, independently average the global-Haar and product-state
families and then take their equal-weight mean.  Trajectories, not individual
measurements or time steps, are the independent statistical samples.

## Pilot, sample allocation, and compute gate

Before production, run `64` trajectories for each initial-state family and
each width.  The pilot measures wall time and the between-trajectory standard
deviations `s_{L,\mathrm{Haar}}` and `s_{L,\mathrm{product}}`.  For an equal
number of trajectories in the two families, define the effective standard
deviation of their equal-weight mean as

\[
s_L=\frac{1}{2}\sqrt{s_{L,\mathrm{Haar}}^2+s_{L,\mathrm{product}}^2}.
\]

The requested production count per initial-state family is

\[
N_L=64\,\left\lceil
\frac{1}{64}\max\left(512,
\left(\frac{s_L}{2\times10^{-4}}\right)^2\right)
\right\rceil,
\]

capped at `25000`.  The target `2e-4` is an accuracy budget for each width,
not a promise; the achieved standard errors are always used in the fit.  If
the cap is reached, the result is labelled cap-limited.

The pilot writes a cost projection before any production launch.  In
accordance with the repository compute policy, a projected run longer than
ten minutes is routed to the configured cluster workflow rather than silently
run for hours on the local machine.  Production begins only after the user has
seen the projected wall time, sample allocation, and local-versus-cluster
route.  This is a compute approval gate, not a request to reconsider the
already fixed physical parameters.

## Central-charge extraction

The quantity measured directly without the anisotropy factor is

\[
\widetilde f_L=\widetilde f_\infty
-\frac{\pi\alpha c_{\mathrm{eff}}}{6L^2}+\cdots.
\]

The primary analysis follows the paper's double-fit procedure:

1. For each `L_min = 8, 10, 12, 14`, fit all available `L >= L_min` to
   `tilde_f_L = a(L_min) + m_0(L_min)/L**2`, weighted by the measured
   trajectory standard errors.
2. Fit the resulting slopes to
   `m_0(L_min) = m_0_inf + b/L_min**2`.
3. Report

\[
c_{\mathrm{eff}}=-\frac{6m_{0,\infty}}{\pi\alpha},
\qquad \alpha=0.81.
\]

A secondary stability fit uses all six widths with an explicit `L^-4`
correction.  Its difference from the double-fit result is reported as a fit
systematic and is not folded into the bootstrap error.

Statistical uncertainty is obtained from `1000` deterministic bootstrap
replicates.  Each replicate resamples whole trajectories independently within
each width and initial-state family, recomputes their equal-weight mean, and
repeats the complete double fit.  The anisotropy uncertainty is reported
separately as

\[
\sigma_{c,\alpha}=|c_{\mathrm{eff}}|\frac{0.09}{0.81}.
\]

No numerical error bar from the fixed but uncertain `p_c` is claimed.  The
final report explicitly lists `p_c = 0.168(5)` as an external systematic and
compares the result with `c_eff = 0.25(3)`.

## Reproducibility, recovery, and progress

Each `(L, initial-family, sample-index)` tuple receives a deterministic seed
derived with `numpy.random.SeedSequence`.  That seed controls the initial
state, Haar gates, measurement locations, and Born outcomes.

Every completed trajectory is written atomically as a compact record
containing the physical parameters, seed, total record cost, per-time-step
cumulative cost, runtime, gate count, attempted-measurement count, and outcome
count.  Restarting the command validates existing records and schedules only
missing trajectories.  Gate matrices and state vectors are not stored because
the seed exactly regenerates them.

Progress is flushed after each completed trajectory and summarizes completed
counts by width and initial family, elapsed time, current `tilde_f_L`, its
between-trajectory standard error, and projected remaining time.  Worker
processes set numerical-library thread counts to one to avoid oversubscription.

## Files and artifacts

Implementation uses the existing transfer/analysis/production separation:

- `scripts/haar_mipt_transfer.py`: Haar-gate generation, local state-vector
  action, Born measurements, and one-trajectory simulation;
- `scripts/haar_mipt_analysis.py`: aggregation, double fitting, bootstrap,
  uncertainty separation, and plotting;
- `scripts/haar_mipt_production.py`: pilot, adaptive allocation, resumable
  parallel execution, and compute projection;
- `scripts/tests/test_haar_mipt_transfer.py`: local-gate and trajectory tests;
- `scripts/tests/test_haar_mipt_analysis.py`: synthetic fit, bootstrap, and
  artifact tests;
- `scripts/tests/test_haar_mipt_production.py`: allocation, resume, and seed
  tests;
- `results/haar_mipt_ceff/`: pilot records, production records, summaries,
  fit metadata, configuration, runtime projection, and figures.

The result figure shows `tilde_f_L` against `1/L**2`, the asymptotic fitted
line, and the extracted `c_eff` with statistical and anisotropy errors kept
separate.  A second diagnostic plots the mean cumulative record entropy versus
recording time for all widths.

## Verification and stopping rules

Before any pilot:

- verify Haar-gate unitarity and low moments;
- compare every local-gate path, including `(L-1,0)`, with an independently
  constructed dense operator at small `L`;
- compare a full even/odd circuit period with a dense small-system oracle;
- verify `q_0 + q_1 = 1`, normalized post-measurement states, and empirical
  Born frequencies on fixed test states;
- verify zero record entropy at `p = 0` and deterministic zero cost for a
  measured computational-basis state;
- verify bitwise reproducibility from identical trajectory seeds;
- recover a known synthetic `c_eff` through the complete double fit and
  bootstrap pipeline;
- run the existing clean-Ising and RBIM tests to detect regressions.

The pilot stops without a central-charge claim if any width or initial-state
family lacks finite trajectory statistics.  Production stops with a partial,
explicitly labelled checkpoint if the adaptive target exceeds the sample cap
or the selected compute route expires.  No subleading Lyapunov spectrum,
critical-point scan, MPS approximation, or implicit change of the measurement
schedule is allowed in this stage.
