# Complete Single-Spin Floquet Influence-Functional Reproduction Design

## Objective

Extend PR #207 from a partial Fig. 2 transient calculation into a reproducible,
testable implementation of the single-spin results in arXiv:2511.08754v3:
Fig. 2 transient dynamics, the augmented Floquet influence-functional
propagator and steady state, Fig. 3 frequency-resolved heat current, and Fig. 5
integrated heat-current scan.

The implementation lives entirely in the harness. It does not modify or fork
UniformTEMPO.jl. It may read the pinned `UniformPTMPO` tensor and boundary
fields through one compatibility module, guarded by version, field, shape, and
small-instance contraction tests.

The normalized user requirements are preserved locally at
`tracks/mps/results/20260728-floquet-if-complete-reproduction/suggested_reproduction_engineering.md`.

## Source and Version Policy

- Primary physics source: arXiv:2511.08754v3 and its End Matter.
- Numerical references: the authors' Zenodo Fig. 2, Fig. 3, and Fig. 5 CSVs.
- The Zenodo Julia files are plotting scripts, not computational
  implementations. They define plot grids and presentation conventions but
  cannot supply QF, correlations, or heat-current algorithms.
- Use two pinned Julia environments:
  - `envs/paper/`: the exact paper-era UniformTEMPO revision when provenance
    identifies it.
  - `envs/current/`: the currently reviewed revision.
- Never infer the paper revision merely by tuning until χ=235. If provenance
  cannot identify it, record that as an unresolved source gap.
- Both environments share the same harness source and tests. Every result
  records the environment, UniformTEMPO tree revision, Julia version, and
  cache key.

## Fixed Physics

- Units: Ω=1.
- Coupling operator: S=σz.
- System Hamiltonian: Hsys(t)=Ωσx/2+Hdrive(t).
- Longitudinal drive: Hdrive(t)=εd cos(ωd t)σx.
- Transversal drive: Hdrive(t)=εd cos(ωd t)σz.
- Bath: J(ω)=αωexp(−ω/ωc), with α=0.05, ωc=2.5, εd=1, and zero temperature.
- Production Fig. 2/3 target step is approximately π/60; the achieved
  compression dimension must be measured rather than forced.
- Every Floquet configuration satisfies T=2π/ωd=Mdt exactly within a declared
  floating-point tolerance. Set M from the target step and then set dt=T/M.
  Reject noncommensurate configurations; do not interpolate the final step and
  do not let UniformTEMPO silently rescale the process tensor.

Before any production or cluster calculation, restate these conventions,
drive direction, frequency set, observable, step rule, and resource estimate
for user ratification.

## Architecture

Use vertical slices in the ten requested stages. Each stage produces working,
tested software and an independently reviewable numerical artifact before the
next stage begins.

```text
tracks/mps/solutions/reproduction/floquet_spin_boson/
├── envs/
│   ├── paper/{Project.toml,Manifest.toml}
│   └── current/{Project.toml,Manifest.toml}
├── configs/{quick,fig2,fig3,fig5}.toml
├── src/
│   ├── FloquetSpinBoson.jl
│   ├── config.jl
│   ├── model.jl
│   ├── bath.jl
│   ├── uniform_if.jl
│   ├── augmented_step.jl
│   ├── floquet_operator.jl
│   ├── steady_state.jl
│   ├── correlations.jl
│   ├── heat_current.jl
│   ├── redfield_magnus.jl
│   ├── reference_data.jl
│   ├── convergence.jl
│   ├── checkpoint.jl
│   └── diagnostics.jl
├── scripts/
│   ├── reproduce_fig2.jl
│   ├── reproduce_fig3.jl
│   ├── reproduce_fig5.jl
│   ├── run_convergence.jl
│   └── benchmark.jl
├── test/
│   ├── runtests.jl
│   ├── test_model.jl
│   ├── test_uniform_if.jl
│   ├── test_floquet_operator.jl
│   ├── test_correlations.jl
│   ├── test_heat_current.jl
│   └── test_regression.jl
└── README.md
```

Responsibilities are strict:

- `uniform_if.jl` alone reads `UniformPTMPO.q`, `v_l`, and `v_r`. It validates
  dependency identity and converts the package object into the harness adapter.
- `augmented_step.jl` alone owns composite-index layout and vectorization.
- `floquet_operator.jl` exposes forward and adjoint matrix-free period actions.
- `correlations.jl` produces C, Casym, and Cdecay, without heat-current logic.
- `heat_current.jl` transforms the decomposed correlation into continuous
  current, delta weights, and integrated current.
- Generated data lives below a timestamped
  `tracks/mps/results/.../output/`, never in the source tree.

## Data Flow

```text
validated config
  → pinned UniformPTMPO + validated cache
  → AugmentedStep Qn and Qn†
  → matrix-free FloquetOperator QF and QF†
  → left/right Floquet steady states
  → one-period micromotion states
  → phase-averaged two-time correlation C
  → periodic Casym + decaying Cdecay
  → continuous spectrum + discrete delta weights
  → Fig. 3 curves and Fig. 5 integrated currents
  → diagnostics, convergence, and performance reports
```

QF acts on Liouville(system)⊗influence-bond with dimension 4χ. It is never
replaced by a 4×4 reduced-system map that resets bath memory.

## Matrix-Free Propagation

- `apply_step!` contracts one cached local channel with one shared q tensor.
- `apply_period!` applies Q1 through QM using two preallocated augmented
  vectors.
- The adjoint path reverses order and uses adjoint contractions, verified by
  an inner-product identity.
- Cache all local half-step propagators for the M phases.
- Do not construct Kronecker products, general matrix exponentials, or large
  temporaries inside the time-step loop.
- Dense QF is a small-instance reference and an explicit opt-in mode. Print
  augmented dimension and memory estimate before allowing it.

The existing `floquet_process_tensor` is a reference for small tests only: it
forms dense QF and may rescale a noncommensurate process tensor.

## Steady State and Micromotion

- Use a Krylov/Arnoldi solver for leading right and left eigenvectors.
- Select the physical eigenvalue near one among the largest-modulus
  candidates.
- Normalize ⟨LF|RF⟩=1.
- Record λ0, subleading eigenvalue, spectral gap, residuals, iteration count,
  and matvec count.
- Contract RF to a reduced state and check trace, Hermiticity, and minimum
  eigenvalue.
- If Arnoldi does not converge, record the failure and use normalized period
  iteration without silently loosening tolerances.
- Warm-start adjacent frequencies only when dt, q, and augmented dimension are
  compatible.
- Cache one-period state vectors, not dense prefix maps, and test augmented and
  reduced periodic closure.

## Correlations and Heat Current

Compute the ordered complex correlation
C(kdt)=M⁻¹Σm⟨S(tm+kdt)S(tm)⟩ by inserting the early-time operator into each
augmented micromotion state, propagating in augmented space, and contracting
the late-time observable. Do not use a Markovian regression theorem or
propagate only reduced density matrices.

Build s[m]=⟨S(tm)⟩ and obtain Casym by FFT periodic autocorrelation, verified
against direct summation. Define Cdecay=C−Casym and require declared tail
norm, mean, and slope criteria before spectral integration.

At zero temperature compute the continuous current with both:

- an FFT backend with explicit one-sided endpoint and normalization rules;
- a blockwise direct quadrature backend used as a validation oracle.

Never allocate a full frequency-by-time exponential matrix. Store delta peaks
separately using ωn=nωd and Wn=πJ(ωn)ωncn. Plots may show vertical lines, but
tests compare peak positions and integrated weights.

## Caching, Parallelism, and Recovery

- The uniform-IF cache key is a SHA256 over bath parameters, S, exact dt,
  compression settings, adapter schema, UniformTEMPO revision, and Julia
  version.
- A cache file contains q, boundaries, achieved χ, convergence metadata, and
  full provenance. Validate all metadata and dimensions on read.
- Write via a same-directory temporary file and atomic rename. Support
  `--rebuild-cache`.
- Implement serial correlation first. The optimized backend parallelizes
  initial phases with one mutable workspace and one partial accumulator per
  Julia thread; BLAS uses one thread.
- Fig. 5 groups frequencies by identical dt and shares q within each group.
- Checkpoints carry the complete configuration hash, completed work range, and
  partial accumulator. Reject incompatible resumes.
- Do not default to simultaneous full frequency-level and phase-level
  parallelism.

## Validation and Failure Policy

Every optimized layer is compared with an independent small reference:

- matrix-free Qn and QF against explicit contractions;
- QF† through the adjoint inner-product identity;
- steady-state residual and reduced-state physicality;
- C(0)=⟨S²⟩;
- FFT periodic autocorrelation against direct summation;
- FFT heat current against blockwise direct quadrature;
- delta coefficients against a direct Fourier fit;
- Fig. 2/3/5 grids and shapes against Zenodo without silent truncation.

Noncommensurate periods, cache mismatches, reference-grid mismatches,
nonphysical states beyond tolerance, or regression errors beyond tolerance
exit nonzero. Production mode never relaxes tolerances automatically.

## Baseline and Performance

Before optimization, record Fig. 2 total time, IF build time, propagation time,
peak memory, allocations, χ, maximum error, and RMSE in:

- `output/baseline/performance.json`
- `output/baseline/fig2_errors.json`

Compare before/after only at identical physics and numerical precision. Do not
claim speedup by lowering χ, loosening tolerance, shortening τmax, dropping
frequencies or delta peaks, or changing the reference grid.

The main allocation report covers `apply_step!`, `apply_period!`, correlation
propagation, and heat-current transformation. It verifies absence of
time-step-sized large allocations, repeated Kronecker/exponential work,
M dense Qn copies, all-lag augmented-state storage, and full ω×τ matrices.

## Run Modes

- `quick`: CI smoke tests with small χ, M, τmax, and frequency sets; no paper
  accuracy claim.
- `validation`: complete Fig. 2 and at least one Fig. 3 point per drive,
  including FFT/direct cross-checks.
- `production`: paper grids and convergence-selected parameters for all
  Fig. 2/3/5 outputs; all diagnostics mandatory.

Production settings come from scans in dt, compression tolerance/χ,
eigensolver tolerance, τmax, frequency resolution/range, and harmonic cutoff.

## Delivery Stages

1. Baseline, profiling, and strict Fig. 2 reference validation.
2. Model and uniform-IF modules plus versioned cache.
3. Matrix-free Qn/QF and explicit-reference tests.
4. Leading left/right Floquet states and micromotion.
5. Serial reference two-time correlation.
6. Phase threading, workspaces, and checkpoint/resume.
7. Casym/Cdecay and FFT autocorrelation.
8. Fig. 3 continuous spectrum and delta peaks.
9. Fig. 5 total current and power-current balance.
10. Convergence, CI, benchmark report, and README.

Each stage follows test-first development and keeps all prior tests runnable.
No production cluster job is submitted without a fresh setup confirmation and
cost estimate.

## Completion Strategy Ratified 2026-07-29

Continue from the existing implementation rather than rebuilding completed
stages. Work proceeds in this order:

1. Make the pinned Julia environment reproducible from the isolated worktree
   and run the complete test suite.
2. Repair any failing or missing acceptance tests before changing numerical
   kernels.
3. Re-run Fig. 2 validation and one Fig. 3 validation point locally, recording
   wall time, peak memory, allocations, numerical diagnostics, and reference
   error.
4. Use those measured rates to estimate every remaining Fig. 3 and Fig. 5
   point before launch. Prefer local execution only when the estimate is below
   10 minutes and 16 GB; use the configured cluster otherwise.
5. Finish the seven-axis convergence evidence before permitting production
   mode, then generate the complete Fig. 3 and Fig. 5 data and report.

Every stage that produces plottable data also produces its comparison figure
immediately. Pause at that visual checkpoint so the user can inspect the
physics before a more expensive stage starts. A CSV-only result is not a
completed visual checkpoint. Existing Fig. 2 output is reviewed first; Fig. 3
validation is plotted against the matching Zenodo curve before the six-point
production run, and Fig. 5 validation is plotted before the full frequency
scan.
