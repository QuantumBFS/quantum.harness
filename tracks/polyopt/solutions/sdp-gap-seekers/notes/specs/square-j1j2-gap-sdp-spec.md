# Square-lattice J1-J2 bulk-gap SDP: programmable specification

Status: mathematical/implementation specification, no SDP result yet.

Primary source: X. Xu et al., *The bulk spectral gap is semi-decidable:
a convergent family of certified upper bounds*, arXiv:2606.03836v1,
especially Definitions 2.1 and 2.4, Theorem 2.5, and Remarks 2.2 and 2.7.

This document corrects the finite-volume excited-state formulation in the
initial theory handoff. The target is not a periodic-cluster value `E1-E0` and
does not introduce an unknown ground-state vector or an orthogonality
constraint. It tests the existence of an infinite-system KMS ground state
whose local excitations obey a gap inequality.

## 0. Physical meaning: state, infinite dynamics, and bulk gap

### 0.1 Finite-temperature KMS state versus KMS ground state

At finite inverse temperature `β`, the Kubo-Martin-Schwinger (KMS) condition is
an equilibrium condition involving the time evolution `τ_t`. For analytic
observables `A,B`, one common convention writes its boundary relation as

```text
ω_β(A τ_(iβ)(B)) = ω_β(B A).
```

For a finite system this selects the Gibbs state

```text
ρ_β = exp(-βH) / Tr(exp(-βH)).
```

The paper uses “KMS ground state” for the zero-temperature ground-state notion,
not for a finite-`β` thermal state. It is characterized by the positive-energy
condition

```text
-i ω(a† δ(a)) ≥ 0
```

for every local `a`, where `δ` generates the infinite-system dynamics. For a
local operator this becomes

```text
ω(a†[H,a]) ≥ 0.
```

This says that no local operation can lower the energy. In finite dimension it
is equivalent to the familiar statement that the density matrix is supported
on the lowest eigenspace. In an infinite system it is the usable replacement
for “diagonalize `H` and take its lowest eigenvector.”

A zero-temperature ground-state condition should therefore not be implemented
by putting `β=∞` into a finite-temperature matrix formula. The hierarchy starts
directly from the positive-energy condition.

### 0.2 Why the infinite Hamiltonian has no directly usable `E0` and `E1`

For an infinite lattice the formal sum

```text
H = Σ_X Φ(X)
```

is extensive and generally does not converge in operator norm to an element of
the quasi-local observable algebra. Consequently, there is no single finite
matrix whose first two eigenvalues can simply be called `E0` and `E1`.

The dynamics is nevertheless well defined. For a local observable `a`, only
finitely many finite-range interaction terms overlap its support, so

```text
δ(a) = i[H,a]
```

is a finite, well-defined local expression. Equivalently, sufficiently large
finite windows all give the same commutator. The SDP uses these local
commutators and local moments; it never assigns a physical boundary condition
and never subtracts two extensive total energies.

### 0.3 The GNS bulk Hamiltonian

Every state `ω` admits a Gelfand-Naimark-Segal (GNS) representation

```text
(H_ω, π_ω, |Ω_ω⟩),
```

where `|Ω_ω⟩` is cyclic and reproduces expectations:

```text
ω(a) = ⟨Ω_ω|π_ω(a)|Ω_ω⟩.
```

For a KMS ground state, the infinite-system dynamics is implemented in this
representation by a unique positive, possibly unbounded, self-adjoint
generator `H_ω`:

```text
π_ω(τ_t(a)) = exp(i t H_ω) π_ω(a) exp(-i t H_ω),
H_ω |Ω_ω⟩ = 0,
H_ω π_ω(a)|Ω_ω⟩ = -i π_ω(δ(a))|Ω_ω⟩.
```

`H_ω` is the paper's bulk Hamiltonian. It is not a finite-window Hamiltonian,
and it depends on the chosen infinite-volume state/representation.

### 0.4 A bulk gap is a local-excitation energy scale, not a ground state

The ground state is the functional `ω`. The gap is a nonnegative number
associated with the spectrum of `H_ω`. The state is locally non-degenerate and
bulk-gapped by at least `γ` when

```text
ker(H_ω) = span{|Ω_ω⟩},
Spec(H_ω) ∩ (0,γ) = ∅.
```

The equivalent commutator inequality is

```text
ω(a†[H,a]) ≥ γ(ω(a†a)-|ω(a)|²).
```

Here

```text
ω(a†a)-|ω(a)|²
```

is the squared norm of the part of the locally excited vector
`π_ω(a)|Ω_ω⟩` perpendicular to `|Ω_ω⟩`. Thus `γ` is the minimum energy cost per
unit norm of a nontrivial local excitation. It is not a variational energy of a
new ground state.

“Locally non-degenerate” does not forbid several globally distinct pure
ground states in inequivalent GNS representations, as in spontaneous symmetry
breaking or topological sectors. It forbids an additional zero-energy vector
reachable from the chosen `|Ω_ω⟩` by local observables.

### 0.5 How the paper turns state-dependent gaps into the system gap

The gap property above is first defined for one KMS ground state `ω`. The paper
then defines the system bulk gap as

```text
Δ_bulk = sup { γ ≥ 0 :
               there exists a KMS ground state ω
               with locally non-degenerate bulk gap at least γ }.
```

The quantifier is **there exists**, not “for every KMS ground state.” In
state-wise language, the paper takes the supremum over the locally
non-degenerate gap scales realized by KMS ground states. This convention
matters when there are multiple pure states and mixed states:

- an unrestricted hierarchy may select any KMS ground state;
- a symmetry constraint first restricts the allowed KMS states and then takes
  the same supremum inside that class;
- a symmetric mixture can have local degeneracy and gap zero even when a pure
  symmetry-broken KMS state has a positive local bulk gap.

Accordingly, an unrestricted and a symmetry-restricted bound answer different
questions and must never be combined into one reported `Δ_bulk`.

## 1. Claim and logical direction

For a state `ω` on the infinite quasi-local algebra and every local operator
`a`, define

```text
energy(a)   = ω(a† [H,a]),
variance(a) = ω(a†a) - |ω(a)|².
```

The locally non-degenerate bulk-gap condition at threshold `γ ≥ 0` is

```text
ω(a† [H,a]) ≥ γ (ω(a†a) - |ω(a)|²)       for every local a.
```

Equivalently, after imposing stationarity, use the Hermitian expression

```text
1/2 ω(a†[H,a] - [H,a†]a)
    ≥ γ (ω(a†a) - |ω(a)|²).
```

At a finite relaxation level:

- infeasibility is a necessary-condition failure and excludes a bulk gap of
  at least `γ`;
- feasibility at one level proves no physical lower bound on the gap;
- the largest relaxation-feasible `γ` is an upper bound on the physical bulk
  gap;
- imposing a state symmetry changes the target to the symmetry-restricted
  bulk gap.

The finite patch below is a local consistency window. It is not assigned OBC,
PBC, or any other physical boundary condition.

## 2. Model and normalization

Sites are `r=(x,y) ∈ Z²`. Let `X_r,Y_r,Z_r` be Pauli matrices and
`S_r = (X_r,Y_r,Z_r)/2`. Set `J1=1` and `g=J2/J1`:

```text
H(g) = 1/4 Σ_(r,r')∈E1 (X_r X_r' + Y_r Y_r' + Z_r Z_r')
     + g/4 Σ_(r,r')∈E2 (X_r X_r' + Y_r Y_r' + Z_r Z_r').
```

`E1` contains each horizontal/vertical nearest-neighbour bond once. `E2`
contains each diagonal next-nearest-neighbour bond once. Both couplings are
antiferromagnetic when positive. The challenge points are
`g ∈ {0, 0.50, 0.535}`.

The polynomial degree of every interaction term is two:

```text
deg(H) = 2.
```

Changing from `S` to Pauli variables without the factor `1/4` changes every
reported energy and gap by a factor of four; the implementation must test this
normalization explicitly.

## 3. Patch, interaction buffer, and local Hamiltonian

The first implementation uses a square exhaustion:

```text
Λ_L = {(x,y): -L ≤ x ≤ L, -L ≤ y ≤ L},
I_L = Λ_(L-1),        L ≥ 1.
```

Thus `Λ_L` has `(2L+1)²` sites. The next-nearest-neighbour interaction changes
each coordinate by at most one, so its interaction range in the max norm is
`l=1`. `I_L` is the one-layer eroded inner patch.

Define `H_Λ(g)` by including every `E1` or `E2` bond whose two endpoints are
in `Λ_L`. If an operator is supported in `I_L`, then every interaction term
that fails to commute with it is contained in `Λ_L`. Therefore

```text
[H_Λ(g), a] = [H(g), a]       for supp(a) ⊆ I_L.
```

This equality, rather than a boundary condition, is why stationarity and gap
tests are restricted to `I_L`.

The API should not encode square-specific erosion in the solver. It should
receive:

```text
Patch(
    outer_sites,
    inner_sites,
    interactions,     # support, coupling, Pauli components
    coordinates,
)
```

and validate that every interaction touching `inner_sites` lies completely in
`outer_sites`.

## 4. Canonical Pauli algebra

A canonical Pauli word is a sorted mapping

```text
site -> X | Y | Z
```

with an external coefficient in `{±1, ±i}`. Reduction uses

```text
σ_r^a σ_r^b = δ_ab I + i ε_abc σ_r^c,
[σ_r^a, σ_s^b] = 0 for r ≠ s,
(σ_r^a)† = σ_r^a.
```

Required implementation properties:

1. Sort by a deterministic coordinate/site ID.
2. Reduce same-site products exactly over Gaussian-rational coefficients.
3. Never use random hashes to identify a word or a linear constraint.
4. Keep the scalar phase separate from the canonical word.
5. Define word degree as the number of nonidentity site factors after Pauli
   reduction.
6. Hash the ordered canonical basis and save that hash with every run.

For `n` sites, the number of canonical operator Pauli words of degree at most
`d` is

```text
P(n,d) = Σ_(k=0)^min(d,n) C(n,k) 3^k.
```

This is only the operator-word count. The state-polynomial moment basis below
is larger.

## 5. State-polynomial variables

Introduce a commuting formal state symbol `ζ(w)` for every canonical operator
word `w`. It represents `ω(w)` and obeys

```text
ζ(I) = 1,
ζ(w†) = ζ(w)*,
ζ(w + c v) = ζ(w) + c ζ(v),
[ζ(w), ζ(v)] = 0,
ζ(w ζ(v)) = ζ(w) ζ(v).
```

A noncommutative state monomial has the normal form

```text
s = ζ(w1) ζ(w2) ... ζ(wk) v,
```

where the `ζ(wi)` factors are sorted as a multiset and `v` is one operator
Pauli word. Its total degree is

```text
deg(s) = Σ_i deg(wi) + deg(v).
```

After canonical Pauli reduction, all bare Pauli strings are Hermitian, so their
individual state symbols are real. Complex coefficients still arise from
operator multiplication and commutators.

For reference, on a finite patch the formal generating function for the full
state-monomial basis is

```text
A(t) = (1+3t)^n,
S(t) = Π_(w ≠ I) (1-t^deg(w))^(-1),
B(t) = A(t) S(t).
```

The sum of coefficients of `B(t)` through degree `d` counts the unreduced full
noncommutative state-monomial basis. It grows too quickly to be the practical
basis at interesting patch sizes.

Two basis modes must be named separately:

- `FullBasis(L,d)`: all canonical state monomials required by Definition 2.4;
- `StructuredBasis(spec)`: a declared subset chosen for locality and symmetry.

A structured subset is still sound: every true `γ`-gapped KMS state restricts
to it, so infeasibility still excludes `γ`. Completeness applies only if the
nested family of structured bases exhausts the full state-polynomial algebra.
Results from an ad hoc subset must be labelled by its basis specification and
hash, not only by `(L,d)`.

## 6. Primal moment feasibility problem

Let `ℒ` be a linear functional on scalar state polynomials of total degree at
most `2d`, supported in `Λ_L`.

### 6.1 Positivity matrix

Let `B_pos` be the selected noncommutative state-monomial basis of degree at
most `d` on `Λ_L`. Define

```text
M_pos[s,t] = ℒ(ζ(s† t)),       s,t ∈ B_pos.
```

Impose

```text
ℒ(1) = 1,
M_pos ⪰ 0.
```

All products are reduced to the canonical scalar state-polynomial basis before
matrix coefficients are assembled.

### 6.2 Stationarity constraints

Because `deg(H)=2`, use state monomials `q` of degree at most `2d-2`, with
their operator support inside `I_L`. Impose

```text
ℒ(ζ([H_Λ(g),q])) = 0.
```

One complex equality is emitted as two real equalities after exact canonical
reduction. Purely zero or duplicate equalities are removed deterministically.

### 6.3 Gap matrix

Because `deg(H)=2`, the gap basis has degree at most `d-1`. Let `B_gap` be the
selected noncommutative state monomials supported in `I_L`. Define

```text
M_gap[s,t] =
  ℒ(
    1/2 ζ(s†[H_Λ(g),t] - [H_Λ(g),s†]t)
    - γ (ζ(s†t) - ζ(s†)ζ(t))
   ),
  s,t ∈ B_gap.
```

Impose

```text
M_gap ⪰ 0.
```

The product `ζ(s†)ζ(t)` is why a standard linear moment hierarchy on operator
words is insufficient. It must remain a product of formal state symbols until
lifted into the state-polynomial moment functional `ℒ`.

At `γ=0`, stationarity plus `M_gap ⪰ 0` recovers the truncated KMS ground-state
condition. At positive `γ`, the variance subtraction removes the component of
the local excitation parallel to the GNS ground-state vector; no explicit
ground-state vector or orthogonality constraint appears.

### 6.4 Optional observable objective

For a square `2R × 2R` window `W_R ⊆ I_L`, first define the operator

```text
O_N(W_R) =
  1/|W_R|² Σ_(i,j∈W_R)
  (-1)^(x_i+y_i+x_j+y_j)
  1/4 (X_iX_j + Y_iY_j + Z_iZ_j).
```

The challenge's squared Néel order parameter is

```text
M_N²(W_R) = ω(O_N(W_R)) = ζ(O_N(W_R)).
```

At fixed `(L,d,γ)`, solve both

```text
min ℒ(ζ(O_N(W_R)))     and     max ℒ(ζ(O_N(W_R)))
```

over the same feasible set. If the feasibility problem is empty, no
observable interval exists at that threshold. If it is nonempty, the interval
is conditional: every physical KMS ground state with bulk gap at least `γ`
must lie inside it.

## 7. Symmetry modes

The default scientific result is:

```text
symmetry_mode = unrestricted
```

No moment is set to zero merely because the anticipated phase is symmetric.

Optional state restrictions are expressed as explicit global automorphisms
`α` commuting with the infinite-system dynamics:

```text
ℒ(α(p)) = ℒ(p)
```

whenever both state polynomials are represented in the truncation. Candidate
groups include lattice translations, centered `D4` operations, global spin
rotations, and time reversal.

Every result must report one of:

```text
unrestricted bulk-gap upper bound
G-symmetric-state bulk-gap upper bound, with generators of G listed
```

Important exclusions:

- The sublattice Marshall sign transformation is not a symmetry of the
  isotropic square Heisenberg Hamiltonian as a Pauli automorphism of the form
  asserted in the original handoff.
- At `g>0`, diagonal J2 bonds also destroy the bipartite sign structure used
  by sign-free QMC.
- The first excitation cannot be assumed to be a one-magnon state in the
  frustrated region. Deleting all other representation blocks would change
  the gap being tested.

Symmetry can be used in two distinct ways and the code must not conflate them:

1. add invariance constraints, which restrict the allowed KMS states;
2. block-diagonalize the resulting invariant SDP, which is an exact numerical
   reparameterization of that already-declared restriction.

## 8. Solver-status semantics and certification

The public result type must not return a Boolean. Use:

```text
GapTestResult(
    conclusion,        # feasible | infeasible | unknown
    rigor,             # exact_certificate | residual_checked_float | none
    raw_termination_status,
    primal_status,
    dual_status,
    objective,
    residuals,
    psd_min_eigenvalues,
    witness_path,
    basis_hash,
    setup,
)
```

Interpretation for a direct primal feasibility model:

- `feasible`: a primal feasible point passed declared residual checks. This
  locates the relaxation threshold but does not prove the physical system is
  gapped.
- `infeasible`: a primal-infeasibility/Farkas witness was extracted and
  independently validated. This excludes physical gap `≥ γ`.
- `unknown`: time limit, iteration limit, numerical error,
  `INFEASIBLE_OR_UNBOUNDED`, missing witness, or failed residual audit.

`DUAL_INFEASIBLE` is not a universal synonym for physical exclusion. Its
meaning depends on whether the encoded JuMP model is the primal moment problem
or the dual sum-of-Hermitian-squares problem. The formulation and
primal/dual orientation must be stored in the run metadata.

A floating-point solver status alone is a numerical result, not a strict
certificate. Until rational or interval post-processing is implemented:

```text
"numerically infeasible at the stated tolerances"
```

is allowed; `"certified upper bound"` is reserved for an independently
validated infeasibility witness.

The current upstream `SpectralGap` convention

```text
flag = (termination_status == OPTIMAL)
```

is unsafe because all other statuses are collapsed into one branch.

## 9. Threshold scan and bisection

At a fixed relaxation, feasibility is theoretically monotone:

```text
γ feasible  => every 0 ≤ γ' ≤ γ is feasible.
```

Use the following protocol:

1. Evaluate a declared coarse increasing grid in `γ`.
2. Require a residual-checked feasible point at the lower bracket.
3. Require a validated infeasibility witness at the upper bracket.
4. If any intermediate solve is `unknown`, retain the last certified upper
   endpoint and do not update the bracket through that point.
5. Bisect only inside a decisive feasible/infeasible bracket.
6. Stop at a declared `γ` width; never infer more digits than the witness and
   residual audit support.

The lower endpoint is not a lower bound on the physical bulk gap. It is only a
lower bracket on the finite relaxation's feasibility threshold. The validated
infeasible upper endpoint is the one-sided physical statement:

```text
Δ_bulk ≤ γ_upper
```

or the corresponding symmetry-restricted statement.

Before accepting a scan, check that conclusions do not change from
`infeasible` back to `feasible` as `γ` increases. Such a reversal is numerical
or implementation failure, not new physics.

## 10. Proposed Julia-facing interface

```julia
patch = square_j1j2_patch(L; exhaustion=:linf_ball, buffer=1)
model = SquareJ1J2(; J1=1//1, g=1//2, spin_normalization=:S)
basis = StructuredGapBasis(;
    positive_words=:local_pauli,
    gap_words=:inner_local_pauli,
    state_symbol_degree=d,
    deterministic=true,
)

result = certify_Heisenberg_square_gap(
    patch,
    model,
    gamma,
    d;
    basis,
    symmetry=NoStateSymmetry(),
    formulation=:primal_moment,
    optimizer,
    tolerances,
    save_witness=true,
)
```

Required pre-solve checks:

```text
validate_unique_bonds(patch)
validate_inner_buffer(patch, model)
validate_pauli_normalization(model)
validate_basis_degree(basis, d)
validate_hermitian_moment_matrices()
estimate_sdp_size()
```

The scan wrapper is:

```julia
scan_gap_threshold(config, gamma_grid)
bisect_gap_threshold(config, feasible_gamma, infeasible_gamma; gamma_tol)
```

Both wrappers consume `GapTestResult.conclusion`; neither is allowed to branch
directly on a raw solver status.

## 11. Run record

Every result cell must preserve:

```text
model and exact rational couplings
spin/Pauli normalization
outer and inner coordinates
NN and NNN bond lists
state-symmetry generators, or "none"
L, d, γ, R
complete basis specification and hash
positive/gap PSD block sizes
number of scalar moments and affine constraints
solver/version/tolerances/formulation
raw status, residuals, PSD eigenvalue diagnostics
infeasibility witness and independent validation result
runtime and peak memory
source commit IDs
```

Failed, timed-out, and unknown cells remain in the scan manifest.

## 12. Lightweight validation gates before any large solve

1. Pauli reducer against explicit 1-, 2-, 3-, and 4-spin Kronecker matrices.
2. Patch bond counts and one-layer commutator-buffer property.
3. Two-spin Heisenberg spectrum: singlet `-3/4`, triplet `+1/4`.
4. Small square-cluster ED only as a Hamiltonian/commutator oracle; it is not
   the bulk-gap result.
5. Reproduce one explicit TFIM entry from Table S1 of arXiv:2606.03836 with
   the same `(L,d)`, normalization, and imposed symmetries.
6. Verify nested-basis hashes and the expected nonincreasing relaxation upper
   bound as `L` or `d` increases.
7. Run a deliberate solver timeout and confirm it returns `unknown`, never
   `infeasible`.

No non-trivial SDP should start until a setup card records the exact
Hamiltonian, patch, state symmetry class, basis, `(L,d,γ,R)`, matrix/block
inventory, estimated memory/time, solver, and certificate policy.
