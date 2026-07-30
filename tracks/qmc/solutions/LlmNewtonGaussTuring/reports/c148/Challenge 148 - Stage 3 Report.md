---
title: "Challenge 148: Stage 3 Report — Cluster-Update SSE and Square-Lattice Benchmark"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - sse
  - quantum-monte-carlo
  - cluster-update
  - finite-size-scaling
status: gate-pending
stage: 3
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 1 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 2 Report.md
---

# Challenge 148: Stage 3 Report

## 1. Stage status

| Item | Status |
|---|---|
| Off-diagonal update redesign (graph-agnostic cluster update) | Complete |
| Stage 2 `m2` gate-pending risk | **Resolved** |
| Stage 2 $J=0$ known limitation | **Resolved** |
| ED oracle defect (diagonal observables) | **Found and fixed** |
| Lattice `smallest_momentum` defect | **Found and fixed** |
| Raw bin-level output | Complete |
| Independent-cell seed contract and block bootstrap | **Failed in historical pilot; repaired code needs fresh data** |
| Square-lattice $h_c$ benchmark | **Invalidated; fresh scan required** |
| Ground-state ($c_\beta$) convergence gate | **Invalidated with historical statistics** |
| Triangular / honeycomb kernel support | Complete (validated, not yet scanned) |
| **Overall stage** | **Gate-pending; kernel retained, pilot conclusions superseded** |

Implementation in `tracks/qmc/solutions/LlmNewtonGaussTuring/`, commits
`98a99fd` (kernel and oracle fixes) and `83f4c50` (scan and analysis).
Compiler GCC 15.2.0, C++17, no external dependencies.

### 1.1 Consolidated-audit correction (2026-07-28)

The cluster-update kernel, ED diagonal-observable repair, and raw-bin export are
retained. The reported square-lattice uncertainty and every significance,
$\chi^2$, crossing, and gate decision derived from it are invalid for two
independent reasons:

1. the same replica seed was reused at every field for fixed $L$, while the
   analysis treated different $(L,h)$ cells as independent;
2. the bootstrap resampled individual bins without first preserving independent
   chains or blocking beyond the integrated autocorrelation time.

The repaired scan now assigns a unique seed to every $(L,h,\mathrm{replica})$,
writes results deterministically on the main thread, and the analysis resamples
chains plus circular blocks. Historical raw data cannot be repaired into the
missing independent experiment; a fresh square scan is required.

## 2. Previous work summary

Stage 0 froze the Hamiltonian, the primary estimator $Q_L=\langle m^2\rangle^2/\langle m^4\rangle$,
the secondary estimator $\xi_L/L$, the fit family, and the verdict gate. Stage 1
delivered the lattice module (chain, square, triangular, honeycomb) and an
exact-diagonalisation oracle. Stage 2 delivered a serial 1D SSE kernel whose
**energy** matched the oracle but whose **magnetisation was badly biased**
($m^2\approx0.036$ against an oracle value of $0.738$ at $N=4$, $h/J=0.75$).

Stage 2 closed with two open items, both of which Stage 3 was required to
resolve before production data:

1. the `m2` bias, marked `gate-pending`, because $Q_L$ and $\xi_L/L$ — the
   primary and secondary critical-field estimators — are built from $m^2$ and $m^4$;
2. the A/B sublattice line update, which assumed a bipartite 1D chain and could
   not be carried to the triangular lattice.

## 3. Stage objective

Per the Stage 2 plan and the Stage 0 protocol, Stage 3 had to:

1. replace the 1D line update with a graph-agnostic update that preserves the
   ferromagnetic weight landscape;
2. extend the solver to the periodic square lattice;
3. locate $Q_L$ and $\xi_L/L$ crossings and recover $h_c/J=3.04438(2)$ within
   the declared pilot uncertainty;
4. confirm compatibility with a continuous transition and demonstrate
   ground-state ($\beta$) convergence.

## 4. Work completed

### 4.1 Diagnosis of the Stage 2 `m2` bias

Stage 2 attributed the bias to its energy-shift convention. That diagnosis was
correct but incomplete. Two independent defects were present, and only one of
them was in the SSE.

**Defect A — inverted weight landscape (SSE).** Stage 2 used
$\text{bondWeight}=-(J\sigma_i\sigma_j+E_{\text{shift}})$ with
$E_{\text{shift}}=-J-0.1$, giving weight $0.1$ to an *aligned* bond and
$2J+0.1$ to an *anti-aligned* bond. The line update walks one world line and
accepts a flip through an aligned bond with
$\exp[\log(2.1/0.1)]\gg1$, so ferromagnetic order was actively destroyed.

**Defect B — ED oracle used basis indices as eigenstate labels.**
`compute_thermal_obs` and `compute_structure_factor` looped over the spectrum
index `s`, took the Boltzmann weight of eigenvalue `s`, and then evaluated the
observable on the *basis state* whose integer label happened to equal `s`:

```cpp
double En  = es.eigenvalues[s];
double boltz = std::exp(-beta * (En - E0));
double m_s = magnetization(s, lattice.N);   // <-- basis state, not eigenstate
```

The eigenvectors were never used. Every diagonal observable ($m$, $m^2$, $m^4$,
$Q$, $S(\mathbf q)$) was therefore wrong, while the eigenvalue-only quantities
($E$, $C_v$) stayed correct. This is exactly the signature Stage 2 observed and
misread: energy agreed, moments did not. **Part of the Stage 2 "bias" was the
reference being wrong, not the sampler.**

The oracle now builds the basis-state probabilities

$$
p(c)=\frac{1}{Z}\sum_n e^{-\beta E_n}\,\bigl|\langle c|\psi_n\rangle\bigr|^2 ,
$$

and evaluates every diagonal observable against $p(c)$.

Two further defects were found while validating:

- $C_v$ divided by $\beta^2$ instead of multiplying by it;
- `Lattice::smallest_momentum()` scanned integer multiples of the reciprocal
  *lattice* vectors and returned $|\mathbf b_1|=2\pi$, which aliases to
  $\mathbf q=0$ on the torus ($e^{i2\pi x}=1$), collapsing $\xi_L/L$ to zero.
  The allowed torus momenta are $(n_a/L_a)\mathbf b_1+(n_b/L_b)\mathbf b_2$,
  so the smallest is $2\pi/L$.

### 4.2 SSE redesign: standard decomposition plus cluster update

The energy-shift convention was abandoned for the standard non-negative
Sandvik (2003) decomposition, $H=-\sum_a H_a + C$ with $C=J N_b + hN$:

| Operator | Type | Weight |
|---|---|---|
| `BOND` | diagonal | $J(1+\sigma_i\sigma_j)$ = $2J$ aligned, $0$ anti-aligned |
| `CONST_SITE` | diagonal | $h$ |
| `FLIP_SITE` | off-diagonal ($\sigma^x$) | $h$ |

Because an anti-aligned bond has weight zero, bond operators only ever sit on
aligned pairs, and they *bind* the two world lines they touch. A single-world-line
update cannot flip through such a bond — which is precisely why Stage 2 needed
its inverted shift. The cluster update flips **both** bound world lines together:

1. cut each site's imaginary-time world line at every site operator; the
   stretches between cuts are *segments*;
2. fuse (union-find) the two segments touched by each `BOND` operator;
3. flip each resulting cluster with probability $1/2$;
4. toggle `CONST_SITE`$\leftrightarrow$`FLIP_SITE` at each site operator whose
   two neighbouring segments disagree on the flip decision.

A cluster flip changes neither $n$, nor the number of bond operators, nor any
matrix element (`CONST` and `FLIP` both have weight $h$), so the configuration
weight is invariant and the move is **rejection-free**. The number of flip
parity changes around each world line is even by construction, so world lines
always close.

The update refers only to the bond list. It carries no bipartite, dimensional,
or coordination assumption, so triangular and honeycomb lattices are supported
without modification — closing the second Stage 2 risk.

### 4.3 Measurement and analysis layer

`run()` previously took one measurement per bin. It now measures every sweep
after thermalisation and averages into bins, and returns the **raw per-bin**
$E$, $m^2$, $m^4$, $S(0)$, $S(q_{\min})$. Stage 0 §4.2 and §7.4 require nonlinear
estimators to be rebuilt inside each resample; that is impossible from terminal
averages alone.

- `tools/scan_square.cpp` — threaded scan over $(L,h,\text{seed})$ at
  $\beta=c_\beta L$, jackknife over bins per cell, CSV output.
- `tools/analyze_crossings.py` — bootstrap ($n=2000$) over bins; $Q_L$ and
  $\xi_L/L$ are recomputed in every resample, crossings are located by sign
  change with linear interpolation, and failed resamples are counted and
  reported rather than silently dropped.

## 5. Artefacts

| Artefact | Location |
|---|---|
| SSE kernel | `src/sse.hpp` (130 lines), `src/sse.cpp` (301 lines) |
| Corrected ED oracle | `src/ed.cpp` |
| Corrected momentum | `src/lattice.cpp` |
| SSE tests | `tests/test_sse.cpp` |
| ED tests | `tests/test_ed.cpp` |
| Scan driver | `tools/scan_square.cpp` (247 lines) |
| Bootstrap analysis | `tools/analyze_crossings.py` (126 lines) |
| Diagnostics | `tools/debug_sse.cpp`, `tools/debug_cv.cpp` |
| Raw bins and summaries | `tracks/qmc/results/stage3/` (git-ignored) |

## 6. Validation evidence

### 6.1 Exact identities and self-checks (no oracle involved)

$H_{\text{const}}=h\mathbb{1}$ has $\langle H_{\text{const}}\rangle=h$ regardless of
state, so $\langle n_{\text{const}}\rangle=\beta hN$ **exactly**. This pins the
diagonal update independently of ED:

| Lattice | $\langle n_{\text{const}}\rangle$ | $\beta hN$ |
|---|---|---|
| chain $L=8$ | 18.0035 | 18 |
| square $3\times3$ | 54.084 | 54 |
| triangular $3\times3$ | 108.107 | 108 |
| honeycomb $2\times2$ | 48.041 | 48 |

A per-sweep self-check propagating $|\alpha(0)\rangle$ through the operator string
confirms world-line closure and that every `BOND` sits on an aligned pair.
Runs with `check_config=true` have zero failures in the test suite. Historical
production cells disabled this $O(M)$ check and therefore provide no failure
count; current output records `config_checked=0` and
`consistency_failures=-1` for such unchecked runs.

### 6.2 Analytic limits

| Test | Expected | SSE |
|---|---|---|
| $J=0$, $h=1$, $\beta=2$, $N=6$ | $E/N=-h\tanh\beta h=-0.9640$ | $-0.9732$ |
| $J=0$ | $m^2=1/N=0.16667$ | $0.16833$ |
| $h=0.1J$, $\beta=5$ (ordered) | $m^2\to1$ | $0.9978$ (Stage 2: $0.036$) |

The $J=0$ case was a declared Stage 2 limitation; it now passes.

### 6.3 Against the corrected ED oracle

Full observable vector, not energy alone:

| Cell | $E$ SSE/ED | $m^2$ SSE/ED | $Q$ SSE/ED |
|---|---|---|---|
| chain $N=4$, $h=0.75$ | $-1.1577$ / $-1.1504$ | $0.8713$ / $0.8744$ | $0.8988$ / $0.9005$ |
| chain $N=6$ | $-1.1485$ / $-1.1468$ | $0.8535$ / $0.8565$ | $0.9048$ / $0.9071$ |
| chain $N=8$ | $-1.1434$ / $-1.1463$ | $0.8428$ / $0.8454$ | $0.9141$ / $0.9152$ |
| square $2\times3$, $h=2$ | $-2.5428$ / $-2.5445$ | $0.7165$ / $0.7226$ | $0.8024$ / $0.8071$ |
| square $3\times3$, $h=2$ | $-2.5140$ / $-2.5147$ | $0.7463$ / $0.7465$ | $0.8651$ / $0.8657$ |
| square $3\times3$, $h=3$ | $-3.2410$ / $-3.2450$ | $0.3839$ / $0.3794$ | $0.5716$ / $0.5677$ |
| square $3\times3$ $\xi_L/L$ | — | — | $0.3519$ / $0.3461$ |

The square-lattice cells exercise the graph-agnostic update on a
non-1D geometry, which the Stage 2 kernel could not do at all.

As an independent check of the corrected $C_v$, the $N=4$ chain at $h=0.5$,
$\beta=100$ has a ground doublet split by $\delta=0.03549$, so $\beta\delta=3.55$
sits on the two-level Schottky peak. The oracle returns
$C_v/N=0.08554826213$ against the exact Schottky value $0.08554826212$ — ten
significant figures. The previous test asserted $C_v<10^{-3}$ here and passed
only because $C_v$ was mis-normalised by $\beta^2=10^4$.

### 6.4 Square-lattice critical field

Pilot: $L\in\{4,6,8,10,12,16\}$, $\beta=L$, 4 seeds/cell, $10^4$ thermalisation
and $10^4$ measurement sweeps/cell, 200 bins. Crossings from a bootstrap over
bins ($n=2000$), narrow window $|h-h_c|\le0.045$:

| Pair | $Q_L$ crossing | $\xi_L/L$ crossing |
|---|---|---|
| 6 vs 8 | $3.02267\pm0.00742$ | $3.03771\pm0.01143$ |
| 8 vs 10 | $3.01749\pm0.00822$ | $3.05657\pm0.01310$ |
| 10 vs 12 | $3.04004\pm0.00507$ | $3.03838\pm0.00749$ |
| **12 vs 16** | $\mathbf{3.04366\pm0.00417}$ | $\mathbf{3.04763\pm0.00261}$ |

Published value $h_c/J=3.04438(2)$. The largest-size pair agrees at
$-0.2\sigma$ ($Q_L$) and $+1.2\sigma$ ($\xi_L/L$). The two independent
dimensionless observables agree with each other and with the literature, and
the residual drift at smaller $L$ has the expected sign and decreases
monotonically with size.

$Q_L$ evaluated at the published $h_c$ flattens with $L$ — the crossing
signature — converging to $Q^*\approx0.501$:

| $L$ | 4 | 6 | 8 | 10 | 12 | 16 |
|---|---|---|---|---|---|---|
| $Q(h_c)$ | 0.5369 | 0.5203 | 0.5108 | 0.5045 | 0.5020 | 0.5012 |

### 6.5 Aspect-ratio ($c_\beta$) study

The historical scan used $\beta=c_\beta L$, but the Blote-Deng mapping gives
$M=\beta h/\epsilon$ and $M_p=\epsilon M$. Their choice $M_p=L$ therefore
requires $\beta h=L$, not $\beta=L$. Because $h$ varied within the scan, the
historical rows did not hold a common physical aspect ratio. Their numerical
table and all conclusions about $Q^*$, aspect-ratio invariance, and
ground-state convergence are withdrawn.

Per [[Challenge 148 - Protocol Revision 1]], the corrected reproduction uses
$\beta=c_\tau L/h$ with $c_\tau=1$ and a doubled check at $c_\tau=2$. Fresh
statistics are required before either the paper's $Q^*$ convention or the
finite-$\beta$ gate can be assessed.

## 7. Deviations and unresolved risks

1. **$Q^*$ convention is not yet matched to Blote-Deng.** The historical
   $\beta=c_\beta L$ scan used the wrong physical aspect-ratio variable. Stage 4
   must use $\beta=c_\tau L/h$ and reproduce the paper's asymptotic $Q$ before
   interpreting this gate.
2. **Historical pilot uncertainty invalid.** The quoted $\sim4\times10^{-3}$
   error cannot be interpreted statistically after the seed/bootstrap audit.
3. **Crossing drift not yet fitted.** The registered form
   $h_\times(L,sL)=h_c+AL^{-(1/\nu+\omega)}$ has not been fitted; the current
   statement is a consistency check at the largest pair, not an extrapolation.
4. **Historical small-$L$ bootstrap failures.** The $L=4$ vs $6$ pair produced resamples
   with no crossing inside the window (up to 1931/2000 at $c_\beta=1$). These
   are reported, not discarded, and that pair is excluded from conclusions.
5. **Autocorrelation was not measured in the historical analysis.** The
   repaired script measures it for every chain and observable, but fresh data
   are required to satisfy the Stage 0 §4.4 gate.
6. **Single-observable measurement point.** Observables are measured on
   $|\alpha(0)\rangle$ only. Propagation-averaged and improved cluster
   estimators (Sandvik §5.2.5) would reduce variance substantially and should
   be considered before production.
7. **ParaToric independent route** remains unqualified; its four Stage 0 gates
   are untouched.

## 8. Stage-gate assessment

Stage 3 gate: *"both dimensionless observables and fit variants give a
consistent square-lattice critical point without unexplained drift."*

| Gate | Status |
|---|---|
| Square lattice implemented and validated against ED | Pass |
| $Q_L$ crossing consistent with $h_c/J=3.04438(2)$ | Invalidated; fresh data pending |
| $\xi_L/L$ crossing consistent | Invalidated; fresh data pending |
| The two observables agree with each other | Invalidated; fresh data pending |
| Drift explained | Pending repaired scaling analysis |
| Ground-state $\beta$ convergence | Pending fresh doubled-$\beta$ cells |
| Stage 2 `m2` risk resolved | Pass |
| Sign positive throughout | Pass |

**The Stage 3 gate is open.** The cluster kernel is qualified for a fresh
benchmark, but Stage 4 production and any ratio verdict remain unauthorized
until the square-lattice scan passes the repaired seed, autocorrelation, and
bootstrap contract.

## 9. Stage 4 work plan

Stage 4 reproduces the 2002 triangular and honeycomb window.

1. **Calibrate $c_\beta$ to the Blote-Deng convention.** Measure the excitation
   velocity or scan $c_\beta$ until $Q^*$ reproduces $0.6206(2)$ on the square
   lattice, then carry the calibrated convention to both target lattices.
   Until then, report $h_c$ (convention-independent) rather than $Q^*$.
2. **Extend the scan driver to triangular and honeycomb.** The kernel already
   supports both; only the driver hard-codes `make_square`. Verify $N$, $N_b$,
   coordination, and the smallest reciprocal vectors for the honeycomb two-site
   basis, whose $\xi_L/L$ needs the correct $\mathbf q_{\min}$.
3. **Reproduce the historical window**, $L=6\ldots20$ (triangular) and
   $L=10\ldots20$ (honeycomb), and compare with $4.76811(9)$ and $2.13250(4)$.
4. **Measure integrated autocorrelation times** and switch the bootstrap unit
   to blocks longer than $\tau_{\text{int}}$ (Stage 0 §4.4, §7.4).
5. **Fit the registered crossing-drift form** rather than quoting the
   largest-pair value.
6. **Implement improved/propagation-averaged estimators** if the pilot cost
   model shows the current variance is the binding constraint.
7. **Stage 4 report** with the reproduction comparison and a cost-and-error
   model for the Stage 5 pilot.

## 10. Agent Review and Suggestions

### 10.1 Requested review focus

- Is the cluster-update construction (§4.2) a faithful Sandvik (2003) TFIM
  update, in particular the `CONST`$\leftrightarrow$`FLIP` toggle rule at
  segment boundaries and the treatment of world lines with no site operators?
- Is measuring on $|\alpha(0)\rangle$ alone acceptable, or should
  propagation-averaged estimators be adopted before Stage 4?
- Is the $c_\beta$ interpretation in §6.5 correct, and is calibrating to
  $Q^*=0.6206$ the right way to match the Blote-Deng convention — or should the
  velocity be measured directly?
- Does treating bins as independent bias the quoted crossing uncertainties
  before $\tau_{\text{int}}$ is measured?
- **Stage 1 and Stage 2 reports contain claims invalidated by the defects found
  here.** Should they be annotated in place, or corrected by a linked erratum?

### 10.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |

### 10.3 Protocol-change rule

Nothing in Stage 3 changes the frozen Hamiltonian, the primary estimator
$Q_L$, the fit family, the blinding rule, or the verdict gate, so no
preregistration revision is required. The SSE decomposition and update
algorithm are implementation choices explicitly allowed to change under
§10.3 of the Stage 2 report, and the estimator and fit conventions are
preserved. The ED-oracle, $C_v$, and momentum corrections are defect repairs
to Stage 1 infrastructure, not protocol changes; they are recorded here
because they invalidate specific numerical claims in the Stage 1 and Stage 2
reports.
