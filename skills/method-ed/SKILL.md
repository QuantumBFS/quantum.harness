---
name: method-ed
description: Use when an exact diagonalization track, ED reproduction, full spectrum, symmetry sector, scar, level statistics, or finite-cluster oracle needs method-level route and tool selection.
---

# Method ED

Exact diagonalization is the finite-Hilbert-space oracle track. Use it to decide what ED route is scientifically required, then invoke the selected tool skill for software setup, parameters, and timing.

## Sources

- Track README: `tracks/ed/README.md`
- Interview notes: `docs/ed/interview.html`
- Review notes: `docs/ed/review.html`
- Tool skills: `/using-xdiag`, `/using-quspin`

## Route

1. Inspect the paper target first. Full-spectrum scars, ETH, overlaps across many eigenstates, and level statistics usually require dense full diagonalization inside a fully specified sector.
2. Identify basis, constraints, boundary, and every conserved sector before recommending software.
3. Recommend `/using-xdiag` by default for research-grade ED, symmetry blocks, Lanczos/Krylov, and Julia harness runs.
4. Recommend `/using-quspin` when the paper/official code is Python or QuSpin, when a QuSpin example matches, or when `user_basis` is the clean constrained-basis route.
5. If neither tool can express the target cleanly, present official code / web search / custom implementation as the setup fork, then record it as a deviation.

## Tool Handoff

After selecting the route, invoke the chosen tool skill:

- `/using-xdiag` owns XDiag parameter setup, dense vs sparse estimate, and cluster threshold.
- `/using-quspin` owns QuSpin basis/operator setup, sparse/dense estimate, and Python runtime caveats.

This method skill does not ask tolerance, thread, or matrix-construction details directly; it uses the tool skill for those questions.

## Details

Finite-Hilbert-space method that constructs a many-body basis, represents the Hamiltonian exactly in that basis or applies it matrix-free, then computes eigenvalues, eigenvectors, dynamics, or level diagnostics. Use ED as the small-system reference method and as the cross-method oracle for approximate methods.

This card is generic methodology. Paper-specific Hamiltonian reductions, constrained bases, figure protocols, and target claims belong in `/reproduce-paper` protocols, not here.

### Scope

Use this card for:

- Small clusters where the Hilbert space fits in memory after symmetry reduction.
- Sparse Lanczos / Krylov ground states and low-lying states.
- Exact or Krylov time evolution on finite Hilbert spaces.
- Eigenstate overlaps, participation diagnostics, and level statistics.
- Small-system cross-checks for DMRG, VMC, QMC, VQE, TEBD, and tensor-network runs.

Do not use this card as the full recipe for:

- Finite-temperature Lanczos, METTS, purification, or thermodynamic trace estimators — out of current scope.
- Frequency-resolved spectral functions — out of current scope.
- Paper-specific constrained Hilbert spaces or figure protocols.

### Notation

- `N`: number of physical sites or orbitals.
- `dim`: dimension of the selected Hilbert-space block.
- Sector: fixed quantum-number block such as total magnetization, particle number, momentum, parity, or lattice irrep.
- Full ED: dense matrix diagonalization of the selected block.
- Lanczos / Krylov: iterative matrix-vector method for extremal eigenpairs or time evolution.
- Shift-invert / interior solve: targeted interior-spectrum method; use only when the linear solver and memory budget are explicit.
- Level-spacing ratio: adjacent-gap diagnostic after resolving symmetries and removing degeneracies.

### Pitfalls

- **Unresolved symmetries**: level statistics are meaningless if independent symmetry sectors are mixed.
- **Basis convention drift**: spin, Pauli, fermion sign, and site-index conventions must match the model card or protocol.
- **Dense matrix overuse**: building `H` explicitly can dominate memory; prefer matrix-free `apply`/Lanczos for larger blocks.
- **Lanczos ghosts**: insufficient orthogonalization or too many iterations can produce repeated spurious eigenvalues.
- **Interior-state fragility**: rare high-energy eigenstates require an explicit targeting method and residual checks.
- **Degeneracy handling**: exact or near degeneracies can make eigenvectors basis-dependent; compare invariant subspaces or projectors when needed.

### Verification

- **Dimension check**: confirm the block dimension against combinatorics or the software-reported basis size.
- **Hermiticity check**: verify the operator is Hermitian before diagonalization when complex terms or custom matrices are used.
- **Residual check**: for every reported eigenpair, check `norm(apply(ops, psi) - E * psi)`; use dense `H * psi` only for deliberately small blocks.
- **Symmetry check**: measure all imposed conserved quantities on returned states.
- **Dense/sparse cross-check**: on a smaller block, compare dense diagonalization with Lanczos.
- **Limit check**: compare against trivial limits from `.knowledge/limits.md`.
- **Level-stat check**: unfold or ratio only within one fully resolved symmetry sector.

### Citations

- `.knowledge/literature/ed/10-1007-978-3-540-74686-7-18.md` - Weiße and Fehske, exact diagonalization techniques.
- `.knowledge/literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` - Sandvik, spin-model ED and Lanczos pedagogy.
- `.knowledge/literature/ed/2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md` - XDiag software reference.
- `.knowledge/literature/ed/1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md` - QuSpin fallback reference.
