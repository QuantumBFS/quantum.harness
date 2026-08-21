---
title: "Challenge 148: Triangular-to-Honeycomb TFIM Critical-Field Ratio"
date: 2026-07-27
tags:
  - quantum-harness
  - challenge-148
  - transverse-field-ising
  - quantum-monte-carlo
  - stochastic-series-expansion
  - finite-size-scaling
status: active
source:
  - https://github.com/QuantumBFS/quantum.harness/issues/148
related:
  - Harnessing Quantum 2026/培训仓库集成计划.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 1.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Report.md
  - src/sse_new/
  - src/cqu-bysj-phy/
---

# Challenge 148: Triangular-to-Honeycomb TFIM Critical-Field Ratio

## Executive summary

Challenge [#148](https://github.com/QuantumBFS/quantum.harness/issues/148) asks whether the ratio of the zero-temperature critical transverse fields of the ferromagnetic transverse-field Ising model (TFIM) on the triangular and honeycomb lattices is exactly $\sqrt{5}$. The conjecture is based on the high-precision continuous-time cluster Monte Carlo results of Blote and Deng (2002):

$$
\left(\frac{h_c}{J}\right)_{\triangle}=4.76811(9),
\qquad
\left(\frac{h_c}{J}\right)_{\hexagon}=2.13250(4).
$$

These values imply

$$
R \equiv \frac{h_c^{\triangle}}{h_c^{\hexagon}}
=2.2359249707,
\qquad
\sigma_R=5.95\times10^{-5},
$$

whereas

$$
\sqrt{5}=2.2360679775.
$$

Thus the published central value lies

$$
R-\sqrt{5}=-1.4301\times10^{-4}
$$

below the conjecture, a tension of approximately $2.40\sigma$. The present data neither establish nor decisively reject the relation.

The challenge is numerically attractive because the ferromagnetic model is sign-problem free. Its main difficulty is not obtaining Monte Carlo samples, but reducing and defending the *total* uncertainty in two non-universal critical couplings to the $10^{-5}$ level. The work therefore depends as much on estimator design, autocorrelation analysis, finite-size corrections, fit-window stability, and independent-code validation as it does on the SSE update itself.

Numerics can decisively falsify $R=\sqrt{5}$, but cannot prove an exact equality. If the conjecture survives a substantially sharper numerical test, a separate analytic mechanism or no-go argument becomes necessary.

---

## 1. Status and provenance

### 1.1 Official challenge record

- **Issue:** [QuantumBFS/quantum.harness#148](https://github.com/QuantumBFS/quantum.harness/issues/148)
- **Released by:** Xiao-Yan Xu, Shanghai Jiao Tong University
- **Method:** Quantum Monte Carlo
- **Labels as of 2026-07-27:** `challenge`, `accepted`, `autoresearch`
- **Issue author:** Jinguo Liu (`GiggleLiu`)
- **Issue created:** 2026-07-27

### 1.2 Primary numerical source

H. W. J. Blote and Y. Deng, "Cluster Monte Carlo simulation of the transverse Ising model," *Physical Review E* **66**, 066110 (2002), [doi:10.1103/PhysRevE.66.066110](https://doi.org/10.1103/PhysRevE.66.066110).

The paper studies square, triangular, kagome, honeycomb, and simple-cubic TFIMs with a continuous-time cluster algorithm obtained from the anisotropic classical Ising representation. For the triangular and honeycomb lattices it used periodic boundaries and sizes no larger than $L=20$:

| Lattice | $L_{\min}$ | $L_{\max}$ | fitted $Q$ | fitted $h_c/J$ |
|---|---:|---:|---:|---:|
| Triangular | 6 | 20 | 0.6238(7) | 4.76811(9) |
| Honeycomb | 10 | 20 | 0.6149(7) | 2.13250(4) |
| Square, for validation | 2 | 48 | 0.6206(2) | 3.04438(2) |

The reported total compute cost for all lattices in the paper was approximately five processor-months on a 750 MHz processor. This historical number shows that modern hardware should make larger systems and more independent replicas practical, but it is not itself a production-cost estimate for the new implementation.

### 1.3 Later literature relevant to the baseline

The 2024 paper by Kott *et al.*, "Quantum robustness of the toric code in a parallel field on the honeycomb and triangular lattice," *SciPost Physics* **17**, 053, [doi:10.21468/SciPostPhys.17.2.053](https://doi.org/10.21468/SciPostPhys.17.2.053), maps sectors of a toric-code problem to ferromagnetic TFIMs on the two lattices. It quotes mapped critical fields

$$
h_{z,c}=0.234467(5),
\qquad
h_{x,c}=0.104863(2),
$$

which correspond to the Blote-Deng values under the paper's normalization. Its high-order series estimates are useful independent consistency checks, but they do not replace the 2002 QMC values with a more precise pair.

A complete state-of-the-art audit remains a required first deliverable. Keyword search alone is insufficient: the audit should trace citations to Blote-Deng, search lattice-specific series/QMC literature, and reconcile every Hamiltonian normalization before comparing numbers.

---

## 2. Scientific question and conventions

### 2.1 Target Hamiltonian

The challenge uses Pauli-matrix normalization:

$$
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
\qquad J>0,
\qquad h\ge 0.
$$

The energy unit is $J=1$, and the control parameter is $g=h/J$. There is no longitudinal field. Bonds are nearest-neighbor bonds counted once. Periodic boundary conditions are required for the thermodynamic finite-size analysis.

This convention must not be mixed with spin-operator notation $S^a=\sigma^a/2$, which changes bond and field coefficients. Every imported reference value must be converted explicitly into the convention above.

### 2.2 Lattice definitions

The implementation should represent lattices as explicit graphs plus geometric metadata, rather than encoding neighbors through site parity or one-neighbor arrays.

| Lattice | Sites in an $L\times L$ cell | Coordination $z$ | Number of bonds |
|---|---:|---:|---:|
| Triangular | $N=L^2$ | 6 | $N_b=3N$ |
| Honeycomb | $N=2L^2$ | 3 | $N_b=3N/2$ |

The exact primitive vectors, basis coordinates, periodic wrapping convention, reciprocal vectors, and definition of $L$ must be stored in run metadata. A correct site count is not enough: a skewed torus or an inconsistent shortest reciprocal vector can bias $\xi/L$ and finite-size corrections.

### 2.3 Why the model is sign-problem free

In the $\sigma^z$ basis, the transverse-field term supplies non-positive off-diagonal matrix elements for $h\ge0$, while the ferromagnetic Ising interaction is diagonal. A suitable SSE decomposition therefore has non-negative configuration weights after the usual constant shift. The triangular geometry does not create a sign problem here because the interaction is ferromagnetic; the familiar triangular-lattice frustration applies to antiferromagnetic Ising coupling.

### 2.4 Expected critical behavior

Both transitions are expected to be continuous and in the three-dimensional Ising universality class, with dynamic exponent $z=1$. Useful modern anchors include

$$
\nu\approx0.629971,
\qquad
y_t=\frac{1}{\nu}\approx1.5874,
$$

and a leading irrelevant exponent near $\omega\approx0.83$. These universal exponents constrain the finite-size form, but the critical fields themselves are non-universal.

That distinction is central to the challenge: no general universality argument requires two non-universal couplings on different lattices to have an algebraic ratio.

---

## 3. Exact challenge requirements

The official issue defines four scientific objectives.

### 3.1 Re-pin the state of the art

Identify the best post-2002 determinations of both critical fields. For each candidate result, record:

- the exact Hamiltonian and Pauli/spin normalization;
- lattice vectors and boundary conditions;
- method and update type;
- system-size and inverse-temperature ranges;
- observable and finite-size ansatz;
- statistical and systematic uncertainties;
- whether the quoted uncertainty is one standard deviation;
- whether both lattices were treated consistently.

### 3.2 Improve both critical fields

The total uncertainties must be at least five times smaller than the 2002 values:

$$
\sigma\!\left(h_c^{\triangle}/J\right)\lesssim1.8\times10^{-5},
\qquad
\sigma\!\left(h_c^{\hexagon}/J\right)\lesssim8\times10^{-6}.
$$

"Total" means statistical uncertainty plus demonstrated finite-$\beta$, finite-size, fit-window, estimator, and implementation systematics. Merely reducing the Monte Carlo standard error does not satisfy the challenge.

### 3.3 Decide the ratio against a pre-registered gate

For independent triangular and honeycomb runs,

$$
R=\frac{h_c^{\triangle}}{h_c^{\hexagon}},
$$

with propagated variance

$$
\sigma_R^2
=\left(\frac{\sigma_{\triangle}}{h_c^{\hexagon}}\right)^2
+\left(\frac{h_c^{\triangle}\sigma_{\hexagon}}
{(h_c^{\hexagon})^2}\right)^2.
$$

If shared random numbers or a joint fitting procedure induce covariance, the covariance term must be included rather than assumed zero.

The issue target is

$$
\sigma_R\lesssim1.2\times10^{-5}.
$$

The verdict rule must be frozen before opening the production result. A practical interpretation of the official gate is:

- **Decisive rejection:** $|R-\sqrt{5}|/\sigma_R\gtrsim10$, with all systematic checks passed.
- **Survival:** $|R-\sqrt{5}|\lesssim2\sigma_R$, which motivates analytic work but does not prove equality.
- **Inconclusive:** intermediate significance or unresolved systematic drift.

### 3.4 Search for a mechanism if the conjecture survives

Possible directions include a quantum Hamiltonian-limit analogue of star-triangle relations, a hidden duality, a common graph-polynomial structure, or a no-go theorem showing that an exact mapping cannot preserve the required spectra and couplings.

---

## 4. Scope decisions for this project

These decisions are binding unless explicitly revised.

1. **The existing `sse_new` code is reference material only.** The two-dimensional implementation will receive a new architecture and new code. It will not be produced by incrementally inserting more neighbors into the one-dimensional data structures.
2. **The existing project is Rydberg-based, not identical to the target TFIM.** Its longitudinal detuning term and repulsive Rydberg interaction must not be silently carried into the challenge Hamiltonian. The challenge implementation has $h_z=0$ and the ferromagnetic TFIM signs stated in Section 2.1.
3. **The correctness baseline is serial.** Initial development and validation use the conceptual equivalent of `singlecpu + lineupdate`. Shared-memory and MPI paths are excluded from the first trusted result.
4. **The existing MPI implementation is experimental.** It may inform later engineering, but it is not evidence for the correctness of the new two-dimensional solver.
5. **Future MPI work should target parallel annealing or replica-level parameter-space parallelism.** It should be added only after the serial Markov chain, estimators, and finite-size pipeline pass all gates. The exact annealing/exchange algorithm must be specified and its stationary distribution proved before use.

### 4.1 What can be learned from the reference code

The current reference checkout is `xeri_chen/sse_new` commit `c40596f073c36931e083ac843daaa6718f46e1c5`. It provides examples of:

- a C++17 SSE operator-string implementation;
- diagonal insertion/removal and a line update;
- RNG and command-line parameter handling;
- a serial baseline plus experimental shared-memory/MPI variants;
- performance and implementation notes in `src/cqu-bysj-phy`.

It is structurally one-dimensional: the default bond map is `bond[i]=(i+1)%N`, the candidate operator count assumes $N$ bond operators plus $N$ site operators, and the A/B update assumes an even one-dimensional decomposition. Its output called `magnetization2` currently averages $m$, not $m^2$. These are reasons to redesign rather than patch the old architecture.

The Rydberg thesis, notes, and bibliography remain useful for SSE derivations, operator conventions, testing ideas, and prior performance observations. They are not source-fixed specifications for Challenge 148.

---

## 5. Proposed serial architecture

### 5.1 Layer boundaries

```text
CLI / run specification
        |
        v
lattice geometry ---> TFIM model decomposition
        |                    |
        +----------+---------+
                   v
          serial SSE Markov chain
          - diagonal update
          - line/cluster update
          - operator-string resize
                   |
                   v
          raw per-bin estimators
                   |
                   v
       collection and validation layer
                   |
                   v
       crossing and finite-size fits
```

The Monte Carlo kernel must not know about plotting, Slurm, MPI, or the final $\sqrt{5}$ verdict. The analysis layer must consume raw bin-level data rather than terminal-formatted averages.

### 5.2 Lattice module

Define a lattice interface containing:

- number of sites $N$ and number of bonds $N_b$;
- undirected bond list `(site_i, site_j)` with each bond exactly once;
- primitive vectors and basis coordinates;
- periodic translation operations;
- reciprocal vectors and smallest allowed momenta;
- optional graph-color information used only for later parallel work.

Required constructors:

- one-dimensional periodic chain, for exact-oracle testing;
- square lattice, for the published $h_c/J=3.04438(2)$ benchmark;
- triangular lattice;
- honeycomb lattice with an explicit two-site basis.

Graph tests must verify site uniqueness, bond uniqueness, coordination numbers, periodic wraparound, connectivity, translation invariance, and the expected $N_b$ formulas.

### 5.3 Model and SSE decomposition

Represent the pure TFIM independently of the lattice. The model supplies:

- the diagonal bond matrix elements for $-J\sigma_i^z\sigma_j^z$ plus a documented constant shift;
- the site operators associated with $-h\sigma_i^x$;
- normalization and energy-offset bookkeeping;
- an explicit proof or exhaustive local check that all sampled weights are non-negative.

The operator list should index bond and site operators separately. All proposal probabilities must use $N_b+N$, not a hard-coded multiple of $N$.

The serial update must satisfy detailed balance and ergodicity for arbitrary supported graphs. The implementation should follow a published TFIM SSE cluster/line-update construction, primarily Sandvik (2003), rather than extrapolating the one-dimensional parity logic by intuition.

### 5.4 Measurements

Save the raw ingredients needed for nonlinear observables:

- expansion order $n$ and energy estimator;
- magnetization density $m=N^{-1}\sum_i\sigma_i^z$;
- $m^2$ and $m^4$;
- structure factor $S(\mathbf{q})$ at $\mathbf{q}=0$ and the smallest lattice-compatible momenta;
- optional transverse magnetization and susceptibility diagnostics;
- update/cluster statistics and sign;
- sweep index, bin index, and seed.

The primary dimensionless observable should reproduce the 2002 definition

$$
Q_L=\frac{\langle m^2\rangle^2}{\langle m^4\rangle}.
$$

This is related to, but not numerically identical to, every convention called a "Binder cumulant" in the literature. The exact definition must appear in every data file and plot.

A second primary diagnostic should be the dimensionless correlation-length ratio $\xi_L/L$, computed from the second-moment estimator with lattice-correct reciprocal vectors. The two observables should locate compatible critical points; disagreement is a diagnostic, not an average to be hidden.

Derived ratios and their uncertainties must be computed by jackknife or bootstrap over bins. Naive propagation from separately averaged $m^2$ and $m^4$ is not acceptable.

### 5.5 Reproducible output contract

Every run cell should record:

- source commit and dirty status;
- compiler and build type;
- Hamiltonian convention;
- lattice name, $L$, $N$, $N_b$, vectors, basis, and boundary;
- $J$, $h$, $\beta$;
- thermalization sweeps, measurement sweeps, bin size, and seed;
- update algorithm and all tunable parameters;
- wall time and host information;
- raw-bin file hash;
- completion and diagnostic status.

Failed, interrupted, or non-converged cells must remain visible in the scan manifest.

---

## 6. Implementation plan and stage gates

### Stage reporting contract

Every stage must produce a separate English report before the stage is closed. The report file is named `Challenge 148 - Stage N Report.md` and must contain:

1. a summary of relevant work completed before the stage;
2. the stage objective, work performed, artifacts, and scientific results;
3. validation evidence, deviations, unresolved risks, and the stage-gate decision;
4. a concrete plan for the following stage;
5. an `Agent Review and Suggestions` section where other agents can record findings, recommendations, dispositions, and status.

A report may be drafted while a gate is pending, but it must state `gate-pending` and may not claim that the stage is closed. Review suggestions that change a frozen scientific choice require a documented protocol revision rather than a silent edit.

### Stage 0: literature and protocol freeze

1. Complete the post-2002 literature audit.
2. Freeze the Hamiltonian, lattice geometry, $Q_L$ definition, and ratio verdict.
3. Select the primary and secondary finite-size ansatz before production.
4. Define what counts as an independent second route.

**Gate:** a source table and pre-registration document are committed before production data exist.

### Stage 1: lattice and exact-oracle infrastructure

1. Implement chain, square, triangular, and honeycomb graph constructors.
2. Implement dense/sparse ED for very small graphs using exactly the same bond lists.
3. Generate exact finite-temperature observables for small $N$ where full diagonalization is feasible.

**Gate:** lattice invariants pass, and ED reproduces hand-checkable spectra and partition functions.

### Stage 2: serial one-dimensional SSE oracle

1. Implement the new serial SSE kernel.
2. Test $J=0$ against independent spins:
   $$
   E/N=-h\tanh(\beta h).
   $$
3. Test $h=0$ against the classical Ising limit.
4. At $J=h=1$, compare finite-$N$, finite-$\beta$ energies to the exact Jordan-Wigner solution.

**Gate:** energy and magnetization moments agree with exact values within statistically valid confidence intervals across multiple seeds.

### Stage 3: square-lattice benchmark

1. Run periodic square lattices over several $L$ and $\beta/L$ values.
2. Locate crossings of $Q_L$ and $\xi_L/L$.
3. Recover $h_c/J=3.04438(2)$ within the declared pilot uncertainty.
4. Confirm compatibility with 3D-Ising scaling.

**Gate:** both dimensionless observables and fit variants give a consistent square-lattice critical point without unexplained drift.

### Stage 4: reproduce the 2002 triangular and honeycomb window

Use at least the historical size ranges, including the paper's largest $L=20$, and reproduce its critical fields at comparable precision. This stage tests geometry, normalization, and fitting against the exact target later being improved.

**Gate:** the new implementation is statistically consistent with both published values, or every discrepancy is resolved before larger systems are run.

### Stage 5: pilot scaling study

Use a provisional geometric size sequence such as

$$
L\in\{8,12,16,24,32,48\},
$$

adjusted for valid lattice shapes. For each lattice:

1. calibrate the ground-state aspect ratio by a $\beta/L$ scan;
2. scan a broad $h$ window around the published $h_c$;
3. estimate crossing drift and autocorrelation time;
4. benchmark sweeps per effective independent sample;
5. use the observed drift and variance to choose production sizes and budgets.

The numbers above are pilot proposals, not immutable production parameters.

**Gate:** a documented cost and error model predicts whether the target precision is achievable with available resources.

### Stage 6: production scan

A plausible production series may extend to $L\sim64$--$128$, but the final range must be selected from pilot evidence. Run multiple independent seeds at every $(\text{lattice},L,h,\beta)$ cell. Use coarse-to-fine $h$ windows without inspecting the hidden final ratio verdict.

Production should be resumable and cell-based. Increasing sweeps is allowed for under-resolved cells; changing axes, estimators, or the fit protocol creates a new run identifier.

### Stage 7: independent route

Complete one of the following:

- an independent continuous-time cluster implementation following Blote-Deng/Rieger-Kawashima;
- an independently written SSE implementation with separate lattice and estimator code;
- another method capable of matching the required precision and systematics.

ED is mandatory for small-system validation but does not by itself satisfy the thermodynamic-limit independent-route requirement.

### Stage 8: sealed verdict and release

1. Freeze all accepted runs and hashes.
2. Run the pre-registered fit and bootstrap pipeline.
3. Compute $R$, $\sigma_R$, and the standardized distance from $\sqrt{5}$.
4. Compare the independent route before interpretation.
5. Publish code, raw bins, manifests, fit tables, residual plots, and a one-command reproduction entry point.

---

## 7. Parameter scans and finite-size analysis

### 7.1 Scan axes

The full experiment is a structured scan over:

| Axis | Purpose |
|---|---|
| lattice | triangular versus honeycomb |
| $L$ | finite-size extrapolation |
| $h/J$ | locate dimensionless-observable crossings |
| $\beta/L$ | demonstrate ground-state convergence for $z=1$ |
| seed/replica | estimate sampling uncertainty and chain-to-chain consistency |
| bin size | verify decorrelation and error stability |

The $h$ grid should be adaptive only at the planning level: a broad pilot brackets crossings, then a predeclared narrower production grid is generated. Histogram reweighting may later reduce the number of field points, but it requires overlap diagnostics and independent validation.

### 7.2 Primary finite-size form

The Blote-Deng analysis used a corrected expansion of the dimensionless ratio near the critical point. A modern primary model can be written schematically as

$$
Q_L(h)=Q^*
+a_1(h-h_c)L^{1/\nu}
+a_2(h-h_c)^2L^{2/\nu}
+b_1L^{-\omega}
+c_1(h-h_c)L^{1/\nu-\omega}
+\cdots.
$$

The primary fit must declare which terms are included and whether $\nu$ and $\omega$ are fixed or fitted. It must not silently add or remove terms until $\chi^2$ looks favorable.

An equivalent crossing-drift diagnostic for a size pair $(L,sL)$ is

$$
h_\times(L,sL)
=h_c+A L^{-(1/\nu+\omega)}+\cdots.
$$

This is useful as a transparent secondary analysis, but it discards information relative to a joint fit.

### 7.3 Fit robustness matrix

Pre-register a small matrix of purposeful variants:

- several $L_{\min}$ values;
- narrow and broad $h$ windows fixed before unblinding;
- leading correction only versus one justified subleading term;
- fixed modern 3D-Ising exponents versus a controlled exponent-release check;
- $Q_L$ versus $\xi_L/L$;
- separate versus joint treatment of the two lattices.

Each variant reports parameter estimates, bootstrap intervals, $\chi^2$/dof, residuals, failed bootstrap resamples, and sensitivity to removing the largest or smallest size. A small $\chi^2$/dof without visually structureless residuals is not sufficient.

### 7.4 Bootstrap unit

The resampling unit must be an independent chain or a block longer than the integrated autocorrelation time. For each bootstrap replicate:

1. resample raw chains/bins;
2. recompute $Q_L$ and $\xi_L/L$;
3. refit $h_c$;
4. propagate both critical fields into $R$.

This end-to-end bootstrap preserves nonlinear estimator and fit uncertainty. Failed replicates are counted and reported rather than discarded silently.

---

## 8. Error budget

Each critical field should carry a table with at least the following components:

| Component | Diagnostic | Treatment |
|---|---|---|
| Monte Carlo statistics | independent chains and blocked autocorrelation analysis | bootstrap interval |
| thermalization | hot/cold starts and discarded-prefix sweep | bound from stable plateau |
| finite $\beta$ | multiple $\beta/L$ values | difference or joint extrapolation |
| finite-size ansatz | $L_{\min}$ and correction-term matrix | model/window envelope |
| field discretization | grid refinement or validated reweighting | refinement difference |
| estimator convention | independent direct calculations of $m^2,m^4,S(q)$ | hard correctness gate |
| lattice geometry | graph invariants and independent generator | hard correctness gate |
| RNG/seed behavior | generator tests and chain spread | included in replica statistics |
| implementation | ED and second-code comparison | discrepancy must be resolved |

Independent uncertainty components may be combined in quadrature only when independence is defensible. Fit-model and fit-window sensitivity is usually better reported as a conservative envelope than treated as a random Gaussian contribution.

The precision target should be allocated before production. For example, the Monte Carlo component should be comfortably smaller than the total target so that finite-size and finite-$\beta$ systematics have room in the budget.

---

## 9. Verification plan

### 9.1 Unit and structural tests

- lattice counts and coordination for every supported $L$;
- each undirected bond occurs exactly once;
- periodic translations preserve the bond set;
- reciprocal vectors reproduce allowed momenta;
- local operator weights are non-negative;
- insertion/removal proposal ratios satisfy detailed balance;
- operator-string propagation returns the basis state to itself under the trace;
- checkpoint/restart gives statistically and, where designed, bitwise consistent continuation.

### 9.2 Exact numerical oracles

- $J=0$ independent-spin partition function and energy;
- $h=0$ classical ferromagnetic limit;
- one-dimensional Jordan-Wigner energies at finite $N$;
- full finite-temperature ED for small chain, square, triangular, and honeycomb clusters;
- direct comparison of the entire observable vector, not energy alone.

### 9.3 Published benchmarks

- 1D critical point $h_c/J=1$;
- square-lattice critical point $h_c/J=3.04438(2)$;
- triangular and honeycomb 2002 values over the historical size window;
- lattice-specific asymptotic $Q$ values under the same aspect-ratio convention.

### 9.4 Sampling diagnostics

- sign remains one within numerical representation;
- time-series stationarity after thermalization;
- stable means and errors under increasing bin size;
- integrated autocorrelation estimates for primary raw observables;
- agreement among independent seeds;
- no systematic dependence on initial ordered/disordered state;
- effective sample size reported, not inferred from raw sweep count.

### 9.5 Criticality diagnostics

At least two dimensionless observables should show compatible crossings. Order-parameter and susceptibility scaling should be consistent with a continuous 3D-Ising transition and rule out a crossover or first-order artifact. The purpose is not to re-discover the universality class, but to detect implementation or aspect-ratio errors that could shift $h_c$.

### 9.6 Independent-method requirement

The second route must agree with each $h_c$ within the combined uncertainty at selected large sizes and in the thermodynamic extrapolation. If it does not, the result is blocked pending diagnosis; the two values must not be averaged.

---

## 10. Deliverables

The minimal complete challenge submission should contain:

1. a literature and normalization audit;
2. a new serial two-dimensional TFIM QMC implementation;
3. lattice and exact-oracle tests;
4. raw bin-level data and immutable manifests;
5. $Q_L$ and $\xi_L/L$ curves for both lattices;
6. finite-$\beta$ and finite-size convergence evidence;
7. fit tables, residuals, bootstrap distributions, and error budgets;
8. an independent-route comparison;
9. the sealed $R$ versus $\sqrt{5}$ verdict;
10. a one-command reproduction script and short technical report.

For the training repository, reproducible source belongs in `tracks/<track>/solutions/`; generated bulk data remain under ignored `tracks/<track>/results/`. The implementation must not depend on absolute paths into the personal workspace.

---

## 11. Risk register

| Risk | Consequence | Mitigation |
|---|---|---|
| Treating the Rydberg reference model as the target TFIM | wrong Hamiltonian and critical point | new pure-TFIM model module; explicit $h_z=0$ tests |
| Incrementally extending the 1D bond representation | hidden geometry and normalization defects | new graph-based architecture |
| Reusing the mislabeled magnetization output | invalid Binder ratio | measure and store raw $m^2$ and $m^4$ independently |
| Insufficient $\beta$ | apparent crossing shifts | explicit $\beta/L$ convergence at representative sizes |
| Critical autocorrelation underestimated | overconfident errors | blocked bins, chain replicas, integrated autocorrelation |
| Too-small $L$ range | correction terms mimic $h_c$ shift | pilot drift study and larger systems |
| Flexible fit chosen after seeing the answer | confirmation bias | pre-registration and sealed verdict |
| Different lattice/aspect conventions | non-comparable critical fields | complete lattice metadata and reproduction of 2002 setup |
| Experimental parallel code changes the chain | biased stationary distribution | serial-only baseline until independently verified |
| No genuinely independent route | shared bug survives tests | separate code/method and ED oracle |

---

## 12. Suggested schedule

### Training-week target

The realistic one-week outcome is a validated foundation, not the final $10^{-5}$ verdict.

- **Day 1:** literature audit, protocol freeze, lattice graph tests.
- **Day 2:** serial SSE kernel and 1D exact-oracle tests.
- **Day 3:** square-lattice benchmark and nonlinear estimators.
- **Day 4:** triangular/honeycomb reproduction over the 2002 size window.
- **Day 5:** pilot crossing analysis, resource estimate, and reproducible report.

A successful week should end with a trustworthy pipeline, a reproduced baseline, and a quantitative plan for production.

### Research continuation

The full challenge likely requires additional weeks for large-$L$ statistics, fit stabilization, and an independent implementation. The schedule should be driven by measured sweep rates and autocorrelation, not by the historical processor-month estimate.

---

## 13. Extensions after the serial result

### 13.1 Parallel annealing and replica-level MPI

Once the serial kernel is frozen and validated, MPI can distribute independent replicas, field points, sizes, or an explicitly defined parallel-annealing schedule. This approach preserves a simple trusted chain and targets the naturally parallel scan dimension.

If replicas exchange configurations or temperatures, the exchange acceptance rule and stationary joint distribution must be derived and tested. Such an algorithm is a new method component, not a transparent performance switch.

### 13.2 Histogram and multi-histogram reweighting

Reweighting can sharpen crossings from fewer simulated field points, provided neighboring histograms overlap and the reweighted estimates are checked against direct simulations. It is especially useful after the serial baseline defines stable raw estimators.

### 13.3 Improved estimators and automated tuning

Possible additions include cluster estimators for magnetization moments, automatic bin growth from autocorrelation, sequential stopping based on target effective sample size, and adaptive proposal tuning that is frozen before measurement.

### 13.4 Broader lattice benchmark suite

After triangular and honeycomb support is established, square and kagome lattices can form a reusable TFIM benchmark suite. Any extension must preserve the same graph, convention, and manifest contracts.

### 13.5 Separate Rydberg model family

The Rydberg Hamiltonian can later be added as a distinct model module with longitudinal detuning and longer-range repulsion. It should share lattice and statistics infrastructure with the TFIM, but not its Hamiltonian-specific decomposition or critical benchmarks.

### 13.6 Analytic follow-up

If $R=\sqrt{5}$ survives, investigate:

- the Hamiltonian limit of classical star-triangle transformations;
- high-field and low-field linked-cluster series on dual lattices;
- graph transformations relating excitation gaps or domain-wall weights;
- duality constraints on non-universal metric factors;
- rigorous arguments excluding an exact coupling relation.

If the ratio is rejected, the improved individual critical fields and the demonstrated finite-size methodology remain useful reference results.

---

## 14. References

1. QuantumBFS, "Is the ratio of transverse-field Ising critical points on the triangular and honeycomb lattices exactly $\sqrt{5}$?" [GitHub issue #148](https://github.com/QuantumBFS/quantum.harness/issues/148), 2026.
2. H. W. J. Blote and Y. Deng, "Cluster Monte Carlo simulation of the transverse Ising model," *Phys. Rev. E* **66**, 066110 (2002), [doi:10.1103/PhysRevE.66.066110](https://doi.org/10.1103/PhysRevE.66.066110).
3. A. W. Sandvik, "Stochastic series expansion method for quantum Ising models with arbitrary interactions," *Phys. Rev. E* **68**, 056701 (2003), [doi:10.1103/PhysRevE.68.056701](https://doi.org/10.1103/PhysRevE.68.056701).
4. H. Rieger and N. Kawashima, "Application of a continuous time cluster algorithm to the two-dimensional random quantum Ising ferromagnet," *Eur. Phys. J. B* **9**, 233-236 (1999), [doi:10.1007/s100510050761](https://doi.org/10.1007/s100510050761).
5. A. W. Sandvik, "Computational Studies of Quantum Spin Systems," *AIP Conf. Proc.* **1297**, 135-338 (2010), [arXiv:1101.3281](https://arxiv.org/abs/1101.3281).
6. V. Kott, M. Muhlhauser, J. A. Koziol, and K. P. Schmidt, "Quantum robustness of the toric code in a parallel field on the honeycomb and triangular lattice," *SciPost Phys.* **17**, 053 (2024), [doi:10.21468/SciPostPhys.17.2.053](https://doi.org/10.21468/SciPostPhys.17.2.053).
7. F. Kos, D. Poland, D. Simmons-Duffin, and A. Vichi, "Precision islands in the Ising and $O(N)$ models," *JHEP* **08**, 036 (2016), [doi:10.1007/JHEP08(2016)036](https://doi.org/10.1007/JHEP08(2016)036).
8. E. Merali, I. J. S. De Vlugt, and R. G. Melko, "Stochastic series expansion quantum Monte Carlo for Rydberg arrays," *SciPost Phys. Core* **7**, 016 (2024), [doi:10.21468/SciPostPhysCore.7.2.016](https://doi.org/10.21468/SciPostPhysCore.7.2.016).
9. Xeri Chen, [`sse_new`](https://gitee.com/xeri_chen/sse_new), reference C++ SSE implementation, inspected at commit `c40596f073c36931e083ac843daaa6718f46e1c5`.
10. Xeri Chen, [`cqu-bysj-phy`](https://gitee.com/xeri_chen/cqu-bysj-phy), undergraduate thesis, notes, bibliography, and benchmark tooling, inspected at commit `1db80e013c7a176984a25c7ce0d4d385e9a65796`.

---

## 15. Open decisions before implementation

- Which published TFIM SSE cluster construction will be the exact serial reference implementation?
- Is $Q_L$ or $\xi_L/L$ the primary registered estimator?
- Which modern values of $\nu$ and $\omega$ will be fixed in the primary fit?
- What lattice shapes and $L$ sequences minimize geometric corrections for each lattice?
- What criterion establishes ground-state convergence in $\beta/L$?
- What second implementation qualifies as independent under the challenge rules?
- What precisely is meant by "parallel annealing" for the later MPI phase: independent schedules, population annealing, or replica exchange?

These decisions should be resolved before production-scale computation, not inferred from whichever choice brings the final ratio closer to or farther from $\sqrt{5}$.
