# Certified bulk-gap bounds for truncated Bose–Hubbard models

**Issue:** [Quantum Harness #92](https://github.com/QuantumBFS/quantum.harness/issues/92)
**Method:** [Xu et al., thermodynamic bulk-gap hierarchy](https://arxiv.org/abs/2606.03836)
**Snapshot:** 2026-07-30T16:47:41+08:00
**Verdict:** Partial challenge result—core implementation complete, certified hard-core baseline subset, mandatory larger-level/cutoff campaign incomplete.

## Executive result

The independently checked hierarchy gives **9 hard-core finite-level gap upper statements** at complete matrix level `(L,d)=(1,2)` in the `U1_INVARIANT_KMS_STATES` sector. It also gives **2 accepted two-sided observable intervals** and **26 accepted one-sided endpoints**. These are thermodynamic hierarchy statements, not finite-cluster ED values.

## Certified gap statements

| graph | point | (t/U,μ/U) | (L,d) | last FEASIBLE | first EXCLUDED | span | unknown inside | 0.005 clean |
|---|---|---|---|---|---|---|---|---|
| {12,4} | P2 | (0.05,0.5) | (1,2) | 0.51 | 0.52 | 0.01 | 1 | open |
| {12,4} | P4 | (0.03,0.15) | (1,2) | — | 0.3 | — | 0 | open |
| {12,4} | P5 | (0.03,0.75) | (1,2) | — | 1 | — | 0 | open |
| {8,3} | P1 | (0.03,0.5) | (1,2) | 0.5 | 0.505 | 0.005 | 0 | PASS |
| {8,3} | P2 | (0.05,0.5) | (1,2) | 0.509 | 0.511 | 0.002 | 1 | open |
| {8,3} | P3 | (0.06,0.5) | (1,2) | 0.514 | 0.518 | 0.004 | 2 | open |
| {8,3} | P4 | (0.03,0.15) | (1,2) | 0.16 | 0.165 | 0.005 | 0 | PASS |
| {8,3} | P5 | (0.03,0.75) | (1,2) | 0.75 | 0.755 | 0.005 | 0 | PASS |
| L({8,3}) | P2 | (0.05,0.5) | (1,2) | 0.51 | 0.53 | 0.02 | 1 | open |

`FEASIBLE` is only non-exclusion at this finite level. `EXCLUDED` means the exact-projected certificate passed affine, 256-bit coefficient, rigorous PSD, and positive Farkas-margin checks. A span containing an unresolved sample is not called a bracket.

## Headline observable bounds

At `{8,3}` P5 and `γ/U=0.05`: `0.9944073 ≤ ρ0 ≤ 0.9999995` and `4.879816e-7 ≤ F0 ≤ 0.005592673`. At hard-core cutoff, `F0=1−ρ0` exactly.

At `{8,3}` P4 and `γ/U=0.10`, exact projection certifies `ρ0≥0.9455347492001175`, `F0≤0.0544652507998825`, and `K0≤0.30258382329239936`.

## Evidence inventory

| item | count |
|---|---|
| accepted one-sided objectives | 26 |
| floating objectives (not certified) | 100 |
| accepted intervals | 2 / 69 |
| durable fixed-γ rows | 146 / 205 |
| verified EXCLUDED trial rows | 48 |
| UNKNOWN fixed-γ rows | 93 |

## Implementation and verification

The Julia core implements exact finite matrix algebra over `Q(sqrt(2),sqrt(3))`, matrix and ladder filtrations, canonical state polynomials, complete moment/stationarity/gap index sets, exact U(1) charge blocks, deterministic nested TS2 sparsity, Clarabel/Mosek solve interfaces, and independent exact certificate checking. The current checkout passes 575 Julia assertions and 21 Python tests, including the exact atomic benchmark, deliberate certificate corruption, and submission-tier separation.

## Limitations

- Complete hard-core `(1,3)` and `(2,2)` solve attempts exhausted 192 GiB, so no nested numerical tightening is claimed.
- Complete cutoff-two `(1,2)` assembled but exhausted 192–237 GiB across MKL and QDLDL routes.
- TS2 cutoff-two dry assembly and unfinished extended-geometry cells were live at this snapshot; only fetched, independently checked rows contribute claims.
- Ladder, unrestricted, optional cutoff-three, and the full observable grid remain incomplete.
- The pinned upstream SpectralGap Ising reproduction remains blocked by the lack of a Mosek license.

## Reproducibility

```bash
make test
make final-report
```

The self-contained presentation is `submission/report.html`. Curated tables are under `submission/tables/`; `submission/data_manifest.json` records source hashes and maps the ignored raw campaign directories. Full primal/dual payloads remain under `results/` and are intentionally not committed.
