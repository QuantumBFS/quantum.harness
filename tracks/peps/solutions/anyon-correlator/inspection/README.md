# inspection/ — M2 stage-wise inspection and mechanism probes

One-off investigative scripts from the M2 simple-update inspection (2026-07-28).
They are **not** part of the main challenge pipeline; they document *why* simple
update fails from random initialization and which routes do reach the toric-code
ground state. Findings summary: [`../FINDINGS.md`](../FINDINGS.md).

Main pipeline files (unchanged roles): `../scripts/ed_checks.jl` (M1),
`../scripts/tc_peps.jl` (M2 machinery), `../scripts/groundstate_h0.jl` (M2 driver),
`../tests/runtests.jl` (fast unit tests).

| Script | Purpose | Key result |
|---|---|---|
| `su_ungraded_test.jl` | Stage-wise ungraded check: random V/P init → contract → full-circuit SU → ground-state checks | E_cell = −6.026, ⟨A⟩ = 1, ⟨B⟩ ≈ 0.5 — SU stall reproduced |
| `gate_isolation.jl` | Sector-isolated gate tests: plaquette-only from \|+⟩^N, star-only from \|0⟩^N; single-sweep value vs tanh(2dt) | both converge to E_cell = −8, stabilizers = 1; single gate matches tanh(2dt) exactly |
| `plaq_continue.jl` | Mechanism probe: continue the stalled state with plaquette gates only | climbs to E_cell = −8.0000000000 in ~75 sweeps — competition picture confirmed |
| `d_sweep.jl` | Full-circuit SU from random init at D = 3, 4, 6 (V/P and direct inits) | stall level rises with D (−0.83/−0.94/−0.99 per edge spin); D=6 interrupted |
| `seed_probe.jl` | Z₂-graded random-init SU across 6 seeds | all land on polarized product states (E/N = −0.5) |
| `norm_probe.jl` | Normalization check: what `expectation_value` returns for the (2,2) cell | unit-cell total −8; per composite site −2; per edge spin −1 |
| `patch_check.jl` | Finite open-patch dense contraction used to diagnose the cycle-gas vs cut-gas tensor error (superseded; kept for the record) | exposed the wrong (dual) exact tensor; motivated the X-basis copy fix |
| `escape_test.jl` | Aborted attempt: perturb the SU product state, then AD escape (inconclusive, superseded by gate_isolation/plaq_continue) | — |

All scripts run with `julia --project=julia-env <script>` from the repo root and
are ungraded (dense tensors) unless stated.
