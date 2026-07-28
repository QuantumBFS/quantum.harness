# SDP Gap Seekers

## Team

| | |
|---|---|
| **Team name** | sdp-gap-seekers |
| **Members** | Xiansheng Cai (蔡贤盛), Sihan Hu (胡思寒) |

## Challenge

Certified bulk spectral-gap bounds for frustrated spin-1/2 models — compute
upper bounds on the locally non-degenerate bulk gap of infinite systems via the
state-polynomial SDP hierarchy of arXiv:2606.03836.

Addresses #88 — released by Xiangling Xu (许湘灵) and Jie Wang (王杰),
polyopt track.

## Approach

The first implementation target is the square-lattice J1-J2 Heisenberg model.
The finite patch is a local consistency window, not a periodic finite-volume
Hamiltonian. The hierarchy tests whether an infinite-volume KMS ground state
can have gap at least `gamma`; finite-level infeasibility excludes that
threshold, while finite-level feasibility does not prove gappedness.

Current sequence:

1. Specify the KMS/state-polynomial hierarchy and its result semantics.
2. Build deterministic square patches, Pauli-word reduction, and reproducible
   basis fingerprints.
3. Select a nested structured basis; a complete dense basis is already too
   large at small `(L,d)`.
4. Reproduce a published transverse-field Ising table entry with the same
   state class and symmetry restriction as the paper.
5. Assemble and validate Square J1-J2 at `g=0`, `0.50`, and `0.535`.
6. Add observable bounds and exact or interval certificate post-processing.

Shastry-Sutherland `g=0` is now implemented as the positive-gap calibration:
its exact dimer-product state passes the assembled `M/G/K` constraints at
`gamma=1` and rejects `gamma=1.1`. This remains a correctness gate, not a
reported SDP bound. Fallbacks #124 and #49 are not part of the current
implementation branch.

## Current artifacts

- [`square-j1j2-gap-sdp-spec.md`](square-j1j2-gap-sdp-spec.md): programmable
  mathematical specification and solver-status semantics.
- [`basis-counts.md`](basis-counts.md): exact solver-free formal basis counts
  and raw dense-memory estimates.
- [`structured-basis-manifest.md`](structured-basis-manifest.md): materialized
  positive/gap row contract, completeness semantics, ordering, and SHA-256.
- [`local-identities.md`](local-identities.md): exact two-, three-, and
  four-site identities and their role in structured relaxations.
- [`spectralgap-refactor-plan.md`](spectralgap-refactor-plan.md): migration
  plan from model-specific code to a generic lattice/patch interface.
- [`validation-report.md`](validation-report.md): tests, finite-patch ED oracle,
  and the precise boundary of what has not yet been certified.
- [`SHASTRY_SUTHERLAND_DIMER_GATE.md`](SHASTRY_SUTHERLAND_DIMER_GATE.md):
  periodic orthogonal-dimer geometry, exact `g=0` moment oracle, assembled
  `M/G/K` gate, and `4x4` finite-torus benchmarks at `g=0,0.8`.

The solver-independent Julia core uses standard libraries only and does not
solve an SDP. The optional finite-torus ED oracle uses NumPy and SciPy. The
external Mosek/SpectralGap/QMBCertify environment reported in [`notes/`](notes/)
is a separate solver setup; its local patches must be committed and
regression-tested before this repository can rely on them.

The Julia checks reported here were run locally; they are not SCNet
reproduction artifacts. Before the legacy inventory becomes a frozen oracle,
Sihan and Xiansheng must each run the same pinned generator and validation
commands independently on SCNet, retain the command/environment logs, and
compare the resulting canonical digests. One person's remote run or the other
person's local unit suite does not satisfy that two-party gate.

## Result language

- `infeasible` is physically conclusive only with a valid solver status and
  auditable infeasibility evidence.
- timeout, numerical failure, and ambiguous statuses are `unknown`.
- floating-point results are numerical SDP bounds until certificate
  post-processing accounts for solver error.
- no current file reports a Square J1-J2 bulk-gap bound.

## Division of labor

- Solver environment, legacy SpectralGap fixes, and paper-baseline logs:
  Xiansheng.
- Square model specification, structured-basis prototype, exact algebra, and
  solver-independent tests: Sihan.
- Independent SCNet reproduction of the frozen manifest/inventory: both
  members, from the same pinned revisions.
- SDP assembly, certificate validation, and reported scans: joint review.
