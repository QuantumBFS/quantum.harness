# RESULTS TABLES (generated from MASTER.csv only — data freeze candidate)

## Target 1 — Heisenberg chain, per-site signed gap = E_Bethe − E_LB

| N | config | E_LB (numerical SDP lower bound) | gap | row |
|---|---|---|---|---|
| 50 | CONFIG A (r=5) | -0.4434935081 | +1.638e-05 | v50/scnet-20260729-001929 |
| 60 | CONFIG A (r=5) | -0.4433963315 | +2.011e-05 | v60/scnet-20260729-001929 |
| 80 | CONFIG A (r=5) | -0.4432993172 | +2.337e-05 | v80/scnet-20260729-001929 |
| 100 | CONFIG A (r=5) | -0.4432532120 | +2.364e-05 | v100/scnet-20260729-001929 |
| 120 | CONFIG A (r=5) | -0.4432291490 | +2.476e-05 | v120/scnet-20260729-001929 |
| 140 | CONFIG A (r=5) | -0.4432129679 | +2.377e-05 | v140/scnet-20260729-001929 |
| 100 | CONFIG A + extra=8 (r=9) | -0.4432395015 | **+9.931e-06** | v100e8/scnet-20260729-001929 |

N=200: resource frontier (CONFIG A construction alone > 11.7 h wall). N=160: > 340 GB.
Fingerprints: v14/v14fp match Table 3 to all 7 printed digits on compute nodes.

## Target 2 — J1-J2 chain N=100, bracket = E_DMRG_upper − E_LB

| J2 | E_LB | E_DMRG (variational upper bound) | bracket |
|---|---|---|---|
| 0.2 | -0.4086076123 | -0.4085729238 | +3.469e-05 |
| 0.4 | -0.3808885700 | -0.3803879204 | +5.006e-04 |
| 0.5 | -0.3749999957 | −0.375 (exact, MG) | -4.304e-09 |
| 0.6 | -0.3814148627 | -0.3806532275 | +7.616e-04 |
| 0.8 | -0.4249105577 | -0.4207006317 | +4.210e-03 |
| 1.0 | -0.4926313793 | -0.4860704208 | +6.561e-03 |

|dev| ≤ 1e-3 holds for J2 ≤ 0.6; frustrated side (0.8, 1.0) lands in the 1e-2 band.
N=40: five J2 points cross-validated vs local runs to ≤1e-10.

## Target 4 — 2D J1-J2 10×10 (lso=0, pso=0 per Remark 6.1)

| J2 | E_LB | note |
|---|---|---|
| 0.2 | -0.6007562490 | bracket vs published variational ≈ 3.3e-3 (inside 1e-2) |
| 0.5 | -0.5116536004 | ≈ 1.5e-2 band |

2D probe chain (Heisenberg): L=4 −0.7024963 (valid vs exact −0.7017802) · L=6 −0.6821741 · L=8 −0.6789488.
Target 3 (16×16): conceded on measured scaling (m: 20854→30928 at L=6→8; wall/RSS frontier).
