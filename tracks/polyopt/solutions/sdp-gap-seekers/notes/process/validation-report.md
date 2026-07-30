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

Result: `289/289` checks passed.

```text
square patch geometry                       24
Pauli canonicalization                     10
bare Pauli basis counts                    72
full state-polynomial formal counts        13
storage estimates                           2
exact local spin identities                22
generic solver-free problem adapter        43
structured basis manifests                100
small finite-patch ED construction oracle   3
```

## Structured basis manifest

The first regression run deliberately added two checks before changing the
implementation. Both failed:

```text
input PauliWord mutation changed an existing StateMonomial
self-consistently rehashed one-row truncation passed manifest validation
```

The implementation now takes defensive copies of nested Pauli words, manifest
entries, and site IDs. Validation reconstructs the exact row inventory for the
declared family/version instead of checking only generic shape and a
self-reported hash. The same two regressions then passed.

An independent review added adversarial tests before the corresponding fixes.
The first red run stopped on the delimiter-collision regression before the
later testset could execute; the same test-first patch also encoded the
remaining review findings:

```text
["C4","mirror"] and ["C4|mirror"] had the same problem hash
the gap manifest was incorrectly marked incomplete at maximum degree 1
no problem-contextual manifest validator existed
reversed but equivalent inner-site IDs were rejected
an out-of-range inner-site ID could enter a manifest
```

After the fixes, a one-argument validator proves only internal consistency.
The contextual overload reconstructs the problem/role expectation and rejects
consistently rehashed role, site, degree, and digest substitutions. Manifest
site IDs are defensively copied, range-checked, deduplicated, and sorted.

Additional checks cover:

- positive degree `d` and gap degree `d-1`;
- actual, non-renumbered inner-patch site IDs at `L=1` and `L=2`;
- permutation invariance plus duplicate/out-of-range rejection for inner IDs;
- full assembly-plan and problem-SHA invariance under inner-ID permutation;
- gap-row inclusion in the positive rows;
- prefix nesting when `d` increases;
- duplicate, nested-mutation, and truncated-list rejection;
- contextual rejection of role/site/degree/hash substitutions;
- finite-inventory completeness at degrees `0`, `1`, and `2` for 1, 2, and 9
  sites;
- injective problem hashing for delimiter-bearing symmetry generators;
- basis-hash independence from model coefficients and `γ`;
- stable manifest and problem SHA-256 anchors.

For `L=1`, `d=2`, `g=1/2`, and `γ=1/10`:

```text
positive rows = 703
positive SHA-256 =
  83befe24c09bccdc7d228fc60c606d301dd76c10688121e1e466d43a583d5c13

gap rows = 7
gap SHA-256 =
  5be3d2db7be104d1bc431898496e8e34116787a7f14a30886fa6933924bea169

problem SHA-256 =
  f6f7cd7a0cc2e053e40ecd82f52a24438536869e3340b959cd7f68cab4467f4e
```

These hashes identify basis/problem inputs only. They are not solver
certificates or numerical gap bounds. The problem digest uses the tagged,
byte-length-prefixed schema `gap-problem-fingerprint-v2`.

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
- The new Julia suite and all three standard-library solver-free scripts run
  with Julia 1.11.1.
- The separate legacy dump could not load locally because `SpectralGap` is not
  installed in `julia-env`; no dependency was installed to manufacture a
  local substitute for the required pinned SCNet reproduction.
- `git diff --check`: passed for the complete structured-basis diff.
- No dependencies were installed.

These are local checks, not SCNet reproduction artifacts. The remote gate
requires Sihan and Xiansheng to run the same pinned generator and validation
commands independently on SCNet, archive command/environment logs, and compare
canonical digests. Xiansheng's reported legacy-generator run and Sihan's local
unit suite are distinct partial evidence; neither alone satisfies that gate.

## Legacy-inventory interface audit

`origin/feature/legacy-affine-inventory` at `a01a425` was inspected read-only;
it was not merged, rebased, or modified. Its intended row mapping is compatible:
legacy `word/aux` corresponds to the manifest's
`operator_word/state_symbols`, and `pos/gpos` corresponds to
`positive/gap`.

The legacy branch is not yet a frozen coefficient-diff oracle:

- its generator now covers Ising and Kagome `tsupp`, and its reported SCNet
  run passed the 17/18-term assertions, but the generated math inventory and
  canonical digest are not committed;
- its schema says the variable header is excluded from SHA-256, while the
  current script hashes the entire buffered output including that header;
- its schema says solver-free runs omit run metadata, while the script always
  writes a run-metadata file;
- the full `(j,k) -> (tsupp row, coefficient)` wiring remains deferred, and the
  branch's spec/status prose still says the generator has not been run.

The current Square manifest is also flat and unsymmetrized, whereas the legacy
inventory has labelled symmetry blocks. A later assembly contract must preserve
block IDs explicitly; row order alone cannot supply that information.

## What remains unvalidated

- a validated, byte-stable legacy Ising/Kagome inventory and
  coefficient-by-coefficient equivalence with the generic encoding;
- explicit symmetry/block metadata joining a flat manifest to legacy labelled
  PSD blocks;
- the actual state-polynomial moment and gap matrices for Square J1-J2;
- any JuMP/solver backend;
- status-to-semantic-result handling under real solver responses;
- infeasibility witness extraction or rational/interval validation;
- any numerical bulk-gap or observable bound.

These are the next gates. In particular, no current output supports the phrase
“certified Square J1-J2 bulk-gap bound.”
