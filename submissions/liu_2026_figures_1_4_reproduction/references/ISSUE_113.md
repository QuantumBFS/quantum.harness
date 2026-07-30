# Source note: Quantum Harness Issue #113

- Title: `[challenge]: Sim-to-Real for Quantum Gates`
- URL: <https://github.com/QuantumBFS/quantum.harness/issues/113>
- Repository: `QuantumBFS/quantum.harness`
- Released by: Lei Wang, Institute of Physics, Chinese Academy of Sciences
- Opened: 2026-07-17
- Track: quantum control and differentiable programming
- Status when consulted: open; labels `accepted` and `challenge`

## Research question

Can a cheap differentiable simulator identify the small set of pulse
directions that matter, so that calibration of an expensive query-only
quantum device uses substantially fewer experiments than an optimizer acting
in the full pulse space?

The motivating tension is:

- Open-loop model optimization is differentiable, precise, and cheap, but
  suffers from model mismatch.
- Closed-loop device optimization corrects unknown mismatch, but every
  derivative-free objective evaluation costs hardware queries and shots.
- The proposed bridge is to obtain a warm-start pulse and the curved Hessian
  subspace from the model, then spend hardware queries only in that subspace.

## Mathematical observation

Near a target unitary, write:

`U(T)=U_target exp(iA)`.

For a small Hermitian error generator `A`, the phase-insensitive infidelity is:

`L approximately (1/(2d)) Tr[(A - Tr(A) I/d)^2]`.

The identity component is a physically irrelevant global phase. In an ideal
controllable closed `d`-dimensional system, the curved space is therefore the
`d^2-1`-dimensional traceless Hermitian algebra. Extra pulse parameters enlarge
a flat solution manifold rather than adding physically distinct error
directions.

## Required pipeline

1. Open-loop model optimization: differentiate through a Schrödinger model
   and find a model-optimal pulse.
2. Landscape extraction: obtain leading Hessian eigenvectors, preferably with
   Hessian-vector products and a Krylov eigensolver at scale.
3. Closed-loop model-free calibration: parameterize corrections in the
   extracted subspace and optimize them using only noisy scalar responses from
   a query-only device.

The black-box device may be a perturbed software model or real pulse-level
hardware. Its internals and derivatives must not be exposed to the closed-loop
optimizer. Every query and shot must be counted.

## Required deliverables

1. Reproducible model → Hessian → black-box pipeline with a clean boundary.
2. Queries-to-target versus search dimension, comparing the model-informed
   subspace with a full-parameter search, including error bars over seeds and
   more than one model–truth gap.
3. Failure-mode study versus gap size, including safety-margin dimensions or
   subspace re-estimation.
4. An invariant check across at least two system sizes, testing the `d^2-1`
   prediction.
5. A short report or notebook and an honest failure case.

The issue also asks for a shot-budget/noise study and treats a data-driven
dimension rule, iterative subspace re-estimation, or real-hardware closure as
bonus research extensions.

## How this submission relates

This bundle realizes one detailed neutral-atom case:

- 400 raw phase controls;
- rank-10 model Hessian subspace;
- query-only finite-shot digital twin;
- synthetic AOM model–truth gap;
- four Hessian correction cycles;
- coherent error reduced from `5.88e-2` to `1.22e-4`;
- raw observation floor near `4e-3`.

It does not contain the issue’s full dimension, gap, seed, Hilbert-space-size,
or shot-budget sweeps. The report therefore calls this a scientific case study
and paper reproduction, not a completed solution to every Issue #113
deliverable.

## Resource links from the issue

- Starting differentiable-control notebook:
  <https://colab.research.google.com/drive/1T0_sJMwmk7rbpxHMcBZwdD9pnYZx93oh>
- GRAPE: <https://doi.org/10.1016/j.jmr.2004.11.004>
- CRAB: <https://arxiv.org/abs/1103.0855>
- Discrete adjoints: <https://arxiv.org/abs/2001.01013>
- Adaptive feedback control:
  <https://doi.org/10.1103/PhysRevLett.68.1500>
- Ad-HOC: <https://arxiv.org/abs/1402.7193>
- Randomized-benchmarking calibration: <https://arxiv.org/abs/1403.0035>
- Trap-free control landscapes:
  <https://doi.org/10.1126/science.1093649>
- Hessian landscape analysis: <https://doi.org/10.1063/1.2198836>
- Dynamic dimensionality identification:
  <https://doi.org/10.1103/PhysRevLett.112.143001>
- Glassy optimal-control phase: <https://arxiv.org/abs/1803.10856>
