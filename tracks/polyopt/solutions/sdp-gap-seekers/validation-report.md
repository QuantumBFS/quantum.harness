# Lightweight validation report

No state-polynomial SDP was assembled or solved. These checks validate only
geometry, algebra, normalization, basis bookkeeping, and a finite-patch
Hamiltonian oracle.

## Julia unit suite

Command:

```bash
julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl
```

Result: `182/182` checks passed.

```text
square patch geometry                       24
Pauli canonicalization                     10
bare Pauli basis counts                    72
full state-polynomial formal counts        13
storage estimates                           2
exact local spin identities                22
generic solver-free problem adapter        36
small finite-patch ED construction oracle   3
```

## Small ED oracle

Setup:

```text
Hamiltonian:
  H = Σ_NN S_i·S_j + (1/2) Σ_NNN S_i·S_j
normalization: S=σ/2
finite oracle geometry: Λ_1=[-1,1]², internal bonds only
sites / Hilbert dimension: 9 / 512
sector: full Hilbert space
target: compare two independent matrix builders and basic invariants
```

The first builder consumes the generic exact Pauli term list. The second uses
the independent spin-basis identity

```text
S_i·S_j = S_i^zS_j^z
          + 1/2(S_i^+S_j^- + S_i^-S_j^+).
```

Result:

```text
maximum matrix difference = 0
Hermiticity error         = 0
Tr(H)                     = 0
||[H,S_total^z]||_max     = 0
ground energy             = -3.9593399973974814
ground residual           = 3.34e-15
ground multiplicity       = 2
first distinct energy     = -3.271581605181318
first distinct separation = 0.6877583922161636
```

The ground doublet is consistent with an odd number of spin-1/2 sites. The
finite-patch separation is not a bulk-gap estimate and is not used anywhere in
the SDP specification.

## Repository-level checks

- `make help`: passed; it confirmed NCTSSoS/QMBCertify are optional install
  targets. Neither was installed.
- `make test`: could not start because the active Python lacks the
  `pytest-cov` plugin.
- Plain `python3 -m pytest scripts/tests/ -q`: collection then failed because
  the active Python is 3.10 and lacks `tomllib`; the repository `.venv` is
  absent.
- No dependencies were installed to work around these unrelated environment
  failures.
- The new Julia suite and all three solver-free scripts run with Julia 1.11.1
  and standard libraries only.
- No trailing whitespace was found in the new files.
- The existing tracked README was not modified; all implementation artifacts
  are currently untracked in the team branch.

## What remains unvalidated

- equivalence of a refactored assembly with upstream Ising/Kagome block and
  affine-constraint inventories;
- the actual state-polynomial moment and gap matrices for Square J1-J2;
- any JuMP/solver backend;
- status-to-semantic-result handling under real solver responses;
- infeasibility witness extraction or rational/interval validation;
- any numerical bulk-gap or observable bound.

These are the next gates. In particular, no current output supports the phrase
“certified Square J1-J2 bulk-gap bound.”
