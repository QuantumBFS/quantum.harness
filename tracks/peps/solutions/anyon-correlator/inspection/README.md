# inspection/ — M2 stage-wise inspection and mechanism probes

One-off investigative scripts from the M2 simple-update inspection (2026-07-28).
They are **not** part of the main challenge pipeline; they document *why* simple
update fails from random initialization and which routes do reach the toric-code
ground state. Findings summary:
[`../M2_SU_FINDINGS.md`](../M2_SU_FINDINGS.md).

Main files: `../scripts/ed_checks.jl` (M1), `../scripts/tc_peps.jl` (shared
machinery), `../scripts/ad_tied_gd.jl` (completed M2 driver),
`../scripts/groundstate_h0.jl` (legacy SU route), and `../tests/runtests.jl`
(unit tests).

| Script | Purpose | Key result |
|---|---|---|
| `su_ungraded_test.jl` | Stage-wise ungraded check: random V/P init → contract → full-circuit SU → ground-state checks | E_cell = −6.026, ⟨A⟩ = 1, ⟨B⟩ ≈ 0.5 — SU stall reproduced |
| `gate_isolation.jl` | Sector-isolated gate tests: plaquette-only from \|+⟩^N, star-only from \|0⟩^N; single-sweep value vs tanh(2dt) | both converge to E_cell = −8, stabilizers = 1; single gate matches tanh(2dt) exactly |
| `plaq_continue.jl` | Mechanism probe: continue the stalled state with plaquette gates only | climbs to E_cell = −8.0000000000 in ~75 sweeps — competition picture confirmed |
| `d_sweep.jl` | Full-circuit SU from random init at D = 3, 4, 6 (V/P and direct inits) | stall level rises with D (−0.83/−0.94/−0.99 per edge spin); D=6 interrupted |
| `seed_probe.jl` | Z₂-graded random-init SU across 6 seeds | all land on polarized product states (E/N = −0.5) |
| `norm_probe.jl` | Normalization check: what `expectation_value` returns for the (2,2) cell | unit-cell total −8; per composite site −2; per edge spin −1 |
| `ad_gradient_diagnosis.jl` | AD failure diagnosis: env quality, gradient-solve convergence (maxiter 10 vs 100), FD directional derivative | gradient solve fully converged; AD gradient FD-exact |
| `ad_full_vs_fixedpoint.jl` | Pinning test: full-AD gradient vs fixed-point-differentiation gradient at the same point | both FD-exact (ratio 1.000); agree to 1e-3 |
| `retract_path_probe.jl` | Linesearch-failure probe: energy along the norm-preserving retract path at the stuck point | smooth monotone descent (−0.267 → −0.896 at α=1) — L-BFGS direction pollution isolated |
| `slow_plaquette_diagnosis.jl` | Defective-plaquette diagnosis at the GD endpoint: exact-state operator verification, per-plaquette deficit, directional derivatives, lift cost | plaquette (2,1) frozen at ~0 (deficit 1.000005); defect mode orthogonal to energy gradient (cos = −0.0024); stiff pinned mode |

Removed (superseded/dead): `escape_test.jl` (aborted AD escape attempt), `patch_check.jl`
(diagnostic for the superseded Z-basis tensor), and the first (wrong-index) version of
`slow_plaquette_diagnosis.jl`.

All scripts run with `julia --project=julia-env <script>` from the repo root and
are ungraded (dense tensors) unless stated.
