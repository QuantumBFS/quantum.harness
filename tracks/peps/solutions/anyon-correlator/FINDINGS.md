# FINDINGS.md — simple-update behavior for the toric-code iPEPS at h = 0

> **Scope.** Working notes from the M2 inspection stage (2026-07-28): which parts of
> the pipeline are validated, where simple update (SU) fails from random
> initialization, why, and which routes do reach the ground state.
> **This is not the challenge report.** Challenge: issue #50 (anyon correlators from
> PEPS) · solution dir: `tracks/peps/solutions/anyon-correlator/`.

## 1. Setup under test

- **Hamiltonian** (PLAN C1/C2): H = −Jₑ Σₛ Aₛ − Jₘ Σₚ B_p − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ,
  Jₑ = Jₘ = 1, h = 0 here. Aₛ = ∏_{i∈s} Xᵢ (stars), B_p = ∏_{i∈p} Zᵢ (plaquettes).
- **iPEPS**: composite site = one vertex + its east/north edge spins (2 physical
  spins, fused dim-4 leg); (2,2) supercell = 4 sites = 8 edge spins, thermodynamic
  limit. `scripts/tc_peps.jl`.
- **SU gates**: star and plaquette terms are 3-site L-shaped terms on the composite
  lattice; exact Pauli exponentials cosh(dt·J) + P·sinh(dt·J) (P² = I), converted to
  3-site MPOs (`PEPSKit.gate_to_mpo`), applied with `PEPSKit.su_iter` + `SUWeight`
  bond weights. dt = 0.05, weight-convergence tol 1e-10.
- **Checks**: CTMRG (`leading_boundary`, χ = 16–40); `expectation_value` returns the
  unit-cell total (verified). Normalization: E_cell = −8, per composite site = −2,
  per edge spin = −1 at the exact ground state.

## 2. Validated components (all independent of SU's convergence issue)

| Check | Result |
|---|---|
| M1 — 2×2 ED Hamiltonian (dense, no PEPS) | 7/7 gates pass: E₀ = −8, degen 4, gap 4, all ground states ⟨Aₛ⟩ = ⟨B_p⟩ = 1 to 1e-15 |
| Exact tensor (V/P: vertex parity simplex + X-basis edge copy) → CTMRG | E_cell = −8.000000000000, max \|⟨stabilizer⟩ − 1\| = 2.2e-16 (graded χ=20), 1.8e-15 (ungraded χ=20) |
| Normalization | raw `expectation_value` = sum of 8 single-term evaluations = −8 exactly (unit-cell total) |
| Single plaquette gate, 1 sweep from \|+⟩^N | ⟨B⟩ = 0.0997 = tanh(2·0.05) **exactly** (analytic) |
| Plaquette-only SU from \|+⟩^N (A=1 sector) | converges to E_cell = −8.0000000000, all stabilizers = 1.000000 |
| Star-only SU from \|0⟩^N (B=1 sector) | same, E_cell = −8.0000000000 |
| Full circuit applied to the exact state | state preserved exactly (E_cell = −8, stabilizers = 1) |

Conclusion from §2: Hamiltonian, tensor spaces, gates, MPO conversion, cluster
machinery, truncation, and environment contraction are all correct.

## 3. Random-init full-circuit SU — failed results

Full circuit (star + plaquette gates every sweep), random init, ungraded dense
tensors unless marked "Z₂". Two init families: V/P (random vertex + edge-projection
tensors, contracted per vertex) and direct (random merged rank-6 tensors).

| Run | D | E_cell | per edge spin | stabilizer pattern | status |
|---|---|---|---|---|---|
| Z₂-graded, 6 seeds | 2 | −4.00 | −0.500 | product states: ⟨A⟩=1,⟨B⟩=0 or ⟨A⟩=0,⟨B⟩=1 exactly | weights converged |
| ungraded V/P, seed 1 | 2 | −6.0264 | −0.7533 | ⟨A⟩ = 1 exact; ⟨B⟩ = 0.469, 0.469, 0.544, 0.544 | weights converged |
| ungraded V/P | 3 | −6.6574 | −0.8322 | ⟨B⟩ = 1 exact; ⟨A⟩ ≈ 0.66 | 400 it, still creeping |
| ungraded direct | 3 | −6.6573 | −0.8322 | ⟨A⟩ = 1 exact; ⟨B⟩ ≈ 0.66 | 400 it, still creeping |
| ungraded V/P | 4 | −7.5400 | −0.9425 | ⟨A⟩ = 1 exact; ⟨B⟩ ≈ 0.885 | 400 it, still creeping |
| ungraded direct | 4 | −7.1186 | −0.8898 | mixed sectors | 400 it, not converged |
| ungraded V/P | 6 | −7.90 (iter 400) | −0.988 | still improving (ϵ ≈ 2e-3) | **interrupted** (runtime) |

AD polish from the D=2 stalled point (PEPSKit `fixedpoint`, L-BFGS, boundary tol
1e-10): "converged" after 1 iteration, ‖∇‖ 1.8e-5 → 4.4e-8, energy unchanged —
spurious stationarity (near-singular fixed-point Jacobian at the rank-deficient
SU fixed point).

**None of the random-init runs reached the toric-code ground state (E_cell = −8,
all stabilizers = 1).**

## 4. Mechanism probes

| Probe | Outcome |
|---|---|
| Stalled D=2 state (⟨A⟩=1, ⟨B⟩≈0.5), continue **plaquette gates only** | ⟨B⟩ climbs monotonically; E_cell = −8.0000000000 in ~75 sweeps, all stabilizers = 1.000000 |
| Product-state init (\|+⟩^N or \|0⟩^N), sector gates | converges to E_cell = −8 to 10 decimals |

## 5. Reasons for the simple-update failure

1. **Mean-field truncation metric.** SU truncates each updated bond back to D using
   only the diagonal bond weights as the environment. This systematically discards
   the small singular values that carry plaquette-flux / loop-constraint growth —
   the correlations that distinguish the toric-code ground state (equal-weight loop
   condensate) from one-sector-pinned states.
2. **Asymmetric gate competition.** Star gates pin ⟨Aₛ⟩ = 1 first (locally easy).
   Thereafter each star gate acts as a scalar physically, but its apply→truncate
   cycle still re-projects the tensors and clips plaquette-flux components 4 times
   per sweep. Plaquette growth and star truncation balance at a frozen fixed point
   (weights converge, |Δλ| → 1e-10, energy stuck). The SU convergence criterion is
   bond-weight stability, **not** energy — a fixed point of the gate→truncate map
   is not an energy minimum. More sweeps cannot help: the map is already stationary
   (observed: E_cell moved 0.001 over 150 sweeps).
3. **The map depends on the gate set, not only on H.** Full circuit and
   plaquette-only circuit are different maps with different fixed points:
   ⟨B⟩ ≈ 0.5 vs the exact TC — this is why the stage-wise continuation works.
4. **Larger D mitigates but does not cure** (at feasible step counts): stall level
   rises with D (−0.75 → −0.83 → −0.94 → −0.99 per edge spin at D = 2, 3, 4, 6),
   because less flux information is truncated away. The D=6 trajectory suggests slow
   convergence toward −8, but at rapidly increasing cost — the wrong route when a
   good initial state is available.
5. **AD inherits the trap** when warm-started at the SU fixed point (§3), because
   the transfer matrix there is rank-deficient and the environment-based gradient
   degenerates.

## 6. Routes that do reach the ground state (validated)

- **Stage-wise SU (keeps random init):** full circuit to weight convergence
  (pins the A sector) → plaquette-only circuit to convergence → E_cell = −8,
  stabilizers = 1 (h = 0 only; at h > 0 the stage split becomes a Trotter
  approximation since fields don't commute with both stabilizer types).
- **Product-state init:** start from \|+⟩^N (exact hₓ → ∞ ground state) → plaquette
  gates (or full circuit) → E_cell = −8 to 10 decimals. Equivalent to starting the
  adiabatic field path at the trivial end.

## 7. Artifacts

- Code: `scripts/tc_peps.jl`, `scripts/groundstate_h0.jl`, `scripts/su_ungraded_test.jl` →
  moved to `inspection/`, `tests/runtests.jl` (M1 7/7 + M2 T1–T7 algebra/normalization tests).
- Inspection probes: `inspection/` (8 scripts + README cataloging purpose and result).
- Results dir (graded pipeline run): `tracks/peps/results/20260728-170126-groundstate-h0/`
  (A1/A2 failed, A3/S0 passed).
