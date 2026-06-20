# XDiag.jl — API + Examples Reference

Extracted reference for **XDiag**, an open-source exact-diagonalization (ED) package
for quantum many-body lattice systems. Core is C++ (Armadillo backend) wrapped in
Julia via `CxxWrap.jl`; this card targets the **Julia interface, `XDiag.jl`**.

## What XDiag does

- Large-scale ED for spin-½, electron, and t-J Hilbert spaces, with and without a
  **symmetry-adapted basis**. It is the first publicly accessible implementation of
  *sublattice coding* for large spin systems (S=½ up to ~50 sites), uses *Lin tables*
  for fast symmetry lookup, and *random-hashing* for distributed (MPI) parallelism.
- **Full lattice-symmetry adaptation**: space-group permutation symmetries +
  1D irreducible representations (irreps, i.e. momentum / point-group labels) reduce
  block dimension and expose physics (tower-of-states analysis).
- Matrix-free (on-the-fly) Lanczos/Krylov for ground states, excited states, dynamical
  spectral functions, real/imaginary time evolution, and finite-T (thermal pure
  quantum states / finite-temperature Lanczos).
- Shared-memory parallelism (OpenMP) in the standard library; distributed (MPI) in a
  separate C++-only `xdiag_distributed` build (`*Distributed` blocks; **no symmetrized
  blocks under MPI yet**).
- TOML input (operators, permutation groups, representations) + HDF5 output.

API design is deliberately ITensors-like. Julia counts **sites and indices from 1**;
C++ and TOML input files count from **0**.

Install (Julia package mode): `pkg> add XDiag` — or via this harness, `make install xdiag`.
Smoke test: `julia --project=julia-env -e 'using XDiag'`.

---

## Quick start (verbatim)

Ground-state energy of the S=½ Heisenberg chain (N=16, periodic), no symmetry:

```julia
using XDiag

let
    say_hello()
    N = 16
    nup = N ÷ 2
    block = Spinhalf(N, nup)

    # Define the nearest-neighbor Heisenberg model
    ops = OpSum()
    for i in 1:N
        ops += "J" * Op("SdotS", [i, mod1(i+1, N)])
    end
    ops["J"] = 1.0

    set_verbosity(2)            # set verbosity for monitoring progress
    e0 = eigval0(ops, block)    # compute ground state energy

    println("Ground state energy: $e0")
end
```

The full skeleton of any XDiag calculation: **(1)** choose a Hilbert-space block,
**(2)** build an `OpSum`, **(3)** diagonalize / evolve, **(4)** measure.

---

## Key API (Julia)

### 1. Hilbert-space blocks

Three Hilbert-space types. Each site is:
- `Spinhalf` — `↑` or `↓`.
- `Electron` — empty `◌`, `↑`, `↓`, or doubly occupied `↕`.
- `tJ` — empty `◌`, `↑`, or `↓` (no double occupancy).

A bare type is the *full* Hilbert space; passing conserved quantum numbers
(`nup`, `ndn`) and/or a `Representation` (irrep) restricts to a **block** (sector).
The `backend::String` arg (default `"auto"`) selects the basis encoding:
`"32bit"`, `"64bit"`, or for `Spinhalf` the sublattice coders
`"2sublattice"`…`"5sublattice"`.

```julia
Spinhalf(nsites::Int64, backend::String="auto")
Spinhalf(nsites::Int64, nup::Int64, backend::String="auto")
Spinhalf(nsites::Int64, irrep::Representation, backend::String="auto")
Spinhalf(nsites::Int64, nup::Int64, irrep::Representation, backend::String="auto")

tJ(nsites::Int64, nup::Int64, ndn::Int64, backend::String="auto")
tJ(nsites::Int64, nup::Int64, ndn::Int64, irrep::Representation, backend::String="auto")

Electron(nsites::Int64, backend::String="auto")
Electron(nsites::Int64, nup::Int64, ndn::Int64, backend::String="auto")
Electron(nsites::Int64, irrep::Representation, backend::String="auto")
Electron(nsites::Int64, nup::Int64, ndn::Int64, irrep::Representation, backend::String="auto")
```

Block methods: `nsites(block)`, `size(block)` / `dim(block)` (block dimension),
and blocks are **iterable** over basis `ProductState`s. `index(block, pstate)` gives
the integer index of a configuration (used to interpret wavefunction coefficients).

Distributed (MPI, C++-only) variants: `SpinhalfDistributed`, `tJDistributed`,
`ElectronDistributed` — same role, no symmetrized blocks yet.

```julia
N = 4
nup = 2

# Spinhalf: with and without Sz conservation, with and without symmetries
block      = Spinhalf(N)          # full Hilbert space
block_sz   = Spinhalf(N, nup)     # fixed Sz sector (nup ↑-spins)
p     = Permutation([2, 3, 4, 1])
group = PermutationGroup([p^0, p^1, p^2, p^3])
rep   = Representation(group, [1.0, -1.0, 1.0, -1.0])   # k=π irrep of C4
block_sym    = Spinhalf(N, rep)         # symmetry-adapted, no Sz
block_sym_sz = Spinhalf(N, nup, rep)    # symmetry-adapted + Sz
@show nsites(block_sym_sz)
@show size(block_sym_sz)
for pstate in block_sym_sz
    @show pstate, index(block_sym_sz, pstate)
end
```

### 2. Operators: `Op` and `OpSum`

A many-body operator is `O = Σ_A c_A O_A`: `OpSum` is the sum, `Op` the local term.
Coupling `c_A` may be a real/complex number **or a string** placeholder set later via
`ops["name"] = value`.

```julia
Op(type::String)
Op(type::String, site::Int64)
Op(type::String, sites::Vector{Int64})
Op(type::String, site::Int64,  matrix::Matrix{Float64})       # for type "Matrix"
Op(type::String, sites::Vector{Int64}, matrix::Matrix{Float64})
Op(type::String, site::Int64,  matrix::Matrix{ComplexF64})
Op(type::String, sites::Vector{Int64}, matrix::Matrix{ComplexF64})

OpSum(op::Op)
OpSum(coupling::Float64,    op::Op)
OpSum(coupling::ComplexF64, op::Op)
OpSum(coupling::String,     op::Op)
```

Build by accumulation; `coupling * Op(...)` makes a one-term `OpSum`:

```julia
ops = OpSum()
for i in 1:N
    ops += "J" * Op("SzSz", [i, mod1(i+1, N)])
end
ops["J"] = 1.0          # set string coupling to a number

# numeric or string couplings, and the generic "Matrix" type:
op = "T"  * Op("Hop", [1, 2])
op = 1.23 * Op("Hop", [1, 2])
op = Op("Matrix", 1, [0 -1.0im; 1.0im 0])   # custom local matrix (here ~ S^y)
@show isreal(op)
```

#### Operator type strings (Appendix A of the paper)

| Type | Definition | Sites | Blocks |
|---|---|---|---|
| `Hop` | hopping both spins, −Σ_σ (t c†_iσ c_jσ + h.c.) | 2 | tJ, Electron (+Distributed) |
| `Hopup` | ↑ hopping −(t c†_i↑ c_j↑ + h.c.) | 2 | tJ, Electron (+Distributed) |
| `Hopdn` | ↓ hopping −(t c†_i↓ c_j↓ + h.c.) | 2 | tJ, Electron (+Distributed) |
| `HubbardU` | uniform Hubbard Σ_i n_i↑ n_i↓ | 0 | Electron (+Distributed) |
| `Cdagup` | create ↑ electron c†_i↑ | 1 | tJ, Electron (+Distributed) |
| `Cdagdn` | create ↓ electron c†_i↓ | 1 | tJ, Electron (+Distributed) |
| `Cup` | annihilate ↑ electron c_i↑ | 1 | tJ, Electron (+Distributed) |
| `Cdn` | annihilate ↓ electron c_i↓ | 1 | tJ, Electron (+Distributed) |
| `Nup` | number ↑, n_i↑ | 1 | tJ, Electron (+Distributed) |
| `Ndn` | number ↓, n_i↓ | 1 | tJ, Electron (+Distributed) |
| `Ntot` | total number n_i = n_i↑ + n_i↓ | 1 | tJ, Electron (+Distributed) |
| `Nupdn` | double occupancy d_i = n_i↑ n_i↓ | 1 | Electron (+Distributed) |
| `NupdnNupdn` | double-occupancy correlation d_i d_j | 2 | Electron (+Distributed) |
| `NtotNtot` | density-density n_i n_j | 2 | tJ, Electron (+Distributed) |
| `SdotS` | Heisenberg Sᵢ·Sⱼ = SˣᵢSˣⱼ + SʸᵢSʸⱼ + SᶻᵢSᶻⱼ | 2 | Spinhalf, tJ, Electron (+Distributed) |
| `SzSz` | Ising SᶻᵢSᶻⱼ | 2 | Spinhalf, tJ, Electron (+Distributed) |
| `Exchange` | ½(J S⁺ᵢS⁻ⱼ + J* S⁻ᵢS⁺ⱼ) | 2 | Spinhalf, tJ, Electron (+Distributed) |
| `Sz` | local moment Sᶻᵢ | 1 | Spinhalf, tJ, Electron (+Distributed) |
| `S+` | spin raising S⁺ᵢ | 1 | Spinhalf (+Distributed) |
| `S-` | spin lowering S⁻ᵢ | 1 | Spinhalf (+Distributed) |
| `ScalarChirality` | Sᵢ·(Sⱼ×Sₖ) | 3 | Spinhalf |
| `tJSzSz` | t-J Ising SᶻᵢSᶻⱼ − n_i n_j/4 | 2 | tJ (+Distributed) |
| `tJSdotS` | t-J Heisenberg Sᵢ·Sⱼ − n_i n_j/4 | 2 | tJ (+Distributed) |
| `Matrix` | generic interaction via an explicit coupling matrix on n sites | arbitrary | Spinhalf |

For `Matrix`, the matrix acts on the 2ⁿ-dim space of the n sites; build multi-site
operators with `kron`.

#### Complex couplings — two meanings (paper §3.4)

1. A complex **prefactor** that conjugates under Hermitian conjugation `hc` → can turn a
   Hermitian operator non-Hermitian. Applies to: `HubbardU, Cdagup, Cdagdn, Cup, Cdn,
   Nup, Ndn, Ntot, NtotNtot, SdotS, SzSz, Sz, S+, S-, ScalarChirality, tJSzSz, tJSdotS,
   Matrix`.
2. Part of the operator definition, kept Hermitian (a hopping phase). Applies to:
   `Hop, Hopup, Hopdn, Exchange` — e.g. `Exchange` = ½(J S⁺ᵢS⁻ⱼ + J* S⁻ᵢS⁺ⱼ).

### 3. Symmetries

A site **permutation** π is a bijection on `1..N`. A set of permutations forms a
`PermutationGroup` (group axioms are validated). A 1D **`Representation`** assigns a
character (a complex number per group element) — its label is the momentum / point-group
irrep; the symmetry-adapted block keeps only the states in that irrep.

```julia
Permutation(array::Vector{Int64})     # explicit image; Julia counts from 1
Permutation(size::Int64)              # identity on `size` elements
inv(perm)::Permutation
Base.:*(p1, p2)::Permutation          # concatenate
Base.:^(p, power::Int64)::Permutation
size(perm)::Int64

PermutationGroup(permutations::Vector{Permutation})
PermutationGroup(matrix::Matrix{Int64})    # rows = permutations
nsites(group)::Int64
size(group)::Int64

Representation(group::PermutationGroup)                              # trivial irrep
Representation(group::PermutationGroup, characters::Vector{Float64})
Representation(group::PermutationGroup, characters::Vector{ComplexF64})
```

```julia
# Cyclic translation group C4 and two of its irreps:
p  = Permutation([2, 3, 4, 1])                # translation by 1 site
C4 = PermutationGroup([p^0, p^1, p^2, p^3])
r1 = Representation(C4, [1.0, -1.0, 1.0, -1.0])      # k = π
r2 = Representation(C4, [1.0, 1.0im, -1.0, -1.0im])  # k = π/2
@show r1 * r2
```

**Symmetrize** an operator over a group (or irrep) — turns a non-symmetric operator
(e.g. a single-bond correlator) into one whose expectation value on a symmetric state is
well defined; also builds momentum operators Sᶻ(q):

```julia
symmetrize(op::Op,     group::PermutationGroup)::OpSum
symmetrize(op::Op,     irrep::Representation)::OpSum
symmetrize(ops::OpSum, group::PermutationGroup)::OpSum
symmetrize(ops::OpSum, irrep::Representation)::OpSum
```

### 4. States

```julia
State(block::Block; real::Bool = true, n_cols::Int64 = 1)   # zero state
State(block::Block, vec::Vector{Float64})
State(block::Block, vec::Vector{ComplexF64})
State(block::Block, mat::Matrix{Float64})     # multi-column (n_cols)
State(block::Block, mat::Matrix{ComplexF64})

product_state(block::Block, local_states::Vector{String}; real::Bool=true)
random_state(block::Block; real::Bool=true, ncols::Int64=1, seed::Int64=42, normalized::Bool=true)
zero_state(block::Block;  real::Bool=true, ncols::Int64=1)
```

State methods: `nsites`, `isreal`, `real(s)`, `imag(s)`, `make_complex!(s)`,
`size`, `nrows`, `ncols`, `col(s, n)`, `vector(s; n, copy)` (single column),
`matrix(s)` (multi-column), `zero(s)`. (No `vectorC`/`matrixC` in Julia — type is
decided at runtime.)

```julia
block = Spinhalf(2)
state = product_state(block, ["Up", "Dn"])          # |↑↓⟩
display(vector(state))
state = random_state(block, real=false, seed=1234, normalized=true)
state = zero_state(block, real=true, ncols=2)
psi1  = State(block, [1.0, 2.0, 3.0, 4.0])
make_complex!(psi1)
```

Apply an operator on-the-fly (matrix-free): `phi = apply(ops, psi)`. If the input block
has a definite quantum number, XDiag auto-detects the output sector or errors if the
operator has no well-defined quantum number.

### 5. Diagonalization

All matrix-free (on-the-fly) by default; each also accepts a precomputed
`csr_matrix(ops, block)` in place of `ops`.

```julia
eigval0(ops::OpSum, block::Block; precision::Float64 = 1e-12,
        max_iterations::Int64 = 1000, random_seed::Int64 = 42)::Float64
# → lowest eigenvalue (ground-state energy)

eig0(ops::OpSum, block::Block; precision::Float64 = 1e-12,
     max_iterations::Int64 = 1000, random_seed::Int64 = 42)
# → (e0, gs::State)

eigvals_lanczos(ops, block; ...)   # eigenvalues only, can target excited states
eigs_lanczos(ops::OpSum, block::Block; neigvals::Int64 = 1,
             precision::Float64 = 1e-12, max_iterations::Int64 = 1000,
             deflation_tol::Float64 = 1e-7, random_seed::Int64 = 42)
eigs_lanczos(ops::OpSum, psi0::State; neigvals = 1, precision = 1e-12,
             max_iterations = 1000, deflation_tol = 1e-7, random_seed = 42)
```

`eigs_lanczos` returns `EigsLanczosResult` with fields: `alphas`, `betas`
(tridiagonal-matrix diagonals), `eigenvalues` (Ritz values), `eigenvectors` (a `State`),
`niterations`, `criterion`. `eig0`/`eigs_lanczos` run Lanczos **twice** (first the
tridiagonal matrix, then the eigenvectors) to minimize memory. For the full spectrum of
small blocks use dense `matrix(ops, block)` + LinearAlgebra `eigen`/`Symmetric`. Sparse
extraction: `coo_matrix`, `csr_matrix`, `csc_matrix` (CSR is the parallel internal
format; convert to `SparseMatrixCSC` via `SparseArrays`).

### 6. Time evolution

```julia
time_evolve(H::OpSum, psi0::State, time::Float64;
            precision::Float64 = 1e-12, algorithm::String = "lanczos")::State
time_evolve_inplace(H::OpSum, psi0::State, time::Float64;
                    precision::Float64 = 1e-12, algorithm::String = "lanczos")

imaginary_time_evolve(ops::OpSum, psi0::State, time::Float64;
                      precision::Float64 = 1e-12, shift::Float64 = 0.0)::State
imaginary_time_evolve_inplace(ops, psi0, time; precision = 1e-12, shift = 0.0)
```

`|φ(t)⟩ = e^{−iHt}|ψ₀⟩` (real) or `|η(τ)⟩ = e^{−τH}|ψ₀⟩` (imaginary). `algorithm`:
`"lanczos"` (default, memory-efficient, runs Lanczos twice) or `"expokit"` (Expokit —
faster/accurate but more memory). Lower-level `evolve_lanczos` / `time_evolve_expokit`
expose more control and return the tridiagonal matrix / error estimates. For imaginary
time, set `shift = e0` for numerical stability.

```julia
psi = time_evolve(ops, psi0, time)
time_evolve_inplace(ops, psi0, time)
psi = imaginary_time_evolve(ops, psi0, time, precision=1e-12, shift=e0)
```

### 7. Measurements / algebra

```julia
inner(op::Op,    v::State)     # ⟨v|O|v⟩ expectation value
inner(ops::OpSum, v::State)    # ⟨v|O|v⟩ expectation value
dot(v::State, w::State)        # ⟨v|w⟩
norm(state::State)::Float64    # ‖ψ‖₂
norm1(state::State)::Float64
norminf(state::State)::Float64
```

In Julia `inner`/`dot` return real or complex at runtime (in C++ use `innerC`/`dotC`
when complex). Expectation values:

```julia
@show norm(psi)
@show dot(psi, psi)
@show e0, inner(ops, psi)        # ⟨H⟩ should equal e0 for an eigenstate
```

---

## Worked examples (verbatim from docs)

### A. Heisenberg ground-state energy via `eigval0`

S=½ Heisenberg chain, N=8, half-filling sector, on-the-fly and via sparse matrix:

```julia
let
    N = 8
    nup = N ÷ 2
    block = Spinhalf(N, nup)

    ops = OpSum()
    for i in 1:N
        ops += "J" * Op("SdotS", [i, mod1(i+1, N)])
    end
    ops["J"] = 1.0

    e0 = eigval0(ops, block)           # on-the-fly
    spmat = csr_matrix(ops, block)
    e0 = eigval0(spmat, block)         # sparse matrix
end
```

### B. Symmetry-adapted block + operator expectation/correlator

Ground state in the trivial (k=0) translation sector, compared with the unsymmetrized
block; a single-bond correlator is symmetrized so its expectation value is well defined
on the symmetric state:

```julia
let
    N = 4
    nup = 2
    block = Spinhalf(N, nup)
    p1 = Permutation([1, 2, 3, 4])
    p2 = Permutation([2, 3, 4, 1])
    p3 = Permutation([3, 4, 1, 2])
    p4 = Permutation([4, 1, 2, 3])
    group = PermutationGroup([p1, p2, p3, p4])
    rep = Representation(group)
    block_sym = Spinhalf(N, rep)

    ops = OpSum()
    for i in 1:N
        ops += Op("SdotS", [i, mod1(i+1, N)])
    end

    e0, psi = eig0(ops, block)
    e0, psi_sym = eig0(ops, block_sym)

    corr = Op("SdotS", [1, 2])
    nn_corr = inner(corr, psi)
    corr_sym = symmetrize(corr, group)
    nn_corr_sym = inner(corr_sym, psi_sym)
    @show nn_corr, nn_corr_sym
end
```

### C. Lowest eigenpairs via `eigs_lanczos`

```julia
let
    N = 8
    nup = N ÷ 2
    block = Spinhalf(N, nup)
    ops = OpSum()
    for i in 1:N
        ops += "J" * Op("SdotS", [i, mod1(i+1, N)])
    end
    ops["J"] = 1.0
    res = eigs_lanczos(ops, block)
    spmat = csr_matrix(ops, block)
    res = eigs_lanczos(spmat, block)
end
```

### D. Time evolution (shape)

```julia
psi = time_evolve(ops, psi0, time)            # real time, e^{-iHt}|psi0>
time_evolve_inplace(ops, psi0, time)
spmat = csr_matrix(ops, block)
psi = time_evolve(spmat, psi0, time)
psi = imaginary_time_evolve(ops, psi0, time, precision=1e-12, shift=e0)  # e^{-τH}
```

For a domain-wall melt example (paper §4.5), build `psi0` via
`product_state(block, ["Up", ..., "Dn", ...])` on a `Spinhalf` block with **open**
boundary conditions, then iterate `time_evolve_inplace` over a time grid measuring
`inner(Op("Sz", i), psi)` per site.

---

## Pitfalls

- **Sites/indices start at 1 in Julia** (0 in C++ and in TOML input files). When a TOML
  `OpSum`/symmetry is read in Julia, indices are auto-incremented by 1.
- **Conserved sectors define the problem.** A bare `Spinhalf(N)` is the full space;
  `Spinhalf(N, nup)` is one Sz sector. Wrong `nup`/`ndn` gives a correct answer to the
  wrong problem. Fix every conserved quantum number (particle number, Sz) *before*
  diagonalizing. `tJ` requires both `nup` and `ndn`; `Electron` forbids no occupancy
  but `tJ` forbids double occupancy.
- **Symmetry representation setup is validated but easy to get wrong.** The
  `PermutationGroup` must satisfy the group axioms (identity present, inverses present,
  closure) or construction errors. The `Representation` characters must satisfy the
  homomorphism χ(f)·χ(g)=χ(h) for f∗g=h. Only **1D irreps** are supported; the character
  list length equals the group order. Symmetrized blocks are **not available under MPI**
  (`*Distributed` blocks) in the current version.
- **Expectation values of non-symmetric operators on symmetric states**: a single-bond
  operator is not translation-invariant — `inner` it directly only on the *unsymmetric*
  block, or `symmetrize` it first before measuring on a symmetric block (Example B).
- **Real vs complex.** In Julia there is only `inner`/`dot`/`vector` (return type chosen
  at runtime); the C++ `innerC`/`dotC`/`vectorC` do not exist in Julia. A complex
  representation (nonzero momentum) or complex coupling forces a complex state — use
  `make_complex!` / `random_state(...; real=false)` as needed. A complex prefactor on a
  Hermitian-by-default op (the §3.4 list) can silently make it non-Hermitian.
- **Memory scaling — estimate from block dimension D, not N.** Dense `matrix` is
  `8·D²` bytes (real) plus eigenvector/workspace, wall ~ D³; use only for small blocks
  needing the full spectrum. Matrix-free Lanczos stores only the operator + a few Krylov
  vectors; building a `csr_matrix` first costs extra memory that grows fast with size, so
  the matrix-free default is preferred at large N (the CSR route only wins when memory is
  ample and the matrix is reused many times). MPS-sized blocks → route to the cluster.
- **Progress visibility**: `set_verbosity(1)` / `set_verbosity(2)` to monitor Lanczos
  iterations on long runs.

---

## Source links

- Docs home: https://awietek.github.io/xdiag/
- Quick start (Julia Heisenberg): https://awietek.github.io/xdiag/quick_start/
- User guide / API index: https://awietek.github.io/xdiag/documentation/
- Blocks: https://awietek.github.io/xdiag/documentation/blocks/spinhalf/ ,
  https://awietek.github.io/xdiag/documentation/blocks/tJ/ ,
  https://awietek.github.io/xdiag/documentation/blocks/electron/
- Operators: https://awietek.github.io/xdiag/documentation/operators/op/ ,
  https://awietek.github.io/xdiag/documentation/operators/opsum/ ,
  https://awietek.github.io/xdiag/documentation/operators/symmetrize/
- States: https://awietek.github.io/xdiag/documentation/states/state/ ,
  https://awietek.github.io/xdiag/documentation/states/create_state/
- Symmetries: https://awietek.github.io/xdiag/documentation/symmetries/permutation/ ,
  https://awietek.github.io/xdiag/documentation/symmetries/permutation_group/ ,
  https://awietek.github.io/xdiag/documentation/symmetries/representation/
- Algorithms: https://awietek.github.io/xdiag/documentation/algorithms/eigval0/ ,
  https://awietek.github.io/xdiag/documentation/algorithms/eig0/ ,
  https://awietek.github.io/xdiag/documentation/algorithms/eigs_lanczos/ ,
  https://awietek.github.io/xdiag/documentation/algorithms/time_evolve/ ,
  https://awietek.github.io/xdiag/documentation/algorithms/imaginary_time_evolve/
- Algebra / measurements: https://awietek.github.io/xdiag/documentation/algebra/algebra/
- Examples (correlators, time evolution, TOS, thermodynamics): https://awietek.github.io/xdiag/examples/
- Source: https://github.com/awietek/XDiag.jl (Julia), https://github.com/awietek/xdiag (C++)
- Paper: A. Wietek et al., *XDiag: Exact diagonalization for quantum many-body systems*,
  SciPost Phys. Codebases 70 (2025), arXiv:2505.02901,
  doi:10.21468/SciPostPhysCodeb.70 — local copy:
  `.knowledge/literature/ed/2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md`
