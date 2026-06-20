# PEPSKit.jl — API + Examples Reference

PEPSKit.jl: "Tools for working with projected entangled-pair states. It contracts, it optimizes, it evolves."
A Julia library for infinite 2D tensor networks (infinite PEPS / iPEPS, classical partition functions, PEPO),
built on **TensorKit.jl** (symmetric + fermionic tensors). Contraction via **CTMRG** or **boundary MPS (VUMPS)**;
ground-state optimization via reverse-mode automatic differentiation (**Zygote**).

- Docs: <https://quantumkithub.github.io/PEPSKit.jl/stable/>
- Repo: <https://github.com/QuantumKitHub/PEPSKit.jl>
- API reference: <https://quantumkithub.github.io/PEPSKit.jl/stable/lib/lib/>
- Install: `pkg> add PEPSKit` (also needs `TensorKit`; examples use `MPSKit`, `MPSKitModels`, `QuadGK`).

Capabilities: build/manipulate infinite PEPS; contract with CTMRG and boundary MPS; symmetric/fermionic tensors;
AD-based PEPS optimization; imaginary-time evolution (simple update); generic unit cells; classical 2D partition
functions and PEPO support; extensible states/operators/algorithms.

---

## Mental model

- **PEPS bond dimension `D`** (a.k.a. virtual dim `Nspace`) — the variational ansatz accuracy. Set in the PEPS.
- **Environment bond dimension `χ` / `χ_env`** (the CTMRG corner/edge space `Venv`) — the *contraction* accuracy.
  These are independent. `χ` must generally grow faster than `D` (rule of thumb `χ ≳ D²`).
- Pipeline: build network (PEPS / partition function) → converge environment (`leading_boundary`) →
  measure (`expectation_value`, `network_value`, `correlation_length`) or optimize (`fixedpoint`).

Spaces are TensorKit objects: `ℂ^n` / `ComplexSpace(n)` (no symmetry), `U1Space(charge => deg, …)` (U(1)),
`Vect[S](sector => deg, …)` (generic, incl. fermionic `fℤ₂`). Symmetry/fermion sectors are combined with `⊠`.

---

## Key API

### State construction

```julia
InfinitePEPS([f=randn, T=ComplexF64,] Pspace, Nspace, [Espace]; unitcell=(1,1))
```
Infinite PEPS on a 2D square lattice. `Pspace` = physical space, `Nspace`/`Espace` = virtual (bond) spaces
(north/east; south/west default to duals). Also constructs from a matrix of tensors or a single tensor + `unitcell`.
- `InfinitePEPS(randn, ComplexF64, ℂ^2, ℂ^D)` — random S=½ PEPS, bond dim `D`.
- `InfinitePEPS(physical_spaces, virtual_spaces)` — pass matrices of spaces for multi-site unit cells / symmetric spaces.

```julia
InfinitePartitionFunction([f=randn, T=ComplexF64,] Pspace, Nspace, [Espace]; unitcell=(1,1))
InfinitePartitionFunction(O)                       # from a single rank-4 tensor
```
Infinite classical partition function as a network of rank-4 tensors. `O` is a `TensorMap` of space `W⊗S ← N⊗E`.

```julia
InfinitePEPO([...]; unitcell=(1,1,1))               # infinite PEPO on a 3D cubic lattice
```

```julia
InfiniteSquare([Nrows=1, Ncols=1])                 # square lattice / unit cell descriptor
InfiniteSquareNetwork(...)                          # contractible square network wrapper
```
`InfiniteSquare(2, 2)` declares a 2×2 unit cell — required for Néel/antiferromagnetic order or staggered charges.

**Tensor type aliases** (TensorKit `TensorMap`s):
- `PEPSTensor(f, T, Pspace, Nspace, [Espace], [Sspace], [Wspace])` → `P ← N⊗E⊗S⊗W`.
- `PEPOTensor` → `P⊗P′ ← N⊗E⊗S⊗W`.
- `PartitionFunctionTensor` → `W⊗S ← N⊗E`.

### CTMRG boundary contraction

```julia
CTMRGEnv([f=randn, T,] network, Venv)              # build environment for a network with env space Venv
CTMRGEnv(randn, ComplexF64, peps, ℂ^χenv)
```
Corner-transfer-matrix environment: `corners::Array{C,3}`, `edges::Array{T,3}` indexed by direction.
`Venv` is the environment (corner/edge) space; its dimension is `χ_env`.

```julia
leading_boundary(env₀, network; kwargs...) -> (env, info)
```
Converge the CTMRG environment (find the leading boundary fixed point). Returns the converged `env` and an
`info` NamedTuple (truncation error, condition number, iteration count, convergence residual).
Key kwargs (also settable via a `boundary_alg = (; …)` NamedTuple spread with `boundary_alg...`):
- `tol=1e-8` — fixed-point tolerance.
- `maxiter=100`, `miniter=4` — iteration bounds.
- `verbosity=2` — log level (0 silent … 3 per-iteration).
- `alg=:simultaneous` or `:sequential` — CTMRG flavor (see below).
- `trunc=(; alg=:fixedspace)` — truncation scheme for the renormalization step.

**CTMRG algorithms** (`<: CTMRGAlgorithm`):
```julia
SimultaneousCTMRG(; tol=1e-8, maxiter=100, miniter=4, verbosity=2, projector_alg=:halfinfinite)
SequentialCTMRG(;  tol=1e-8, maxiter=100, miniter=4, verbosity=2, projector_alg=:halfinfinite)
```
- `SimultaneousCTMRG` (`alg=:simultaneous`) — grows/renormalizes all four sides at once; the usual choice with AD.
- `SequentialCTMRG` (`alg=:sequential`) — column-wise expansion with four-fold rotation.

**Truncation schemes** (the `trunc` step):
- `FixedSpaceTruncation` (`alg=:fixedspace`) — keeps the bond space fixed across directions; standard for CTMRG.
- `ALSTruncation(; trunc, maxiter=50, tol=1e-15, check_interval=0)` — alternating least-squares bond optimization.
- `FullEnvTruncation(; trunc, maxiter=50, tol=1e-15, trunc_init=true)` — full-environment bond truncation.

### Boundary MPS contraction (VUMPS alternative to CTMRG)

```julia
T   = InfiniteTransferPEPS(ψ, dir, row)             # row-to-row transfer operator from a PEPS
mps₀ = initialize_mps(T, [ComplexSpace(χ)])          # boundary MPS guess with env space χ
mps, env, ϵ = leading_boundary(mps₀, T, VUMPS(; tol=1e-6, verbosity=2))
val = abs(prod(expectation_value(mps, T)))           # network value / norm
```
Other types: `PEPSKit.MultilineTransferPEPS(ψ, dir)` for multi-row unit cells (`initialize_mps(T, fill(ℂ^χ, r, c))`);
`InfiniteTransferPEPO(ψ, O, row, col)` for PEPO overlaps. `VUMPS` comes from MPSKit.jl.

### Hamiltonians / models

```julia
LocalOperator(lattice::Matrix{S}, terms::Pair...)
```
Sum of local operators on the lattice. `lattice` is a matrix of physical spaces; each term maps lattice site
index tuples to a `TensorMap`. Example single-site operator:
```julia
σ_z = TensorMap([1.0 0.0; 0.0 -1.0], ℂ^2, ℂ^2)
M   = LocalOperator(fill(ℂ^2, 1, 1), (CartesianIndex(1, 1),) => σ_z)
```

Built-in model constructors (return a `LocalOperator`; re-exported from MPSKitModels.jl unless noted). Leading
positional args `elt::Type{<:Number}` and symmetry `Type{<:Sector}` are optional and default to `ComplexF64` / `Trivial`:

| Constructor | Signature | Notes |
|---|---|---|
| `transverse_field_ising` | `transverse_field_ising([elt],[symmetry],[lattice]; J=1.0, g=1.0)` | TFIM, spin-½ Paulis |
| `heisenberg_XYZ` | `heisenberg_XYZ([elt],[lattice]; Jx=1.0, Jy=1.0, Jz=1.0, spin=1)` | XYZ Heisenberg |
| `heisenberg_XXZ` | `heisenberg_XXZ([elt],[symmetry],[lattice]; J=1.0, Delta=1.0, spin=1)` | anisotropic XXZ |
| `j1_j2_model` | `j1_j2_model([elt, symm,] lattice::InfiniteSquare; J1=1.0, J2=1.0, spin=1//2, sublattice=true)` | NN + NNN (PEPSKit) |
| `hubbard_model` | `hubbard_model([elt],[particle_symmetry],[spin_symmetry],[lattice]; t, U, mu, n)` | fermionic Hubbard |
| `bose_hubbard_model` | `bose_hubbard_model([elt],[symmetry],[lattice]; cutoff, t, U, mu, n)` | bosons, truncated Hilbert space |
| `tj_model` | `tj_model([elt],[particle_symmetry],[spin_symmetry],[lattice]; t, J, mu, slave_fermion=false)` | t-J, no double occupancy |
| `pwave_superconductor` | `pwave_superconductor([T=ComplexF64,] lattice::InfiniteSquare; t=1, μ=2, Δ=1)` | p-wave SC (PEPSKit) |

`physicalspace(H)` returns the matrix of physical spaces of a Hamiltonian (use to size the PEPS). For symmetric
sectors, `add_physical_charge(H₀, charges)` (from MPSKit) re-centers physical charges for a target filling /
staggered order.

### Ground-state optimization

```julia
PEPSOptimize(; boundary_alg, gradient_alg, optimizer_alg, reuse_env=true, symmetrization=nothing)
```
Bundles the optimization algorithm (CTMRG inner contraction, gradient method, optimizer). `reuse_env=true`
warm-starts each environment from the previous one (large speedup). `symmetrization` can impose lattice symmetry.

```julia
fixedpoint(H, peps₀, env₀; boundary_alg, gradient_alg, optimizer_alg, reuse_env, verbosity) -> (peps, env, E, info)
```
Variationally optimize the PEPS for Hamiltonian `H`, starting from `peps₀` / `env₀`. Returns the optimized PEPS,
its converged environment, the energy `E`, and an `info` NamedTuple (iterations, gradient norm, convergence).
The three algorithm groups are passed as NamedTuples:
- `boundary_alg = (; tol=1e-8, alg=:simultaneous, trunc=(; alg=:fixedspace))` — inner CTMRG per gradient step.
- `gradient_alg = (; tol=1e-6, alg=:eigsolver, maxiter=10, iterscheme=:diffgauge)` — reverse-mode gradient of the
  CTMRG fixed point. `alg=:eigsolver` uses a linear/eigen solver for the fixed-point derivative; `iterscheme=:diffgauge`
  fixes the gauge for stable AD (alternative `:fixed`).
- `optimizer_alg = (; alg=:lbfgs, tol=1e-4, maxiter=100, lbfgs_memory=16, ls_maxiter=3, ls_maxfg=3)` — outer optimizer
  (L-BFGS; `tol` is the gradient-norm stop, `lbfgs_memory` the history size, `ls_*` line-search budgets).

### Observables & analysis

```julia
expectation_value(state, O::LocalOperator, env::CTMRGEnv)              # ⟨O⟩ = ⟨ψ|O|ψ⟩/⟨ψ|ψ⟩
expectation_value(Z::InfinitePartitionFunction, (i,j) => O, env)      # classical insertion at site (i,j)
expectation_value(bra, O::LocalOperator, ket, env::CTMRGEnv)          # bilayer / PEPO density-matrix form
expectation_value(mps, T)                                             # boundary-MPS network value
network_value(Z, env)                                                 # partition-function value per site (λ)
correlation_length(state, env::CTMRGEnv; num_vals=2) -> (ξ_h, ξ_v, λ_h, λ_v)   # from transfer spectrum
```
For optimization internals, the cost + reverse-mode gradient are computed inside `fixedpoint` (the energy is the
cost; its gradient w.r.t. PEPS tensors is obtained by differentiating through the converged CTMRG environment).

### Time evolution (simple update)

```julia
SimpleUpdate(; trunc, imaginary_time::Bool, force_3site::Bool, bipartite::Bool, purified::Bool)
TimeEvolver(psi0, H::LocalOperator, dt, nstep, alg::SimpleUpdate, env0::SUWeight; t0=0.0)
time_evolve(psi0, H, dt, nstep, alg, env0; tol=0.0, t0=0.0) -> (psi, env, info)
```
Trotter-based imaginary/real-time evolution of an InfinitePEPS/PEPO via simple update with bond weights.

---

## Worked examples (verbatim)

### 1. 2D classical Ising partition function — CTMRG

```julia
using Random, LinearAlgebra
using TensorKit, PEPSKit
using QuadGK
Random.seed!(234923);
```

Build the rank-4 local tensor `O(β)`, plus magnetization `M` and energy `E` insertion tensors:

```julia
function classical_ising(; beta = log(1 + sqrt(2)) / 2, J = 1.0)
    K = beta * J

    # Boltzmann weights
    t = ComplexF64[exp(K) exp(-K); exp(-K) exp(K)]
    r = eigen(t)
    nt = r.vectors * sqrt(Diagonal(r.values)) * r.vectors

    # local partition function tensor
    O = zeros(2, 2, 2, 2)
    O[1, 1, 1, 1] = 1
    O[2, 2, 2, 2] = 1
    @tensor o[-1 -2; -3 -4] := O[3 4; 2 1] * nt[-3; 3] * nt[-4; 4] * nt[-2; 2] * nt[-1; 1]

    # magnetization tensor
    M = copy(O)
    M[2, 2, 2, 2] *= -1
    @tensor m[-1 -2; -3 -4] := M[1 2; 3 4] * nt[-1; 1] * nt[-2; 2] * nt[-3; 3] * nt[-4; 4]

    # bond interaction tensor and energy-per-site tensor
    e = ComplexF64[-J J; J -J] .* nt
    @tensor e_hor[-1 -2; -3 -4] :=
        O[1 2; 3 4] * nt[-1; 1] * nt[-2; 2] * nt[-3; 3] * e[-4; 4]
    @tensor e_vert[-1 -2; -3 -4] :=
        O[1 2; 3 4] * nt[-1; 1] * nt[-2; 2] * e[-3; 3] * nt[-4; 4]
    e = e_hor + e_vert

    # fixed tensor map space for all three
    TMS = ℂ^2 ⊗ ℂ^2 ← ℂ^2 ⊗ ℂ^2

    return TensorMap(o, TMS), TensorMap(m, TMS), TensorMap(e, TMS)
end;
```

```julia
beta = 0.6
O, M, E = classical_ising(; beta)
@show space(O)
Z = InfinitePartitionFunction(O)
```

```julia
Venv = ℂ^20
env₀ = CTMRGEnv(Z, Venv)
env, = leading_boundary(env₀, Z; tol = 1.0e-8, maxiter = 500);
```

```julia
space.(env.edges)
```

```julia
λ = network_value(Z, env)
m = expectation_value(Z, (1, 1) => M, env)
e = expectation_value(Z, (1, 1) => E, env)
@show λ m e;
```

Exact Onsager solution for comparison:

```julia
function classical_ising_exact(; beta = log(1 + sqrt(2)) / 2, J = 1.0)
    K = beta * J

    k = 1 / sinh(2 * K)^2
    F = quadgk(
        theta -> log(cosh(2 * K)^2 + 1 / k * sqrt(1 + k^2 - 2 * k * cos(2 * theta))), 0, pi
    )[1]
    f = -1 / beta * (log(2) / 2 + 1 / (2 * pi) * F)

    m = 1 - (sinh(2 * K))^(-4) > 0 ? (1 - (sinh(2 * K))^(-4))^(1 / 8) : 0

    E = quadgk(theta -> 1 / sqrt(1 - (4 * k) * (1 + k)^(-2) * sin(theta)^2), 0, pi / 2)[1]
    e = -J * cosh(2 * K) / sinh(2 * K) * (1 + 2 / pi * (2 * tanh(2 * K)^2 - 1) * E)

    return f, m, e
end

f_exact, m_exact, e_exact = classical_ising_exact(; beta);
```

```julia
@show (-log(λ) / beta - f_exact) / f_exact
@show (abs(m) - abs(m_exact)) / abs(m_exact)
@show (e - e_exact) / e_exact;
```

Free energy and magnetization agree excellently with the exact solution; energy accuracy is limited by `χ_env`.
(Note: `β = log(1+√2)/2 ≈ 0.4407` is the critical point; the example runs at `β = 0.6`, in the ordered phase.)

### 2. 2D Heisenberg ground state — AD optimization

```julia
using Random
Random.seed!(123456789)

using TensorKit, PEPSKit
```

```julia
H = heisenberg_XYZ(InfiniteSquare(); Jx = -1, Jy = 1, Jz = -1)
```

```julia
Dbond = 2
χenv = 16

boundary_alg = (; tol = 1.0e-10, trunc = (; alg = :fixedspace))

optimizer_alg = (; alg = :lbfgs, tol = 1.0e-4, maxiter = 100, lbfgs_memory = 16)

reuse_env = true
verbosity = 3
```

```julia
peps₀ = InfinitePEPS(randn, ComplexF64, ℂ^2, ℂ^Dbond)

env_random = CTMRGEnv(randn, ComplexF64, peps₀, ℂ^χenv)
env₀, info_ctmrg = leading_boundary(env_random, peps₀; boundary_alg...)
```

```julia
peps, env, E, info_opt = fixedpoint(
    H, peps₀, env₀; boundary_alg, optimizer_alg, reuse_env, verbosity
)
```

Converges after ~81 iterations to **E = -0.6625142736962993**.

```julia
ξ_h, ξ_v, λ_h, λ_v = correlation_length(peps, env)

σ_z = TensorMap([1.0 0.0; 0.0 -1.0], ℂ^2, ℂ^2)
M = LocalOperator(fill(ℂ^2, 1, 1), (CartesianIndex(1, 1),) => σ_z)

expectation_value(peps, M, env)
```

Magnetization ⟨σ_z⟩ ≈ **-0.753**.

### 3. README quickstart (full PEPS workflow in ~10 lines)

```julia
using TensorKit, PEPSKit

# construct the Hamiltonian
H = heisenberg_XYZ(InfiniteSquare())

# configure the parameters
D = 2
χ = 20
ctmrg_tol = 1e-10
grad_tol = 1e-4

# initialize a PEPS and CTMRG environment
peps₀ = InfinitePEPS(ComplexSpace(2), ComplexSpace(D))
env₀, = leading_boundary(CTMRGEnv(peps₀, ComplexSpace(χ)), peps₀; tol=ctmrg_tol)

# ground state search
peps, env, E, = fixedpoint(H, peps₀, env₀; tol=grad_tol, boundary_alg=(; tol=ctmrg_tol))

@show E # -0.6625...
```

### 4. XXZ Néel order — U(1) symmetry + 2×2 unit cell + staggered charges

```julia
using Random
using TensorKit, PEPSKit
using MPSKit: add_physical_charge
Random.seed!(2928528935);
```

```julia
J = 1.0
Delta = 1.0
spin = 1 // 2
symmetry = U1Irrep
lattice = InfiniteSquare(2, 2)
H₀ = heisenberg_XXZ(ComplexF64, symmetry, lattice; J, Delta, spin);
```

```julia
S_aux = [
    U1Irrep(-1 // 2) U1Irrep(1 // 2)
    U1Irrep(1 // 2) U1Irrep(-1 // 2)
]
H = add_physical_charge(H₀, S_aux);
```

```julia
V_peps = U1Space(0 => 2, 1 => 1, -1 => 1)
V_env = U1Space(0 => 6, 1 => 4, -1 => 4, 2 => 2, -2 => 2)
virtual_spaces = fill(V_peps, size(lattice)...)
physical_spaces = physicalspace(H)
```

```julia
boundary_alg = (; tol = 1.0e-8, alg = :simultaneous, trunc = (; alg = :fixedspace))
gradient_alg = (; tol = 1.0e-6, alg = :eigsolver, maxiter = 10, iterscheme = :diffgauge)
optimizer_alg = (; tol = 1.0e-4, alg = :lbfgs, maxiter = 85, ls_maxiter = 3, ls_maxfg = 3)

peps₀ = InfinitePEPS(randn, ComplexF64, physical_spaces, virtual_spaces)
env₀, = leading_boundary(CTMRGEnv(peps₀, V_env), peps₀; boundary_alg...);

peps, env, E, info = fixedpoint(
    H, peps₀, env₀; boundary_alg, gradient_alg, optimizer_alg, verbosity = 3
)
@show E / prod(size(lattice));
```

E/site ≈ **-0.6689** (vs QMC -0.6694; the non-symmetric D=2 result is ≈ -0.6625). The staggered auxiliary charges
encode the two-sublattice Néel order into a U(1)-symmetric ansatz.

### 5. Fermi-Hubbard — fermionic (fℤ₂) ⊠ U(1) symmetry

```julia
using Random
using TensorKit, PEPSKit
using MPSKit: add_physical_charge
Random.seed!(2928528937);
```

```julia
t = 1.0
U = 8.0
lattice = InfiniteSquare(2, 2);
```

Combine fermion parity with particle number, then build symmetric virtual/env spaces at half filling:

```julia
fermion = fℤ₂
particle_symmetry = U1Irrep
spin_symmetry = Trivial
S = fermion ⊠ particle_symmetry
```

```julia
D, χ = 1, 1
V_peps = Vect[S]((0, 0) => 2 * D, (1, 1) => D, (1, -1) => D)
V_env = Vect[S](
    (0, 0) => 4 * χ, (1, -1) => 2 * χ, (1, 1) => 2 * χ, (0, 2) => χ, (0, -2) => χ
)
S_aux = S((1, 1))
H₀ = hubbard_model(ComplexF64, particle_symmetry, spin_symmetry, lattice; t, U)
H = add_physical_charge(H₀, fill(S_aux, size(H₀.lattice)...));
```

```julia
boundary_alg = (; tol = 1.0e-8, alg = :simultaneous, trunc = (; alg = :fixedspace))
gradient_alg = (; tol = 1.0e-6, alg = :eigsolver, maxiter = 10, iterscheme = :diffgauge)
optimizer_alg = (; tol = 1.0e-4, alg = :lbfgs, maxiter = 80, ls_maxiter = 3, ls_maxfg = 3)
```

```julia
physical_spaces = physicalspace(H)
virtual_spaces = fill(V_peps, size(lattice)...)
peps₀ = InfinitePEPS(randn, ComplexF64, physical_spaces, virtual_spaces)
env₀, = leading_boundary(CTMRGEnv(peps₀, V_env), peps₀; boundary_alg...);
```

```julia
peps, env, E, info = fixedpoint(
    H, peps₀, env₀; boundary_alg, gradient_alg, optimizer_alg, verbosity = 3
)
@show E;
```

```julia
E_ref = -2.09765625
@show (E - E_ref) / E_ref;
```

E ≈ **-2.071** (≈1.26% relative error vs Qin et al. benchmark). Fermionic tensors are handled automatically by
TensorKit once the physical space carries the `fℤ₂` sector.

### 6. Bose-Hubbard — U(1) symmetry, truncated bosons

```julia
t = 1.0
U = 30.0
cutoff = 2
mu = 0.0
lattice = InfiniteSquare(1, 1)

symmetry = U1Irrep
n = 1
H = bose_hubbard_model(ComplexF64, symmetry, lattice; cutoff, t, U, n)
```

```julia
V_peps = U1Space(0 => 2, 1 => 1, -1 => 1)
V_env = U1Space(0 => 6, 1 => 4, -1 => 4, 2 => 2, -2 => 2)
```

```julia
boundary_alg = (; tol = 1.0e-8, alg = :simultaneous, trunc = (; alg = :fixedspace))
gradient_alg = (; tol = 1.0e-6, maxiter = 10, alg = :eigsolver, iterscheme = :diffgauge)
optimizer_alg = (; tol = 1.0e-4, alg = :lbfgs, maxiter = 150, ls_maxiter = 2, ls_maxfg = 2)

peps, env, E, info = fixedpoint(H, peps₀, env₀; boundary_alg, gradient_alg, optimizer_alg)
```

`cutoff=2` caps bosons per site; `n=1` sets density 1 (Mott phase). E = **-0.2733** vs reference -0.273285.

### 7. Boundary MPS (VUMPS) contraction — alternative to CTMRG

```julia
using Random
Random.seed!(29384293742893)

using TensorKit, PEPSKit, MPSKit
```

```julia
ψ = InfinitePEPS(randn, ComplexF64, ComplexSpace(2), ComplexSpace(2))

dir = 1  # does not rotate the partition function
row = 1
T = InfiniteTransferPEPS(ψ, dir, row)
```

```julia
mps₀ = initialize_mps(T, [ComplexSpace(20)])

mps, env, ϵ = leading_boundary(mps₀, T, VUMPS(; tol = 1.0e-6, verbosity = 2))
```

```julia
norm_vumps = abs(prod(expectation_value(mps, T)))
```

Larger unit cells and PEPO overlaps:

```julia
ψ_2x2 = InfinitePEPS(rand, ComplexF64, ComplexSpace(2), ComplexSpace(2); unitcell = (2, 2))
T_2x2 = PEPSKit.MultilineTransferPEPS(ψ_2x2, dir)

mps₀_2x2 = initialize_mps(T_2x2, fill(ComplexSpace(20), 2, 2))
mps_2x2, = leading_boundary(mps₀_2x2, T_2x2, VUMPS(; tol = 1.0e-6, verbosity = 2))
norm_2x2_vumps = abs(prod(expectation_value(mps_2x2, T_2x2)))
```

```julia
transfer_pepo = InfiniteTransferPEPO(ψ, T, 1, 1)

mps₀_pepo = initialize_mps(transfer_pepo, [ComplexSpace(20)])
mps_pepo, = leading_boundary(mps₀_pepo, transfer_pepo, VUMPS(; tol = 1.0e-6, verbosity = 2))
norm_pepo = abs(prod(expectation_value(mps_pepo, transfer_pepo)))
```

---

## Pitfalls

- **PEPS bond dim `D` vs environment bond dim `χ_env` are independent.** `D` (the `Nspace` of `InfinitePEPS`) sets
  ansatz expressiveness; `χ_env` (the `Venv` of `CTMRGEnv`) sets contraction accuracy. A converged environment on
  an under-dimensioned PEPS is still wrong physics, and vice versa. Rule of thumb `χ_env ≳ D²`; always check the
  observable's stability as `χ_env` grows before trusting it.
- **CTMRG convergence.** Use `tol` ~ `1e-8` to `1e-10`. Near criticality the correlation length diverges, so
  `χ_env` must be large and `maxiter` increased (the Ising example uses `maxiter=500`) — a stuck residual usually
  means `χ_env` is too small, not that more iterations will help. Inspect the `info` from `leading_boundary`
  (truncation error, condition number, iterations) rather than assuming convergence.
- **Tighter CTMRG inside optimization than outside.** The inner `boundary_alg.tol` (e.g. `1e-10`) should be
  tighter than the outer `optimizer_alg.tol` (e.g. `1e-4`): a noisy energy/gradient from a loosely-converged
  environment derails L-BFGS.
- **Gradient/optimization stability.** The energy gradient is taken by differentiating through the CTMRG fixed
  point. Use `gradient_alg = (; alg=:eigsolver, iterscheme=:diffgauge)` — the gauge-fixed (`:diffgauge`) scheme is
  the robust default; AD without it can give wrong/unstable gradients because the fixed point is gauge-dependent.
  Keep `reuse_env=true` to warm-start environments across optimizer steps.
- **Random init → metastability.** Optimization from a random PEPS can land in a local minimum; restart with a
  different `Random.seed!`, raise `D`, or simple-update warm-start. Energies drifting up between iterations signal
  too-loose CTMRG, not a code bug.
- **Symmetry / ordered phases need the right unit cell + charges.** Néel/antiferromagnetic order needs
  `InfiniteSquare(2, 2)` plus staggered `add_physical_charge`; a 1×1 cell cannot represent two sublattices.
  Symmetric/fermionic spaces must list every sector with adequate degeneracy in *both* `V_peps` and `V_env`,
  or charge sectors get silently truncated. Fermionic models require the `fℤ₂` sector in the physical space.
- **`χ`/`D=1` examples are illustrative only.** The Fermi-Hubbard example runs at `D=χ=1` (multiplied by sector
  degeneracies) for speed; real calculations need substantially larger bond dimensions.

---

## Source links

- Docs index: <https://quantumkithub.github.io/PEPSKit.jl/stable/>
- API / library reference: <https://quantumkithub.github.io/PEPSKit.jl/stable/lib/lib/>
- Models manual: <https://quantumkithub.github.io/PEPSKit.jl/stable/man/models/>
- Multithreading: <https://quantumkithub.github.io/PEPSKit.jl/stable/man/multithreading/>
- Precompilation: <https://quantumkithub.github.io/PEPSKit.jl/stable/man/precompilation/>
- Example — 2D Ising partition function: <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/2d_ising_partition_function/>
- Example — 3D Ising partition function: <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/3d_ising_partition_function/>
- Example — Heisenberg ground state: <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/heisenberg/>
- Example — XXZ Néel order (U(1)): <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/xxz/>
- Example — Bose-Hubbard (U(1)): <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/bose_hubbard/>
- Example — Fermi-Hubbard (fℤ₂ ⊠ U(1)): <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/fermi_hubbard/>
- Example — Boundary MPS (VUMPS): <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/boundary_mps/>
- Time-evolution examples — heisenberg_su / hubbard_su / j1j2_su: <https://quantumkithub.github.io/PEPSKit.jl/stable/examples/>
- Repository: <https://github.com/QuantumKitHub/PEPSKit.jl>
- Examples folder: <https://github.com/QuantumKitHub/PEPSKit.jl/tree/main/examples>
