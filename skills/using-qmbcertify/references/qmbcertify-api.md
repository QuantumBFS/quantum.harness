# QMBCertify.jl — API + Examples Reference

Extracted from the GitHub source (no docs website exists). Repo: <https://github.com/wangjie212/QMBCertify>
Source verified against `master` (package version `0.3.5`).

## What it does

QMBCertify.jl (J. Wang, AMSS) computes **certified bounds on ground-state properties** of quantum
many-body systems — currently the **1D and 2D (J1-J2) Heisenberg spin-½ models** — via the
**structured NPA hierarchy** (a Lasserre / NPA-style noncommutative-polynomial-optimization moment
relaxation specialized to spin lattices). It is a bootstrap / NPA-bound certifier: rather than
diagonalizing or sampling, it builds a moment SDP whose optimum is a **rigorous lower (or two-sided)
bound** on the energy per site (or on a correlation, structure factor, or partition function), and
solves it with **Mosek**.

The package's symmetry exploitation (translation, point group, spin-flip, SU(2), reduced-density-matrix
positivity, state optimality) block-diagonalizes the SDP so the binding cost is the largest residual
block, not the bare moment-matrix dimension — this is what lets it reach large lattices.

Two layers:

1. **Numeric SDP bound (the core deliverable).** `GSB` (ground-state bound) builds and solves the
   structured moment SDP; `PFB` does the same for partition functions. With `Gram=true`, `GSB` also
   exports the **Gram matrices** (the sum-of-Hermitian-squares certificate blocks).
2. **Exact rational certification (post-processing, 1D chains only).** `certify_qmb` /
   `certify_qmb_corr` round the exported Gram blocks onto the exact SOHS identity in rational
   arithmetic, then shift the numeric optimum by a rigorous Arblib minimum-eigenvalue enclosure. The
   result is an *exactly* certified bound. Report the SDP optimum as a *numeric* certified bound; only
   call a number *exactly* certified after this post-step runs cleanly.

Reference paper: Wang & Magron et al., *Certifying ground-state properties of many-body systems*,
Phys. Rev. X **14**, 031006 (2024) — <https://journals.aps.org/prx/abstract/10.1103/PhysRevX.14.031006>.

License: CeCILL-2.1 (file `LICENSE.en`; GitHub sidebar shows "NOASSERTION").

## Installation & setup

Not in the Julia General registry — install by repo URL:

```julia
pkg> add https://github.com/wangjie212/QMBCertify
```

Dependencies (from `Project.toml`): `JuMP`, `Mosek`, `MosekTools` (pinned `Mosek = 11.0.1`,
`MosekTools = 0.15.10`), `Arblib`, `Dualization`, `DynamicPolynomials`, `ITensors`, `ITensorMPS`,
`LinearAlgebra`.

In this harness: `make install qmbcertify` (adds the package + Mosek + ITensors to `julia-env`).
Smoke test: `julia --project=julia-env -e 'using QMBCertify'`.

**Mosek is a hard dependency — there is no open-source-solver path.** Mosek 11 is commercial; a
**free academic license** is required. The license file must resolve before any solve
(`MOSEKLM_LICENSE_FILE` env var or `~/mosek/mosek.lic`), or the SDP solve aborts.

## Encoding: how a Hamiltonian / observable is specified

A term is a **support word** (`Vector{Int}`) plus a **coefficient** (`Float64`). The word uses a
flat site×Pauli index: **site `i`, Pauli component `α ∈ {1=x, 2=y, 3=z}` → index `3*(i-1)+α`**.
So index `1` = `S^x` on site 1, `4 = 3*(2-1)+1` = `S^x` on site 2, `7` = `S^x` on site 3, etc.

By spin-rotation symmetry only the `x`-`x` (component-1) representative of each two-site coupling is
written; the package reconstructs `y`-`y` and `z`-`z` internally. Hence:

- 1D J1-J2 Heisenberg: `supp = [[1,4], [1,7]]`, `coe = [3/4, 3/4*J2]`
  (`[1,4]` = nearest-neighbour `S₁·S₂`, `[1,7]` = next-nearest `S₁·S₃`; the `3/4` is `3 × (1/4)`
  from the three components of `S=½`).
- 2D square Heisenberg uses `coe = [3/2, ...]` (the factor is `3/2`, not `3/4`).

Words are reduced to a canonical normal form by `reduce!` / `reduce4` before being matched against
the SDP's monomial support. `slabel(i, j; L)` maps 2D site coordinates `(i,j)` to the flat site label.

## Exported API

From `src/QMBCertify.jl`:

```julia
export certify_qmb, certify_qmb_corr, dmrg_heisenberg_rat
export GSB, PFB, slabel, reduce!, mosek_para
```

### `GSB` — ground-state bound (the main entry point)

```julia
GSB(supp::Vector{Vector{Int}}, coe::Vector{Float64}, L::Int, d::Int;
    H_supp=supp, H_coe=coe, SU2_symmetry=false, lso=true, lol=L, pso=3,
    energy=[], QUIET=false, lattice="chain", rdm=false, extra=0,
    three_type=[1;1], J2=0, correlation=false, Gram=false,
    writetofile=false, mosek_setting=mosek_para())
    -> (objv, data::qmb_data)
```

Builds the structured moment SDP for objective `Σ coe[i]·supp[i]` over the J1-J2 Heisenberg state
space on `L` sites (chain) or `L×L` sites (square), at relaxation order `d`, and solves it with Mosek.
Returns the **numeric optimum `objv`** (a certified bound on the objective per the relaxation) and a
`qmb_data` struct (correlations, bases, support, Gram matrices, multipliers).

Positional arguments:

| Arg | Meaning |
|---|---|
| `supp` | objective support words (site×Pauli flat indices) |
| `coe`  | objective coefficients (must match `supp` length) |
| `L`    | system size — number of sites (chain) or linear dimension (square, total `L²` sites) |
| `d`    | relaxation order — monomial-basis degree; moment matrix reaches degree `2d` |

Keyword arguments (semantics from `src/bound_gsp.jl`):

| Kwarg | Default | Effect |
|---|---|---|
| `lattice` | `"chain"` | `"chain"` (1D) or `"square"` (2D `L×L`); selects geometry + symmetry group |
| `extra` | `0` | long-range reach of two-site basis words. Chain: separations up to `extra+1` (paper's `r = extra+1`). Square: appends `extra` further displacement vectors. Degree is set by `d`, not this. `0` = nearest-neighbour basis only |
| `rdm` | `false` | k-site reduced-density-matrix positivity on k *contiguous* sites (U(1)-block-diagonalized). Only `8` / `9` / `10` implemented; `false` / `0` = off |
| `pso` | `3` (**on**) | PSD state-optimality blocks; value caps the word length of their localizing basis. `0` = off. Pass `pso=0` for the lightest run |
| `lso` | `true` (**on**) | linear state-optimality constraints `⟨[H, m]⟩ = 0` over a generated monomial family. `lso=0`/`false` to disable |
| `lol` | `L` | caps the site range of the `lso` monomial family |
| `three_type` | `[1;1]` | site-gap pattern of three-site basis words. Chain: the two successive gaps (`[1,1]` = adjacent triple). Square: selects one of two fixed displacement families. Active only at `d ≥ 3` |
| `SU2_symmetry` | `false` | add SU(2)-invariance equality constraints for further reduction |
| `H_supp`, `H_coe` | `=supp`, `=coe` | the *Hamiltonian* (used by `pso`/`lso` and the `energy` bracket); set separately from the objective when bounding an observable |
| `energy` | `[]` | pass a known energy bracket `[lb, ub]` to switch to two-sided observable bounds over near-ground states |
| `correlation` | `false` | with an `energy` bracket, bound an observable; also makes `GSB` extract correlation vectors into `data` |
| `J2` | `0` | NNN coefficient supplied to the `energy`-bracket constraint |
| `Gram` | `false` | export Gram (SOHS certificate) matrices into `data.GramMat` / `data.sGramMat` — **required** for any exact post-certification |
| `QUIET` | `false` | suppress progress / solver logs |
| `writetofile` | `false` | dump the dualized SDP to a file (e.g. `.dat-s`) instead of/in addition to solving |
| `mosek_setting` | `mosek_para()` | Mosek tolerances + thread count (see `mosek_para`) |

`GSB` prints `SDP size: n = <largest block>, m = <#moment constraints>` during block-diagonalization —
read this to gauge cost before committing a large run.

### `PFB` — partition-function bound

```julia
PFB(supp::Vector{Vector{Int}}, coe::Vector{Float64}, beta, L::Int, d::Int;
    lb=nothing, QUIET=false) -> objv
```

Bounds the partition function of the 1D chain at inverse temperature `beta`. Returns a numeric
optimum; `2^L * objv` is the bound on `Z` (see example). `lb` is an optional energy lower bound used to
tighten an internal upper bound. **Numeric only** — no exact-rounding layer. `supp`/`coe` give the
Hamiltonian (`[[1,4]]`, `[3/4]` for plain Heisenberg).

### `certify_qmb` — exact rational energy certificate (1D chains only)

```julia
certify_qmb(data, Nsites, J, numopt;
            tol_gram::Real=1e-12, tol_dft::Real=1e-20,
            snn::Bool=false, J2::Real=1.0,
            check::Bool=false, eig_prec::Int=256)
    -> (oldbound, newbound, shift, mineigs, dims)
```

Post-processes a 1D-chain `GSB(...; Gram=true)` solve into an exact rational certificate. It rounds the
Gram blocks to rationals (`round_project_qmb`), checks the Frobenius residual against the SOHS identity,
computes a rigorous minimum-eigenvalue enclosure per block (`rigorous_min_eig`, Arblib), and shifts the
numeric optimum:

```
shift   = λ_min(G1)·|basis₁| + λ_min(G2)·|basis₂|
newbound = numopt + shift
```

Arguments: `data` (the `qmb_data` from `GSB`), `Nsites` = `L`, `J` = the NN coefficient (`coe[1]`),
`numopt` = the numeric optimum returned by `GSB`.

| Kwarg | Default | Effect |
|---|---|---|
| `snn`, `J2` | `false`, `1.0` | **define the certified Hamiltonian** — `snn=true` adds the J2 (NNN) term so the certificate is verified against the J1-J2 model. Match these to the model you actually solved |
| `tol_gram`, `tol_dft` | `1e-12`, `1e-20` | tolerances for Gram / discrete-Fourier rounding to rationals (examples use `1e-15` / `1e-12`) |
| `eig_prec` | `256` | Arblib bit-precision for the rigorous PSD enclosure; raise if rounding fails |
| `check` | `false` | extra residual verification |

Return is a NamedTuple: `oldbound` (raw numeric optimum), `newbound` (exactly certified bound),
`shift`, `mineigs` (per-block min eigenvalues), `dims` (`[|basis₁|, |basis₂|]`).

### `certify_qmb_corr` — exact rational correlation / observable certificate (1D chains)

```julia
certify_qmb_corr(N::Int, d_E::Int, d_corr::Int;
                 J2::Real=0.0, dist=1, extra_E::Int=0, extra_corr::Int=0,
                 tol_gram::Real=1e-15, tol_dft::Real=1e-12, tol_E::Real=1e-12,
                 digits_dmrg::Int=12, QUIET::Bool=false, check::Bool=true,
                 eig_prec::Int=256)
    -> NamedTuple
```

Self-contained driver for two-sided certified bounds on a two-point correlation `⟨S₁·S_{1+dist}⟩`. It
internally (1) runs `GSB` at order `d_E` and certifies the energy via `certify_qmb` to get a rigorous
energy lower bound, (2) calls `dmrg_heisenberg_rat` for a rationalized energy upper bound, (3) runs two
`GSB` solves (upper / lower) at order `d_corr` with the energy bracket as a constraint, and (4) rounds
+ certifies the correlation Gram blocks.

| Arg / Kwarg | Meaning |
|---|---|
| `N` | chain length |
| `d_E`, `d_corr` | relaxation orders for the energy solve and the correlation solve |
| `J2` | NNN coupling |
| `dist` | site separation(s) of the correlation; integer or iterable |
| `extra_E`, `extra_corr` | `extra` long-range reach for the two solves |
| `tol_gram`, `tol_dft`, `tol_E` | rounding tolerances (Gram / DFT / energy) |
| `digits_dmrg` | DMRG rounding precision for the upper bound |

Returns a NamedTuple with `e_lb`, `e_ub` (rational energy bracket), `dist`, and per-distance
`C_num_upper` / `C_rat_upper` / `shift_upper` and `C_num_lower` / `C_rat_lower` / `shift_lower`
(numeric and exactly-certified correlation bounds + shifts).

### `dmrg_heisenberg_rat` — rationalized DMRG energy reference

```julia
dmrg_heisenberg_rat(N, J; J2=0.0, digits=12) -> Rational{BigInt}
```

Runs an ITensors DMRG on the periodic 1D J1-J2 Heisenberg chain (4 sweeps, maxdim up to 180,
cutoff `1e-7`) and returns the energy **per site**, rounded up and rationalized to `digits` precision —
used as a rigorous variational *upper* bound inside `certify_qmb_corr`.

### `mosek_para` — solver settings

```julia
mutable struct mosek_para
    tol_pfeas::Float64    # MSK_DPAR_INTPNT_CO_TOL_PFEAS
    tol_dfeas::Float64    # MSK_DPAR_INTPNT_CO_TOL_DFEAS
    tol_relgap::Float64   # MSK_DPAR_INTPNT_CO_TOL_REL_GAP
    num_threads::Int64    # MSK_IPAR_NUM_THREADS (0 = auto)
end
mosek_para()  # = mosek_para(1e-8, 1e-8, 1e-8, 0)
```

Pass via `GSB(...; mosek_setting=mosek_para(1e-9, 1e-9, 1e-9, 16))` to tighten tolerances or pin
thread count.

### `slabel`, `reduce!` — encoding helpers (also exported)

```julia
slabel(i, j; L=0)                                   # 2D (i,j) -> flat site label
reduce!(a::Vector{UInt16}; L=0, lattice="chain", realify=false) -> (word, coef)  # canonical normal form
```

Useful, **non-exported but public** helpers seen in the examples (call as `QMBCertify.<name>`):
`bfind(A, a)` (binary search in sorted support), `reduce4(a, L; lattice)` (symmetry reduction to normal
form), `PSDstate_entry(...)` (state-optimality block entry). The `qmb_data` struct returned by `GSB`
has fields: `correlation1`, `correlation2`, `correlation3`, `basis`, `sbasis`, `tsupp`, `GramMat`,
`sGramMat`, `multiplier`, `moment`.

## Worked examples (verbatim from `examples/`)

### `examples/certified_energy.jl` — certified energy vs system size

Sweeps the 1D J1-J2 chain (`J2 = 0.2`) over even sizes `N = 4…30` at relaxation order `d=2`, then
exactly certifies each via `certify_qmb`. The lightest-strengthening run (`rdm=0, pso=0, lso=0`) with
long-range reach `extra=1`.

```julia
using QMBCertify

J2   = 0.2
supp = [[1;4], [1;7]]
coe  = [3/4; 3/4*J2]
tt   = [1;1]

Ns = [4,6,8,10,12,14,16,18, 20 ,22, 24, 26, 28, 30]

oldbounds  = Float64[]
newbounds  = Float64[]
shifts     = Float64[]
mineigs_list = []
dims   = []
times = []

for N in Ns
    println("=== N = $N ===")

    time = @elapsed begin

        opt, data = GSB(supp, coe, N, 2;
            QUIET=true, rdm=0, lol=N, extra=1, pso=0, lso=0, three_type=tt, Gram=true)

        result = certify_qmb(data, N, coe[1], opt; tol_gram=1e-15, tol_dft=1e-12, snn=true, J2=J2)

    end

    println("Total time for N=$N: $time seconds")
    push!(times, time)
    push!(oldbounds,  Float64(result.oldbound))
    push!(newbounds,  Float64(result.newbound))
    push!(shifts,     Float64(result.shift))
    push!(mineigs_list, result.mineigs)
    push!(dims,   result.dims)
end
```

`result.newbound` = exactly certified lower bound on `E₀/N`; `result.oldbound` = the raw Mosek optimum.

### `examples/certified_corr.jl` — certified correlation bounds across J2

Two-sided certified bounds on the nearest-neighbour correlation (`dist=1`) of the `N=12` chain, scanned
over `J2 = 0.2…2.0`, with energy solve at order 3 and correlation solve at order 3.

```julia
using QMBCertify
using ITensorMPS
using ITensors

J2s = 0.2:0.2:2.0
e_lbs = Float64[]
e_ubs = Float64[]
C_bounds_upper = Float64[]
C_bounds_lower = Float64[]
shifts_upper = Float64[]
shifts_lower = Float64[]

for J2 in J2s
    println("=== J2 = $J2 ===")
    res = certify_qmb_corr(
        12,
        3,
        3;
        J2 = J2,
        dist = 1,
        extra_E = 3,
        extra_corr = 3,
        QUIET = true,
        tol_gram = 1e-13,
        tol_dft  = 1e-12
    )
    push!(C_bounds_upper, Float64(res.C_rat_upper[1]))
    push!(C_bounds_lower, Float64(res.C_rat_lower[1]))
    push!(shifts_upper, Float64(res.shift_upper[1]))
    push!(shifts_lower, Float64(res.shift_lower[1]))
    push!(e_lbs, Float64(res.e_lb))
    push!(e_ubs, Float64(res.e_ub))
end
```

### `examples/ground_state.jl` — numeric ground-state bounds (chain, square, J1-J2, two-sided, DMRG)

The catch-all numeric-bound example. Highlights:

```julia
using QMBCertify

# 1d Heisenberg model
supp = [[1;4]]
coe = [3/4]
N = 10 # number of spins
r = 5
@time opt,data = GSB(supp, coe, N, 4, QUIET=false, rdm=8, pso=0, lso=0, extra=r-1)


ub = -0.4872305
lb = -0.4911407
L = 20
d = 4
r = 10
J2 = 1
supp = [[1;4]]
coe = [1/4]
GSB(supp, coe, L, d, H_supp=[[1;4], [1;7]], H_coe=[3/4; 3/4*J2], energy=[lb, ub], J2=J2, QUIET=true, rdm=9, pso=3, extra=r-1, correlation=false)
GSB(supp, -coe, L, d, H_supp=[[1;4], [1;7]], H_coe=[3/4; 3/4*J2], energy=[lb, ub], J2=J2, QUIET=true, rdm=9, pso=3, extra=r-1, correlation=false)


# 1d J1-J2 Heisenberg model
N = 20 # number of sites
J2 = 1.0
supp = [[1;4], [1;7]]
coe = [3/4; 3/4*J2]
r = 5
tt = [1;1]
@time opt,data = GSB(supp, coe, N, 4, QUIET=true, rdm=10, pso=3, extra=r-1, three_type=tt, correlation=true)

# 2d L×L Heisenberg model
L = 4
supp = [[1;4]]
coe = [3/2]
@time opt,data = GSB(supp, coe, L, 4, lattice="square", rdm=0, pso=0, lso=0, extra=0, QUIET=false)


supp = [[1;4]]
coe = [1/4]
ub = -0.700780
lb = -0.702784
GSB(supp, coe, 4, 4, energy=[lb, ub], lattice="square", rdm=0, pso=0, extra=0, QUIET=false)
GSB(supp, -coe, 4, 4, energy=[lb, ub], lattice="square", rdm=0, pso=0, extra=0, QUIET=false)


# 2d L×L J1-J2 Heisenberg model
L = 4
supp = [[1;4], [1;7]]
J2 = 0.3
coe = [3/2, 3/2*J2]
@time opt,data = GSB(supp, coe, L, 4, lattice="square", rdm=8, pso=0, extra=0, QUIET=false)
```

Notes from this file:
- The two-sided observable pattern: pass an energy bracket `[lb, ub]` plus `H_supp`/`H_coe`, then run
  `GSB` once with `+coe` and once with `-coe` to bracket the observable.
- 2D uses `lattice="square"`, `L` is the linear size (`L×L` sites), and the NN coefficient is `3/2`.
- The file also contains an ITensors DMRG block for cross-checking energies/correlations of the same
  periodic chain (the in-package `dmrg_heisenberg_rat` is the packaged version of this).

### `examples/partition_function.jl` — partition-function bound + ED cross-check

```julia
using QMBCertify

# 1d Heisenberg model
supp = [[1;4]]
coe = [3/4]
N = 10 # number of spins
lb = -0.4515446 # N = 10
beta = 0.1
@time opt = PFB(supp, coe, beta, N, 3, QUIET=false)
println(2^N*opt)


using LinearAlgebra

Pauli = Matrix{Complex{Int8}}[[1 0; 0 1], [0 1; 1 0], [0 -im; im 0], [1 0; 0 -1]]
H = zeros(Int, 2^N, 2^N)
for i = 1:N-1, j = 2:4
    ind = ones(Int, N)
    ind[i] = ind[i+1] = j
    H += real(kron(Pauli[ind]...))
end
for j = 2:4
    ind = ones(Int, N)
    ind[1] = ind[N] = j
    H += real(kron(Pauli[ind]...))
end
v = eigvals(H/4)
println(sum(exp.(-beta*v)))
```

`2^N * opt` is the bound on the partition function `Z`; the exact-diagonalization block below computes
the true `Z = Σ exp(-β·Eᵢ)` to validate it.

### `examples/rdm_block.jl` — RDM block-structure inspection

Uses `QMBCertify.reduce4` and `QMBCertify.bfind` plus `Graphs`/`DynamicPolynomials` to build the
symbolic reduced-density-matrix operator and find its connected (block-diagonal) components — i.e. it
shows *why* the RDM positivity constraint block-diagonalizes. Demonstrates the normal-form reduction
and the Pauli-string encoding directly:

```julia
using QMBCertify
using Graphs
using DynamicPolynomials

d = 6
L = 20
tsupp = [UInt16[]]
for i = 0:3, j = 0:3, k = 0:3, l = 0:3, u = 0:3, v = 0:3
  ind = [i,j,k,l,u,v]
  if all(x->iseven(sum(ind .== x)), 1:3)
    inx = ind .!= 0
    bi = QMBCertify.reduce4(UInt16.(3*(Vector(1:d)[inx] .- 1) + ind[inx]), L) # reduce a monomial to the normal form
    push!(tsupp, bi)
  end
end
unique!(tsupp)
sort!(tsupp)
@polyvar y[1:length(tsupp)]
A = zeros(Int, 2^d, 2^d)
Pauli = Matrix{Complex{Int8}}[[1 0; 0 1], [0 1; 1 0], [0 -im; im 0], [1 0; 0 -1]]
for i = 0:3, j = 0:3, k = 0:3, l = 0:3, u = 0:3, v = 0:3
  ind = [i,j,k,l,u,v]
  if all(x->iseven(sum(ind .== x)), 1:3)
    inx = ind .!= 0
    bi = QMBCertify.reduce4(UInt16.(3*(Vector(1:d)[inx] .- 1) + ind[inx]), L)
    Locb = QMBCertify.bfind(tsupp, length(tsupp), bi)
    if Locb !== nothing
      A += y[Locb]*real(kron(Pauli[i+1], Pauli[j+1], Pauli[k+1], Pauli[l+1], Pauli[u+1], Pauli[v+1]))
    end
  end
end

G = SimpleGraph(2^d)
for i = 1:2^d, j = i+1:2^d
    if abs(A[i,j]) > 1e-6
        add_edge!(G, i, j)
    end
end
blocks = connected_components(G)
println(length.(blocks))
```

### `examples/certify.jl` — manual SOHS reconstruction from exported Gram matrices

The ground-truth for the Gram-export format: takes a `GSB(...; Gram=true)` solve and rebuilds the RHS
coefficient vector (the SOHS certificate's expansion w.r.t. `data.tsupp`) by hand from
`data.GramMat` / `data.sGramMat`, using the discrete-Fourier matrix `P` and the normal-form reduction.
Confirms how the exported Gram blocks reconstruct the moment constraints.

```julia
using QMBCertify

# 1d Heisenberg model
supp = [[1;4]]
coe = [3/4]
N = 4 # number of spins
opt,data = GSB(supp, coe, N, 3, QUIET=false, rdm=0, pso=2, lso=0, Gram=true)

RHS = zeros(length(data.tsupp))
s = Int.(length.(data.basis)/N)
P = [cos(2*pi*(i-1)*(j-1)/N) + sin(2*pi*(i-1)*(j-1)/N)*im for i = 1:N, j = 1:N]
RHS[1] += data.GramMat[1][1][1,1]
for k = 1:s[1]
    w,c = reduce!(data.basis[1][N*(k-1)+1], L=N)
    if c != 0
        Locb = QMBCertify.bfind(data.tsupp, w)
        RHS[Locb] += 2*sqrt(N)*data.GramMat[1][1][1,k+1]
    end
end
for l = 1:2, i = 1:Int(N/2)+1, j = 1:s[l], k = j:s[l], v = 1:N
    w,c = reduce!([data.basis[l][N*(j-1)+1]; data.basis[l][N*(k-1)+v]], L=N, realify=true)
    if c != 0
        Locb = QMBCertify.bfind(data.tsupp, w)
        if j == k
            if l == 1 && i == 1
                RHS[Locb] += c*data.GramMat[1][1][j+1,k+1]
            else
                RHS[Locb] += c*real(data.GramMat[l][i][j,k]*P[i,v])
            end
        else
            if l == 1 && i == 1
                RHS[Locb] += 2*c*data.GramMat[1][1][j+1,k+1]
            else
                RHS[Locb] += 2*c*real(data.GramMat[l][i][j,k]*P[i,v])
            end
        end
    end
end
println(RHS) # The coefficient vector of RHS w.r.t. the monomial vector stored in data.tsupp
```

(The file continues with a second Fourier variant and a J1-J2 `N=10`, `rdm=8`, `pso=3` reconstruction
that also folds in the `PSDstate_entry` / `sGramMat` state-optimality blocks.)

## Pitfalls

- **Relaxation order vs SDP size.** `d` is the tightening knob and cost grows steeply in it (moment
  matrix to degree `2d`). `extra`, `rdm`, and the `pso`/`lso` strengthenings each enlarge the SDP.
  Probe at `d=2` with strengthenings off (`rdm=0, pso=0, lso=0`), read the printed
  `SDP size: n = …, m = …`, then decide what to enable and local-vs-cluster. The binding resource is
  **memory** (Mosek factorizations) — the reference results used a 32-core / 1 TB workstation.
- **`pso` / `lso` are ON by default** (`pso=3`, `lso=true`). For the lightest possible run you must
  pass `pso=0, lso=0` explicitly — the examples that probe cost all do.
- **`rdm` only accepts 8 / 9 / 10** (`else` prints "Adding rdm > 10 is not supported!" and adds
  nothing); `false`/`0` disables it.
- **Solver licensing.** Mosek 11 is required and commercial; obtain the free academic license and make
  sure `MOSEKLM_LICENSE_FILE` / `~/mosek/mosek.lic` resolves *before* the run or the solve aborts.
  There is no open-source fallback.
- **Match the certified Hamiltonian.** In `certify_qmb`, `snn`/`J2` define which Hamiltonian the
  certificate is verified against — set them to match the model you actually solved or you certify the
  wrong system.
- **`Gram=true` is mandatory for any exact post-step.** Without it `data.GramMat` is `nothing` and
  `certify_qmb` / the manual `certify.jl` route have nothing to project.
- **Exact certification is 1D-chain only.** `certify_qmb` / `certify_qmb_corr` target the 1D
  (J1-J2) chain; 2D square-lattice runs get the numeric bound + Gram export with no packaged exact
  certification.
- **Coefficient convention differs by lattice.** NN coefficient is `3/4` (chain) vs `3/2` (square);
  the two-sided observable bound uses `1/4` / `1/2` representatives. Watch the factor.

## Source links

- Repo: <https://github.com/wangjie212/QMBCertify>
- README: <https://github.com/wangjie212/QMBCertify/blob/main/README.md>
- `Project.toml`: <https://github.com/wangjie212/QMBCertify/blob/main/Project.toml>
- Module / exports: <https://github.com/wangjie212/QMBCertify/blob/main/src/QMBCertify.jl>
- `GSB` source: <https://github.com/wangjie212/QMBCertify/blob/main/src/bound_gsp.jl>
- `PFB` source: <https://github.com/wangjie212/QMBCertify/blob/main/src/bound_partfunc.jl>
- Bases / `reduce!` / `slabel` / `mosek_para`: <https://github.com/wangjie212/QMBCertify/blob/main/src/basic_function.jl>
- RDM positivity (`posepsd8/9/10!`): <https://github.com/wangjie212/QMBCertify/blob/main/src/rdm_positivity.jl>
- `certify_qmb`: <https://github.com/wangjie212/QMBCertify/blob/main/src/certification/energy_cert.jl>
- `certify_qmb_corr`: <https://github.com/wangjie212/QMBCertify/blob/main/src/certification/corr_cert.jl>
- Certification helpers (`rigorous_min_eig`, `round_project_qmb`, `dmrg_heisenberg_rat`): <https://github.com/wangjie212/QMBCertify/blob/main/src/certification/helpers.jl>
- Examples folder: <https://github.com/wangjie212/QMBCertify/tree/main/examples>
  - `examples/certified_energy.jl`, `examples/certified_corr.jl`, `examples/ground_state.jl`,
    `examples/partition_function.jl`, `examples/rdm_block.jl`, `examples/certify.jl`
- Reference paper (PRX 14, 031006, 2024): <https://journals.aps.org/prx/abstract/10.1103/PhysRevX.14.031006>
