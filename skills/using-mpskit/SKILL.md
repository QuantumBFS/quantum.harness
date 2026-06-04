---
name: using-mpskit
description: Use when choosing or running MPSKit.jl for infinite / uniform matrix product states — VUMPS, IDMRG / IDMRG2, finite DMRG, TDVP — including unit-cell construction, the tangent-space gradient-norm convergence probe (calc_galerkin), symmetry setup via TensorKit, or MPSKit setup failures. MPSKit has no TEBD; route iTEBD to /using-tenpy.
---

# MPSKit.jl

Use MPSKit as the harness's canonical Julia stack for **infinite / uniform MPS** ground states (VUMPS, IDMRG) and for finite DMRG / TDVP, paired with **MPSKitModels.jl** (ready Hamiltonians) and **TensorKit.jl** (symmetric tensors).

## Sources

- Method card: `skills/method-mps/SKILL.md`
- Stack: the shared `julia-env` (MPSKit, MPSKitModels, TensorKit already in `julia-env/Project.toml`); install/instantiate via `/setup-julia`.
- Smoke test: `julia --project=julia-env -e 'using MPSKit, MPSKitModels, TensorKit'`
- Primary literature: `1701.07035` (VUMPS) in `.knowledge/literature/mps-based-algorithm/`.

## Workflow

1. Confirm the model, geometry (infinite unit-cell length or finite chain), bond dimension, and symmetry before code.
2. Choose the algorithm with `/method-mps`: **VUMPS** for infinite ground states (default), **IDMRG/IDMRG2** when DMRG infrastructure is wanted, **DMRG/DMRG2** for finite chains, **TDVP** for time evolution. **There is no TEBD in MPSKit** — for iTEBD route to `/using-tenpy`.
3. Build H from MPSKitModels (or a custom MPO); build the initial `InfiniteMPS` at the chosen unit cell and D.
4. Run `find_groundstate`; converge on the **tangent-space gradient norm ‖B‖** (`calc_galerkin`), not the energy.
5. Record bond dimension, unit-cell length, tolerance, max iterations, symmetry, BLAS/Julia thread count, and the final ‖B‖ in the run plan.

## Parameter setup

Use this as the source for MPSKit-specific reproduction knobs unless the paper or official code fixes a value.

- **Bond dimension D** — set via the virtual `ComplexSpace(D)` (no symmetry) or a graded space per sector (symmetric). The accuracy lever; run a D-series until the energy stops moving. For gapless systems, scale D (finite-entanglement scaling).
- **Unit cell L** — the `length` of the `InfiniteMPS` (number of site tensors repeated). Must be ≥ the ground-state order period: 1-site for uniform/Haldane states, 2-site for Néel/AFM. A sublattice rotation can fold a 2-site ordered state to a 1-site cell (e.g. critical XXZ).
- **Symmetry** — chosen through the TensorKit element/space: `Trivial` (no symmetry, the VUMPS-paper benchmark choice) or an abelian/non-abelian sector (`U1Irrep`, `SU2Irrep`) for a smaller, sector-pinned tensor. Match the paper.
- **Tolerance / stop criterion** — `tol` in the algorithm (e.g. `VUMPS(; tol=1e-12)`); the run stops when ‖B‖ falls below it. Probe ‖B‖ explicitly with `calc_galerkin`.
- **Max iterations** — `maxiter`; the stop criterion should fire first. Hitting it = not converged.
- **Eigensolver** — VUMPS uses an adaptive Lanczos/Arnoldi tolerance internally; do not pin it to a single coarse step (that defeats the adaptive schedule and can stall IDMRG — see the iterator note below).
- **Initial state** — random `InfiniteMPS([...], [...])`, or seed from a product state in the target sector if convergence stalls.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| Bond dimension `ComplexSpace(D)` | dominant accuracy lever; cost ~D³ | D-series until energy asymptotes; scale D if gapless |
| Unit-cell length | must hold the order period | 1-site uniform, 2-site AFM (or rotate to 1-site) |
| `tol` / ‖B‖ target | convergence stringency | 1e-10…1e-12 for VUMPS/IDMRG |
| `maxiter` | work cap | hundreds; raise if ‖B‖ hasn't met `tol` |
| Symmetry sector (TensorKit) | block-diagonalizes → faster, pins sector | `Trivial` to match the VUMPS paper; U(1) Sz for speed |
| BLAS / Julia threads | wall time; benchmark fairness | `BLAS.set_num_threads(n)`, `JULIA_NUM_THREADS`; for a wall-time benchmark, **confirm the count with the user and warm up first** (see reproduce-paper) |

## Code shape

Check exact constructors against the installed MPSKit / MPSKitModels docs before a production script; the harness-level shape:

```julia
using MPSKit, MPSKitModels, TensorKit, LinearAlgebra

# 1. Hamiltonian (MPSKitModels). XXZ takes a symmetry positional arg; XYZ does NOT.
H = heisenberg_XXZ(ComplexF64, Trivial, InfiniteChain(2); spin=1//2, Delta=2.0)
# H = heisenberg_XYZ(ComplexF64, InfiniteChain(1); Jx=-1.0, Jy=-1.0, Jz=1.0, spin=1//2)

# 2. Uniform MPS at unit cell L and bond dimension D (no symmetry → ComplexSpace).
L, D = 2, 54
psi = InfiniteMPS([physicalspace(H, i) for i in 1:L], fill(ComplexSpace(D), L))

# 3. Ground state by VUMPS; ‖B‖ is the convergence diagnostic.
psi, envs = find_groundstate(psi, H, VUMPS(; tol=1e-12, maxiter=300, verbosity=1))
e_site = real(expectation_value(psi, H)) / length(psi)

# 4. Tangent-space gradient norm ‖B‖ (per-site RMS Galerkin gradient).
bnorm = sqrt(sum(abs2(MPSKit.calc_galerkin(pos, psi, H, psi, envs)) for pos in 1:length(psi)) / length(psi))
```

**Per-iteration trajectory (for a convergence / wall-time benchmark):**

```julia
# VUMPS exposes a finalize callback: (iter, ψ, H, envs) -> (ψ, envs). Log inside it.
fin = (iter, psi, H, envs) -> (push!(recs, (e=real(expectation_value(psi,H))/length(psi),
                                            B=MPSKit.calc_galerkin(psi,H,psi,envs))); (psi, envs))
find_groundstate(psi, H, VUMPS(; tol=1e-12, maxiter=300, finalize=fin))

# IDMRG has NO finalize — use the public IterativeSolver iterator (non-invasive, perf-neutral):
it = MPSKit.IterativeSolver(IDMRG(; tol=1e-12, maxiter=300), state)
for (mps, envs, ϵ, ΔE) in it
    # log e/site and calc_galerkin here; break on ϵ ≤ tol or iter cap
end
```

> Both hooks are public — no `Pkg.develop` needed for VUMPS/IDMRG trajectories. If a future probe needs internals MPSKit doesn't expose, `Pkg.develop("MPSKit")` and instrument the source non-invasively (reproduce-paper step 2).

## Time estimate

Cost is `(L_cell · d · D³ · n_iter) ÷ throughput`. The work count is firm; throughput (BLAS rate, threads) is the unknown — settle it with one timed iteration at the target D.

- Per iteration ∝ unit-cell length × physical dim d × D³ (local effective eigensolves).
- **VUMPS reaches a given ‖B‖ in fewer iterations than IDMRG** (and far fewer than iTEBD at criticality) — the FIG.7 result.
- Memory is modest (O(D²) tensors + environments); compute is the gate.
- D in the tens-to-low-hundreds (FIG.7: 54–120) is seconds-to-minutes on a laptop, single-thread. Larger D (cylinders, near-critical) scales as D³ → route to `/using-slurm`.
- **For a wall-time benchmark:** confirm the thread count with the user, run a warm-up pass to exclude JIT, and subtract per-checkpoint measurement time (reproduce-paper *performance benchmark* rules).

## Use Another Route When

- **The algorithm is iTEBD** — MPSKit has no TEBD; route to `/using-tenpy`.
- The target is genuinely 2D / a wide system → PEPS (`/using-pepskit`).
- The paper used official non-MPSKit code that is runnable, or a finite ITensor workflow is preferred → `/using-itensors`.
