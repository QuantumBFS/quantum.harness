---
name: using-xdiag
description: Use when choosing or running XDiag.jl for exact diagonalization, symmetry-resolved sectors, Lanczos/Krylov calculations, or XDiag setup failures.
---

# XDiag

Use XDiag as the harness's canonical exact-diagonalization stack when the target can be expressed through its Hilbert-space blocks and operators. Method judgment — which route (dense / Lanczos / dynamics / finite-T), which sectors, and the work counts — is owned by `/method-ed`; this skill owns expressing those decisions in XDiag and the package-level values.

## Sources

- Stack contract: `skills/using-xdiag/stack.toml`
- Method card (route, sectors, work counts, verification): `skills/method-ed/SKILL.md`
- Install target: `make install xdiag`
- Smoke test: `julia --project=julia-env -e 'using XDiag'`
- Local API reference (key API + worked examples, with links to upstream docs): `references/xdiag-api.md`

## Workflow

1. Consult the stack contract before offering setup choices.
2. Arrive with the method decisions fixed by `/method-ed`: model, basis, boundary, the full sector list, and the solver route. If any is still open, return to the method card — don't decide it here.
3. Express the block and `OpSum`, run the pre-diagonalization diagnostics (below), then the chosen solver.
4. Record thread count, block dimension, diagonalization mode, tolerance, and residual checks in the run plan.

## Parameter setup

How to express each method decision in XDiag, and what only XDiag can answer.

- **Block**: `Spinhalf` / `tJ` / `Electron`; conserved charges as `nup` (and `ndn` — required for `tJ`); a spatial sector as a `Representation` (a `PermutationGroup` + one character per element). Only 1D irreps are supported. `dim(block)` is the D that all estimates use.
- **Symmetries**: build the `PermutationGroup` explicitly (group axioms are validated); characters must satisfy the homomorphism rule. Julia sites count from 1 (C++/TOML from 0). A nonzero-momentum irrep forces complex states. Measuring a non-invariant operator (single bond) on a symmetric state requires `symmetrize(op, group)` first.
- **Constrained bases**: XDiag has no constrained-basis block. A PXP-type constraint means the full `Spinhalf(N)` space with projector-dressed operators (`Op("Matrix", …)` built via `kron`) — dimension consequence per the method card; if that overturns the tool choice, go back to step 2 there.
- **Solver calls**: `eigval0` / `eig0` for the ground state; `eigs_lanczos(ops, block; neigvals, precision, max_iterations, deflation_tol)` for low-lying towers (returns Ritz values, eigenvectors, `criterion`); dense `matrix(ops, block)` + `LinearAlgebra.eigen` for full spectra of small blocks; `csr_matrix` only when memory is ample and the matrix is reused many times.
- **Dynamics**: `time_evolve` (real) / `imaginary_time_evolve` (set `shift = e0` for stability); `algorithm = "lanczos"` (memory-lean, runs twice) vs `"expokit"` (faster, more memory).
- **Diagnostics before diagonalizing** (the method card's mid-run checklist, in XDiag terms): print `dim(block)`, the sector labels, the `OpSum` term count, and `isreal(ops)`; `set_verbosity(1–2)` for Lanczos progress on long runs. Stop on dimension mismatch or memory far above the 8·D²/8·D estimate.

## Knobs

Package-level values only; what each route needs is the method card's call.

| Knob | Effect | Starting point |
|---|---|---|
| `precision` | Lanczos convergence target (residual scale) | `1e-12` default; loosen only if the observable tolerance allows |
| `max_iterations` | Lanczos iteration cap | 1000 default; raising it past ~200 without convergence usually signals a problem, not patience |
| `neigvals` | how many low-lying eigenpairs `eigs_lanczos` returns | the states the figure needs; more states → more iterations and stricter deflation |
| `deflation_tol` | ghost/duplicate suppression in `eigs_lanczos` | `1e-7` default; tighten when repeated eigenvalues look spurious |
| `random_seed` | Lanczos start vector | fix it in the run plan for reproducibility |
| `backend` | basis encoding: `"auto"`, `"32bit"`, `"64bit"`, `"2sublattice"`…`"5sublattice"` | `"auto"`; sublattice coders are what make N ≳ 40 spin-½ feasible |
| Threads | OpenMP shared-memory matvec | record `JULIA_NUM_THREADS` / OpenMP settings in manifests |

## Code shape

The exact constructors and keyword names should be checked against `references/xdiag-api.md` before writing a production script; the harness-level shape is:

```julia
using XDiag

# 1. Block: charges + (optionally) a space-group irrep fixed by /method-ed.
N = 16
nup = div(N, 2)
p = Permutation([collect(2:N); 1])                 # translation by one site
group = PermutationGroup([p^k for k in 0:(N-1)])
rep = Representation(group)                          # trivial irrep (k = 0)
block = Spinhalf(N, nup, rep)

# 2. Operator sum. Julia site labels count from 1.
ops = OpSum()
for i in 1:N
    ops += "J" * Op("SdotS", [i, mod1(i + 1, N)])
end
ops["J"] = 1.0

# 3. Diagnostics, then the route's solver.
@show dim(block), isreal(ops)
e0, psi0 = eig0(ops, block)                          # ground state
# res = eigs_lanczos(ops, block; neigvals = 4)       # low-lying tower
# psi_t = time_evolve(ops, psi0, t)                  # Krylov dynamics

# 4. Measure; symmetrize non-invariant operators on symmetric blocks.
corr = symmetrize(Op("SdotS", [1, 2]), group)
@show inner(corr, psi0)
```

Densify only for deliberately small blocks where the complete spectrum is needed:

```julia
H = matrix(ops, block)   # 8·D² bytes real; then LinearAlgebra.eigen
```

## Time estimate

The method card owns the work counts and feasibility anchors; this skill measures the XDiag rate and multiplies.

- Dense: memory `8 D^2` bytes real (×2 complex) plus eigenvector/workspace; time one small dense `eigen` to fix the D³ rate before promising a wall time.
- Sparse / matrix-free: time one representative `apply(ops, psi)` on the target block (or a smaller block with the same terms-per-site); wall = matvec time × iterations × requested states. The probe measures only a rate, is discarded, and is gated per reproduce-paper step 4.
- Route to `/using-slurm` when the block exceeds local memory or the 15-minute target by a large factor. Distributed XDiag (`*Distributed` blocks, MPI, C++-only) has **no symmetrized blocks yet** — a symmetry-resolved target that needs MPI is a real constraint to surface, not a silent fallback.

## Use Another Route When

- The target needs a constrained basis XDiag cannot express cleanly (`user_basis` in `/using-quspin` is the documented route).
- The target needs shift-invert interior eigenpairs (QuSpin's `eigsh(sigma=…)` one-liner, or SLEPc-class tooling).
- The official paper code exists and is runnable.
- The route decision itself is in doubt — that belongs to `/method-ed`, not here.
