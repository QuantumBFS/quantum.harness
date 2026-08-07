# Expert review note: certified \(L=4\) finite-size PXP gap scan

Recorded on 2026-07-30 for the draft contribution associated with
[QuantumBFS/quantum.harness#233](https://github.com/QuantumBFS/quantum.harness/issues/233).
Raw solver and certificate payloads remain gitignored and local.

## Executive conclusion

The `global-d2` hierarchy gives an independently checked, strictly positive
lower bound on the finite-size global gap at all 61 points
\(\delta=0,0.05,\ldots,3.0\). Every bound is contained below the ED value for
the identical Hamiltonian. The largest absolute ED-minus-certificate deficit
is \(5.4030\times10^{-7}\), and the largest relative deficit is
\(2.44\times10^{-6}\).

This is deliberately a minimal \(L=4\) result. It validates the SDP,
exact-repair, independent-check, and ED-containment workflow; it does **not**
locate the thermodynamic transition, prove a thermodynamic gap, or satisfy the
original issue's \(N\le20\) acceptance gate.

## Physical contract

\[
H_L(\delta)
=\sum_{i=0}^{L-1}P_{i-1}X_iP_{i+1}
-\delta\sum_{i=0}^{L-1}n_i,
\qquad
P=\frac{I-Z}{2},
\qquad
n=\frac{I+Z}{2}.
\]

The Rabi coefficient is \(+1\), \(0=\downarrow\), \(1=\uparrow\), site
indices are periodic, and the constrained Hilbert space obeys
\(n_i n_{i+1}=0\), including the wrap bond. Translation and reflection are
Hamiltonian symmetries, but the target is the multiplicity-counted global
\(E_1-E_0\) across the full constrained Hilbert space.

## Normalization and transition window

In the hard-boson convention of
[Fendley, Sengupta, and Sachdev](https://arxiv.org/abs/cond-mat/0309438),
the \(V=0\) Ising transition is at \(U/w\simeq-1.308\). A product of on-site
\(Z\) rotations changes the sign of the drive, while the present convention
has \(w=1\) and \(U=-\delta\). Thus the corresponding value is
\(\delta_c\simeq1.308\). The extended interval \([0,3]\) covers both sides of
this commonly quoted transition. Conventions writing the Rabi term as
\(\Omega_{\rm R}/2\) differ by a factor of two and must not be compared
without rescaling.

The target here is the multiplicity-counted global \(E_1-E_0\). In a
finite periodic chain this quantity includes the low-energy splitting between
states that become symmetry related in the ordered phase. Its decrease with
\(\delta\) is therefore not, by itself, a bulk excitation-gap estimate.

## Certified scan

The `global-d2` hierarchy with sound blockade localizers produces a strictly
positive, independently checked certificate at every point
\(\delta=0,0.05,\ldots,3.0\). Each point passed exact certificate
reconstruction, the independent checker, identical-point ED containment, and
Slurm accounting.

The table below records the original \([0,1]\) window in full. Selected
points from the certified extension are listed afterward; the combined
61-point summary is bound by the provenance hashes below.

| \(\delta\) | \(\Delta_{\mathrm{cert}}\) | \(\Delta_{\mathrm{ED}}\) | ED minus cert |
|---:|---:|---:|---:|
| 0.00 | 1.035275841514023 | 1.035276180410083 | \(3.389\times10^{-7}\) |
| 0.05 | 1.002192486042760 | 1.002192750351918 | \(2.643\times10^{-7}\) |
| 0.10 | 0.969621311137566 | 0.969621496808025 | \(1.857\times10^{-7}\) |
| 0.15 | 0.937580828590716 | 0.937580949401025 | \(1.208\times10^{-7}\) |
| 0.20 | 0.906089436138754 | 0.906089508246959 | \(7.211\times10^{-8}\) |
| 0.25 | 0.875165268853762 | 0.875165316754301 | \(4.790\times10^{-8}\) |
| 0.30 | 0.844826043956490 | 0.844826126437031 | \(8.248\times10^{-8}\) |
| 0.35 | 0.815088666722083 | 0.815089155249612 | \(4.885\times10^{-7}\) |
| 0.40 | 0.785970576652259 | 0.785970941282937 | \(3.646\times10^{-7}\) |
| 0.45 | 0.757486974518204 | 0.757487193975124 | \(2.195\times10^{-7}\) |
| 0.50 | 0.729652563382037 | 0.729652645272869 | \(8.189\times10^{-8}\) |
| 0.55 | 0.702480363111422 | 0.702480903410625 | \(5.403\times10^{-7}\) |
| 0.60 | 0.675984250498130 | 0.675984312139020 | \(6.164\times10^{-8}\) |
| 0.65 | 0.650173767456647 | 0.650173818314824 | \(5.086\times10^{-8}\) |
| 0.70 | 0.625058767233032 | 0.625058850749555 | \(8.352\times10^{-8}\) |
| 0.75 | 0.600647113417833 | 0.600647213093788 | \(9.968\times10^{-8}\) |
| 0.80 | 0.576944872765918 | 0.576944993305873 | \(1.205\times10^{-7}\) |
| 0.85 | 0.553956270390378 | 0.553956491920169 | \(2.215\times10^{-7}\) |
| 0.90 | 0.531683803211680 | 0.531684170900264 | \(3.677\times10^{-7}\) |
| 0.95 | 0.510128542346574 | 0.510128624352912 | \(8.201\times10^{-8}\) |
| 1.00 | 0.489288516466503 | 0.489288571810079 | \(5.534\times10^{-8}\) |

| \(\delta\) | \(\Delta_{\mathrm{cert}}\) | \(\Delta_{\mathrm{ED}}\) | ED minus cert |
|---:|---:|---:|---:|
| 1.05 | 0.469160852794336 | 0.469160874185090 | \(2.139\times10^{-8}\) |
| 1.30 | 0.378973954750358 | 0.378974252462368 | \(2.977\times10^{-7}\) |
| 1.35 | 0.362957557508223 | 0.362957991632607 | \(4.341\times10^{-7}\) |
| 1.50 | 0.318711513570314 | 0.318711578688422 | \(6.512\times10^{-8}\) |
| 2.00 | 0.207183610608148 | 0.207184060547196 | \(4.499\times10^{-7}\) |
| 2.05 | 0.198601792285701 | 0.198602276773019 | \(4.845\times10^{-7}\) |
| 2.50 | 0.137156200278300 | 0.137156316662734 | \(1.164\times10^{-7}\) |
| 3.00 | 0.093357907761249 | 0.093358003655545 | \(9.589\times10^{-8}\) |

The certified curve is monotonically decreasing on the 61-point grid. Its
minimum is

\[
\Delta_{\mathrm{cert}}(3)
=0.093357907761249050\ldots>0.
\]

The largest absolute deficit occurs at \(\delta=0.55\):
\(\Delta_{\mathrm{ED}}-\Delta_{\mathrm{cert}}
=5.4029920221\times10^{-7}\). The largest relative deficit occurs at
\(\delta=2.05\) and is \(2.4395\times10^{-6}\). These are fixed-\(L\)
facts only and do not establish a thermodynamic window.

## Exact anchor

The point is \(L=4\), \(\delta=1/2\), hierarchy `global-d2`, with sound
blockade localizers. The exact post-processed quantities are

\[
\begin{aligned}
A_{\mathrm{cert}}
&=-\frac{58821294818297914491}{11529215046068469760},\\
B_{\mathrm{var}}
&=-\frac{391664201486901837504506}
        {134325091068378508914003},\\
\Delta_{\mathrm{cert}}
&=A_{\mathrm{cert}}-2B_{\mathrm{var}}\\
&=\frac{
1129985826350554520336818858694628882959647
}{
1548662861010066926541798527783637646049280
}\\
&=0.7296525633820369387551400049161309\ldots .
\end{aligned}
\]

The independently verified ED oracle gives

\[
E_0=-2.915793306907376,\qquad
E_1=-2.186140661634507,\qquad
\Delta_{\mathrm{ED}}=0.7296526452728687,
\]

with maximum eigenpair residual
\(1.2135865151914198\times10^{-15}\). Thus

\[
\Delta_{\mathrm{ED}}-\Delta_{\mathrm{cert}}
=8.189083176124486\times10^{-8}>0.
\]

The certificate uses the physical-operator residual route. Its exact
corrections are

\[
\rho_{\mathrm{mom}}
=\frac{935964126663}{46116860184273879040},
\qquad
\rho_{\mathrm{op}}=\rho
=\frac{434499015743}{46116860184273879040}.
\]

The independent checker reconstructed ten PSD factors, checked 54 residual
coordinates, verified the original logical problem and solver reduction, and
returned `status=verified` and `certificate_status=certified`.

## Numerical seeds and resources

Clarabel 0.11.1 with JuMP 1.31.1 and Julia 1.12.6 generated a Float64
candidate dual. The solver status was
`ALMOST_OPTIMAL/NEARLY_FEASIBLE_POINT/NEARLY_FEASIBLE_POINT`, with raw status
`ALMOST_SOLVED`; this status was accepted only as a numerical seed. The exact
certificate above comes from dyadic PSD reconstruction and exact residual
correction, not from floating-point feasibility.

At the exact anchor, the solver objective was \(-5.10193396095102\), the
numerical dual objective was \(-5.101934040071849\), and the raw absolute
duality gap was \(7.91208289996348\times10^{-8}\).

The other 60 points used the same immutable logical structure. All
returned reduced-accuracy numerical seeds, with raw absolute duality gaps at
most \(5.55\times10^{-7}\), and were subsequently repaired and checked
exactly.
Slurm job `23033056` used 4 CPU cores and 8 GiB requested memory per task; the largest
observed task RSS was 882458624 bytes and elapsed times including Julia
startup were 71--84 seconds.

The \(\delta=1.05,\ldots,3.0\) extension ran as Slurm array job
`23034042_[1-40]` with the same per-task request. All 40 tasks completed in
43--89 seconds, with maximum observed RSS 915066880 bytes. Clarabel solve
times were 0.953--1.917 seconds; all numerical candidates were subsequently
repaired and independently checked exactly.

The existing \(\delta=1/2\) certificate was reused without recomputation.
Ten coarse ED points were extracted from the previously verified 187-point
artifact without diagonalization, and only the ten new half-step ED points
were computed.

## Provenance

- run-spec SHA-256:
  `f6bfc31806d5ba670d4a5e24269501b75e8ac34edd3c4436da86ea8bac3a17bc`
- logical structure SHA-256:
  `21890a21d98372fb986dc7df0e70c6f58a43c52174991706b6cbfb05ce5641fe`
- instance SHA-256:
  `6f1869629a1a43e2873684923566910f09e82633395b8d967cfce753ab949488`
- solver reduction SHA-256:
  `35bb369a9efe56952b45a5a5f9488f1a3fcb1168b0d097d3801e262b0a93bb68`
- trial-vector SHA-256:
  `23b9a81d1279f57d9e35e5d30fa17f4e3a2f5500b3e8f0d1d983ea8e2db04fe1`
- certificate SHA-256:
  `c878313a2b11806386946fa9c4f98ac63be72ee3284d3f5e2b30c7480664f114`
- final local manifest SHA-256:
  `b702006ca7580001afd3efdf01a9d37f69c817181b8d2910896400caaefcd181`
- Slurm job/task: `23030151_1` on `xhacnormalb`
- 20-point scan run-spec SHA-256:
  `91e7ad05e4e6dad07f1b96d1864c830f2bf734e97f6a6b58df942bb5d5c53ecf`
- independently checked 20-point summary SHA-256:
  `ba5d3735d87fd7c4179df1b3669792dca7badf3d9985c1044634856775e39cb1`
- combined 21-point summary SHA-256:
  `4f487aa103466cdc67733911506df3b3406ec0d36b1ecc730bc62593b3cc0d32`
- scan Slurm array job: `23033056_[1-20]` on `xhacnormalb`
- extension run-spec SHA-256:
  `523165a201a707b9ea357039679fe244095028f5d5814dbd6c2030a5091d6591`
- extension solver reduction SHA-256:
  `4129c05b09059b4a7187f6aa4d7e249ed99b55d272b752c6ffeb1301a02f5ec8`
- independently checked extension summary SHA-256:
  `71374754cb796d2257f111b9f621af407c12a837c628f98634657afad3d05644`
- combined 61-point summary SHA-256:
  `8bcba4a26c0ee8ce62f8c600a71e37b0b5762ebc754e0c405830c53d1f810681`
- extension Slurm array job: `23034042_[1-40]` on `xhacnormalb`

Given the local artifacts, rerun the standard-library-only independent
checker with

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 \
  src/challenge233/sdp/verify_kyfan_certificate.py \
  results/kyfan/20260730-n4-presolve-anchor/cells/cell-0001
```

Recheck the 40 extension cells, their ED containment, and their accounting with

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 \
  src/challenge233/sdp/run_kyfan.py certify-run \
  --run-spec \
  results/kyfan/20260730-n4-d2-delta105-300-scan/run_spec.json
```

This completes the user-approved minimal fixed-\(L\) submission. It is not a
thermodynamic-limit certificate and does not satisfy the original issue's
\(n\le20\) success gate.
