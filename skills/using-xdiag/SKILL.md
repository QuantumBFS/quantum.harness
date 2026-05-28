---
name: using-xdiag
description: Use when choosing or running XDiag.jl for exact diagonalization, symmetry-resolved sectors, Lanczos/Krylov calculations, or XDiag setup failures.
---

# XDiag

Use XDiag as the harness's canonical exact-diagonalization stack when the target can be expressed through its Hilbert-space blocks and operators.

## Sources

- Stack contract: `skills/using-xdiag/stack.toml`
- Method card: `skills/method-ed/SKILL.md`
- ED interview notes: `docs/ed/interview.html`
- ED review notes: `docs/ed/review.html`
- Install target: `make install xdiag`
- Smoke test: `julia --project=julia-env -e 'using XDiag'`

## Workflow

1. Consult the stack contract before offering setup choices.
2. Confirm the exact model, basis, boundary, and all symmetry sectors before code.
3. Choose dense diagonalization only when the selected block fits with eigensolver workspace; otherwise use sparse / Lanczos and state what is no longer full-spectrum.
4. Record thread count, block dimension, diagonalization mode, tolerance, and residual checks in the run plan.

## Parameter setup

Use this section as the source for XDiag-specific reproduction knobs unless the paper or official code fixes a value. The ED interview makes the setup problem-driven: full-spectrum scar/ETH targets need a dense Hamiltonian in the correct sector; ground-state targets need the expected ground-state sector; thermodynamics may require all sectors.

- ED purpose: full spectrum, selected eigenpairs, level statistics, time evolution, or cross-method oracle. Do not choose the solver before this is known.
- Basis: physical local space, constrained basis rule, state indexing, fermion/sign convention, and whether XDiag can express the block directly.
- Sectors: start with cheap conserved quantities such as particle number / total `Sz`; add translation, inversion/parity, point group, spin flip, or particle-hole only when the paper uses them or the observable requires them. Record exact symmetries intentionally unused.
- Geometry: boundary condition, cluster shape, momentum convention, and phase convention; for 2D, record aspect ratio, allowed momenta, and point-group symmetry.
- Solver policy: dense full diagonalization for full spectra and scar/ETH overlap plots when the block fits; Lanczos/Krylov for extremal or targeted states; shift-invert / polynomial filtering only when the target is an interior window and the linear/filter setup is explicit.
- Debug/validation: before diagonalization print basis dimension, sector label, bond/term count, Hermiticity error, and memory estimate. Stop on sector-dimension mismatch or memory far above estimate.
- Trust checks: residuals, symmetry labels, tiny dense brute force or analytic/free-limit checks, benchmark comparison, and the plotted observable's normalization.

## Knobs

Concrete starting points for the ED knobs in Parameter setup.

| Knob | Effect | Starting point |
|---|---|---|
| Sector choice | Dominates memory and correctness. Wrong sector gives a correct answer to the wrong problem. | Fix all conserved quantities before diagonalizing. |
| Dense vs sparse | Dense gives complete spectra but scales quickly; sparse Lanczos gives selected eigenpairs. | Dense only for small `dim`; Lanczos otherwise. |
| Lanczos tolerance | Controls eigenvalue residual and runtime. | Tight enough that residual is below the target observable tolerance. |
| Number of Lanczos vectors | Controls convergence and memory. | Increase until target eigenpairs and observables stop moving. |
| Reorthogonalization | Controls ghost eigenvalues in long Lanczos runs. | Enable or strengthen when repeated eigenvalues appear. |
| Symmetry resolution | Required before level statistics and degeneracy claims. | Block by every exact symmetry used by the Hamiltonian. |
| Thread count | XDiag uses shared-memory parallelism for matrix-vector operations. | Record `JULIA_NUM_THREADS` / OpenMP settings in manifests. |

## Code shape

The exact constructors and keyword names should be checked against the installed XDiag docs before writing a production script; the harness-level shape is:

```julia
using XDiag

# 1. Select a Hilbert-space block.
N = 16
nup = div(N, 2)
block = Spinhalf(N, nup)

# 2. Build an operator sum. Julia site labels follow the XDiag Julia interface.
ops = OpSum()
for i in 1:(N - 1)
    ops += 1.0 * Op("SdotS", [i, i + 1])
end

# 3. Ground state / low-lying states.
e0, psi0 = eig0(ops, block)

# 4. Operator application and Krylov dynamics stay matrix-free when possible.
phi = apply(ops, psi0)
# psi_t = time_evolve(ops, psi0, t; algorithm = "lanczos")
```

Densify only for deliberately small blocks where the complete spectrum is needed:

```julia
H = matrix(ops, block)
```

For scripts that need precise control over convergence or excited states, use the lower-level Lanczos routines exposed by XDiag rather than only the convenience ground-state wrapper.

## Time estimate

Estimate cost from the symmetry-reduced block dimension `D` after basis constraints and sectors are fixed. Use `D`, not site count, as the scale variable.

- Dense full-spectrum: memory starts at `8 D^2` bytes for a real dense matrix, plus eigenvectors/workspace; wall scales as `D^3`. Use `docs/ed/review.html` anchors when relevant: workstation dense full spectrum is roughly `D ~ 1e5`-scale, while much larger ED must be sparse/distributed.
- Sparse / matrix-free: memory is operator/state storage plus Krylov vectors; wall is measured or estimated as `matvec_cost * iterations * requested_states`.
- Paper-size estimate: compute or bound the paper's `D` after all sectors, then estimate dense vs sparse feasibility.
- Local-15-min estimate: solve for the largest `D` that fits the local memory and time budget under the chosen solver; if uncertain, time one representative matvec or tiny block only.
- Route to `/using-slurm` when the paper-size block exceeds local memory, exceeds the 15-minute target by a large factor, or needs MPI/distributed XDiag.

## Use Another Route When

- The paper needs a custom constrained basis that XDiag cannot express cleanly.
- The official paper code exists and is runnable.
- QuSpin is explicitly declared as the fallback by the protocol or method card.
