# DMRG (Density Matrix Renormalization Group)

A variational MPS method for ground states of 1D and quasi-1D Hamiltonians. Optimizes a matrix-product state by sweeping site by site, locally minimizing the energy.

## Setup

```
make install julia        # Install Julia via juliaup if missing
make install itensors     # Install ITensors.jl + ITensorMPS.jl + KrylovKit.jl into julia-env/
```

Activate the environment with `julia --project=julia-env`.

## Notation

- Bond dimension `D` (or `chi`): MPS link size. Controls accuracy.
- Sweep: one full left-to-right + right-to-left pass through the chain.
- Truncation cutoff `eps`: SVD threshold; any singular value below this is dropped.
- Energy variance: `⟨H²⟩ - ⟨H⟩²`. Zero for an exact eigenstate; small means well-converged.

## Code shape (Julia / ITensors.jl)

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

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `maxdim` schedule | Maximum bond dimension per sweep. Drives accuracy and cost. | Grow gently from ~10. Targets: 50–200 (1D chains), 200–1000 (cylinders), 1000+ (frustrated 2D). |
| `cutoff` | SVD truncation threshold. | `1e-10` for entry/medium accuracy; tighten for critical points or if variance is non-zero at convergence. |
| `nsweeps` | Number of sweeps. | 10–30; stop when the energy stops changing within accuracy goal. |
| Initial state | Random MPS or a product state in the target sector. | Product state for sectors (e.g., Néel for `S^z = 0`). Random for sectors without a clear product-state representative. |
| `noise` | Adds noise to break stuck states (older API). | Use only if convergence stalls. |

## Pitfalls

- **Stuck in metastable state**: random initial states can land in local minima. Restart with a different seed or with a product state in the target sector.
- **Bond dimension too small**: energy keeps improving as `D` grows. Always sweep `D` and confirm asymptotic behavior before reporting.
- **Wrong sector**: with `conserve_qns=true`, the initial MPS pins the sector. Verify `S^z_total` (or `(N↑, N↓)`) of the result matches expectation.
- **Boundary effects**: OBC introduces edge effects that decay over `~ correlation length`. For chains, fit `E(N)` vs `1/N²` to extrapolate. PBC requires `D` ~ 2× larger.
- **Long-range Hamiltonians**: OpSum handles them; bond dimension grows accordingly. Use cutoff to keep MPO manageable.
- **2D periodic geometry**: 2D periodic ladders or kagome cylinders have larger `D` requirements. Document the cylinder-width and circumference choice.
- **Quasi-degeneracy**: gapless or near-degenerate problems converge slowly and may flip between low-lying states. Compute multiple states or break degeneracy with a small field.

## Verification (per-method, complements skill-level verification)

- **Energy convergence as `D` grows**: the curve `E(D)` should be monotonically decreasing and asymptote.
- **Energy variance**: report `⟨H²⟩ - ⟨H⟩²` (or `(⟨H²⟩ - ⟨H⟩²) / ⟨H⟩²` for dimensionless). Should be small at convergence.
- **Symmetry checks**: total `S^z`, particle number, expectation values respect imposed conservation laws (see `knowledge-base/symmetry-cheatsheet.md`).

## Citations

- White, *Phys. Rev. Lett.* **69**, 2863 (1992) — original DMRG.
- White, *Phys. Rev. B* **48**, 10345 (1993) — DMRG for spin chains.
- Schollwöck, *Ann. Phys.* **326**, 96 (2011) — modern MPS formulation.
- Fishman, White, Stoudenmire, *SciPost Phys. Codebases* **4** (2022) — ITensors.jl reference.
