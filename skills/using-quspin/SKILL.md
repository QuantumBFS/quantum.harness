---
name: using-quspin
description: Use when choosing or running QuSpin as the Python fallback for exact diagonalization, constrained-basis ED, spin-chain ED examples, or QuSpin setup failures.
---

# QuSpin

Use QuSpin when `/method-ed` routes here: Python/official-code workflows, a matching QuSpin example, or a constrained Hilbert space via `user_basis`. Method judgment — route, sectors, work counts — is owned by `/method-ed`; this skill owns expressing those decisions in QuSpin and the package-level values.

## Sources

- Stack contract: `skills/using-quspin/stack.toml`
- Method card (route, sectors, work counts, verification): `skills/method-ed/SKILL.md`
- Install target: `make install quspin`
- Smoke test: `.venv/bin/python -c 'import quspin; print(quspin.__version__)'`
- Local API reference (key API + worked examples, with links to upstream docs): `references/quspin-api.md`

## Workflow

1. Consult the stack contract before offering setup choices.
2. Arrive with the method decisions fixed by `/method-ed`: model, basis, boundary, the full sector list, and the solver route. If any is still open, return to the method card — don't decide it here.
3. Express the basis and operator lists, run the pre-diagonalization diagnostics (below), then the chosen solver.
4. Record basis class, block dimension, solver call, dtype, and residual checks in the run plan; do not replace QuSpin with generic NumPy/SciPy ED unless that deviation is recorded.

## Parameter setup

How to express each method decision in QuSpin, and what only QuSpin can answer.

- **Basis class**: `*_basis_1d` for chains (built-in symmetry keywords), `*_basis_general` for any lattice/dimension (symmetries as permutation maps). Charges: `Nup`/`m` (spin), `Nf` (fermions, tuple for spinful), `Nb` (bosons). **`pauli` flag**: `spin_basis_1d` defaults to Pauli matrices — set `pauli=False` for textbook spin-½ operators, or every coupling silently gains a factor of 2 per operator.
- **Symmetry blocks**: `kblock` (with `a` sites per unit cell), `pblock`, `zblock`, `pzblock`, sublattice `zAblock`/`zBblock` — one sector each, only for symmetries H actually has. For k ≠ 0, π QuSpin switches to real semi-momentum states when `kblock` and `pblock` are combined.
- **Constrained bases (`user_basis`)**: the clean route for PXP/dimer/Rydberg constraints — a Numba-compiled precheck function enumerates only legal states. Check `basis.Ns` against the exact combinatorial count (the method card's first mid-run check) before anything downstream.
- **Operators**: `static`/`dynamic` lists of `[operator string, site-coupling list]`; the k-th string character acts on the k-th site index per row. Add the Hermitian-conjugate string explicitly (`"+-"` needs `"-+"`) or QuSpin raises. dtype: `float64` unless a complex block (`kblock` ≠ 0, π) or complex coupling forces `complex128`. Keep `check_herm` / `check_symm` on — they are the Hermiticity diagnostic and run once at construction.
- **Solver calls**: `H.eigh()` dense full spectrum; `H.eigsh(k=…, which="SA")` Lanczos low-lying; `eigsh(sigma=…)` shift-invert interior one-liner; `expm_multiply_parallel` / `H.evolve` for Krylov dynamics; example 21 is the FTLM reference implementation (R ≈ 100, bootstrap errors).
- **Diagnostics before diagonalizing**: print `basis.Ns`, the sector labels, and the term count; on a tiny system compare against a dense brute-force build, and against `/using-xdiag` when both express the target.

## Knobs

Package-level values only; what each route needs is the method card's call.

| Knob | Effect | Starting point |
|---|---|---|
| `pauli` | Pauli vs spin-½ operator normalization | `False` for textbook spin models — the classic factor-of-2 trap |
| `dtype` | real vs complex storage (memory ×2) | `float64`; `complex128` only when the block or couplings force it |
| `k` (in `eigsh`) | number of Lanczos eigenpairs | the states the figure needs; ARPACK wants `k ≪ Ns` |
| `sigma` | shift-invert target energy | interior windows only, with the memory budget stated |
| `check_herm`, `check_symm`, `check_pcon` | construction-time diagnostics | keep on; they run once at construction |
| Threads | MKL/OpenBLAS OpenMP under the hood | record the thread env (`OMP_NUM_THREADS`, MKL) in manifests |

## Code shape

Check constructors against `references/quspin-api.md` before a production script; the harness-level shape is:

```python
from quspin.basis import spin_basis_1d
from quspin.operators import hamiltonian

# 1. Basis: charges + symmetry blocks fixed by /method-ed.
L = 16
basis = spin_basis_1d(L, Nup=L // 2, kblock=0, pblock=1, pauli=False)

# 2. Operator lists; conjugate strings added explicitly.
J_zz = [[1.0, i, (i + 1) % L] for i in range(L)]
J_xy = [[0.5, i, (i + 1) % L] for i in range(L)]
static = [["+-", J_xy], ["-+", J_xy], ["zz", J_zz]]

# 3. Diagnostics, then the route's solver.
print(basis.Ns)                                   # check vs combinatorics first
H = hamiltonian(static, [], basis=basis, dtype=float)
E, V = H.eigsh(k=1, which="SA")                   # ground state
# E_full, V_full = H.eigh()                       # dense full spectrum
```

For a constrained space, replace step 1 with a `user_basis` (Numba precheck) per the API reference, and verify `basis.Ns` against the exact count before step 2.

## Time estimate

The method card owns the work counts and feasibility anchors; this skill measures the QuSpin rate and multiplies.

- Dense: memory `8 D^2` bytes real (×2 complex) plus eigenvector/workspace; time one small `eigh` to fix the D³ rate.
- Sparse: time one representative `H.dot(v)`; wall = matvec time × iterations × requested states, plus the Python/basis-construction overhead paid before the eigensolver (it can dominate small runs).
- Time-dependent runs: matvec time × time steps × solver substeps; include observable-evaluation cost when it is not cheap.
- QuSpin is single-node (no MPI), practical ceiling D ~ 10⁷–10⁸: past that, the answer is `/using-xdiag` (distributed) or a smaller target — surface it, never silently downsize. Cluster submission composes with `/using-slurm`.

## Use Another Route When

- The block needs generic space-group irreps or distributed memory (`/using-xdiag`).
- The official paper code exists and is runnable.
- The route decision itself is in doubt — that belongs to `/method-ed`, not here.
