# Gap ledger — numerical γ-transition candidates (NOT yet certified)

> ⚠️ **Honest status (corrected 2026-07-28 per advisor review):** the values
> below are **numerical flag-transition candidates**, not certified upper bounds.
> The legacy `certify_*_gap` returns `flag = (status==OPTIMAL ? 1 : 0)`, which
> collapses every non-OPTIMAL Mosek status (true infeasible, timeout, slow
> progress, numerical failure) into `flag=0`. No result below has an extracted
> and independently validated infeasibility witness. Until that exists, claim
> only "numerical transition candidate," not "certified upper bound."
>
> This ledger is kept separate from the energy-cert ledger
> (`feature/energy-cert-floor`) per the agreed split.
>
> **Scope correction:** challenge #88 (per its official text) requests extensions
> to **square J1-J2 → Shastry-Sutherland → triangular J1-J2**, in that order.
> Kagome is **already in the upstream `SpectralGap.jl` example**, so the kagome
> rows below are a **legacy-pipeline reproduction / calibration**, not the
> challenge's requested scientific extension. The square J1-J2 extension is the
> actual target.

## Methodology — γ-scan, three-way semantics (required)

`certify_*(N, H, γ, d)` solves an SOS-side conic problem `Max λ` s.t. a
homogeneous coefficient identity + PSD Gram blocks (positivity, gap) + free
stationarity multipliers. The intended interpretation:
- `termination=OPTIMAL` → γ feasible → Δ could be ≥ γ.
- a clean `termination=DUAL_INFEASIBLE` with a primal improving ray → γ excludes
  the gap (candidate certified infeasible).
- anything else (`SLOW_PROGRESS`, timeout, numerical) → **unknown**, must not be
  collapsed into "infeasible."

The legacy `flag=(status==OPTIMAL?1:0)` loses this three-way distinction. We
patched the certifiers to retain raw `(termination, primal_status, dual_status,
objective)`, but the **witness itself is not yet extracted** — and the first
extraction attempt read the wrong conic side (`dual(con_eq)`; the ray is actually
in the variable primal values). See §8 open item.

## Run ledger

| # | model | config | numerical Δ-transition | reference | solver | runtime/case | status |
|---|---|---|---|---|---|---|---|
| 1 | 1D TFIM (transverse-field Ising) | N=9, g=0.5, d=2, legacy "sign-symmetric" | flag flips 0.25→0.26 | 0.258 provenance **unverified** (example.jl sets ub=lb=0.24, no 0.258 emitted; cite the paper's Table S1 if used) | Mosek 11.2.2 | 4–25 s | pipeline calibration only; **not** a #88 target |
| 2 | Kagome Heisenberg | N=13, d=3 | flag flips 1.26→1.28 | ~1.28 (bundled in `example.jl`) | Mosek 11.2.2 | ~290 s | **legacy reproduction** (kagome is in the upstream example; low novelty) |
| 3 | Kagome Heisenberg | N=27, d=3 | — | ~1.15 (example.jl) | Mosek 11.2.2 | — | **killed** — 2h08m zero progress on 128-cpu/486GB; do not brute-force again without phase instrumentation |
| 4 | Kagome Heisenberg | N=13, d=4 | flag flips 1.26→1.28 | identical to d=3 | Mosek 11.2.2 | ~220 s | **identical-SDP regression**, not convergence — `get_kagome_basis` has no `d>3` branch, so d=4 builds the same model as d=3 |

**Raw γ-scans (numerical):**
- **TFIM N=9 g=0.5 d=2:** flag=1 at γ∈{0.15,0.20,0.22,0.24,0.25}; flag=0 at
  γ∈{0.26,0.27,0.28,0.30,0.34}. Raw Mosek status at γ=0.26/0.30: `SLOW_PROGRESS`
  + `primal_status=INFEASIBILITY_CERTIFICATE` + `dual_status=NO_SOLUTION`.
- **Kagome N=13 d=3:** flag=1 at γ∈{1.0,1.2,1.26}; flag=0 at
  γ∈{1.28,1.29,1.30,1.32,1.35,1.4,1.6}. Monotone, no reversals.

## Interpretation corrections (per advisor)

- **TFIM Δ≈0.26 is NOT a "nine-site tunneling gap."** `N=9` is the size of a
  local-consistency window in an infinite-volume relaxation, not a 9-site
  diagonalization. The value is a finite-relaxation threshold for the imposed
  symmetry class — neither a finite-chain gap nor a proof of the true
  infinite-volume gap. The earlier "exponentially-small tunneling gap" framing
  is retracted.
- **"d-convergence at N=13" is retracted.** The kagome basis builder
  (`get_kagome_basis`, `get_kagome_bulkbasis`) adds no words beyond `d>2`/`d>1`,
  so d=3 and d=4 produce **identical SDPs**; equality of the transition is a
  regression check, not mathematical convergence. (Same artifact on the energy
  side — see that ledger.)
- **Kagome d=2 is not "structurally invalid."** The 0-dimension label-1 gap block
  at d=2 is mathematically vacuous, and the added guards (`lgb[l] > 0 || continue`)
  let it be omitted. d=2 is a smaller, valid relaxation (the original
  `MosekError(20401)` was Mosek rejecting a 0×0 PSD variable, now guarded). Per
  advisor: **try N=13 d=2 then N=27 d=2 before any more d=3.**
- **Symmetry labelling:** the `model="kagome"` reduction does component-count
  parity zeroing + cyclic X/Y/Z identification (`reduce_perm`). It does **not**
  apply square translations/C4/mirrors and is **not a full SU(2) irrep quotient**.
  The label "sign-symmetric" is vague; record the exact automorphisms imposed.

## Status (2026-07-28, corrected)

- The turnkey `SpectralGap.jl` certifiers (`certify_Ising_gap`,
  `certify_Heisenberg_kagome_gap`) reproduce the bundled TFIM and kagome
  examples. These are **calibration/reproduction**, not the #88 deliverable.
- **#88 target = square J1-J2** (then Shastry-Sutherland, then triangular). The
  square path needs a custom certifier + structured basis (see
  `SQUARE_BASIS_SPEC.md`, to be corrected, and PR #3).
- Competition: `wangfh5` upstream PRs #219 (NPA cert) + #221 (kagome energy) are
  adjacent; the square-J1-J2 gap extension is where novelty lies.

## Open items (prioritized per advisor)

1. **§8 — extract the primal SOS ray correctly.** Read `value.(pos/gpos/λ)` on a
   `DUAL_INFEASIBLE` (decisive) outcome — not `dual(con_eq)`. Require `λ_ray>0`,
   normalize, then independently validate the affine identity + PSD blocks + the
   ray. Scale down (smaller N / lower lso) until the status is decisive, not
   `SLOW_PROGRESS`. (This is the real §8 path; my `dual(con_eq)` attempt was the
   wrong side.)
2. **Freeze one reproducible TFIM instance** — complete patch incl. `Project.toml`,
   API-compatible script (consume named fields), committed raw results + source
   hashes, deterministic row filtering.
3. **Square J1-J2** on the simplest explicit unsymmetrized basis (review PR #3's
   manifest first); calibrate positive-gap on **Shastry-Sutherland g=0 (Δ=1)**,
   not square Heisenberg g=0 (which is gapless — Néel + Goldstone).
4. **Kagome tightening (low priority):** N=13 d=2 regression, then one N=27 d=2
   γ-point — only after the certificate path is fixed.
