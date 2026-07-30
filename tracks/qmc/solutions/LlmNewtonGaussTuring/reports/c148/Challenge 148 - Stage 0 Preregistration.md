---
title: "Challenge 148: Stage 0 Literature Audit and Preregistration"
date: 2026-07-27
tags:
  - quantum-harness
  - challenge-148
  - preregistration
  - literature-audit
  - transverse-field-ising
status: frozen
source:
  - https://github.com/QuantumBFS/quantum.harness/issues/148
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 1.md
---

# Challenge 148: Stage 0 Literature Audit and Preregistration

This document freezes the scientific conventions and analysis gates before production data exist. Pilot evidence may select numerical budgets and valid lattice sizes, but it may not change the target Hamiltonian, primary estimator, fit family, uncertainty rules, or ratio verdict without creating a new preregistration identifier.

> **Protocol revision:** The continuous-time aspect-ratio convention is
> clarified by [[Challenge 148 - Protocol Revision 1]]: paper-matched runs use
> $\beta h=L$, not $\beta=L$. Original clauses below remain as the
> preregistration record.

## 1. Audit snapshot

The audit snapshot was taken on 2026-07-27. It covered:

- the official issue and its four named references;
- the 291-work OpenAlex citation set for Blote-Deng, filtered manually for TFIM, triangular/honeycomb lattices, toric-code mappings, criticality, QMC, and series work;
- Semantic Scholar citations and title/keyword searches independent of OpenAlex;
- Crossref metadata and the local `.knowledge/` and `notes/文献库/` corpora;
- primary-text checks of Blote-Deng (2002), Kott et al. (2024), Linsel et al. (2025/2026), and the ParaToric 1.0 codebase paper (2026).

This is a reproducible search snapshot, not a claim that bibliographic databases are complete. Citation snowballing remains open until the production protocol is frozen, but new sources must be logged even when they do not improve the baseline.

## 2. Normalization ledger

The target convention is

$$
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z-h\sum_i\sigma_i^x,
\qquad g=h/J,
\qquad J>0.
$$

Blote-Deng use the same Pauli convention with $J=1$ and call the transverse field $t$, so $g=t$ directly.

Kott et al. obtain, after a toric-code duality and axis relabeling,

$$
H_{\mathrm{dual}}=-\frac12\sum_i\mu_i^z-h_{\mathrm{TC}}\sum_{\langle i,j\rangle}\mu_i^x\mu_j^x.
$$

Thus $J=h_{\mathrm{TC}}$, $h=1/2$, and

$$
g=\frac{1}{2h_{\mathrm{TC}}}.
$$

Linsel et al. use unit coefficients for the toric-code stabilizers rather than $1/2$. In their single-field limits the corresponding conversion is $g=1/h_{\mathrm{TC}}$. These two toric-code normalizations must never be mixed.

## 3. Source table

| Source | Route and setup | Reported result | Target-convention result | Baseline status |
|---|---|---|---|---|
| Blote and Deng, PRE 66, 066110 (2002) | Continuous-time Wolff cluster; PBC; physical imaginary-time length $=L$; $Q_L=\langle m^2\rangle^2/\langle m^4\rangle$; fixed $y_t=1.587(2)$ and $y_i=-0.815(4)$; triangular $L=6\ldots20$, honeycomb $L=10\ldots20$ | $t_c^\triangle=4.76811(9)$; $t_c^\hexagon=2.13250(4)$ | Same | Current best pair and challenge baseline |
| Kott et al., SciPost Phys. 17, 053 (2024) | Exact toric-code mapping plus tenth-order linked-cluster/DLogPade gap series; no new QMC determination of the ferromagnetic pair | $h_{\mathrm{TC},c}=0.10491(13)$ (triangular TFIM mapping); $0.2352(9)$ (honeycomb mapping) | $g_c^\triangle=4.76599(591)$; $g_c^\hexagon=2.12585(813)$ | Independent consistency check, much less precise. The paper's $0.104863(2)$ and $0.234467(5)$ values are explicitly imported from Blote-Deng |
| Linsel, Pollet, and Grusdt, arXiv:2504.03512v3 / PRX Quantum (2025/2026) | Independent continuous-time QMC of the full toric code; PBC; $T=1/L$; up to $L=32$ unit cells and $3\times10^4$ snapshots; Binder crossings of percolation/SIT observables | $h_{\mathrm{TC},c}=0.210(2)$ and $0.475(5)$ in the two dual limits | $g_c^\triangle=4.762(45)$; $g_c^\hexagon=2.105(22)$ | Independent but far less precise; useful implementation evidence, not a replacement baseline |
| Linsel and Pollet, SciPost Phys. Codebases 75 (2026), ParaToric v1.0.3 | MIT-licensed C++23 continuous-time QMC; square/triangular/honeycomb/cubic; PBC/open; HDF5, full time series, integrated autocorrelation, stationary bootstrap | Code paper benchmarks a square-lattice toric-code transition; it does not publish sharper triangular/honeycomb TFIM critical fields | N/A | Preferred Stage 7 candidate, subject to dual-sector and finite-$\beta$ validation |

The best published direct pair therefore remains

$$
g_c^\triangle=4.76811(9),\qquad g_c^\hexagon=2.13250(4).
$$

For independent runs this gives

$$
R=2.23592497069,\qquad
\sigma_R=5.9499\times10^{-5},\qquad
R-\sqrt5=-1.43007\times10^{-4}.
$$

## 4. Frozen scientific protocol

### 4.1 Geometry and Hamiltonian

- Pauli normalization, $J=1$, $h\ge0$, no longitudinal field.
- Explicit undirected graph with every bond stored once.
- PBC for all scaling data.
- Triangular: $N=L^2$, $N_b=3N$, coordination six.
- Honeycomb: two-site basis, $N=2L^2$, $N_b=3N/2$, coordination three.
- Primitive vectors, basis coordinates, reciprocal vectors, torus wrapping, and smallest momenta are immutable run metadata.

### 4.2 Primary and secondary estimators

The primary registered estimator is

$$
Q_L=\frac{\langle m^2\rangle^2}{\langle m^4\rangle}.
$$

This choice exactly matches the 2002 baseline and minimizes reproduction ambiguity. The mandatory secondary estimator is $\xi_L/L$ from the second-moment structure factor using lattice-correct smallest reciprocal vectors. The two estimates of $h_c$ must agree within their combined total uncertainty; they are not averaged when they disagree.

Order parameter and susceptibility scaling are supporting diagnostics for continuity and universality. Nonlinear estimators are recomputed inside a chain/block bootstrap, never from independently propagated terminal averages.

### 4.3 Scaling models

The primary joint fit for each lattice is

$$
Q_L(h)=Q^*+a_1\delta hL^{1/\nu}+a_2\delta h^2L^{2/\nu}
+b_1L^{-\omega}+c_1\delta hL^{1/\nu-\omega},
\qquad \delta h=h-h_c.
$$

The primary exponents are fixed at $\nu=0.629971$ and $\omega=0.83$. They are not fitted in the primary analysis. Registered robustness variants are:

- omit $c_1$;
- add one justified subleading correction only when the pilot residuals show a reproducible size trend;
- vary $L_{\min}$ over the pilot-approved matrix;
- use the predeclared narrow and broad field windows;
- repeat with $\omega\in\{0.80,0.83,0.86\}$;
- release $\nu$ only as a universality diagnostic;
- repeat the full analysis for $\xi_L/L$;
- fit crossing drift $h_\times(L,sL)=h_c+AL^{-(1/\nu+\omega)}$ as a transparent secondary route.

Fit variants report estimates, bootstrap intervals, residuals, $\chi^2/\mathrm{dof}$, failed resamples, and leave-one-size-out shifts. Model/window sensitivity contributes a conservative envelope, not an automatically Gaussian error.

### 4.4 Ground-state and sampling gates

- The production inverse temperature is $\beta=c_\beta L$. The pilot selects the smallest $c_\beta$ whose shift in both primary estimators and the fitted $h_c$ is below one quarter of the allocated finite-$\beta$ error when $c_\beta$ is doubled.
- Every production cell has multiple independently seeded chains.
- Hot/cold starts, discarded-prefix stability, integrated autocorrelation time, bin growth, and chain-spread tests are hard gates.
- A bootstrap unit is an independent chain or a block longer than the measured integrated autocorrelation time.
- The QMC sign must remain exactly positive in the implemented representation.

### 4.5 Blinding and verdict

Triangular and honeycomb production scans, fits, and error budgets are finalized separately. The ratio script remains disabled until accepted run IDs, file hashes, fit windows, $L_{\min}$ matrix, and uncertainty envelopes are frozen. Reopening an accepted lattice fit after viewing $R$ creates a new preregistration ID and invalidates the old verdict.

The frozen gate is:

- decisive rejection if $|R-\sqrt5|/\sigma_R\ge10$ and every systematic gate passes;
- survival if $|R-\sqrt5|\le2\sigma_R$ and every systematic gate passes;
- inconclusive otherwise.

Survival is not a proof of exact equality.

## 5. Independent-route decision

The preferred independent thermodynamic route is ParaToric v1.0.3 at the exactly dual single-field limits, with `PARATORIC_ENABLE_FAST_MATH=OFF`. It is independent in algorithm, implementation, observables, and data path from the new SSE solver.

A local fixed-tag smoke on 2026-07-27 confirmed that GCC 15.2 and CMake 4.2 satisfy the compiler requirements. Configuration reached the package dependency check and stopped because the Boost development configuration is not installed. No system package was installed during Stage 0; this is an environment prerequisite, not an algorithmic test result.

Before it can qualify for Stage 7 it must pass four extra gates:

1. derive and test the toric-code-to-TFIM normalization for the precise ParaToric Hamiltonian;
2. demonstrate suppression of unwanted charge/flux sectors under the chosen $\beta/L$ schedule;
3. reproduce the direct TFIM ED oracle on dual small tori after normalization;
4. reproduce direct simulations at selected finite sizes before any thermodynamic comparison.

ParaToric's documented Binder ratio is the inverse convention of the registered $Q_L$ for a generic observable. This is acceptable for locating a crossing but must be labeled explicitly and must not be numerically compared to $Q_L^*$.

## 6. Stage gates now open

Stage 0 is complete in the notes commit containing this preregistration: conventions, estimators, fit family, verdict, and independent-route candidate are frozen. Citation snowballing continues as a logged maintenance action and does not reopen the protocol by itself.

Stage 1 may begin in a real development worktree once the training team name is known. Until then, no placeholder `group-*` branch or challenge code is created in the benchmark clone. The first implementation deliverable is the graph and exact-oracle layer, before any SSE production kernel.

## 7. References checked

1. H. W. J. Blote and Y. Deng, *Phys. Rev. E* **66**, 066110 (2002), doi:10.1103/PhysRevE.66.066110.
2. V. Kott, M. Muhlhauser, J. A. Koziol, and K. P. Schmidt, *SciPost Phys.* **17**, 053 (2024), doi:10.21468/SciPostPhys.17.2.053.
3. S. M. Linsel, L. Pollet, and F. Grusdt, *PRX Quantum* (2025/2026), arXiv:2504.03512v3, doi:10.1103/gtth-cclr.
4. S. M. Linsel and L. Pollet, *SciPost Phys. Codebases* **75** (2026), doi:10.21468/SciPostPhysCodeb.75; ParaToric v1.0.3 commit `e7bc78446ba083aeeae1ada9c883fa03bf205890`.

Local MinerU full texts and source hashes are indexed in [`notes/文献库/QMC/TFIM/Challenge-148/`](../文献库/QMC/TFIM/Challenge-148/MINERU_INDEX.md). Source PDFs, extracted images, API responses, and job manifests remain under ignored `library/` paths.
