# MPSKit.jl + MPSKitModels.jl + TensorKit.jl — API & Examples Reference

Compact usage reference for the canonical Julia MPS stack:

- **TensorKit.jl** — symmetric tensors (`TensorMap`) and the vector-space / symmetry-sector layer everything else builds on.
- **MPSKitModels.jl** — ready-made lattice Hamiltonians and local operators.
- **MPSKit.jl** — MPS states, MPO Hamiltonians, and algorithms (DMRG, VUMPS, IDMRG, TDVP, quasiparticle excitations).

Conventions used below: `ℂ^n` is `ComplexSpace(n)`; `←` separates codomain ← domain of a `TensorMap`; `⊗` is tensor product, `⊕` direct sum, `'` adjoint/dual. Spin operators `S_x, S_z, …` come from MPSKitModels. There is **no TEBD** in MPSKit — for iTEBD use TeNPy. Source URLs are listed at the end.

---

## 1. TensorKit — vector spaces & symmetry sectors

The symmetry choice is made *through the spaces* you hand to MPS/MPO constructors. A space is either trivial (`ComplexSpace`) or graded by a symmetry sector (`GradedSpace` via `Rep[G]` / `Vect[I]`).

### Elementary spaces

```julia
ℂ^d                  # ComplexSpace(d), the no-symmetry virtual/physical space
ComplexSpace(d)      # same
ComplexSpace(d; dual=true) == (ℂ^d)'   # dual space
ℝ^d                  # CartesianSpace(d) (real Euclidean)
```

Helpers (work on any space `V` and product space `P = V1 ⊗ V2`):

```julia
dim(V)            # total dimension
dims(V1 ⊗ V2)     # tuple of per-factor dims
field(V)          # underlying field (ℂ or ℝ)
V'                # dual; == dual(V) == conj(V) for ℂ
isdual((ℂ^5)')    # true
V1 ⊗ V2 ⊗ V1'     # fusion (== V1 * V2 * V1'); V1^3 repeats
V1 ⊕ V2           # direct sum
one(V)            # monoidal unit (ProductSpace{S,0}), neutral for ⊗
```

### Symmetry sectors

A `Sector` is an irrep of a symmetry group. Built-ins (concrete type via `Irrep[G]`):

| Sector | Group | Notes / label type |
|---|---|---|
| `Trivial` | none | no symmetry |
| `Z2Irrep` (`= ZNIrrep{2}`) | ℤ₂ | `Irrep[ℤ₂]`, labels `0,1` |
| `ZNIrrep{N}` | ℤ_N | `Irrep[ℤ₃]`, … |
| `U1Irrep` | U(1) | `Irrep[U₁]`, integer/half-integer charge |
| `SU2Irrep` | SU(2) | `Irrep[SU₂]`, spin-j label `0, 1//2, 1, …`; non-abelian |
| `FermionParity` (`fℤ₂`) | ℤ₂-graded | fermionic braiding (twist ±1) |

```julia
SU2Irrep(3//2)              # spin-3/2 irrep; dim = 4
U1Irrep(1) ⊗ Irrep[U₁](1//2)   # fusion (abelian → unique)
collect(SU2Irrep(1//2) ⊗ SU2Irrep(1//2))   # → spins 0 and 1
a = Z3Irrep(1) ⊠ Irrep[U₁](1)   # ⊠ = direct-product sector (ℤ₃ × U₁)
```

### Graded spaces (sector ⇒ multiplicity)

`Rep[G]` and `Vect[I]` are aliases; the arrow pairs map each sector to its degeneracy (block size). Convenience aliases: `U1Space`, `Z2Space`, `SU2Space`.

```julia
Vect[U1Irrep](0=>2, 1=>1)        # charge-0 block dim 2, charge-1 block dim 1
U1Space(0=>2, 1=>1)              # same
Rep[U₁](0=>2, 1=>1, -1=>1)
Rep[ℤ₂](0=>3, 1=>2)
Rep[SU₂](0=>1, 1//2=>1)         # 1 singlet + 1 doublet (dim 1+2 = 3)
SU2Space(0=>3, 1=>2)
```

A graded space's `dim` counts the *true* dimension (multiplicity × irrep dim): `dim(Rep[SU₂](1//2=>1)) == 2`.

### TensorMap (manual operators)

```julia
S_x = TensorMap(ComplexF64[0 1; 1 0], ℂ^2 ← ℂ^2)   # 1-site operator
S_z = TensorMap(ComplexF64[1 0; 0 -1], ℂ^2 ← ℂ^2)
rand(ComplexF64, ℂ^1 ⊗ ℂ^2 ← ℂ^1)                  # an MPS site tensor (Dl ⊗ d ← Dr)
```

---

## 2. State construction (MPSKit)

### FiniteMPS

```julia
# Structure spec (random init): (rng/init, eltype, L, physical_space, max_bond_space)
state = FiniteMPS(rand, ComplexF64, L, ℂ^2, ℂ^4)
state = FiniteMPS(L, ℂ^2, ℂ^32)            # shorthand; integers also accepted: FiniteMPS(L, 2, 32)

# From explicit site tensors
data  = [rand(ComplexF64, ℂ^1 ⊗ ℂ^2 ← ℂ^1) for _ in 1:L]
state = FiniteMPS(data)

# Symmetric: pass graded spaces
ψ = FiniteMPS(L, SU2Space(1=>1), SU2Space(0=>12, 1=>12, 2=>5, 3=>3))

# Window edge bond spaces (for WindowMPS)
FiniteMPS(5, ℂ^2, ℂ^4; left=ℂ^4, right=ℂ^4)
```

Gauge forms (auto-cached, recomputed on indexed assignment): `ψ.AL[i]` left-iso, `ψ.AR[i]` right-iso, `ψ.C[i]` bond/center matrix right of site i, `ψ.AC[i] == AL*C`.

### InfiniteMPS (uniform / unit cell)

```julia
# From spaces (one entry per site in the unit cell)
state = InfiniteMPS(ℂ^2, ℂ^4)                       # 1-site cell, d=2, D=4
state = InfiniteMPS([ℂ^2, ℂ^2], [ℂ^4, ℂ^5])         # 2-site cell
state = InfiniteMPS(fill(2, 2), fill(20, 2))         # integer shorthand: 2 sites, d=2, D=20
state = InfiniteMPS(2, 20)                           # shorthand 1-site

# Symmetric: graded physical + virtual spaces, one per cell site
P  = Rep[SU₂](1//2 => 1)
V1 = Rep[SU₂](1//2 => 10, 3//2 => 5, 5//2 => 2)
V2 = Rep[SU₂](0 => 15, 1 => 10, 2 => 5)
state = InfiniteMPS([P, P], [V1, V2])

# From explicit tensors
data  = [rand(ComplexF64, ℂ^4 ⊗ ℂ^2 ← ℂ^4) for _ in 1:2]
state = InfiniteMPS(data)
```

Gauge forms are `PeriodicArray`s (`ψ.AL`, `ψ.AR`, `ψ.C`, `ψ.AC`); changing one tensor recomputes the cell.

### WindowMPS / MultilineMPS

```julia
inf = InfiniteMPS(ℂ^2, ℂ^4)
fin = FiniteMPS(5, ℂ^2, ℂ^4; left=ℂ^4, right=ℂ^4)
win = WindowMPS(inf, fin, inf)              # finite window in infinite bath
ml  = MultilineMPS(fill(inf, 2))            # 2D partition-function rows (PEPSKit)
```

> **Bond dimension is set by the virtual space**, never a separate argument: `ℂ^D` (no symmetry) or a graded space whose multiplicities sum to D (symmetric). To grow D mid-run use `changebonds(ψ, H, OptimalExpand(; trscheme=truncrank(k)), envs)`.

---

## 3. Hamiltonians

### From MPSKitModels (preferred)

Common signature shape: `model([elt], [symmetry], [lattice]; kwargs...)`. Defaults: `elt = ComplexF64`, `symmetry = Trivial`, `lattice = InfiniteChain(1)`. Lattices: `InfiniteChain(L)`, `FiniteChain(L)`, plus 2D lattices (see MPSKitModels lattices page).

| Function | Signature | Key kwargs |
|---|---|---|
| `transverse_field_ising` | `(elt, sym, lattice)` | `J=1.0, g=1.0` — sym ∈ `Trivial, Z2Irrep, FermionParity` |
| `quantum_potts` | `(elt, sym, lattice)` | `q=3, J=1.0, g=1.0` |
| `kitaev_model` | `(elt, lattice)` | `t=1.0, mu=1.0, Delta=1.0` |
| `heisenberg_XXX` | `(elt, sym, lattice)` | `J=1.0, spin=1` — sym ∈ `Trivial, U1Irrep, SU2Irrep` |
| `heisenberg_XXZ` | `(elt, sym, lattice)` | `J=1.0, Delta=1.0, spin=1` |
| `heisenberg_XYZ` | `(elt, lattice)` | `Jx=1.0, Jy=1.0, Jz=1.0, spin=1` (no symmetry arg) |
| `bilinear_biquadratic_model` | `(elt, sym, lattice)` | `spin=1, J=1.0, θ=0.0` |
| `hubbard_model` | `(elt, particle_sym, spin_sym, lattice)` | `t, U, mu, n` |
| `bose_hubbard_model` | `(elt, sym, lattice)` | `cutoff, t, U, mu, n` |
| `tj_model` | `(elt, particle_sym, spin_sym, lattice)` | `t, J, mu, slave_fermion=false` |
| `quantum_chemistry_hamiltonian` | `(E0, K, V, [elt])` | one- (`K`) and two-body (`V`) integrals |
| `ashkin_teller` | `(T, S, lattice)` | `h=1.0, J=1.0, λ=1.0` |

2D statistical-mechanics transfer operators: `classical_ising(; beta=log(1+√2)/2)`, `sixvertex(; a, b, c)`, `hard_hexagon()`, `qstate_clock(; beta, q)`.

```julia
H  = transverse_field_ising(FiniteChain(16); g=10.0)
H  = heisenberg_XXX(ComplexF64, SU2Irrep, InfiniteChain(2); spin=1//2)
H  = heisenberg_XXZ(ComplexF64, Trivial, InfiniteChain(2); spin=1//2, Delta=2.0)
```

### Manual MPOHamiltonian

`FiniteMPOHamiltonian` / `InfiniteMPOHamiltonian` take a vector of local physical spaces plus `inds => operator` pairs (`inds` is a tuple of sites; single ints allowed).

```julia
chain = fill(ℂ^2, 3)
H = FiniteMPOHamiltonian(chain,
        1 => -h*S_z, 2 => -h*S_z, 3 => -h*S_z,
        (1,2) => -J*S_x⊗S_x, (2,3) => -J*S_x⊗S_x)

# Generator form (composes with +, -, scalar *)
H = -J * FiniteMPOHamiltonian(chain, (i,i+1) => S_x⊗S_x for i in 1:length(chain)-1) -
     h * FiniteMPOHamiltonian(chain, i => S_z for i in 1:length(chain))

# Infinite: give one unit cell, list interactions reaching across the boundary
H∞ = InfiniteMPOHamiltonian(PeriodicVector([ℂ^2]),
        1 => -h*S_z, (1,2) => -J*S_x⊗S_x)
```

2D: build local / horizontal / vertical `Dict`s over a `fill(ℂ^2, Lx, Ly)` array (Cartesian indices) and add the three `FiniteMPOHamiltonian`s. Non-Hamiltonian MPOs: `FiniteMPO(S_x⊗S_z⊗S_x)`, `InfiniteMPO(tensorvec)`.

---

## 4. Ground state — `find_groundstate`

```julia
find_groundstate(ψ₀, H, [environments]; tol, maxiter, verbosity) -> (ψ, environments, ϵ)
find_groundstate(ψ₀, H, algorithm, [environments])              -> (ψ, environments, ϵ)
```

`ϵ` is the final convergence error. With no algorithm, a sensible default is chosen by state type (VUMPS for infinite, DMRG for finite).

### Algorithms and key knobs

| Algorithm | Use | Key fields/kwargs |
|---|---|---|
| `DMRG(; tol, maxiter, verbosity, alg_eigsolve, finalize)` | finite, single-site | gold standard for `FiniteMPS` |
| `DMRG2(; …, alg_svd, trscheme)` | finite, two-site | grows bond dim adaptively via `trscheme` |
| `VUMPS(; tol, maxiter, verbosity, alg_gauge, alg_eigsolve, alg_environments, finalize)` | infinite | default infinite ground state |
| `IDMRG(; tol, maxiter, verbosity, alg_gauge, alg_eigsolve)` | infinite, single-site | DMRG-style infinite |
| `IDMRG2(; …, alg_svd, trscheme)` | infinite, two-site | adaptive infinite bond dim |
| `GradientGrassmann(; method=ConjugateGradient, tol, maxiter, verbosity, finalize!)` | finite/infinite | Riemannian gradient descent |

- `tol` — convergence target (≈ `1e-10…1e-12`). For VUMPS/IDMRG this is the tangent-space gradient norm.
- `maxiter` — iteration cap; `tol` should fire first.
- `trscheme` (two-site algos) — `TruncationScheme`: `truncrank(D)` (keep D values), `truncerr(ε)` (discard weight ≤ ε), `truncbelow(σ)`, combinable with `&`. This is how D grows in `DMRG2`/`IDMRG2`/`TDVP2`.
- `finalize(iter, ψ, H, envs) -> (ψ, envs)` — per-iteration callback (VUMPS/DMRG/TDVP) for logging trajectories. **IDMRG has no `finalize`** — iterate `MPSKit.IterativeSolver(IDMRG(...), state)` instead.

```julia
ψ, envs, ϵ = find_groundstate(ψ₀, H, VUMPS(; maxiter=100, tol=1e-12))
ψ, envs, ϵ = find_groundstate(ψ₀, H, DMRG2(; trscheme=truncrank(200)))
ψ, envs, ϵ = find_groundstate(ψ₀, H, IDMRG2(; trscheme=truncrank(50), maxiter=20, tol=1e-12))
```

---

## 5. Time evolution

```julia
timestep(ψ, H, t, dt, [alg], [envs]; imaginary_evolution=false) -> (ψ, envs)
timestep!(ψ, H, t, dt, [alg], [envs]; …)                        -> (ψ, envs)   # in-place
time_evolve(ψ, H, t_span, [alg], [envs]; verbosity=0, imaginary_evolution=false)
make_time_mpo(H::MPOHamiltonian, dt, alg; imaginary_evolution=false) -> MPO    # ≈ exp(-iH·dt)
```

Algorithms:

- `TDVP(; integrator, tolgauge, gaugemaxiter, finalize)` — single-site (bond dim fixed).
- `TDVP2(; …, alg_svd, trscheme)` — two-site, **grows bond dim** via `trscheme` (use early in a quench, then switch to `TDVP`).
- MPO-evolution orders for `make_time_mpo`: `WI` (1st-order Taylor), `WII` (Euler generalization), `TaylorCluster(; N, extension, compression)`.

Imaginary time (`dt = -im*β`, or `imaginary_evolution=true`) gives finite-T / ground-state cooling.

```julia
ψₜ, envs = timestep(ψₜ, H₁, 0, 0.01, TDVP2(; trscheme=truncrank(20)))
# typical quench: two-site early, single-site once bond dim saturates
alg = t > 3dt ? TDVP() : TDVP2(; trscheme=truncrank(50))
ψₜ, envs = timestep(ψₜ, H₁, 0, dt, alg, envs)
```

---

## 6. Excitations / gaps — `excitations`

```julia
excitations(H, alg, ψ, [envs]; num=1, sector=…)              # finite, FiniteQP / FiniteExcited
excitations(H, alg, momentum, ψ, [envs]; num, sector)        # infinite, single momentum
excitations(H, alg, kspace, ψ, [envs]; num, sector)          # infinite, momentum scan
-> (energies, states)
```

- `alg = QuasiparticleAnsatz()` — topologically-trivial single-mode excitations (the standard gap tool). `FiniteExcited(; gsalg, weight)` minimizes `H − λᵢ|ψᵢ⟩⟨ψᵢ|` for finite excited states; `ChepigaAnsatz()` / `ChepigaAnsatz2()` exploit long-range correlations in critical chains.
- `num` — number of states; `sector` — charge/spin sector of the excitation (e.g. `SU2Irrep(1)` for a triplet); `momentum`/`kspace` — quasimomentum for infinite systems.

```julia
# Finite Ising gap (≈ 2(g-1))
H = transverse_field_ising(FiniteChain(16); g=10.0)
ψ, = find_groundstate(FiniteMPS(16, ℂ^2, ℂ^32), H; verbosity=0)
Es, ϕs = excitations(H, QuasiparticleAnsatz(), ψ; num=1)

# Infinite Heisenberg, single momentum
H = heisenberg_XXX()
ψ, = find_groundstate(InfiniteMPS(ℂ^3, ℂ^48), H; verbosity=0)
Es, ϕs = excitations(H, QuasiparticleAnsatz(), π, ψ)   # Es[1] ≈ 0.41047925
```

---

## 7. Observables & diagnostics

```julia
expectation_value(ψ, O, [envs])         # ⟨ψ|O|ψ⟩ for an MPO/Hamiltonian (per-site for ∞)
expectation_value(ψ, inds => O)         # local operator at site(s) inds
correlator(ψ, O1, O2, i, j)             # ⟨O1[i] O2[j]⟩ two-point function
entanglement_spectrum(ψ, site)          # singular values of bond matrix (SectorVector)
entropy(ψ, [site])                      # von Neumann entanglement entropy
entropy(spectrum)                       # from an entanglement_spectrum
correlation_length(ψ::InfiniteMPS)      # from next-to-leading transfer eigenvalue
marek_gap(ψ::InfiniteMPS)               # transfer-matrix gap / finite-entanglement scale
transfer_spectrum(ψ)                    # transfer-matrix eigenvalues
calc_galerkin(pos, below, H, above, envs)  # tangent-space (Galerkin) gradient at a site
physicalspace(ψ, [pos]); left_virtualspace(ψ, [pos]); right_virtualspace(ψ, [pos])
```

Energy per site (infinite) and total energy (finite):

```julia
e_site = real(expectation_value(ψ, H)) / length(ψ)        # InfiniteMPS
E₀     = real(expectation_value(ψ, H))                    # FiniteMPS (already a sum)
```

Tangent-space gradient norm ‖B‖ (the VUMPS/IDMRG convergence probe — converge on this, not energy):

```julia
bnorm = sqrt(sum(abs2(MPSKit.calc_galerkin(pos, ψ, H, ψ, envs)) for pos in 1:length(ψ)) / length(ψ))
```

---

## 8. Worked examples (verbatim from docs)

### 8.1 Infinite XXZ / Heisenberg ground state (VUMPS)

```julia
using MPSKit, MPSKitModels, TensorKit, Plots

H = heisenberg_XXX(; spin = 1 // 2)
state = InfiniteMPS(2, 20)
groundstate, cache, delta = find_groundstate(state, H, VUMPS())
```

Two-site cell (better convergence):

```julia
state = InfiniteMPS(fill(2, 2), fill(20, 2))
H2 = heisenberg_XXX(ComplexF64, Trivial, InfiniteChain(2); spin = 1 // 2)
groundstate, envs, delta = find_groundstate(
    state, H2, VUMPS(; maxiter = 100, tol = 1.0e-12)
)
```

### 8.2 SU(2)-symmetric infinite state (fastest)

```julia
H2 = heisenberg_XXX(ComplexF64, SU2Irrep, InfiniteChain(2); spin = 1 // 2)

P = Rep[SU₂](1 // 2 => 1)
V1 = Rep[SU₂](1 // 2 => 10, 3 // 2 => 5, 5 // 2 => 2)
V2 = Rep[SU₂](0 => 15, 1 => 10, 2 => 5)
state = InfiniteMPS([P, P], [V1, V2])

groundstate, cache, delta = find_groundstate(
    state, H2, VUMPS(; maxiter = 400, tol = 1.0e-12)
)
```

IDMRG2 with explicit truncation (controls infinite bond dim):

```julia
groundstate, envs, delta = find_groundstate(
    state, H2, IDMRG2(; trscheme = truncrank(50), maxiter = 20, tol = 1.0e-12)
)
entanglementplot(groundstate)
transferplot(groundstate, groundstate)
```

### 8.3 Finite DMRG ground state + gap (Haldane, SU(2))

```julia
L = 11
chain = FiniteChain(L)
H = heisenberg_XXX(symmetry, chain; J, spin)

physical_space = SU2Space(1 => 1)
virtual_space = SU2Space(0 => 12, 1 => 12, 2 => 5, 3 => 3)
ψ₀ = FiniteMPS(L, physical_space, virtual_space)
ψ, envs, delta = find_groundstate(ψ₀, H, DMRG(; verbosity = 0))
E₀ = real(expectation_value(ψ, H))
En_1, st_1 = excitations(H, QuasiparticleAnsatz(), ψ, envs; sector = SU2Irrep(1))
En_2, st_2 = excitations(H, QuasiparticleAnsatz(), ψ, envs; sector = SU2Irrep(2))
ΔE_finite = real(En_2[1] - En_1[1])
```

Thermodynamic-limit Haldane gap (VUMPS + momentum scan):

```julia
chain = InfiniteChain(1)
H = heisenberg_XXX(symmetry, chain; J, spin)
virtual_space_inf = Rep[SU₂](1 // 2 => 16, 3 // 2 => 16, 5 // 2 => 8, 7 // 2 => 4)
ψ₀_inf = InfiniteMPS([physical_space], [virtual_space_inf])
ψ_inf, envs_inf, delta_inf = find_groundstate(ψ₀_inf, H; verbosity = 0)

kspace = range(0, π, 16)
Es, _ = excitations(H, QuasiparticleAnsatz(), kspace, ψ_inf, envs_inf; sector = SU2Irrep(1))

ΔE, idx = findmin(real.(Es))
println("minimum @k = $(kspace[idx]):\t ΔE = $(ΔE)")
```

### 8.4 Finite excitation (quasiparticle gap, Ising)

```julia
g = 10.0
L = 16
H = transverse_field_ising(FiniteChain(L); g)
ψ₀ = FiniteMPS(L, ℂ^2, ℂ^32)
ψ, = find_groundstate(ψ₀, H; verbosity=0)
Es, ϕs = excitations(H, QuasiparticleAnsatz(), ψ; num=1)
isapprox(Es[1], 2(g - 1); rtol=1e-2)
```

### 8.5 TDVP time evolution (finite Ising quench, Loschmidt echo)

```julia
function finite_sim(L; dt = 0.05, finaltime = 5.0)
    ψ₀ = FiniteMPS(L, ℂ^2, ℂ^10)
    H₀ = transverse_field_ising(FiniteChain(L); g = -0.5)
    ψ₀, _ = find_groundstate(ψ₀, H₀, DMRG())

    H₁ = transverse_field_ising(FiniteChain(L); g = -2.0)
    ψₜ = deepcopy(ψ₀)
    envs = environments(ψₜ, H₁)

    echos = [echo(ψₜ, ψ₀)]
    times = collect(0:dt:finaltime)

    for t in times[2:end]
        alg = t > 3 * dt ? TDVP() : TDVP2(; trscheme = truncrank(50))
        ψₜ, envs = timestep(ψₜ, H₁, 0, dt, alg, envs)
        push!(echos, echo(ψₜ, ψ₀))
    end

    return times, echos
end
```

Infinite version (bond growth via `changebonds` early in the quench):

```julia
function infinite_sim(dt = 0.05, finaltime = 5.0)
    ψ₀ = InfiniteMPS([ℂ^2], [ℂ^10])
    ψ₀, _ = find_groundstate(ψ₀, H₀, VUMPS())

    ψₜ = deepcopy(ψ₀)
    envs = environments(ψₜ, H₁)

    echos = [echo(ψₜ, ψ₀)]
    times = collect(0:dt:finaltime)

    for t in times[2:end]
        if t < 50dt
            ψₜ, envs = changebonds(ψₜ, H₁, OptimalExpand(; trscheme = truncrank(1)), envs)
        end
        ψₜ, envs = timestep(ψₜ, H₁, 0, dt, TDVP(), envs)
        push!(echos, echo(ψₜ, ψ₀))
    end

    return times, echos
end
```

### 8.6 Manual MPO Hamiltonian (transverse-field Ising)

```julia
J = 1.0
h = 0.5
chain = fill(ℂ^2, 3)
H_ising = FiniteMPOHamiltonian(chain,
    1 => -h * S_z, 2 => -h * S_z, 3 => -h * S_z,
    (1, 2) => -J * S_x ⊗ S_x, (2, 3) => -J * S_x ⊗ S_x)

# Infinite, one unit cell:
H_ising_infinite = InfiniteMPOHamiltonian(PeriodicVector([ℂ^2]),
    1 => -h * S_z, (1, 2) => -J * S_x ⊗ S_x)
```

---

## 9. Pitfalls

- **Bond dimension lives in the virtual space, not a number.** No-symmetry → `ℂ^D`. Symmetric → a graded space whose block multiplicities *sum* to the target D; the distribution across sectors matters for accuracy, so seed generously in the dominant sectors. Use `dim(V)` to read off the real D.
- **Symmetry must match across H, physical space, and virtual space.** A `Trivial` Hamiltonian with `SU2Space` virtuals (or vice versa) errors or silently mis-sectors. Pass the same `symmetry` positional arg to the model and build spaces with the matching `Rep[G]`. Note `heisenberg_XYZ` and `kitaev_model` take **no symmetry argument**.
- **Infinite vs finite is a different state/algorithm family.** `InfiniteMPS` + `VUMPS`/`IDMRG`; `FiniteMPS` + `DMRG`. `expectation_value(ψ, H)` is **per-site-aware**: divide by `length(ψ)` for the infinite energy density; the finite result is already the total. Don't mix.
- **Unit-cell length must hold the order period.** 1-site cell for uniform/Haldane; ≥2-site for Néel/AFM order. A sublattice rotation can fold a 2-site AFM state into a 1-site cell.
- **Converge on the gradient norm ‖B‖ (`calc_galerkin`), not the energy** — energy plateaus long before the state does. Hitting `maxiter` means *not converged*.
- **Single-site algorithms (DMRG/VUMPS/IDMRG/TDVP) keep bond dim fixed.** To grow D use the two-site variants (`DMRG2`/`IDMRG2`/`TDVP2`) with a `trscheme`, or `changebonds(...; OptimalExpand)`. `truncrank(D)` caps the rank; `truncerr(ε)` caps discarded weight — pick the one the paper specifies.
- **IDMRG has no `finalize` callback** — for per-iteration logging iterate `MPSKit.IterativeSolver(IDMRG(...), state)` instead of relying on a callback.
- **No TEBD in MPSKit.** Real/imaginary-time evolution is TDVP (or `make_time_mpo` with `WI`/`WII`/`TaylorCluster`). For iTEBD, use TeNPy.
- **TensorKit docs:** the `stable` deep-link subpages may 404 in a raw fetch; the canonical sources are the GitHub markdown and the `dev`/`latest` doc trees (links below).

---

## 10. Source links

MPSKit.jl:
- Home / manual index: https://quantumkithub.github.io/MPSKit.jl/stable/
- States: https://quantumkithub.github.io/MPSKit.jl/stable/man/states/
- Operators (MPOHamiltonian): https://quantumkithub.github.io/MPSKit.jl/stable/man/operators/
- Algorithms (find_groundstate, DMRG/VUMPS/IDMRG/TDVP, excitations): https://quantumkithub.github.io/MPSKit.jl/stable/man/algorithms/
- Library reference: https://quantumkithub.github.io/MPSKit.jl/stable/lib/lib/
- Examples — XXZ: https://quantumkithub.github.io/MPSKit.jl/stable/examples/quantum1d/4.xxz-heisenberg/
- Examples — Haldane gap: https://quantumkithub.github.io/MPSKit.jl/stable/examples/quantum1d/2.haldane/
- Examples — Ising DQPT (time evolution): https://quantumkithub.github.io/MPSKit.jl/stable/examples/quantum1d/3.ising-dqpt/

MPSKitModels.jl:
- Home: https://quantumkithub.github.io/MPSKitModels.jl/stable/
- Models (Hamiltonians): https://quantumkithub.github.io/MPSKitModels.jl/stable/man/models/
- Operators: https://quantumkithub.github.io/MPSKitModels.jl/stable/man/operators/
- @mpoham macro: https://quantumkithub.github.io/MPSKitModels.jl/stable/man/mpoham/
- Lattices: https://quantumkithub.github.io/MPSKitModels.jl/stable/man/lattices/

TensorKit.jl:
- Home: https://jutho.github.io/TensorKit.jl/stable/
- Vector spaces: https://jutho.github.io/TensorKit.jl/dev/man/spaces/ (source: https://github.com/Jutho/TensorKit.jl/blob/master/docs/src/man/spaces.md)
- Sectors / graded spaces: https://jutho.github.io/TensorKit.jl/dev/man/sectors/ (source: https://github.com/Jutho/TensorKit.jl/blob/master/docs/src/man/sectors.md)
- Tutorial: https://github.com/Jutho/TensorKit.jl/blob/master/docs/src/man/tutorial.md
