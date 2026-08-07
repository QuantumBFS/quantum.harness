# tfim-ratio-sqrt5-001 — is h_c(triangular)/h_c(honeycomb) exactly √5?

**Card:** `cards/round3/tfim-ratio-sqrt5-001.yaml` (challenge issue #148, released by Xiao-Yan Xu, SJTU)
**Verdict:** round 1 `dead (no_solver)` → builder added → round 2 `deferred` (decisiveness 0.73, kill threshold 2.0)
**One command:** `python3 run_sqrt5.py` (anchors: `python3 tests/test_tfim2d.py`)

## Physics picture

The ferromagnetic transverse-field Ising model H = −J Σ⟨ij⟩ σz_i σz_j − h Σ_i σx_i
is sign-problem free on any lattice. Its 2D quantum critical points were pinned by
Blöte & Deng (PRE 66, 066110 (2002), continuous-time cluster QMC): triangular
h_c/J = 4.76811(9), honeycomb h_c/J = 2.13250(4). The ratio 2.23592(6) sits 2.4σ
from √5 = 2.236068. The classical star–triangle analogue fails (T_c ratio
2.3975 ≠ √5), so if the ratio is exact it is a specifically (2+1)D-quantum fact
about non-universal quantities — surprising, since no duality is known that
relates the two models at criticality.

## What the factory did

1. **Mining (§2).** Citation sweep of all 203 papers citing Blöte–Deng (Semantic
   Scholar, 2026-07-30) + arXiv abstract searches: **no post-2002 determination of
   h_c on either lattice improves on 2002** — the SOTA pair is still Blöte–Deng.
   The literature anchor is pinned on the card; the challenge baseline is the best
   published pair.
2. **Crystallization (§3).** One card, gate frozen before any solve: decisiveness
   = |R − √5| / σ_R, kill below 2.0; target precision σ_R ≤ 1.2×10⁻⁵ taken from
   issue #148 item 3. Observable: Binder-cumulant crossings on declared clusters.
3. **Round 1 launch: `no_solver`.** The registry had no 2D TFIM builder — the card
   died at the registry gate before any physics. This is the interface working as
   designed (a capability signal, not a quality signal).
4. **Builder cycle (TDD).** `pf/tfim2d.py` (~90 lines): chain / square /
   triangular / honeycomb clusters on L1×L2 tori, even-parity sector. Anchors
   (`tests/test_tfim2d.py`, 6/6 green): exact dimer E0 = −√(J²+4h²) all h;
   E0(h=0) = −#bonds on all four lattices; variational bound −h−z/4h ≤ E0/N ≤ −h
   at h=50; [H, P] = 0; **independent Jordan–Wigner cross-check** (chain N=16,
   h = 0.5, 1, 2, agreement to 1e-10 — an entirely separate code path through the
   same matrix elements); Binder limits U = 2/3 (cat state) and U = 2/3N
   (polarized).
5. **Round 2 launch: static fire 4/4 → hop → `deferred`.**

## Results (hop test, ED reconnaissance scale)

Binder cumulant U = 1 − ⟨m⁴⟩/3⟨m²⟩² on the even-parity ground state; h_c per
lattice = crossings of U_L(h) over size pairs (triangular N = 9, 12, 18;
honeycomb N = 8, 12, 18; PBC tori, h-grid step 0.1).

| lattice | h_c (this work) | Blöte–Deng 2002 |
|---|---|---|
| triangular | 4.342 ± 0.002 | 4.76811(9) |
| honeycomb | 1.986 ± 0.062 | 2.13250(4) |
| square (validation) | 2.870 (N=9×16 pair) | 3.04438(2) |

Ratio: **R = 2.186 ± 0.068** vs √5 = 2.23607 → decisiveness 0.73. Builder
validation: the square-lattice crossing undershoots the literature value by the
same ~5–7% as triangular and honeycomb — small-cluster crossings systematically
underestimate h_c and drift upward with N (visible in the figure), so the method
is understood, not broken.

## What the verdict means

- **R is consistent with √5 (0.73σ) and 3.1σ away from the classical value
  2.3975** — but σ_R = 0.068 is ~5700× the required 1.2×10⁻⁵. At ED sizes the
  conjecture is untestable; the factory says so with numbers, not vibes.
- **Deferred, with a cost-to-decision statement:** closing σ_R to 1.2e-5 needs
  σ(h_c) ~ 5e-6 per lattice. ED cost grows as 2^N and is already exhausted;
  the frozen gate routes the problem to sign-free QMC (SSE/continuous-time
  cluster) with FSS crossing analysis — exactly the verification plan of issue
  #148. Estimated effort there: days of laptop-scale compute per lattice (the
  2002 study cost ~5 processor-months at 750 MHz).
- **Loop closure:** round 1 died `no_solver`, one builder cycle later the same
  card reached a physics verdict. The registry grew (tfim_2d), the heuristics
  library gained two entries, and the next fleet already knows: ratio tests at
  1e-5 relative precision are QMC-class problems; ED is the static-fire/hop
  layer only.

## Honest novelty assessment

Nothing here is new physics: the h_c values are 24 years old and our crossings
are cruder. The deliverable is the *process* — a catalog challenge carried
搜索→提出→测试→(侦察级)解决 with a frozen gate, machine-readable telemetry, and
an honest verdict that routes it to the right method. The R = 2.186 ± 0.068
number itself must not be quoted as evidence for or against √5.

## Artifacts

- `briefs/data/sqrt5.json` — all Binder curves and crossings
- `briefs/figures/binder_crossings.png` — U(h) both lattices vs Blöte–Deng lines
- `results/telemetry_sqrt5.jsonl` — both rounds (no_solver → deferred)
- `heuristics/tfim-ratio-sqrt5-001{,-no-solver}.yaml` — lessons deposited

## Next steps toward the real verdict (issue #148 items 2–3)

1. SSE with cluster updates (Sandvik PRE 68, 056701 (2003)) on both lattices,
   L up to ~64, T = 2L/J scaling; Binder/ξ_L crossings with 3D-Ising FSS.
2. Cross-method redundancy per the issue: two independent codes agreeing within
   quoted errors; ED anchors here serve as the small-cluster code validation.
3. The frozen gate stays: σ_R ≤ 1.2×10⁻⁵, verdict on √5 pre-registered.
