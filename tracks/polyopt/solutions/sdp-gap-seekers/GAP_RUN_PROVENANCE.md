# Gap-cert run provenance — frozen for independent reproduction

> ## ⚠️ STALE (2026-07-28, per advisor P0 review) — do NOT trust for reproduction yet
>
> This document is **out of sync with the current checkout** and is preserved
> only as a historical reference. Known defects (to be fixed in Phase 1):
> - describes an **older patch** than the current `spectralgap_a1171c9.patch`
>   (omits the status-return, the `optimizer` keyword, and the attempted
>   certificate-extraction logic);
> - records an **obsolete `src/sdp.jl` hash** (current is
>   `1e13b401a0a83c64ea1d40cfb8c91ff007ea10bd28b9a0e94f9882338a27fde0`);
> - the patch **omits `Project.toml`** (the `using Clarabel` addition requires a
>   dependency change that is not in the checked-in patch);
> - the "bit-for-bit reproducible" claim is **retracted** — `filter_mons` uses
>   `rand(...)` for stationarity-row fingerprinting, so assembly is not literally
>   deterministic without a frozen seed / deterministic selection;
> - **raw result files are not committed** to the branch (they live on SCNet);
> - the §8 "Farkas cert available" framing is **wrong** — the witness, if any,
>   is on the variable-primal side (`value.()`), not `dual(con_eq)`; and
>   `SLOW_PROGRESS` means the outcome is not decisive.
>
> It will be regenerated after one complete patch (incl. `Project.toml`) is
> frozen, raw results are committed, and the certificate path is corrected.
> Until then, treat the gap values as **numerical transition candidates**, not
> reproducible certified bounds.

> Frozen record of the turnkey `SpectralGap.jl` gap-certification runs, per the
> 2026-07-28 coordination ask (independent SCNet dual-run to verify the
> feasible/infeasible → gap-upper-bound direction). Anyone pulling
> `challenge/polyopt-sdp-gap` + the SpectralGap pin below can reproduce these
> numbers bit-for-bit.
>
> ⚠️ **Status: numerical result, not a strict certificate.** The `flag =
# (status==OPTIMAL ? 1 : 0)` convention (SpectralGap.jl upstream) collapses all
# non-OPTIMAL statuses into flag=0. Per `square-j1j2-gap-sdp-spec.md` §8 this is
# adequate for bound-localization but a residual/witness audit is required
# before claiming a formally certified bound. Flag values below are labelled
# "numerical" accordingly.

## 1. SpectralGap.jl source pin (frozen) — CORRECTED 2026-07-28

> **Correction (per Sihan's 11:19 review):** an earlier version of this section
> claimed "pristine `SpectralGap@a1171c9`". That was **wrong**. The mounted
> `.external/SpectralGap` working tree carries a **small local patch** on top of
> `a1171c9` (two files modified, uncommitted). The SHA-256 values below are the
> **working-tree (patched)** files — i.e. the code that actually produced the
> results. The patch is documented in full and is **result-neutral on the Mosek
> path** (see "patch effect" below). Reproducers must apply the same patch.

| field | value |
|---|---|
| upstream repo | https://github.com/wangjie212/SpectralGap.git |
| base commit | `a1171c906ff2cc2901e58c2426397a2f68c32bb7` ("use the new formulation and add extra constraints") |
| **patch** | local, uncommitted, 2 files (`src/SpectralGap.jl`, `src/sdp.jl`) — full diff below |
| mounted at | `.external/SpectralGap/` (local path dep, gitignored; resolved via `julia-env/Project.toml` UUID `2cd8220c-fa98-40a0-8d32-c3094c958e9c`) |
| `src/SpectralGap.jl` working-tree SHA-256 | `ec0a8b4e723e0accaee33826bd6f2bb4eef82debaf3a9f9a9e51cc749fb7648f` (base-blob `940cd72b…`) |
| `src/basicfunction.jl` SHA-256 | `2095cf7401355f37e9d17915b3ab29d44712d8e40f750eb8449f8c294229b03a` (unmodified = base) |
| `src/sdp.jl` working-tree SHA-256 | `dbdb31d13f4eb484a9f80f6190d8ac31e8030580246228ca5dca3a1bc86e9208` (base-blob `b35c4ed6…`) |
| `src/strengthening.jl` SHA-256 | `de56b12b17049f81f689d4caef193b9dfd3bf50061fc78b1bf1547a748f7c57b` (unmodified = base) |

### The local patch (exact diff vs `a1171c9`)

```diff
--- a/src/SpectralGap.jl   # + `using Clarabel` and an UNUSED _select_optimizer helper
+++ b/src/SpectralGap.jl
@@ using MathOptInterface
 using JuMP
 using MosekTools
+using Clarabel
 using LinearAlgebra
@@
+# Solver selection: Mosek if available (MOSEKBINDIR set), else Clarabel
+function _select_optimizer()
+    if haskey(ENV, "MOSEKBINDIR") || haskey(ENV, "MOSEK_PLATFORM")
+        return Mosek.Optimizer
+    else
+        return Clarabel.Optimizer
+    end
+end

--- a/src/sdp.jl   # + two empty-PSD-block skip guards in certify_Heisenberg_kagome_gap
+++ b/src/sdp.jl
@@ in the positivity-block loop:
     for i = 1:length(basis)
+        lb[i] > 0 || continue
         pos[i] = @variable(model, [1:lb[i], 1:lb[i]], PSD)
@@ in the gap-block loop:
     for l = 1:length(gbasis)
+        lgb[l] > 0 || continue
         gpos[l] = @variable(model, [1:lgb[l], 1:lgb[l]], PSD)
```

**Patch effect on results: none on the Mosek path.**
- The `_select_optimizer` helper is defined but **never called** — both
  `certify_*_gap` functions still hardcode `Model(optimizer_with_attributes(Mosek.Optimizer))`.
  So the solver, model, and solution are identical to base `a1171c9`.
- The `lb[i] > 0 || continue` / `lgb[l] > 0 || continue` guards **skip the
  construction of 0-dimension PSD blocks**. A 0×0 PSD variable contributes zero
  rows/columns to the SDP, so skipping it is numerically equivalent to
  constructing it — it only avoids a `MosekError(20401)` ("dimension 0 invalid")
  on inputs where some basis block is empty. For the runs that succeeded
  (TFIM N=9 d=2; kagome N=13 d=3), all blocks were non-empty, so the guards are
  no-ops there.

(All working-tree files also have mode `100755` vs base `100644` — a cosmetic
`chmod +x`, no content effect.)

## 2. Hamiltonian conventions (normalization)

Both use the `ncpoly` encoding: site `i` → `3i-2 = X_i`, `3i-1 = Y_i`, `3i = Z_i`.

- **1D TFIM**: `H = -Σ_{i=1}^{N-1} Z_i Z_{i+1} + g Σ_{i=1}^{N} X_i`, with
  `supp = [[3i,3(i+1)] for bonds; [3i-2] for fields]`, `coe = [-1,…; g,…]`.
- **Kagome Heisenberg**: `H = Σ_{triangles} Σ_{pairs∈tri} S_i·S_j` where
  `S_i·S_j = ¼(XX+YY+ZZ)`. Per triangle: 9 terms (3 pairs × 3 Pauli components),
  coefficient `0.25`. `supp` built from `triples`; `coe = 0.25·ones(9·|triples|)`.

## 3. Exact commands (reproducible)

Scripts committed on `challenge/polyopt-sdp-gap`:
- `tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_tfim_validate.sh`
- `tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_kagome.sh`

Both are SLURM scripts for SCNet (`xhacnormalb`). Required env:
```
PATH=$HOME/julia-1.11.5/bin:$PATH
MOSEKBINDIR=$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin
LD_LIBRARY_PATH=$HOME/julia-1.11.5/lib/julia:$LD_LIBRARY_PATH
```
Then: `sbatch gap_tfim_validate.sh` / `sbatch gap_kagome.sh` from `~/quantum.harness`.

The Julia entry points (inside the heredoc):
```julia
# TFIM
H = ncpoly([[3*[i;i+1] for i=1:N-1]; [[3i-2] for i=1:N]], [-ones(N-1); g*ones(N)])
flag = certify_Ising_gap(N, H, gamma, d, QUIET=true)          # lso=6 default

# Kagome
H = ncpoly(<9 terms per triangle>, 0.25*ones(9*length(triples)))
flag = certify_Heisenberg_kagome_gap(N, H, triples, edges, triples0, edges0,
                                     gamma, d, lso=5, QUIET=true)
```

## 4. Run config + solver

| | TFIM | Kagome |
|---|---|---|
| N | 9 | 13 |
| d (relaxation order) | 2 | 3 (d=2 structurally invalid — empty bulk basis) |
| symmetry | sign-symmetric (default) | sign-symmetric (default) |
| lso (localizing support order) | 6 (default) | 5 |
| γ-scan | 0.15…0.34 | 1.0…1.6 |
| solver | Mosek 11.2.2 | Mosek 11.2.2 |
| tolerances | Mosek defaults (no custom `mosek_setting`) | Mosek defaults |
| SCNet job | 22970362 | 22970838 |

## 5. Results — γ-scan legacy-flag transitions

> **Status semantics (per Sihan's 11:19 review):** the certify functions collapse
> every non-OPTIMAL Mosek status to `flag=0`. They do **not** expose raw
> termination/primal-dual status, residuals, or an infeasibility/Farkas witness.
> The transitions below are therefore **legacy flag-transition candidates**, not
> "validated infeasibility" or "certified Δ upper bounds." Promoting a candidate
> to a certified bound requires the §8 residual/witness audit (capture raw
> status + a Farkas certificate for the infeasible γ). Direction (monotone
> decrease of flag with γ, no reversals) is confirmed in both scans.

**TFIM (Gate 5 — pipeline calibration):**
| γ | 0.15 | 0.20 | 0.22 | 0.24 | 0.25 | 0.26 | 0.27 | 0.28 | 0.30 | 0.34 |
|---|---|---|---|---|---|---|---|---|---|---|
| flag | 1 | 1 | 1 | 1 | **1** | **0** | 0 | 0 | 0 | 0 |

Flag transition γ* ∈ (0.25, 0.26] → **Δ_TFIM ≤ 0.26 candidate** (reference 0.258).

**Kagome Heisenberg, N=13, d=3 (#88 frustrated target):**
| γ | 1.0 | 1.2 | 1.26 | 1.28 | 1.29 | 1.30 |
|---|---|---|---|---|---|---|
| flag | 1 | 1 | **1** | **0** | 0 | 0 |

Flag transition γ* ∈ (1.26, 1.28] → **Δ_kagome ≤ 1.28 candidate** (reference ~1.28).

Raw per-γ logs: `gap_tfim.results`, `gap_kagome.results` (on SCNet; N=27 d=3 +
N=13 d=4 scans are running to tighten the kagome candidate).

## 6. Direction reminder (for the dual-run check)

Feasibility is monotone decreasing in γ (per SPEC §1 / arXiv:2606.03836):
- `flag=1` (OPTIMAL) → γ feasible → Δ could be ≥ γ (not excluded).
- `flag=0` (non-OPTIMAL collapsed) → treated as infeasible → would give Δ < γ,
  **but** without the raw status this could mask a timeout/numerical failure.
- largest feasible γ* → **candidate** upper bound Δ ≤ γ*, pending the §8 audit.

The kagome scan obeys this (feasible at low γ, infeasible above the transition,
no reversals) — the direction check Sihan's side will independently confirm.
