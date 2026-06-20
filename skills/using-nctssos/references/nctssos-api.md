# NCTSSoS.jl — API & Examples Reference

Distilled API + worked-example reference for **NCTSSoS.jl**, the Julia package for
sparse **noncommutative polynomial optimization** (NC polyopt) via the structured
**moment / sum-of-Hermitian-squares (SOHS) hierarchy**. Successor to NCTSSOS.
Author: Jie Wang et al. License: MIT. Solved with any JuMP-compatible SDP backend
(Clarabel — open-source default here; Mosek — faster, academic license; COSMO).

> Verified against the `dev` docs and the `master` source (June 2026). The docs
> site is rich (Quick Start + 10 manual pages + ~25 examples + 4 API pages); this
> reference is **high-confidence** for the public API. A few internal helpers
> (`moment_relax`, `solve_moment_problem`, `hankel_matrix`) are `NCTSSoS.`-qualified
> non-exported names used in the GNS example and are flagged as such below.

## What problem it solves

Given a polynomial `f` in **non-commuting** operator variables (matrices /
operators on a Hilbert space), compute a **certified lower bound** on either:

- the **minimum eigenvalue** `λ_min(f)` (eigenvalue / ground-state-energy problem), or
- the **minimum trace** `tr(f)` (tracial problem),

subject to operator inequality (`gᵢ(x) ⪰ 0`) and equality (`hⱼ(x) = 0`) constraints.
The method builds a hierarchy of SDP relaxations indexed by **order** `d`; the
optimal value of each SDP is a **lower bound** on the true optimum, monotonically
tightening as `d` (and the term-sparsity refinement `k`) increase. This is the
operator-algebraic generalization of Lasserre's moment-SOS hierarchy — the NPA
hierarchy for quantum bounds is the Bell/dichotomic special case.

Typical uses: ground-state energy lower bounds for spin/fermionic/bosonic
Hamiltonians, Bell-inequality (e.g. CHSH → Tsirelson) maxima, trace/state-polynomial
optimization, and **GNS reconstruction** of the optimal operators + state when the
relaxation is exact (flat).

## Links

- Docs (dev): https://quantumsos.github.io/NCTSSoS.jl/dev/
- Repo: https://github.com/QuantumSOS/NCTSSoS.jl
- Solver (Clarabel): https://github.com/oxfordcontrol/Clarabel.jl  ·  settings: http://clarabel.org/stable/api_settings/
- Install: `pkg> add NCTSSoS` (stable) or `add NCTSSoS#main` (dev). In this harness: `make install nctssos`.
- Smoke: `julia --project=julia-env -e 'using NCTSSoS, Clarabel'`

---

## Workflow at a glance

```
create_*_variables(...)        →  registry + operator vectors
   build objective `f` (and constraints) from those operators
polyopt(f, registry; eq_constraints, ineq_constraints, moment_eq_constraints)
   →  PolyOpt
SolverConfig(; optimizer, order, cs_algo, ts_algo, symmetry, moment_basis)
cs_nctssos(pop, config)        →  PolyOptResult ; result.objective is the bound
   [optional] cs_nctssos_higher(pop, result, config)   # refine term sparsity
   [optional] gns_reconstruct(...) + test_flatness(...) # recover operators/state
```

---

## Key API

### 1. Declaring non-commuting variables

One constructor per algebra. Each returns `(registry, (op_vectors...))`. The
registry tracks symbols/indices; the operator vectors are indexed `op[i]`.
Variables in **separate label groups commute**; variables in one shared group do not.

| Algebra | Constructor | Enforces |
|---|---|---|
| Pauli (spin-½) | `create_pauli_variables(subscripts)` → `(σx, σy, σz)` | `σ²=1`, `σx·σy=i·σz`; **needs `ComplexF64` coefficients** |
| Fermionic (CAR) | `create_fermionic_variables(subscripts)` → `(a, a_dag)` | `{aᵢ,aⱼ†}=δᵢⱼ`, `{aᵢ,aⱼ}=0` |
| Bosonic (CCR) | `create_bosonic_variables(subscripts)` → `(a, a_dag)` | `[aᵢ,aⱼ†]=δᵢⱼ` (∞-dim) |
| Unipotent (±1 observables) | `create_unipotent_variables([("A",1:2),("B",1:2)])` | `U²=I`; no cross rules |
| Projector (projective meas.) | `create_projector_variables([("P",1:3)])` | `P²=P` |
| Free noncommutative | `create_noncommutative_variables([("x",1:n)])` | none; add ball/relations via `ineq_constraints` |

```julia
# two equivalent calling forms
registry, (σx, σy, σz) = create_pauli_variables(1:N)              # integer subscripts
registry, (x, y)       = create_unipotent_variables([("x",1:2),("y",1:2)])  # prefixed groups
```

Coefficient type defaults to `coeff_type(A)`: **`ComplexF64` for Pauli**, `Float64`
otherwise. Pauli objectives therefore wrap each coefficient in `ComplexF64(...)`.
Identity element: `one(ham)` or `one(NormalMonomial{ProjectorAlgebra, UInt8})` /
`one(typeof(x[1]))`.

### 2. Building the objective and constraints

The objective is an ordinary Julia expression in the operator variables (`+ - *`,
`^`, `sum`, `prod`). Then wrap with `polyopt`:

```julia
NCTSSoS.polyopt(objective::P, registry::VariableRegistry{A,T};
        eq_constraints   = P[],     # hⱼ(x) = 0   (e.g. parity, projector relations)
        ineq_constraints = P[],     # gᵢ(x) ⪰ 0   (e.g. ball 1 - xᵢ² ⪰ 0)
        moment_eq_constraints = [])  # linear-in-moment equalities (e.g. particle number)
```

- **Eigenvalue (ground-state) problem** → pass a plain operator polynomial.
- **Maximization** → minimize the negative (`polyopt(-f, …)`), then negate the bound.
- **Trace / state-polynomial problem** → build the objective with `tr(...)` / `ς(...)`
  (see §6); `polyopt` promotes it to an `NCStatePolynomial` internally.
- **Particle-number** constraint helper (fermionic/bosonic):
  ```julia
  particle_number_constraint(registry, N)                    # total number = N
  particle_number_constraint(registry, group => N, more => M)  # per-group
  ```

### 3. Relaxation / solve entry points

```julia
@kwdef struct SolverConfig
    optimizer                                     # required: Clarabel.Optimizer / Mosek.Optimizer / COSMO.Optimizer
    order::Int                  = 0               # relaxation order (the tightening knob)
    moment_basis::Union{Nothing,Vector} = nothing # explicit basis (mutually exclusive with order)
    cs_algo::EliminationAlgorithm = NoElimination()  # correlative sparsity
    ts_algo::EliminationAlgorithm = NoElimination()  # term sparsity
    symmetry::Union{Nothing,SymmetrySpec} = nothing  # Wedderburn block-diagonalization
end
```

```julia
cs_nctssos(pop::PolyOpt, config::SolverConfig; dualize::Bool=true) -> PolyOptResult
# Solve via the CS-NCTSSOS moment-SOHS hierarchy (correlative + term sparsity).

cs_nctssos_higher(pop, prev_res::PolyOptResult, config; dualize=true) -> PolyOptResult
# One more term-sparsity refinement iteration WITHOUT raising `order`. 1–2 iters usually converge.
```

Specify **either** `order` **or** `moment_basis`, not both (the latter via
`get_ncbasis(registry, d)`). `order` defaults to `0`, meaning "auto from objective
degree"; for real control set it explicitly (2 is the standard starting point).

### 4. Reading the bound / result

```julia
struct PolyOptResult{T, A, TI, P, M, ST}
    objective::T                              # the certified lower bound  (E_lb ≤ E₀ / λ_min)
    sparsity::SparsityResult                 # CS/TS structure that was used
    model::GenericModel{T}                   # the underlying JuMP model
    moment_matrix_sizes::Vector{Vector{Int}} # PSD block sizes per clique — sizes the SDP
    n_unique_moment_matrix_elements::Int
    symmetry::Union{Nothing,SymmetryReport}  # set only when symmetry reduction was on
end
```

```julia
res = cs_nctssos(pop, config)
res.objective            # the bound (per-site: res.objective / N)
res.moment_matrix_sizes  # inspect SDP block sizes (cost proxy)
res.model                # JuMP model for low-level inspection
```

`res.objective` is a **lower bound** for an eigenvalue problem (cannot exceed the
true minimum), tightening monotonically with `order` and term-sparsity refinement.

### 5. Sparsity options (the scaling lever)

Two graph-elimination knobs, each an `EliminationAlgorithm`:

| Value | Meaning |
|---|---|
| `NoElimination()` | dense — no sparsity exploited (default; required for symmetry) |
| `MF()` | minimum-fill-in ordering |
| `MMD()` | minimum-degree ordering (good default for local Hamiltonians) |
| `MaximalElimination()` | maximal-clique elimination |
| `AsIsElimination()` | use the graph as-is (assumes already chordal — CS only) |

- `cs_algo` = **correlative sparsity** (chordal): blocks the moment matrix by maximal
  cliques of the variable-coupling graph. Use `MF()`/`MMD()` for local/lattice Hamiltonians.
- `ts_algo` = **term sparsity** (ideal sparsity): drops basis monomials absent from
  the support, blocking each clique's moment matrix. `MMD()` is a good default.

Inspect the SDP **without solving** (sizes the run, shows whether CS/TS found structure):

```julia
sparsity = compute_sparsity(pop, config)
sparsity.corr_sparsity.cliques               # CS clique decomposition
sparsity.corr_sparsity.clq_mom_mtx_bases     # moment-matrix basis size per clique
sparsity.cliques_term_sparsities             # TS blocks per clique
```

`CorrelativeSparsity` fields: `cliques`, `registry`, `cons`, `clq_cons`,
`global_cons`, `clq_mom_mtx_bases`, `clq_localizing_mtx_bases`.
`TermSparsity` fields: `term_sparse_graph_supp`, `block_bases`.

### 6. State-polynomial / tracial objectives

For objectives that multiply expectations (`⟨A⟩⟨B⟩`, covariances) or score by a
trace, build the objective from state words instead of a plain operator polynomial:

- `tr(p)` — trace / **maximally-entangled** (maximally-mixed) expectation `⟨p⟩`.
- `ς(p)` (aliases `varsigma`, `expect`) — expectation in an **arbitrary** state.

Multiply combined state words by an identity monomial `𝟙` to lift to an
`NCStatePolynomial`, then pass to the same `polyopt` → `cs_nctssos` hierarchy.
(Exported: `tr`, `ς`, `varsigma`, `expect`, `StateWord`, `StatePolynomial`,
`NCStateWord`, `StatePolynomial`, `MaxEntangled`, `Arbitrary`.) See §"Worked example C".

### 7. Solver selection & options (Clarabel / Mosek)

```julia
using Clarabel
SolverConfig(optimizer = Clarabel.Optimizer)            # open-source default

using MosekTools
SolverConfig(optimizer = Mosek.Optimizer)               # academic license, faster

using COSMO
SolverConfig(optimizer = COSMO.Optimizer)               # ADMM, large-scale
```

Pass **solver attributes** with MOI / JuMP `optimizer_with_attributes`. Two idioms
seen in the docs:

```julia
# Mosek — silence + threads
using JuMP
SOLVER = optimizer_with_attributes(Mosek.Optimizer,
    "MSK_IPAR_LOG" => 0, "MSK_IPAR_NUM_THREADS" => 0)

# Mosek — via MOI directly
const MOI = NCTSSoS.MOI
SILENT_MOSEK = MOI.OptimizerWithAttributes(Mosek.Optimizer, MOI.Silent() => true)

SolverConfig(optimizer = SOLVER, order = 3)
```

**Clarabel settings** (set the same way: `optimizer_with_attributes(Clarabel.Optimizer, "name" => val)`):

| Setting | Default | Purpose |
|---|---|---|
| `max_iter` | 200 | maximum iterations |
| `time_limit` | Inf | max run time (s) |
| `verbose` | true | verbose printing (set `false` to silence) |
| `tol_gap_abs` | 1e-8 | absolute duality-gap tolerance |
| `tol_gap_rel` | 1e-8 | relative duality-gap tolerance |
| `tol_feas` | 1e-8 | primal/dual feasibility tolerance |
| `max_step_fraction` | 0.99 | max interior-point step length |
| `direct_solve_method` | `:qdldl` | linear solver (`:qdldl`, `:mkl`, `:panua`, …) |
| `equilibrate_enable` | true | data equilibration pre-scaling |

```julia
SILENT_CLARABEL = optimizer_with_attributes(Clarabel.Optimizer,
    "verbose" => false, "max_iter" => 500, "tol_feas" => 1e-6)
SolverConfig(optimizer = SILENT_CLARABEL, order = 2, ts_algo = MMD())
```

### 8. GNS reconstruction & flatness (exactness certificate)

When the relaxation is **flat** (numerically exact), reconstruct the optimal
operators and state from the solved moment map:

```julia
# exported
gns_reconstruct(...)            -> GNSResult      # fields: .matrices (Dict op→matrix), .xi (|Ω⟩), .rank, .full_rank
test_flatness(hankel, full_basis, basis; atol) -> FlatnessResult   # .is_flat ⇒ relaxation exact
flat_extend(...) ; reconstruct(...) ; verify_gns(gns, monomap, registry; poly, f_star, atol)
robustness_report(...) -> RobustnessReport
get_ncbasis(registry, d)        # degree-d NC monomial basis
```

The reconstruction reads the low-level moment result's `monomap`; the dense GNS
example uses the non-exported `NCTSSoS.moment_relax`, `NCTSSoS.solve_moment_problem`,
and `NCTSSoS.hankel_matrix` (see worked example D). **Symmetry reduction blocks GNS**
(the reduced `monomap` lacks dense moments).

### 9. Symmetry reduction (Wedderburn block-diagonalization)

For finite-group-invariant problems, block-diagonalize the moment matrix into one
smaller PSD block per symmetry sector (via SymbolicWedderburn / SympleQ):

```julia
# manual signed permutations of registry operators:
spec = SymmetrySpec(SignedPermutation( A[1].word[1] => A[2].word[1], … ))

# Pauli Hamiltonians — automatic Clifford detection:
spec = sympleq_symmetry_spec(ham)   # also: pauli_site_permutation, CliffordSymmetry(:H/:S/:CNOT/:SWAP)

config = SolverConfig(optimizer = …, symmetry = spec,
                      cs_algo = NoElimination(), ts_algo = NoElimination())  # REQUIRED
res = cs_nctssos(pop, config)
res.symmetry        # SymmetryReport: group order, invariant moment count, PSD block sizes
```

**Symmetry and sparsity are mutually exclusive**: symmetry requires a dense
single-clique relaxation (`NoElimination` for both CS and TS) and blocks
`cs_nctssos_higher` + GNS. Use it when the group is large relative to the moment
basis; prefer CS/TS for large, weakly symmetric problems. Related specs:
`PauliChargeSectorSpec`, `PauliSingletConstraintSpec`, `FermionicSectorSpec`,
`FermionicSpinAdaptationSpec`, `CliffordSymmetryGroup`.

---

## Worked examples (verbatim from docs)

### A. Minimal scalar NC optimization — Broyden banded (Quick Start)

```julia
using NCTSSoS, MosekTools

function broyden_banded(n::Int)
    # Create non-commutative variables
    registry, (x,) = create_noncommutative_variables([("x", 1:n)])

    # Build the objective function using sum
    f = sum(1:n) do i
        jset = setdiff(max(1, i-5):min(n, i+1), i)
        g = isempty(jset) ? 0.0 * x[1] : sum(x[j] + x[j]^2 for j in jset)
        (2.0*x[i] + 5.0*x[i]^3 + 1 - g)^2
    end

    # Define inequality constraints
    ineq_cons = [[1.0 - x[i]^2 for i in 1:n]; [x[i] - 1//3 for i in 1:n]]

    return polyopt(f, registry; ineq_constraints=ineq_cons)
end

pop = broyden_banded(6)

solver_config = SolverConfig(optimizer=Mosek.Optimizer, order=3)
result = cs_nctssos(pop, solver_config)

# with sparsity:
solver_config = SolverConfig(optimizer=Mosek.Optimizer, order=3, cs_algo=MF(), ts_algo=MMD())
result_sparse = cs_nctssos(pop, solver_config)

# refine the sparse relaxation:
result_higher = cs_nctssos_higher(pop, result_sparse, solver_config)
```

Explicit-basis variant of the config:

```julia
basis = get_ncbasis(pop.registry, 3)
solver_config = SolverConfig(optimizer=Mosek.Optimizer, moment_basis=basis)
```

### B. Spin-Hamiltonian ground-state lower bound

**1D Heisenberg (nearest neighbor), `N=6`** — bound `res.objective / N = -0.46712927…`,
matching reference `-0.467129`:

```julia
using NCTSSoS, MosekTools
N = 6

registry, (σx, σy, σz) = create_pauli_variables(1:N)

ham = sum(ComplexF64(1 / 4) * op[i] * op[mod1(i + 1, N)] for op in [σx, σy, σz] for i in 1:N)

pop = polyopt(ham, registry)

solver_config = SolverConfig(
                    optimizer=Mosek.Optimizer,
                    order=3,
                    ts_algo=MMD(),
                    )

res = cs_nctssos(pop, solver_config)
res.objective / N
```

**1D J1–J2 (next-nearest neighbor), `N=6`, `J1=1.0`, `J2=0.2`** — bound `-0.4270083…` per site:

```julia
using NCTSSoS, MosekTools
N = 6
J1 = 1.0
J2 = 0.2

registry, (σx, σy, σz) = create_pauli_variables(1:N)

ham = sum(ComplexF64(J1 / 4) * op[i] * op[mod1(i + 1, N)] + ComplexF64(J2 / 4) * op[i] * op[mod1(i + 2, N)] for op in [σx, σy, σz] for i in 1:N)

pop = polyopt(ham, registry)

solver_config = SolverConfig(optimizer=Mosek.Optimizer, order=3, ts_algo=MMD())

res = cs_nctssos(pop, solver_config)
res.objective / N
```

**2D square lattice (correlative + term sparsity), `3×3`** — note CS turned on (`cs_algo=MF()`):

```julia
using NCTSSoS, MosekTools
Nx = 3
Ny = 3
N = Nx * Ny
J1 = 1.0
J2 = 0.0

registry, (σx, σy, σz) = create_pauli_variables(1:N)

LI = LinearIndices((1:Nx, 1:Ny))

ham = sum(ComplexF64(J1 / 4) * op[LI[CartesianIndex(i, j)]] * op[LI[CartesianIndex(i, mod1(j + 1, Ny))]] + ComplexF64(J1 / 4) * op[LI[CartesianIndex(i, j)]] * op[LI[CartesianIndex(mod1(i + 1, Nx), j)]] + ComplexF64(J2 / 4) * op[LI[CartesianIndex(i, j)]] * op[LI[CartesianIndex(mod1(i + 1, Nx), mod1(j + 1, Ny))]] + ComplexF64(J2 / 4) * op[LI[CartesianIndex(i, j)]] * op[LI[CartesianIndex(mod1(i + 1, Nx), mod1(j - 1, Ny))]] for op in [σx, σy, σz] for i in 1:Nx for j in 1:Ny)

pop = polyopt(ham, registry)

solver_config = SolverConfig(optimizer=Mosek.Optimizer, order=3, cs_algo=MF(), ts_algo=MMD())
res = cs_nctssos(pop, solver_config)
```

### B′. Fermionic ground state (XY chain) — with equality (parity) constraint + refinement

```julia
using NCTSSoS, MosekTools, JuMP

SOLVER = optimizer_with_attributes(Mosek.Optimizer,
    "MSK_IPAR_LOG" => 0,
    "MSK_IPAR_NUM_THREADS" => 0)

# N = 4 with a parity equality constraint
N₁ = 4
j_c = 1.0
registry₁, (a₁, a₁_dag) = create_fermionic_variables(1:N₁)

ham₁ = sum(
    -ComplexF64(j_c / 2) * (a₁_dag[i] * a₁[i+1] + a₁_dag[i+1] * a₁[i])
    for i in 1:N₁-1
) + ComplexF64(j_c / 2) * (a₁_dag[N₁] * a₁[1] + a₁_dag[1] * a₁[N₁])

parity₁ = prod(one(ham₁) - 2.0 * a₁_dag[i] * a₁[i] for i in 1:N₁)

pop₁ = polyopt(ham₁, registry₁; eq_constraints = [parity₁ - one(ham₁)])
config₁ = SolverConfig(optimizer = SOLVER, order = 4, ts_algo = MMD())
result₁ = cs_nctssos(pop₁, config₁)

# General solver for N ≥ 6 using cs_nctssos_higher to refine
function solve_xy(N::Int; j_c::Real = 1.0, order::Int = 3)
    registry, (a, a_dag) = create_fermionic_variables(1:N)

    ham = sum(
        -ComplexF64(j_c / 2) * (a_dag[i] * a[i+1] + a_dag[i+1] * a[i])
        for i in 1:N-1
    ) + ComplexF64(j_c / 2) * (a_dag[N] * a[1] + a_dag[1] * a[N])

    pop = polyopt(ham, registry)
    config = SolverConfig(optimizer = SOLVER, order = order, ts_algo = MMD())

    res1 = cs_nctssos(pop, config)
    res2 = cs_nctssos_higher(pop, res1, config)

    return (first = res1.objective, refined = res2.objective)
end

r6 = solve_xy(6; order = 3)
```

### C. Bell inequality (CHSH → Tsirelson) — operator form

```julia
using NCTSSoS, MosekTools

# Step 1: Create unipotent variables (±1 observables)
registry, (x, y) = create_unipotent_variables([("x", 1:2), ("y", 1:2)])

# Step 2: Define the CHSH objective
f = 1.0 * x[1] * y[1] +
    1.0 * x[1] * y[2] +
    1.0 * x[2] * y[1] -
    1.0 * x[2] * y[2]

# Step 3: minimize -f to maximize f
pop = polyopt(-f, registry)

# Step 4: order-1 relaxation suffices (NPA level 1)
solver_config = SolverConfig(optimizer = Mosek.Optimizer, order = 1)

# Step 5: Solve
result = cs_nctssos(pop, solver_config)

# Step 6: Extract bound
chsh_bound = -result.objective
tsirelson_bound = 2 * sqrt(2)
println("CHSH bound: $chsh_bound")     # ≈ 2.828, the Tsirelson bound
```

### C′. Trace / state-polynomial optimization (`tr`, covariances)

Projector trace polynomial (lift to a state polynomial via `* 𝟙`):

```julia
using NCTSSoS, MosekTools
registry, (x,) = create_projector_variables([("x", 1:3)]);

𝟙 = one(NormalMonomial{ProjectorAlgebra, UInt8})
p = (tr(x[1] * x[2] * x[3]) + tr(x[1] * x[2]) * tr(x[3])) * 𝟙;

spop = polyopt(p, registry);
solver_config = SolverConfig(; optimizer=Mosek.Optimizer, order=2);
result = cs_nctssos(spop, solver_config);
@show result.objective
```

CHSH in tracial form (transpose trick) + covariance Bell inequality:

```julia
registry, (vars,) = create_unipotent_variables([("v", 1:4)]);
x = vars[1:2];  # Alice
y = vars[3:4];  # Bob
𝟙 = one(NormalMonomial{UnipotentAlgebra, UInt8})

p = -1.0 * tr(x[1] * y[1]) + -1.0 * tr(x[1] * y[2]) +
    -1.0 * tr(x[2] * y[1]) +  1.0 * tr(x[2] * y[2]);

tpop = polyopt(p * 𝟙, registry);
solver_config = SolverConfig(; optimizer=Mosek.Optimizer, order=1, ts_algo=MaximalElimination());
result = cs_nctssos(tpop, solver_config);   # result.objective ≈ -2√2

# Covariance form: cov(a,b) = tr(xₐ yᵦ) - tr(xₐ) tr(yᵦ)
registry, (vars,) = create_unipotent_variables([("v", 1:6)]);
x = vars[1:3]; y = vars[4:6];
cov(a, b) = 1.0 * tr(x[a] * y[b]) - 1.0 * tr(x[a]) * tr(y[b]);
p = -1.0 * (cov(1,1)+cov(1,2)+cov(1,3)+cov(2,1)+cov(2,2)-cov(2,3)+cov(3,1)-cov(3,2));
tpop = polyopt(p * one(typeof(x[1])), registry);
result = cs_nctssos(tpop, SolverConfig(; optimizer=Mosek.Optimizer, order=2));  # ≈ -5.0
```

### D. Higher-order GNS reconstruction + flatness (dense CHSH, order 4)

Uses the **non-exported** low-level path (`NCTSSoS.moment_relax`,
`NCTSSoS.solve_moment_problem`, `NCTSSoS.hankel_matrix`) plus exported
`compute_sparsity`, `get_ncbasis`, `test_flatness`, `gns_reconstruct`, `verify_gns`:

```julia
using NCTSSoS, MosekTools, LinearAlgebra, Logging
const MOI = NCTSSoS.MOI
const SILENT_MOSEK = MOI.OptimizerWithAttributes(Mosek.Optimizer, MOI.Silent() => true)

registry, (A, B) = create_unipotent_variables([("A", 1:2), ("B", 1:2)]);
chsh = 1.0*A[1]*B[1] + 1.0*A[1]*B[2] + 1.0*A[2]*B[1] - 1.0*A[2]*B[2];
pop = polyopt(-chsh, registry);

solver_config = SolverConfig(optimizer=SILENT_MOSEK, order=4,
                             cs_algo=NoElimination(), ts_algo=NoElimination());

# low-level solve to get the moment map
sparsity = compute_sparsity(pop, solver_config);
moment_problem = NCTSSoS.moment_relax(pop, sparsity.corr_sparsity, sparsity.cliques_term_sparsities);
moment_result  = NCTSSoS.solve_moment_problem(moment_problem, SILENT_MOSEK);

# flatness check
using NCTSSoS: get_ncbasis
full_basis = get_ncbasis(registry, 3);
basis      = get_ncbasis(registry, 2);
hankel     = NCTSSoS.hankel_matrix(moment_result.monomap, full_basis);
flatness   = test_flatness(hankel, full_basis, basis; atol=1e-8)   # flatness.is_flat

# GNS reconstruction
gns = with_logger(Logging.SimpleLogger(devnull, Logging.Error)) do
    gns_reconstruct(moment_result.monomap, registry, 3; hankel_deg=2, atol=1e-8)
end;
A1 = gns.matrices[registry[:A₁]];   # operator matrices keyed by registry symbol
gns.rank      # quotient Hilbert-space dimension
gns.xi        # distinguished vector |Ω⟩

verification = verify_gns(gns, moment_result.monomap, registry;
    poly = -chsh, f_star = moment_result.objective, atol = 1e-5)
```

---

## Pitfalls

- **Order vs cost.** SDP size scales ~`n^order` (dense). `order` is monotone in the
  bound but cost (and especially memory) rises steeply. Start at `order=2`; go to 3+
  only for a tighter bound or GNS. Probe with `compute_sparsity` / inspect
  `res.moment_matrix_sizes` before committing to higher order. Note: `order=0`
  (the `SolverConfig` default) means auto-from-degree — set it explicitly for control.
- **Pauli needs `ComplexF64`.** Pauli coefficients are complex (`σx·σy = i·σz`); wrap
  every coefficient `ComplexF64(...)` or the build errors / mistypes.
- **Sparsity for scaling.** `cs_algo`/`ts_algo` default to `NoElimination()` (dense).
  Local 1D/lattice Hamiltonians: `ts_algo=MMD()` (and `cs_algo=MF()`/`MMD()` for 2D).
  **Term-sparsity stabilization ≠ exactness** — the TS graph can stop gaining edges
  while the bound stays strictly loose; if so, raise `order` or disable TS.
- **Symmetry XOR sparsity.** `symmetry=spec` requires `cs_algo = ts_algo = NoElimination()`
  and blocks `cs_nctssos_higher` and GNS. Anything outside the MVP scope raises
  `ArgumentError` rather than silently building the wrong relaxation.
- **`order` and `moment_basis` are mutually exclusive** — setting both throws.
- **Certifying vs heuristic.** `res.objective` is a *rigorous lower bound* for the
  eigenvalue problem (a certificate, not a variational estimate). It only equals the
  true ground-state energy when the relaxation is **flat** — confirm with
  `test_flatness(...).is_flat` before treating it as exact. A loose bound is still
  valid as a bound; it is not the energy.
- **Solver choice.** Clarabel (open source) is the harness default; Mosek (academic
  license) is faster on large blocks. Silence the solver in scans
  (`"verbose"=>false` / `MOI.Silent()=>true`). v0.1.0 of NCTSSoS carries an explicit
  performance caveat — weigh absolute timings accordingly.
- **First-run precompilation** is setup time, not solve time; report separately.

---

## Source links

- Quick Start: https://quantumsos.github.io/NCTSSoS.jl/dev/quick_start/
- Polynomial optimization manual: https://quantumsos.github.io/NCTSSoS.jl/dev/manual/polynomial_optimization/
- SDP relaxation manual: https://quantumsos.github.io/NCTSSoS.jl/dev/manual/sdp_relaxation/
- Sparsities manual: https://quantumsos.github.io/NCTSSoS.jl/dev/manual/sparsities/
- Optimizers manual: https://quantumsos.github.io/NCTSSoS.jl/dev/manual/optimizers/
- API — interface: https://quantumsos.github.io/NCTSSoS.jl/dev/apis/interface/
- API — polynomials: https://quantumsos.github.io/NCTSSoS.jl/dev/apis/polynomials/
- API — sparsities: https://quantumsos.github.io/NCTSSoS.jl/dev/apis/sparsities/
- API — relaxations: https://quantumsos.github.io/NCTSSoS.jl/dev/apis/relaxations/
- Example — ground state energy: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/ground_state_energy/
- Example — fermionic ground state: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/fermionic_ground_state/
- Example — Bell / CHSH: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/bell/
- Example — trace polynomial: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/trace_poly/
- Example — CHSH GNS reconstruction: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/chsh_gns_reconstruction/
- Symmetry examples: https://quantumsos.github.io/NCTSSoS.jl/dev/examples/generated/chsh_symmetry/ , .../pauli_clifford_symmetry/
- Repo: https://github.com/QuantumSOS/NCTSSoS.jl  ·  Source: `src/optimization/interface.jl`, `src/optimization/gns.jl`
- Clarabel settings: http://clarabel.org/stable/api_settings/
