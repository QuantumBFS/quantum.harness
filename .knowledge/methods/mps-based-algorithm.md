# MPS Based Algorithm

Matrix Product State methods for ground states and time evolution of 1D and quasi-1D Hamiltonians. This card covers two primary algorithms: DMRG (variational ground-state optimization by sweeping) and TEBD (imaginary- or real-time evolution via Trotter gates).

## Setup

Canonical stack: `itensors` (`skills/using-itensors/stack.toml`).

```
make install julia        # Install Julia via juliaup if missing
make install itensors     # Install ITensors.jl + ITensorMPS.jl + KrylovKit.jl into julia-env/
```

Activate the environment with `julia --project=julia-env`.

MPSKit.jl (also installed) has a more polished iTEBD/iDMRG interface for infinite systems.

## Notation

- Bond dimension `D` (or `chi`): MPS link size. Controls accuracy.
- Sweep: one full left-to-right + right-to-left pass through the chain.
- Truncation cutoff `eps`: SVD threshold; any singular value below this is dropped.
- Energy variance: `⟨H²⟩ - ⟨H⟩²`. Zero for an exact eigenstate; small means well-converged.
- Trotter step `τ` (TEBD): imaginary-time step size. Trotter error scales as `τ^2` (2nd order).

## DMRG

A variational MPS method that optimizes a matrix-product state by sweeping site by site, locally minimizing the energy.

### Code shape (Julia / ITensors.jl)

```julia
using ITensors, ITensorMPS

# 1. Build site indices
sites = siteinds("S=1/2", N; conserve_qns=true)   # use conserve_qns to pin S^z sector

# 2. Build the Hamiltonian as an MPO via OpSum
ampo = OpSum()
for j in 1:N-1
    ampo += "Sz", j, "Sz", j+1
    ampo += 0.5, "S+", j, "S-", j+1
    ampo += 0.5, "S-", j, "S+", j+1
end
H = MPO(ampo, sites)

# 3. Initial state — pick a state in the target sector
psi0 = MPS(sites, n -> isodd(n) ? "Up" : "Dn")     # Néel-like, S^z_total = 0 for even N

# 4. Sweep schedule (grow bond dimension)
nsweeps = 20
maxdim = [10, 20, 50, 100, 200, 200]
cutoff = [1e-10]

# 5. Run
energy, psi = dmrg(H, psi0; nsweeps, maxdim, cutoff, outputlevel=1)

# 6. Observables
sz = expect(psi, "Sz")
SiSj = correlation_matrix(psi, "Sz", "Sz")
```

For Hubbard / fermion problems, use `siteinds("Electron", N; conserve_qns=true)` and operators `"Cdagup"`, `"Cup"`, `"Cdagdn"`, `"Cdn"`, `"Nup"`, `"Ndn"`.

### DMRG knobs

| Knob | Effect | Starting point |
|---|---|---|
| `maxdim` schedule | Maximum bond dimension per sweep. Drives accuracy and cost. | Grow gently from ~10. Targets: 50–200 (1D chains), 200–1000 (cylinders), 1000+ (frustrated 2D). |
| `cutoff` | SVD truncation threshold. | `1e-10` for entry/medium accuracy; tighten for critical points or if variance is non-zero at convergence. |
| `nsweeps` | Number of sweeps. | 10–30; stop when the energy stops changing within accuracy goal. |
| Initial state | Random MPS or a product state in the target sector. | Product state for sectors (e.g., Néel for `S^z = 0`). Random for sectors without a clear product-state representative. |
| `noise` | Adds noise to break stuck states (older API). | Use only if convergence stalls. |

## TEBD

MPS-based time-evolution method. Used here in **imaginary-time** mode to project an initial MPS onto the ground state via `e^{-τ H}`. Real-time TEBD exists for dynamics; out of current scope.

### Code shape (Julia / ITensors)

```julia
using ITensors, ITensorMPS

# 1. Sites + Hamiltonian (as ops or MPO)
sites = siteinds("S=1/2", N; conserve_qns=true)

# 2. Build Trotter gates (2nd-order Trotter shown)
function trotter_gates(sites, J, τ)
    gates = ITensor[]
    for j in 1:N-1
        s1, s2 = sites[j], sites[j+1]
        hj = J * (op("Sz", s1) * op("Sz", s2)
                + 0.5 * op("S+", s1) * op("S-", s2)
                + 0.5 * op("S-", s1) * op("S+", s2))
        push!(gates, exp(-τ/2 * hj))
    end
    append!(gates, reverse(gates))   # 2nd-order: half step forward, half backward
    return gates
end

# 3. Initial state
psi = MPS(sites, n -> isodd(n) ? "Up" : "Dn")

# 4. Imaginary-time sweep
gates = trotter_gates(sites, J, τ)
T_total = 20.0
n_steps = round(Int, T_total / τ)
for step in 1:n_steps
    psi = apply(gates, psi; cutoff=1e-10, maxdim=200)
    normalize!(psi)
end

# 5. Energy
energy = inner(psi', H, psi)
```

### TEBD knobs

| Knob | Effect | Starting point |
|---|---|---|
| `τ` (Trotter step) | Trotter error scales as `τ^2` (2nd order). Smaller is more accurate but slower. | `0.05–0.1` for entry; reduce if energy not converged. |
| `T_total` | Imaginary-time evolution length. Need `T_total ≫ 1/Δ`. | Start at 10–20 (units where largest coupling = 1); extend until energy stops dropping. |
| `maxdim` | MPS bond dimension cap. | 50–200 for 1D entry-level. |
| `cutoff` | SVD truncation per gate application. | `1e-10`. |

## DMRG vs TEBD (when to choose)

- **DMRG** is usually faster for ground-state energies of gapped 1D / quasi-1D systems.
- **TEBD imaginary time** is competitive when the ground state has a clean physical preparation (Néel, dimer, …) and the gap is reasonable; sometimes more robust to local-minimum issues than DMRG.
- For **real-time dynamics** (which is *out of current scope*), TEBD is one of the standard tools.

## Pitfalls

- **Stuck in metastable state**: random initial states can land in local minima. Restart with a different seed or with a product state in the target sector.
- **Bond dimension too small**: energy keeps improving as `D` grows. Always sweep `D` and confirm asymptotic behavior before reporting.
- **Wrong sector**: with `conserve_qns=true`, the initial MPS pins the sector. Verify `S^z_total` (or `(N↑, N↓)`) of the result matches expectation.
- **Boundary effects**: OBC introduces edge effects that decay over `~ correlation length`. For chains, fit `E(N)` vs `1/N²` to extrapolate. PBC requires `D` ~ 2× larger.
- **Long-range Hamiltonians**: OpSum handles them; bond dimension grows accordingly. Use cutoff to keep MPO manageable.
- **2D periodic geometry**: 2D periodic ladders or kagome cylinders have larger `D` requirements. Document the cylinder-width and circumference choice.
- **Quasi-degeneracy**: gapless or near-degenerate problems converge slowly and may flip between low-lying states. Compute multiple states or break degeneracy with a small field.
- **Trotter error accumulation** (TEBD): a too-large `τ` produces a converged but biased energy. Always sweep `τ → 0`.
- **Slow ground-state convergence near criticality** (TEBD): gapless / near-gapless systems need very long `T_total` for good ground state.

## Verification (per-method, complements skill-level verification)

- **Energy convergence as `D` grows**: the curve `E(D)` should be monotonically decreasing and asymptote.
- **Energy variance**: report `⟨H²⟩ - ⟨H⟩²` (or `(⟨H²⟩ - ⟨H⟩²) / ⟨H⟩²` for dimensionless). Should be small at convergence.
- **Symmetry checks**: total `S^z`, particle number, expectation values respect imposed conservation laws (see `.knowledge/symmetry-cheatsheet.md`).
- **`τ`-extrapolation** (TEBD): run two `τ` values; energy difference should scale as `τ^2`.
- **`T_total` convergence** (TEBD): energy decreases monotonically and asymptotes.

## Citations

- White, *Phys. Rev. Lett.* **69**, 2863 (1992) — original DMRG.
- White, *Phys. Rev. B* **48**, 10345 (1993) — DMRG for spin chains.
- Vidal, *Phys. Rev. Lett.* **91**, 147902 (2003) — original TEBD.
- Vidal, *Phys. Rev. Lett.* **93**, 040502 (2004) — efficient simulation.
- Schollwöck, *Ann. Phys.* **326**, 96 (2011) — modern MPS formulation and TEBD review.
- Fishman, White, Stoudenmire, *SciPost Phys. Codebases* **4** (2022) — ITensors.jl reference.
