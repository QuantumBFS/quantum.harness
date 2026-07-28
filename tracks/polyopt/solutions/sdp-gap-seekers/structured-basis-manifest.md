# Structured basis manifest

This file defines the solver-independent basis contract implemented by
`src/GenericGapModel.jl`. The contract is needed because a finite
state-polynomial relaxation is identified by its actual rows, not only by the
patch level `L` and degree `d`.

No SDP is assembled or solved here. A manifest makes later coefficient
assembly reproducible; it is not a spectral-gap result.

## Scientific role

At a trial threshold `γ`, the hierarchy asks whether an infinite-volume KMS
ground state can satisfy the local gap inequality

```text
ω(a†[H,a]) ≥ γ(ω(a†a) - |ω(a)|²)
```

for every local operator `a`. In matrix form, the gap constraint is the
positive-semidefinite condition `K - γG ⪰ 0`, together with normalization,
moment positivity, and stationarity.

Every physical state with gap at least `γ` restricts to a feasible point of
every sound finite basis. Consequently:

- validated finite-level infeasibility excludes `gap ≥ γ` and gives the
  one-sided statement `Δ_bulk ≤ γ`;
- finite-level feasibility does not give a physical lower bound and need not
  extend to an infinite-volume state;
- a nested complete hierarchy is needed for the relaxation thresholds to
  converge tightly to `Δ_bulk`.

An incomplete structured subset can therefore support a rigorous exclusion,
provided all encoded constraints are exact and an infeasibility witness is
independently validated. It cannot turn a feasible pseudo-moment into evidence
for a nonzero bulk gap.

## Mathematical object

A row is represented by

```text
StateMonomial = ζ(w₁)…ζ(wₖ) v,
degree        = Σ_i degree(w_i) + degree(v),
```

where each `w_i` and `v` is a canonical Pauli word. State symbols commute, so
`w₁,…,wₖ` are stored in canonical sorted order. Identity state symbols are
removed because `ζ(I)=1`; the operator word `v` may be identity.

The first versioned selector is

```text
StructuredBasisSpec(:one_symbol_lift, 1).
```

For a declared site set and maximum degree, it contains:

1. every bare Pauli word `v` through that degree;
2. one pure scalar row `ζ(w)` for every nonidentity Pauli word `w` through that
   degree.

It deliberately omits multi-symbol rows such as `ζ(w₁)ζ(w₂)` and mixed rows
such as `ζ(w)v`. It applies no lattice, spin, reflection, or other symmetry
quotient. The family is therefore not a complete hierarchy, but that is
different from the finite-level meaning of `is_complete`.

For one concrete `site_ids,max_degree` pair, `is_complete=true` means that the
materialized rows equal the full formal state-polynomial inventory for exactly
those inputs. The v1 rows are a proved subset of that inventory. The
implementation checks its materialized count against the exact one-symbol
count and then uses equality with the exact full-basis count to prove finite
equality. Thus, for every nonempty site set:

- maximum degree `0` or `1`: `is_complete=true`;
- maximum degree `2` or higher: `is_complete=false`.

This flag says nothing about whether the selector family becomes complete as
the degree grows.

## Positive and gap roles

For a `GapProblem` at degree `d`:

- the `:positive` manifest uses all outer-patch site IDs through degree `d`;
- the `:gap` manifest uses the actual inner-patch site IDs through degree
  `d-1`.

The inner site IDs are not renumbered to `1:n_inner`. Preserving the original
IDs is necessary for later commutator and Hamiltonian coefficient assembly.
Manifest generation takes a defensive copy, rejects duplicates and IDs outside
the outer patch, and sorts the copy. Reversing an otherwise identical
`LocalPatch.inner_ids` vector therefore produces identical rows and a
byte-identical manifest hash without mutating the patch.

The v1 selector is nested in degree. Increasing `d` appends higher-degree rows
without reordering the existing prefix. Because the inner sites are a subset
of the outer sites, the gap rows are also contained in the corresponding
positive manifest.

`AssemblyPlan.is_complete` describes the mathematical selection, not whether
a solver matrix has been allocated:

- `:one_symbol`: incomplete count-only baseline;
- `:full_count_only`: complete formal-basis count, not a materialized basis;
- `:structured`: conjunction of the materialized manifests' completeness
  flags.

For the `L=1,d=2` fixture, the positive manifest has maximum degree `2` and is
incomplete, while the gap manifest has maximum degree `1` and is complete.
Their conjunction, and hence `AssemblyPlan.is_complete`, remains `false`.

## Ordering contract

Pauli factors inside a word are site-sorted and use the fixed axis order
`X,Y,Z`. State symbols inside a monomial are sorted by their canonical Pauli
strings. Manifest rows then use the total order

```text
(
  total degree,
  number of state symbols,
  joined canonical state-symbol strings,
  canonical operator-word string,
)
```

The serialized row form is

```text
zeta=[<word>|...];op=<word>
```

with `I` for the identity. Row indices are one-based and are included in the
manifest fingerprint.

## SHA-256 contract

The manifest digest hashes UTF-8 lines joined by `\n` under schema
`structured-basis-manifest-v1`. The hashed metadata includes:

- family and family version;
- role (`positive` or `gap`);
- exact site IDs and maximum degree;
- completeness and the fixed selection rule;
- the explicit `symmetry_applied=false` marker;
- every ordered serialized row and its stable index.

The manifest hash intentionally does not depend on the Hamiltonian
coefficients, `γ`, or model name: it identifies a basis. The separate
`AssemblyPlan.problem_sha256` includes those physical inputs and embeds both
manifest hashes. Problem hashes use schema `gap-problem-fingerprint-v2`: every
tag and UTF-8 value is byte-length-prefixed, and symmetry name and generators
are serialized as separate indexed fields. The inner-site set is serialized
through the same sorted, unique, range-validated IDs used by the manifests, so
mere input permutation cannot change the problem identity. In particular,
generators `["C4","mirror"]` cannot collide with the single generator
`["C4|mirror"]`.

For the Square J1-J2 `L=1`, `d=2` fixture:

```text
positive rows = 703
positive SHA-256 =
  83befe24c09bccdc7d228fc60c606d301dd76c10688121e1e466d43a583d5c13

gap rows = 7
gap SHA-256 =
  5be3d2db7be104d1bc431898496e8e34116787a7f14a30886fa6933924bea169

problem SHA-256 at g=1/2 and γ=1/10 =
  f6f7cd7a0cc2e053e40ecd82f52a24438536869e3340b959cd7f68cab4467f4e
```

Constructors take defensive copies of nested Pauli words, row arrays, and site
IDs. Exported Julia vectors remain technically mutable, so downstream code
must treat a manifest as immutable.

The one-argument `validate_basis_manifest(manifest)` checks exact membership
for the manifest's own declared family, role, sites and degree, along with
order, completeness semantics, selection-rule text, and SHA-256. Mutation or a
self-consistently rehashed truncated list is rejected. That method cannot
establish that the declarations belong to a particular problem.

Assembly must instead call
`validate_basis_manifest(manifest, problem, expected_role)`. This contextual
method reconstructs the expected manifest from the problem and compares every
field. It rejects an internally valid manifest whose role, site set, or degree
was consistently changed and rehashed. `assembly_plan` applies this contextual
check to both generated roles.

## Legacy inventory integration

The read-only legacy branch `origin/feature/legacy-affine-inventory` uses:

```text
legacy word  ↔ StateMonomial.operator_word
legacy aux   ↔ StateMonomial.state_symbols
pos          ↔ positive role
gpos         ↔ gap role
```

The legacy Ising/Kagome inventory also has two labelled symmetry blocks. The
current Square manifest is one flat, unsymmetrized list, so block identity and
symmetry action must be added at the assembly layer rather than inferred from
row order. The v1 one-symbol selector is a declared Square baseline; it is not
claimed to reproduce the legacy hand-selected bases.

Before generic SDP assembly, the frozen legacy oracle and the generic encoding
must be compared coefficient by coefficient after a shared canonical
word/state-symbol conversion. Hamiltonian terms, basis rows, affine rows, and
block IDs are separate comparison layers. Sihan and Xiansheng must each
reproduce the pinned inventory/manifest independently on SCNet and retain the
resulting digests and logs; the current local Julia suite is not a remote
reproduction artifact.

## Current boundary and next gate

Covered now:

- materialized positive and gap row inventories;
- actual inner-site numbering;
- canonicalization and validation of the inner-site set;
- deterministic nesting, serialization, and SHA-256;
- finite-inventory incomplete/complete semantics;
- self-contained plus problem-contextual validation;
- mutation, truncation, role, site, and degree attack rejection;
- injective, versioned problem-fingerprint framing;
- model- and threshold-independent basis identity.

Not covered:

- products of rows and their canonical scalar moments;
- covariance entries `ζ(s†t)-ζ(s†)ζ(t)`;
- commutator-energy entries and stationarity rows;
- symmetry quotienting or PSD block decomposition;
- coefficient comparison with a validated legacy dump;
- JuMP/solver construction, solver status, or witness validation;
- any numerical or certified Square J1-J2 bulk-gap bound.

The next implementation gate is the frozen legacy coefficient diff. Only after
that diff passes should the generic code assemble moment, stationarity, and gap
matrices. A solver run remains a later, separately reviewed step.
