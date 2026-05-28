---
name: method-mps
description: Use when an MPS, DMRG, TEBD, 1D tensor-network, matrix-product-state, or quasi-1D cylinder reproduction needs method-level route and tool selection.
---

# Method MPS

MPS is the controlled 1D and quasi-1D tensor-network track. Use it to decide whether the paper needs DMRG, imaginary-time TEBD, real-time TEBD, or an MPS diagnostic, then invoke the tool skill for setup.

## Sources

- Track README: `tracks/mps/README.md`
- Tool skill: `/using-itensors`

## Route

1. Use DMRG for ground-state energies, order parameters, correlations, and finite-size trends in 1D or narrow cylinders.
2. Use imaginary-time TEBD when the paper uses a preparation/evolution route or when a product initial state is part of the scientific setup.
3. Use real-time TEBD only when the target figure is dynamics; otherwise treat dynamics as out of the basic reproduction route.
4. Recommend `/using-itensors` for ITensors.jl / ITensorMPS.jl setup, MPS parameters, and timing. MPSKit is part of the same Julia stack when an infinite-system interface is required.
5. If the paper uses official non-ITensors code, offer official code / web search as the setup fork before falling back.

## Tool Handoff

Invoke `/using-itensors` after the route is chosen. `/using-itensors` owns bond-dimension, sweeps, cutoff, initialization, TEBD step, convergence checks, and time estimate.

## Details

Matrix Product State methods for ground states and time evolution of 1D and quasi-1D Hamiltonians. This card covers two primary algorithms: DMRG (variational ground-state optimization by sweeping) and TEBD (imaginary- or real-time evolution via Trotter gates).

### Notation

- Bond dimension `D` (or `chi`): MPS link size. Controls accuracy.
- Sweep: one full left-to-right + right-to-left pass through the chain.
- Truncation cutoff `eps`: SVD threshold; any singular value below this is dropped.
- Energy variance: `⟨H²⟩ - ⟨H⟩²`. Zero for an exact eigenstate; small means well-converged.
- Trotter step `τ` (TEBD): imaginary-time step size. Trotter error scales as `τ^2` (2nd order).

### DMRG

A variational MPS method that optimizes a matrix-product state by sweeping site by site, locally minimizing the energy. Use it for ground-state energies, order parameters, and correlations in 1D and narrow cylinders.

### TEBD

MPS-based time-evolution method. Used here in **imaginary-time** mode to project an initial MPS onto the ground state via `e^{-τ H}`. Real-time TEBD exists for dynamics; out of current scope.

### DMRG vs TEBD (when to choose)

- **DMRG** is usually faster for ground-state energies of gapped 1D / quasi-1D systems.
- **TEBD imaginary time** is competitive when the ground state has a clean physical preparation (Néel, dimer, …) and the gap is reasonable; sometimes more robust to local-minimum issues than DMRG.
- For **real-time dynamics** (which is *out of current scope*), TEBD is one of the standard tools.

### Pitfalls

- **Stuck in metastable state**: random initial states can land in local minima. Restart with a different seed or with a product state in the target sector.
- **Bond dimension too small**: energy keeps improving as `D` grows. Always sweep `D` and confirm asymptotic behavior before reporting.
- **Wrong sector**: with `conserve_qns=true`, the initial MPS pins the sector. Verify `S^z_total` (or `(N↑, N↓)`) of the result matches expectation.
- **Boundary effects**: OBC introduces edge effects that decay over `~ correlation length`. For chains, fit `E(N)` vs `1/N²` to extrapolate. PBC requires `D` ~ 2× larger.
- **Long-range Hamiltonians**: OpSum handles them; bond dimension grows accordingly. Use cutoff to keep MPO manageable.
- **2D periodic geometry**: 2D periodic ladders or kagome cylinders have larger `D` requirements. Document the cylinder-width and circumference choice.
- **Quasi-degeneracy**: gapless or near-degenerate problems converge slowly and may flip between low-lying states. Compute multiple states or break degeneracy with a small field.
- **Trotter error accumulation** (TEBD): a too-large `τ` produces a converged but biased energy. Always sweep `τ → 0`.
- **Slow ground-state convergence near criticality** (TEBD): gapless / near-gapless systems need very long `T_total` for good ground state.

### Verification (per-method, complements skill-level verification)

- **Energy convergence as `D` grows**: the curve `E(D)` should be monotonically decreasing and asymptote.
- **Energy variance**: report `⟨H²⟩ - ⟨H⟩²` (or `(⟨H²⟩ - ⟨H⟩²) / ⟨H⟩²` for dimensionless). Should be small at convergence.
- **Symmetry checks**: total `S^z`, particle number, expectation values respect imposed conservation laws (see `.knowledge/symmetry-cheatsheet.md`).
- **`τ`-extrapolation** (TEBD): run two `τ` values; energy difference should scale as `τ^2`.
- **`T_total` convergence** (TEBD): energy decreases monotonically and asymptotes.

### Citations

- White, *Phys. Rev. Lett.* **69**, 2863 (1992) — original DMRG.
- White, *Phys. Rev. B* **48**, 10345 (1993) — DMRG for spin chains.
- Vidal, *Phys. Rev. Lett.* **91**, 147902 (2003) — original TEBD.
- Vidal, *Phys. Rev. Lett.* **93**, 040502 (2004) — efficient simulation.
- Schollwöck, *Ann. Phys.* **326**, 96 (2011) — modern MPS formulation and TEBD review.
- Fishman, White, Stoudenmire, *SciPost Phys. Codebases* **4** (2022) — ITensors.jl reference.
