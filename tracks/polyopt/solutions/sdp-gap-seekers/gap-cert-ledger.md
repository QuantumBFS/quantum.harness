# Gap-cert ledger — certified spectral-gap upper bounds

> The #88 challenge track: **certified upper bounds on the bulk spectral gap**
> Δ of (frustrated) spin-1/2 models, via the state-polynomial γ-feasibility SDP
> hierarchy of arXiv:2606.03836, using the turnkey `SpectralGap.jl` certifiers in
> `.external/SpectralGap` (`certify_Ising_gap`, `certify_Heisenberg_kagome_gap`).
>
> Direction (per the SPEC + arXiv:2606.03836): for a threshold γ, the SDP tests
> whether a KMS ground state can have a locally non-degenerate bulk gap ≥ γ.
> **Feasibility is monotone decreasing in γ**: small γ feasible, large γ
> infeasible. The largest feasible γ* is a **certified upper bound on Δ**
> (Δ ≤ γ*); the hierarchy converges downward as (L, d) increase. Infeasibility
> at γ excludes a gap ≥ γ. Orthogonality is encoded by the **covariance term**
> ω(a†a)−|ω(a)|², not an S=1 sector.
>
> Owner: xcai side. Kept separate from the energy-cert ledger
> (`feature/energy-cert-floor`) per the agreed energy/gap split.

## Methodology — γ-scan to locate the feasibility transition

`certify_*(N, H, γ, d)` returns `flag = (status==OPTIMAL ? 1 : 0)`:
- `flag=1` → γ feasible → Δ could be ≥ γ (not excluded).
- `flag=0` → γ infeasible → Δ < γ (excludes gap ≥ γ).

A coarse γ-scan localizes the transition γ* ∈ (largest-feasible, smallest-infeasible];
the certified statement is **Δ ≤ smallest-infeasible-γ**. Bisection tightens it.

> ⚠️ The `flag=(status==OPTIMAL)` convention (SpectralGap.jl upstream) collapses
> all non-OPTIMAL statuses into flag=0. Per SPEC §8 this is unsafe for rigorous
> certification (timeouts/numerics also give flag=0). For run-time validation
> and bound-localization it is adequate; a residual/witness audit is needed
> before claiming a formally certified bound. (Todo: §8 audit.)

## Run ledger

Columns: model | (N, d, symmetry) | certified Δ ≤ | reference | solver | runtime/case | status

| # | model | config | certified Δ ≤ | reference / expected | solver | runtime/case | status |
|---|---|---|---|---|---|---|---|
| 1 | 1D TFIM (transverse-field Ising) | N=9, g=0.5, d=2, sign-symmetric | **≤ 0.26** (candidate; Farkas cert available) | 0.258 (example.jl / legacy-inventory-spec) | Mosek 11.2.2 | 4–25 s | pipeline calibration (Gate 5); §8 status-gate run |
| 2 | Kagome Heisenberg (frustrated, #88) | N=13, d=3, sign-symmetric | **≤ 1.28** (candidate) | ~1.28 (example.jl) | Mosek 11.2.2 | ~290 s | flag-transition candidate (matches ref) |
| 3 | Kagome Heisenberg (frustrated, #88) | N=27, d=3, sign-symmetric | — | ~1.15 (example.jl) | Mosek 11.2.2 | — | running (128-cpu/486GB, first solve in progress) |
| 4 | Kagome Heisenberg (frustrated, #88) | N=13, d=4, sign-symmetric | **≤ 1.28** (candidate) | = d=3 | Mosek 11.2.2 | ~220 s | **d-converged** (= d=3; gap bound saturated in d at N=13) |

**Row 1 detail (Gate 5 — pipeline validated):** γ-scan N=9 g=0.5 d=2 sign-symmetric —
feasible at γ ∈ {0.15, 0.20, 0.22, 0.24, 0.25}, infeasible at γ ∈ {0.26, 0.27, 0.28, 0.30, 0.34}.
Transition γ* ∈ (0.25, 0.26] → **Δ ≤ 0.26**, matching the reference 0.258.
Physics: g=0.5 < 1 is the ordered phase; the sign-symmetric sector sees the
exponentially-small tunneling gap (hence Δ ~ 0.26, not the 2|1−g|=1.0 magnon gap,
which lives in the symmetry-broken / no-sign-symmetry sector).

**Kagome note (row 2–4):** d=2 is **structurally invalid** for kagome — the
degree-1 bulk/gap basis is empty → 0-dimension PSD block → `MosekError(20401)`.
d=3 (degree-2 bulk basis) is the minimum working order, matching `example.jl`.

**Row 2 detail (kagome N=13 d=3 — frustrated #88 bound):** γ-scan was clean and
monotone (no reversals — the SPEC §9 sanity check passes): feasible at
γ ∈ {1.0, 1.2, 1.26}, infeasible at γ ∈ {1.28, 1.29, 1.30, 1.32, 1.35, 1.4, 1.6}.
Transition γ* ∈ (1.26, 1.28] → **Δ_kagome ≤ 1.28**, matching `example.jl`.
~290 s/solve. **Row 3 (N=27 d=3) OOM'd** at the 243 GB node limit (the SDP for
N=27 is too large for `xhacnormalb` at `mem-per-cpu=3800M`); N=27 needs a
larger-memory node or a sparser formulation. **Row 4 (N=13 d=4) running** — same
N=13 patch that succeeded at d=3, one order higher → should fit and tighten.

## Status (2026-07-28)

- **Pipeline validated** on TFIM (row 1). `ncpoly` Hamiltonian construction +
  `certify_Ising_gap` + γ-scan transition localization all correct.
- **Kagome (#88 frustrated target) running.** First solve (γ=1.0) feasible at
  235 s; scanning toward the expected Δ ≤ ~1.28 transition.
- **Strategic note:** SpectralGap.jl has turnkey Ising + kagome certifiers but
  **no square-J1-J2 certifier**. The square path needs custom code (SPEC); the
  kagome path is turnkey and already frustrated (#88-relevant). Awaiting Sihan's
  call on whether to pivot #88 to kagome (fast) vs keep pursuing square custom.
- **Competition:** `wangfh5` has upstream PRs #219 (coarse-grained NPA cert for
  spin systems) and #221 (kagome energy bracket) — adjacent to our gap work.

## Open items

1. Append kagome N=13 d=3 / N=27 d=3 / N=13 d=4 transitions when they land.
2. §8 residual/witness audit before calling any bound "formally certified"
   (currently "numerically validated at stated tolerances").
3. Square J1-J2 gap: decide custom-code path after the A/B strategic call.
