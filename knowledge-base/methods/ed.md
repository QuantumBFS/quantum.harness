# ED (Exact Diagonalization)

Finite-Hilbert-space method that constructs a many-body basis, represents the Hamiltonian exactly in that basis or applies it matrix-free, then computes eigenvalues, eigenvectors, dynamics, or level diagnostics. Use ED as the small-system reference method and as the cross-method oracle for approximate methods.

This card is generic methodology. Paper-specific Hamiltonian reductions, constrained bases, figure protocols, and target claims belong in `/reproduce-paper` protocols, not here.

## Setup

Recommended stack order:

1. `xdiag` (`tools/software/stacks/xdiag.toml`) — canonical ED stack.
2. `quspin` (`tools/software/stacks/quspin.toml`) — Python fallback stack.

```
make install julia
make install xdiag
```

Activate the environment with `julia --project=julia-env`.

Fallback means the second recommended stack, not arbitrary installed Python packages. QuSpin is a Python ED library with a broad spin-chain interface. Use `quspin` only when a workflow already depends on Python, when a QuSpin example exactly matches the target model, or when the canonical XDiag route is recorded as failed/pending and the protocol declares `route = "fallback"`. XDiag remains the default harness route. Generic NumPy/SciPy ED is a deviation unless the paper's official code uses it.

## Scope

Use this card for:

- Small clusters where the Hilbert space fits in memory after symmetry reduction.
- Sparse Lanczos / Krylov ground states and low-lying states.
- Exact or Krylov time evolution on finite Hilbert spaces.
- Eigenstate overlaps, participation diagnostics, and level statistics.
- Small-system cross-checks for DMRG, VMC, QMC, VQE, TEBD, and tensor-network runs.

Do not use this card as the full recipe for:

- Finite-temperature Lanczos, METTS, purification, or thermodynamic trace estimators; route those to `methods/finite-t.md`.
- Frequency-resolved spectral functions; route those to `methods/spectral.md`.
- Paper-specific constrained Hilbert spaces or figure protocols.

## Notation

- `N`: number of physical sites or orbitals.
- `dim`: dimension of the selected Hilbert-space block.
- Sector: fixed quantum-number block such as total magnetization, particle number, momentum, parity, or lattice irrep.
- Full ED: dense matrix diagonalization of the selected block.
- Lanczos / Krylov: iterative matrix-vector method for extremal eigenpairs or time evolution.
- Shift-invert / interior solve: targeted interior-spectrum method; use only when the linear solver and memory budget are explicit.
- Level-spacing ratio: adjacent-gap diagnostic after resolving symmetries and removing degeneracies.

## Code Shape (Julia / XDiag.jl)

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

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| Sector choice | Dominates memory and correctness. Wrong sector gives a correct answer to the wrong problem. | Fix all conserved quantities before diagonalizing. |
| Dense vs sparse | Dense gives complete spectra but scales quickly; sparse Lanczos gives selected eigenpairs. | Dense only for small `dim`; Lanczos otherwise. |
| Lanczos tolerance | Controls eigenvalue residual and runtime. | Tight enough that residual is below the target observable tolerance. |
| Number of Lanczos vectors | Controls convergence and memory. | Increase until target eigenpairs and observables stop moving. |
| Reorthogonalization | Controls ghost eigenvalues in long Lanczos runs. | Enable or strengthen when repeated eigenvalues appear. |
| Symmetry resolution | Required before level statistics and degeneracy claims. | Block by every exact symmetry used by the Hamiltonian. |
| Thread count | XDiag uses shared-memory parallelism for matrix-vector operations. | Record `JULIA_NUM_THREADS` / OpenMP settings in manifests. |

## Pitfalls

- **Unresolved symmetries**: level statistics are meaningless if independent symmetry sectors are mixed.
- **Basis convention drift**: spin, Pauli, fermion sign, and site-index conventions must match the model skill or protocol.
- **Dense matrix overuse**: building `H` explicitly can dominate memory; prefer matrix-free `apply`/Lanczos for larger blocks.
- **Lanczos ghosts**: insufficient orthogonalization or too many iterations can produce repeated spurious eigenvalues.
- **Interior-state fragility**: rare high-energy eigenstates require an explicit targeting method and residual checks.
- **Degeneracy handling**: exact or near degeneracies can make eigenvectors basis-dependent; compare invariant subspaces or projectors when needed.

## Verification

- **Dimension check**: confirm the block dimension against combinatorics or the software-reported basis size.
- **Hermiticity check**: verify the operator is Hermitian before diagonalization when complex terms or custom matrices are used.
- **Residual check**: for every reported eigenpair, check `norm(apply(ops, psi) - E * psi)`; use dense `H * psi` only for deliberately small blocks.
- **Symmetry check**: measure all imposed conserved quantities on returned states.
- **Dense/sparse cross-check**: on a smaller block, compare dense diagonalization with Lanczos.
- **Limit check**: compare against trivial limits from `knowledge-base/limits.md`.
- **Level-stat check**: unfold or ratio only within one fully resolved symmetry sector.

## Citations

- `knowledge-base/literature/ed/10-1007-978-3-540-74686-7-18.md` - Weiße and Fehske, exact diagonalization techniques.
- `knowledge-base/literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` - Sandvik, spin-model ED and Lanczos pedagogy.
- `knowledge-base/literature/ed/2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md` - XDiag software reference.
- `knowledge-base/literature/ed/1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md` - QuSpin fallback reference.
