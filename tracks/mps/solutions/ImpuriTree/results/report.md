# ImpuriTree: purified tensor-network Anderson solver at beta = 16

- Challenge: [QuantumBFS/quantum.harness#81](https://github.com/QuantumBFS/quantum.harness/issues/81)
  — "How cold can a purified tensor-network Anderson impurity solver go?"
- Team registration: [PR #157](https://github.com/QuantumBFS/quantum.harness/pull/157)
  (ImpuriTree: Weiyi Guo, Linjie Chen, Wenfeng Wu, Xiaoteng Huang)
- Date: 2026-07-30
- Code: `Graft.jl` / `GraftImpurity.jl` / `GreenFunc.jl` (revisions recorded per
  run below); TDVP comparison artifacts in `tdvp_beta16/`, implicit
  log-step reproduction scripts in `implicit_logstep/`, partial `beta = 4`
  demonstration in `beta4_partial/`.

## Headline result: the beta = 16 continuous-bath milestone is met

A deterministically purified tensor-network solver reproduces the
continuous-bath CT-QMC imaginary-time Green function at `beta = 16` for two
interaction strengths, both at half filling (`n = 1`):

| parameter set | `-G(0+)` | RMS(ΔG) | rel-L2 | max abs. dev. | CT-QMC SE (median) |
|---|---|---|---|---|---|
| `U = 2`, `eps_d = -1` | 0.5003 | `4.27e-3` | 2.82% | `5.8e-3` | `6.8e-4` |
| `U = 8`, `eps_d = -4` | 0.4978 | `2.34e-3` | 2.95% | `4.8e-3` | `7.9e-4` |

The reference is TRIQS/CTSEG 4.0.0 on the exact continuous semicircular bath
(8 independent replicas, 200,000 production cycles each). The tensor-network
result uses a 9-pole ESPRIT-tau finite bath per spin and two-site TDVP
(`chi = 96`, `dt = 0.5`, 65 tau points at 0.25 spacing; Graft revision
`49d97da`). Residuals are a few `1e-3` in absolute units — a factor of a few
above the CT-QMC statistical band — and are dominated by the 9-pole bath
discretization, not by the state propagation (Section "Error budget").
`tdvp_beta16/comparison_overview.png` shows both overlays and pointwise deviations,
including the particle-hole-symmetrized CT-QMC comparison.

This satisfies the challenge's continuous-bath acceptance item
("one beta = 16 or 32 calculation cross-checked against CT-HYB") for two
parameter sets rather than one.

## Model and thermal-state convention

Spinful single-impurity Anderson model at particle-hole symmetry:
semicircular hybridization of half-bandwidth `D = 2`, `mu = 0`, and the two
parameter sets `U = 2, eps_d = -U/2 = -1` and `U = 8, eps_d = -U/2 = -4`.
The thermal state is the deterministic purification of the complete
interacting finite Hamiltonian,
`|Psi_beta> = (e^{-beta K / 2} ⊗ I_a) |I>`, with impurity, bath modes, and
thermal ancillas in one purified state; `G(tau)` is measured by operator
insertion on purification branches. `-G(0+) = 0.5` in both parameter sets
confirms `n = 1` without symmetry enforcement in the solver.

## Bath representation: ESPRIT-tau (with PES as the surveyed alternative)

The continuous hybridization is compressed to a finite pole bath by ESPRIT on
a uniform tau-domain sample of `Delta(tau)`:

- `beta = 16`: 257 tau samples, 9 poles per spin, relative L2 fit error
  `2.4e-8`.
- `beta = 4` (control, see below): the block-Hankel numerical rank drops to 8
  — ESPRIT's rank gate refuses a 9-pole request outright — and a 7-pole fit
  on 513 tau samples reaches relative L2 `9.0e-12`.

Two properties motivated choosing ESPRIT-tau over PES/ADAPOL (Matsubara-node
interpolation with an SDP-positive pole measure) for production:

1. **Fail-closed order selection.** ESPRIT is gated by the Hankel numerical
   rank: requesting more poles than the data supports fails immediately
   instead of fitting noise. In our semicircular benchmark PES interpolates
   its training nodes essentially to machine precision while its pole measure
   is less stable between grids; ESPRIT's hard rank gate is the more
   conservative order-selection mechanism.
2. **Native domain.** The tau-domain fit is performed in the same domain as
   the target observable `G(tau)`, so the bath-discretization error enters
   the error budget directly and measurably.

The bath-fit error is reported here as the plain training-domain relative L2
against the analytic hybridization; no cross-grid generalization ("overfit")
metric is included, since our calibrated-replica study showed that metric's
value is dominated by the choice of validation geometry rather than by
predictive failure.

## Method A (reference): uniform-step two-site TDVP

Per the challenge specification, uniform-step TDVP2 is the reference
propagator: `dt = 0.5`, two-site updates with SVD truncation
(`atol = 1e-8`, `chi = 96`, saturated), propagating the purification to
`beta/2 = 8` with enforced particle-hole symmetry and measuring `G(tau)` on
65 tau points (0.25 spacing). Wall clock: 82 minutes per parameter set on
16 threads; peak RSS 7.3 GiB. This is the method behind
the headline table and `tdvp_beta16/comparison_overview.png`. Runner:
`tdvp_beta16/graft_solve_tdvp_beta16.jl METHOD=tdvp2`.

## Method B (research target): implicit A-stable logarithmic-grid evolution

The same purification is propagated by the implicit trapezoid ("implicit
log-time") scheme: on each panel of a logarithmic grid
(`logarithmic_time_grid(tau_first, beta/2)`, `tau_first = 0.01–0.05`), solve

```
(I + (h/2) K) psi_{n+1} = (I - (h/2) K) psi_n
```

with a GMRES-preconditioned variational linear solve. A-stability removes the
step-size stability constraint, so the grid can grow geometrically — the
prerequisite for the `beta = 100` stretch target. The production controls,
all active in the runs below:

- **Strict global-Krylov bootstrap** (`k = 2` exact actions) opens the bond
  manifold on the first panel (`bond 2 -> 21` at `beta = 16`,
  `2 -> 17` at `beta = 4`) before any implicit step.
- **Exact physical-residual authority**: every implicit step reports the
  uncompressed residual `|| rhs - (a0 + a1 K) psi ||` and must reach
  `1e-6`.
- **Certified RHS truncation**: the trapezoid right-hand side may be
  SVD-truncated with a rigorously accumulated discarded-norm bound
  `eps_rhs` that is charged against the solve tolerance
  (`tol_eff = tol - eps_rhs`), so a converged step still certifies the
  original bound. In production `eps_rhs ≈ 3e-9` (a 0.4% tightening) and
  step residuals match the exact-RHS baseline to five digits.
- **Adaptive bond growth**: two production expansion policies are compared
  under identical grids and tolerances — the two-site linear solve with a
  singular-value cutoff (`rtol = 1e-12`) and residual-driven expansion (RDE),
  which expands only the bonds implicated by the unconverged full residual.

### Status of the implicit-log-grid runs

- **Paired first-step gate (beta = 16) passed.** After the strict bootstrap,
  RDE and the two-site reference were required to reach the same `1e-6`
  physical residual on the same post-bootstrap implicit step at matched
  budgets. Matched at caps 24 and 48 (RDE `8.1e-7` in 3 expansion rounds vs
  two-site `6.6e-7` at cap 24); this exonerates RDE's
  residual-to-subspace path at the first step.
- **`beta = 4` control: preparation complete; measurement partial.**
  21 implicit steps to `beta/2 = 2`, every step converged below `1e-6`
  (typically `1e-7`–`9e-7`), bond capped at 128, wall clock 90 minutes on
  32 cores. The `G(tau)` 8-way fan-out was still running when this report
  was written: **5 of 17 tau points were finished — the full implicit
  `G(tau)` sweep did not complete in time**. The five available points were
  compared against a quick locally generated TRIQS/CTSEG reference
  (8 × 100k cycles, particle-hole symmetrized) whose per-bin
  high-frequency statistical noise we accept as-is: the purpose of this
  comparison is a **working demonstration of the implicit log-step
  pipeline** — bootstrap, logarithmic-grid implicit steps, thermal
  checkpoints, operator insertion, and branch propagation all operating
  end-to-end with every step residual-certified at `1e-6` — not an error
  quantification. The points track the noisy reference at its own noise
  scale (`tau = 0.75` agrees to `4e-4`); quantitative error budgets are
  deferred to the full sweep against the high-statistics reference. See
  `beta4_partial/beta4_u2_gtau_partial_vs_ctseg.png`.
- **`beta = 16` production sweeps in flight; first bond-demand markers
  recorded.** The exact-RHS two-site baseline has passed `tau = 1.0` with
  every step below tolerance (`3.5e-7`–`9.3e-7` at bond 128, no warnings
  after five hours). The measurement mode (record a warning and continue
  instead of aborting when a step cannot reach `1e-6`) has produced its
  first quantitative cap-saturation points: with the bond cap at 128, the
  truncated-RHS two-site lane reaches an achievable residual of `2.3e-6`
  on the `tau = 1.0 -> 1.5` step (`dtau = 0.5`), and the RDE lane
  saturates earlier — `1.2e-6` already at `tau = 0.5` — consistent with
  its greedier rank allocation. These are the first entries of the
  full-trajectory achievable-residual / bond-demand curves that will set
  the cap budgets for the colder targets.

## Error budget (beta = 16, headline comparison)

| source | size | evidence |
|---|---|---|
| bath discretization (9 poles/spin) | few `1e-3` in `G(tau)` — dominant | ESPRIT fit `2.4e-8` in `Delta(tau)` but finite-vs-continuous bath is the leading systematic; deviation shape is smooth in tau and exceeds the CT-QMC band coherently |
| bond truncation | subdominant at `chi = 96` (TDVP2, saturated); `<= 1e-6` per step by construction (implicit) | implicit lanes enforce the uncompressed residual; TDVP2 truncation `atol = 1e-8` |
| time stepping | subdominant | TDVP2 `dt = 0.5` uniform; implicit trapezoid is A-stable, per-step residual certified |
| RHS truncation (implicit) | `~3e-9`, certified and charged to tolerance | `RHS_TRUNCATION` records per step |
| CT-QMC statistics | `~7e-4` (SE) | 8 replicas × 200k cycles, between-replica spread |

The immediate lever for the residual few-`1e-3` disagreement is the pole
count: `beta = 16` supports at least 9 ESPRIT poles (rank-gated), and the
finite-bath systematic shrinks rapidly with additional poles.

## Resources

- TDVP2 comparison: single-node runs, 16 Julia threads, 82 min per
  parameter set, peak RSS 7.3 GiB (Julia 1.12.6); TRIQS/CTSEG references
  8 × 200k cycles. `comparison_data.h5` is self-contained (G(tau),
  Matsubara `mps_iw`, and full provenance attributes); the complete
  reproducibility bundle (JLD2 archive, driver and PBS scripts, workflow
  doc, bath CSV SHA-256) is `tdvp_beta16/reproducibility_bundle.zip`.
- Implicit-log-grid campaign: Snellius (genoa), one shared node per lane;
  preparation 32 cores / 240 GB, measurement fan-out 8 × 16 cores. Julia
  parallel runtime with thread-level task fan-out (BLAS pinned to 1 thread).
  `beta = 4` preparation: 90 min; `beta = 16` exact-RHS baseline: ~30 min per
  implicit step at bond 128, roughly halved by certified RHS truncation.

## Reproducibility

- `tdvp_beta16/graft_solve_tdvp_beta16.jl METHOD CHI RESOLUTION PROFILE
  OUTPUT_DIR` runs either method (`tdvp2` | `implicit`) with
  environment-pinned bath, grid, and solver settings and records code
  revisions in its output.
- `tdvp_beta16/triqs_ctseg_u2_u8.py` regenerates the CT-QMC references;
  `tdvp_beta16/plot_beta16_u2_u8_tdvp_cthyb.py` rebuilds
  `comparison_overview.png` from `comparison_data.h5`
  (schema `mps_ctqmc_gtau_comparison_v1`).
- The implicit-log-grid campaign runs under immutable, content-locked run
  roots with source/config/environment hashes; the evidence trail is
  registered in the team's harness ledger
  (workstream `residual-driven-expansion`, report
  `2026-07-30-rde-beta16-matched-gate-and-warn-measurement`).
- `implicit_logstep/` contains the exact production scripts and the
  full environment contract for the implicit log-step runs, with the
  heavy-computing costs and the `beta = 4` ESPRIT 7-pole bath documented;
  note again that **no full implicit data set exists yet** — partial
  `beta = 4` measurement points and the local CTSEG comparison live in
  `beta4_partial/`.

## Outlook toward beta = 100

The remaining obstacles are economic rather than algorithmic: (i) the uniform
`G(tau)` checkpoint grid currently forces ~24 implicit steps at `beta = 16`
where a pure logarithmic grid needs ~9; replacing it with DLR measurement
nodes restores geometric stepping and would directly accelerate the
Green-function calculation. The sharpened requirement, if the half-scaled
DLR nodes are to embed as a subset of the implicit preparation grid
(`P_implicit ⊃ T/2`) without reusing values across the reflection
`G(tau) <-> G(beta - tau)`, is that the DLR node set must be self-dual,
`T = beta - T`. Checking the available Lehmann constructions: the plain
`:none` DLR grids do **not** satisfy self-duality; the pregenerated `:sym`
grids do; and the exact-`E_uv` reconstruction path does not guarantee it —
it would need paired node selection in place of the plain pivoted QR. The
practical route is therefore the self-dual `:sym`-style node set; (ii) RDE's rank allocation is greedier than the
two-site reference at equal residual and is under active measurement; and
(iii) bond demand grows along the trajectory, which the warn-mode sweeps are
quantifying to set caps for `beta = 32` and beyond.
