> **Main work & results: see [`SYNTHESIS_REPORT.md`](SYNTHESIS_REPORT.md)**
> (中文版 [`SYNTHESIS_REPORT_ZH.md`](SYNTHESIS_REPORT_ZH.md)) ·
> PR deliverable: [`FINAL_REPORT.md`](FINAL_REPORT.md) ·
> reproduction: [`REPRODUCE.md`](REPRODUCE.md)

## Team

| | |
|---|---|
| **Team name** | its-a-trap |
| **Members** | Yan-Bai Zhang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Certify ground-state properties of quantum spin-1/2 systems by combining the NPA hierarchy of SDP relaxations with renormalization-group coarse-graining maps, and layering on the structure-exploiting techniques of arXiv:2604.01555 — going beyond plain NPA, whose SDP sizes explode well before the target system sizes are reachable. |
| **Catalog issue** | `Addresses #49` — *Certifying ground-state properties of quantum 1/2-spin systems via the coarse-grained NPA hierarchy*, released by 王杰 (Jie Wang), AMSS-CAS. |
| **Track** | `polyopt`. The issue names no solution folder, so the track comes from its `Method` field, *Noncommutative polynomial optimization / Quantum bootstrap*. |

## Results — the four targets

All bounds are **numerical SDP lower bounds**; gaps are signed, per site,
against **high-precision Bethe references** / **variational upper bounds**
(only the MG point −0.375 and the 4×4 torus ED are called exact). Every
number traces to a frozen CSV (`freeze/MASTER.csv`, `audit/provenance.csv`).

| target | required | delivered | status |
|---|---|---|---|
| **T1** 1D Heisenberg ≤ 200 spins | gap ≤ 1e-5 | **+9.931e-06 at N=100** (reach r 5→9); ladder N=50–140 at +1.6…2.5e-05 | **threshold met at N=100**; N=200 = quantified frontier (three one-sided points; no bound row) |
| **T2** 1D J1–J2 ≤ 100 spins | bracket ≤ 1e-3 | brackets +3.5e-05 / +5.0e-04 / −4.3e-09 (MG) / +7.6e-04 for J2 ≤ 0.6; +4.2e-03 / +6.6e-03 at J2 = 0.8/1.0 | **met for J2 ≤ 0.6**; frustrated side honest, out of band |
| **T3** 2D Heisenberg ≤ 16×16 | gap ≤ 1e-3 | L=4 valid vs exact torus ED (−0.7024963 vs −0.7017802); L=6/8 scaling rows; upstream `lattice="square"` bug found + patched | **measured concession** at 16×16 (basis rows 20854→30928 at L=6→8) |
| **T4** 2D J1–J2 10×10 | ≤ 1e-2 | J2=0.2: −0.6007562490 (bracket ≈3.3e-3, in-band); J2=0.5: −0.5116536004 (≈1.5e-2) | **two rows delivered**; j05 out of band; brackets published variational energies, excludes none |

## Method (short version — full story in the synthesis report)

**Foundation.** Structured NPA via QMBCertify (pinned unmodified at
be63c27) plus a sha-pinned textual fork adding one untyped seam hook —
every extension enters through that seam and is gate-verified
(ED-substitution, mutation red-tests, semantic hashes; ledger C1–C21).

**What met the targets.** The reach axis (spatial range of the two-site
basis) is the accuracy lever: r 5→9 alone closed the T1 gap at N=100.
RDM positivity nearly saturates small N on top of it; PSO sets the
~110 GB memory floor at N=100 (hence pso=0 in 2D per the paper's own
Remark 6.1).

**The method campaign (coarse graining).** Three controlled experiments
on one question — can a coarse multiscale representation replace
expensive fine-scale moments?

1. **Additive tower** (finite-depth dual-parity specialization of the
   Sec. III-D-2 hierarchy, gate-verified): structural crossover confirmed
   (SDP-size ratio 1.447 → 0.530 over N=14→30) but realized solver cost
   stayed 9–10.7× — structural size ≠ realized cost.
2. **Direct elimination** (deleted fine variables provably never
   created): 30.3% structural reduction at realized cost parity (N=10);
   at N=20 the first configuration cheaper on every axis — structural
   0.383×, wall 0.75×, memory 0.51×. Accuracy recovery stayed unresolved
   at every size (one-sided bounds ≤ 0.56% of the resolved gap) — a
   successful compression scheme, not yet an accuracy-recovery scheme.
3. **D-package isolation**: swapping only the coarse-map package D=2→D=4
   (same size, basis, levels, links) moved realized cost from ~parity to
   2.37×/6.80× — PSD block dimension, not scalar count, drives
   interior-point cost.

Moment bundles were structurally absorbed by the retained quotient
closure at every tested size (W_bundle = 0, enumerated) — correction
families must be anchored in the deleted subspace (55 classes enumerated
at N=10). Full narrative, tables, figures, pre-registrations and claim
boundaries: [`SYNTHESIS_REPORT.md`](SYNTHESIS_REPORT.md) ·
[`SYNTHESIS_REPORT_ZH.md`](SYNTHESIS_REPORT_ZH.md).

## Tooling named by the issue

[QMBCertify](https://github.com/wangjie212/QMBCertify) · [NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl) · [NCTSSOS](https://github.com/wangjie212/NCTSSOS)

Work lands on this branch as it goes: scripts under this folder, data and plots under
`tracks/polyopt/results/<run>/` (out of git).
