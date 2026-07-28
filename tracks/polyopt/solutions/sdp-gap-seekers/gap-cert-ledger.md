# Gap ledger — numerical γ-transition candidates (NOT yet certified)

> ⚠️ **Honest status (corrected 2026-07-28, reconciled per advisor recheck
> @491083f):** the γ-transition values below are **numerical flag-transition
> candidates**, not certified upper bounds. The legacy `certify_*_gap` returns
> `flag = (status==OPTIMAL ? 1 : 0)`, which collapses every non-OPTIMAL Mosek
> status into `flag=0`. We patched the certifiers to retain raw
> `(termination, primal_status, dual_status, objective)` and to export a
> portable certificate artifact.
>
> For the TFIM N=9 γ=0.26 instance we now have a **schema-complete standalone
> verifier** that audits the exported conic instance against one vector `x`
> and rejects 14/14 deliberate corruptions (see §8). That makes the ray a
> **soundly audited numerical candidate** — still `SLOW_PROGRESS`, so NOT a
> rigorous proof.
>
> **Scope correction:** challenge #88 requests extensions to
> **square J1-J2 → Shastry-Sutherland → triangular J1-J2**, in that order.
> Kagome is already in the upstream `SpectralGap.jl` example, so the kagome
> rows are a **legacy reproduction / calibration**, not the requested
> scientific extension. The square J1-J2 extension is the actual target.

## Methodology — γ-scan, three-way semantics

`certify_*(N, H, γ, d)` solves an SOS-side conic problem `Max λ` s.t. a
homogeneous coefficient identity + PSD Gram blocks (positivity, gap) + free
stationarity multipliers. The three-way interpretation:
- `termination=OPTIMAL` → γ feasible → Δ could be ≥ γ.
- a clean `termination=DUAL_INFEASIBLE` with a primal improving ray → γ excludes
  the gap (candidate certified infeasible).
- anything else (`SLOW_PROGRESS`, timeout, numerical) → **unknown**, must not be
  collapsed into "infeasible."

The legacy `flag=(status==OPTIMAL?1:0)` loses this distinction; the patched
certifiers retain the raw statuses. The §8 pipeline (below) extracts the primal
ray and audits it independently of the originating model/solve.

## Run ledger

| # | model | config | numerical Δ-transition | reference | solver | runtime | status |
|---|---|---|---|---|---|---|---|
| 1 | 1D TFIM | N=9, g=0.5, d=2 | flag flips 0.25→0.26; **primal ray extracted + schema-completely audited** (λ=0.0051>0, Gram PSD, ‖A·x+const‖=1.3e-13, 14/14 corruptions rejected) | 0.258 provenance unverified (example.jl sets lb=ub=0.24; cite paper Table S1 if used) | Mosek 11.2.2 | 4–25 s | pipeline calibration; **§8 status: NUMERICALLY_AUDITED_CANDIDATE** (SLOW_PROGRESS, not a rigorous proof) |
| 2 | Kagome Heisenberg | N=13, d=3 | flag flips 1.26→1.28 | ~1.28 (bundled in `example.jl`) | Mosek 11.2.2 | ~290 s | legacy reproduction (kagome is in the upstream example; low novelty) |
| 3 | Kagome Heisenberg | N=27, d=3 | — | ~1.15 (example.jl) | Mosek 11.2.2 | — | killed — 2h08m zero progress on 128-cpu/486GB |
| 4 | Kagome Heisenberg | N=13, d=4 | flag flips 1.26→1.28 | identical to d=3 | Mosek 11.2.2 | ~220 s | identical-SDP regression, not convergence — `get_kagome_basis` has no `d>3` branch |

**Raw γ-scans (numerical):**
- **TFIM N=9 g=0.5 d=2:** flag=1 at γ∈{0.15,0.20,0.22,0.24,0.25}; flag=0 at
  γ∈{0.26,0.27,0.28,0.30,0.34}. Raw Mosek status at γ=0.26/0.30: `SLOW_PROGRESS`
  + `primal_status=INFEASIBILITY_CERTIFICATE` + `dual_status=NO_SOLUTION`.
- **Kagome N=13 d=3:** flag=1 at γ∈{1.0,1.2,1.26}; flag=0 at
  γ∈{1.28,1.29,1.30,1.32,1.35,1.4,1.6}. Monotone, no reversals.

## Interpretation corrections (per advisor)

- **TFIM Δ≈0.26 is NOT a "nine-site tunneling gap."** `N=9` is the size of a
  local-consistency window in an infinite-volume relaxation, not a 9-site
  diagonalization. Finite-relaxation threshold for the imposed symmetry class —
  neither a finite-chain gap nor a proof of the true infinite-volume gap. The
  earlier "exponentially-small tunneling gap" framing is retracted.
- **"d-convergence at N=13" is retracted.** The kagome basis builder
  (`get_kagome_basis`, `get_kagome_bulkbasis`) adds no words beyond `d>2`/`d>1`,
  so d=3 and d=4 produce identical SDPs; equality of the transition is a
  regression check, not mathematical convergence.
- **Kagome d=2 is not "structurally invalid."** The 0-dimension gap block at d=2
  is vacuous; the `lgb[l] > 0 || continue` guards let it be omitted. d=2 is a
  smaller valid relaxation.
- **Symmetry labelling:** `model="kagome"` does component-count parity zeroing +
  cyclic X/Y/Z identification (`reduce_perm`). It does NOT apply square
  translations/C4/mirrors and is NOT a full SU(2) irrep quotient.

## Status (2026-07-28)

- Turnkey `SpectralGap.jl` certifiers reproduce the bundled TFIM and kagome
  examples — **calibration/reproduction**, not the #88 deliverable.
- **#88 target = square J1-J2** (then Shastry-Sutherland, then triangular). The
  square path needs a custom certifier + structured basis (`SQUARE_BASIS_SPEC.md`,
  PR #3).
- Competition: `wangfh5` upstream PRs #219 (NPA cert) + #221 (kagome energy) are
  adjacent; the square-J1-J2 gap extension is where novelty lies.

## §8 certificate pipeline — staged status (reconciled @4b89b1a)

Four stages, honestly assessed:

1. **Preliminary same-model extraction/check — DONE.** `certify_Ising_gap` reads
   `value.(pos/gpos/λ)`, reports λ>0, Gram min-eigs, and `value.(cons)` residual
   within the originating JuMP model. Independent of the legacy `flag`, NOT
   independent of the model/solve.
2. **Complete certificate serialization — DONE.** `certify_Ising_gap` returns
   `cert_artifact`: the primal ray as one vector `x = ray_values`, the sparse
   affine map (14,360 entries), the **actual** affine constants
   (`cons[k].constant`), objective vector `c`, block index maps
   (`pos_var_positions`/`gap_var_positions`), declared block sizes, and
   `lambda_var_position`. Serialized artifact committed at
   `evidence/tfim_cert_N9_g0.26.jls` (SHA-256 `7b6fa98c…`).
3. **Schema-complete standalone verification — DONE (advisor Priority 0A+0B,
   commit `4c4d2de`).** `scripts/verify_certificate.jl` uses only
   `Serialization`+`LinearAlgebra` (no JuMP/Mosek/assembly). It treats **one
   vector `x`** as the sole source of truth and REQUIRES the artifact to declare
   its full block inventory:
   - `length(pos_var_positions) == length(pos_sizes)` (and gap), and every block
     has `size(map) == (declared, declared)` incl. 0×0 — so a malformed artifact
     cannot drop its block list and pass vacuously (the @491083f hole).
   - every schema violation → immediate `SCHEMA_FAIL` (never throws, never
     continues into a numerical op): required fields, `schema_version`, nvars>0,
     finite arrays, in-range affine/constraint indices, exact block dims.
   - rebuilds every declared >0 Gram block from `x` via the index maps, checks
     symmetry (aliasing), PSD, the affine identity `‖A·x+const‖∞`, homogeneity
     (`max|const|`), and `c·x>0` with the binding check `c·x == x[λ_pos]`.
   - classification: `DUAL_INFEASIBLE`→`DECISIVE_AUDITED`;
     `OPTIMAL`+positive-ray→`STATUS_CONTRADICTION` (not decisive);
     `SLOW_PROGRESS`→`NUMERICALLY_AUDITED_CANDIDATE`.
   **TFIM N=9 γ=0.26: PASSES** — ‖A·x+const‖=1.3e-13, max|const|=0.0,
   c·x=0.00508==x[λ_pos], all rebuilt Gram blocks PSD.
   **Soundness self-test (Priority 0B):** `scripts/test_verifier_corruption.jl`
   runs 14 corruptions (5 one-x binding + 9 schema-completeness: omitted/extra
   blocks, empty-for-positive-size, rectangular, out-of-range indices, objective
   length, schema_version); the verifier **rejects all 14**. An exact test
   counter means a skipped required test fails the suite.
   **Note (advisor @491083f):** this audits the *exported conic instance*, NOT
   the physical formulation — whether the instance faithfully represents the
   intended TFIM relaxation needs a problem/basis manifest (Priority 3).
4. **Decisive solver status or rigorous post-processing — NOT DONE.** Termination
   is `SLOW_PROGRESS` (not `DUAL_INFEASIBLE`). The audited ray is a numerical
   candidate; strict certification needs rational/interval post-processing (or a
   decisive solve). Tolerances are a single absolute `1e-6` on an unnormalized
   ray — scale-aware tolerances + normalization are open (Priority 1).

**Current defensible claim:** "TFIM N=9 γ=0.26: a candidate primal improving ray
was exported binding all checks to one vector x; a schema-complete standalone
verifier (no JuMP/Mosek) reconstructed the affine identity (1.3e-13), confirmed
`c·x>0` and every declared Gram block PSD from x, requires the full declared
block inventory, and rejects 14/14 deliberate corruptions. Numerical candidate
(`SLOW_PROGRESS`), not a rigorous proof."

**Reproducibility (full log `evidence/tfim_N9_g0.26_full_log.txt`):**
julia 1.11.5, JuMP v1.31.1, MosekTools v0.15.10, Mosek 11.2.2; patch SHA-256
`3bdd31f7…`; artifact SHA-256 `7b6fa98c…`.

## Open items (prioritized per advisor recheck @491083f)

- **Priority 1 (scale/repro):** normalize `x` (e.g. c·x=1) + documented relative
  residual/PSD tolerances; replace opaque `.jls` with a versioned format; remove
  unseeded `rand` from `filter_mons`; regenerate `GAP_RUN_PROVENANCE.md`.
- **Priority 2 (engineering):** repair legacy TFIM/Kagome drivers for the named
  return API; one three-way classifier everywhere; remove unused
  `Serialization` package dep (now only in the driver); consolidate ledger/
  provenance contradictions (this rewrite addresses the ledger).
- **Priority 3 (scientific deliverable):** add the problem/basis/support manifest
  needed to audit the *formulation*; calibrate positive-gap on Shastry-Sutherland
  g=0 (Δ=1, NOT square Heisenberg g=0 which is gapless); integrate the structured
  square J1-J2 basis + certifier (PR #3); produce the square result before more
  kagome scans.
