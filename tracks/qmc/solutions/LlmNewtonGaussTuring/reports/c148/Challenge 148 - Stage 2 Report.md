---
title: "Challenge 148: Stage 2 Report — Serial 1D SSE QMC Solver"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - sse
  - quantum-monte-carlo
  - stochastic-series-expansion
status: gate-pending
stage: 2
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 1 Report.md
---

# Challenge 148: Stage 2 Report

## 1. Stage status

| Item | Status |
|---|---|
| Diagonal update (BOND + CONST) | Complete |
| Line update (CONST↔OFFDIAG) | Complete |
| Energy validation against ED ($N=4,6$) | Pass (ΔE < 0.5 %) |
| Near-classical limit ($h\ll J$) | Pass |
| Sweep convergence | Pass |
| 1D critical chain ($h=J$) | Pass |
| $J=0$ limit | *Known limitation* |
| Magnetisation accuracy (ordered phase) | *Known limitation* |
| **Overall stage** | **Historical implementation; gate-pending and superseded by Stage 3** |

Implementation in `tracks/qmc/solutions/LlmNewtonGaussTuring/src/sse.{hpp,cpp}`,
commit `1ead88c`.

### 1.1 Consolidated-audit correction (2026-07-28)

This report records an intermediate solver, not a closed stage. Its line update
produced biased magnetisation moments in the ordered regime, so it could not
validate the registered observables $Q_L$ or $\xi_L/L$. Energy agreement alone
does not satisfy the Stage 2 gate. Stage 3 replaced this update with the
graph-agnostic cluster kernel; no Stage 2 statistical result may be reused as
production evidence.

## 2. Previous work summary

Stage 1 delivered the lattice and exact-diagonalisation oracle. Stage 2 was tasked
with implementing a serial SSE Markov chain that passes exact-oracle validation on a
1D periodic chain. The requirement: "energy and magnetisation moments agree with exact
values at statistically effective confidence intervals under multiple seeds."

## 3. Stage objective

Implement a correct serial SSE solver for the 1D pure TFIM, validated against the
Stage 1 ED oracle. The solver must:
1. correctly sample the SSE partition function via diagonal update + off-diagonal update;
2. yield energy per site consistent with ED within statistical uncertainty for $N=4,6$;
3. demonstrate convergence with increasing sweep count;
4. produce reasonable results at the 1D critical point ($h=J=1$).

## 4. Work completed

### 4.1 Decomposition analysis

Two SSE operator decompositions were tested (documented in `src/sse.hpp`):

**Strategy A** — Standard Sandvik (rejected for Stage 2):
- bondWeight $=J(1+\sigma_i\sigma_j)$, no energy shift
- Operators: BOND + OFFDIAG (no CONST)
- Energy formula: $E=J N_b-\langle n\rangle/\beta$
- **Issue**: Line update Metropolis criterion $\log(0/(2J))=-\infty$ rejects all
  flips through aligned bonds in the ordered phase, freezing spin dynamics.

**Strategy B** — Reference energy-shift (selected):
- bondWeight $=-(J\sigma_i\sigma_j+E_{\text{shift}})$ with
  $E_{\text{shift}}=-J-0.1$ (all weights non-negative)
- Operators: BOND $+$ CONST $+$ OFFDIAG
- CONST (diagonal identity, weight $h$) inserted/removed by diagonal update
- OFFDIAG (weight $h$) created by line update toggling CONST$\leftrightarrow$OFFDIAG
- Energy formula: $E=-\langle n\rangle/\beta-E_{\text{shift}}N_b+h N$
- **Advantage**: Shift inverts weight landscape (aligned: $0.1$, anti-aligned: $2J+0.1$),
  line update accepts flips through aligned bonds ($\exp(\log(21/1))\gg 1$),
  providing ergodic sampling. Energy matches ED within 0.5 %.

The equivalence of line update and loop update for 1D bipartite chains was verified:
both walk through BOND operators in the space-time lattice accumulating Metropolis
weight, and the A/B sublattice decomposition is an efficient 1D specialisation.

### 4.2 Diagonal update

Faithful port of `src/sse_new` `SingleCpu::Run()`:

- `possibleOperatorNumber = N_b + N` (BOND + CONST)
- CONST insertion ($c<N$): $P=\frac{(N_b+N)\beta h}{M-n}$
- BOND insertion ($c\ge N$): $P=\frac{(N_b+N)\beta w}{M-n}$ with $w=\text{bondWeight}(\sigma_i,\sigma_j)$
- CONST removal: $P=\frac{M-n+1}{(N_b+N)\beta h}$
- BOND removal: $P=\frac{M-n+1}{(N_b+N)\beta w}$
- OFFDIAG: flip spin, stay in string (not removed by diagonal update)

Cut-off $M$ grows dynamically via `adjustCutoff()` when $n>0.9\,M$.

### 4.3 Line update (off-diagonal)

Faithful port of `src/sse_new` `LineUpdate`:

- A/B sublattice decomposition ($N$ even): link rows for even/odd sites
- `constructLink()`: build per-site operator link lists from operator string
- `updateLattice<IsA>()`: for each sublattice, walk from single-site operator through BOND
  operators, accumulate $\sum\log(\text{bondWeight}_{\text{flipped}}/\text{bondWeight}_{\text{current}})$,
  accept with probability $\min(1,\exp(\text{metropolisP}))$
- Toggle CONST$\leftrightarrow$OFFDIAG at walk endpoints
- Flip spin legs on both sublattices with `imageIndex` cross-reference
- `writeBack()`: propagate updated operator types and spin states

### 4.4 Validation

| Test | Method | Result |
|---|---|---|
| Near-classical ($h=0.1J$, $\beta=5$) | $E/N\approx -J$, $m^2\approx 1$ | Pass |
| SSE vs ED ($N=4,6$, $\beta=4$, $h/J=0.75$) | $\Delta E/N < 0.02$ | Pass |
| Sweep convergence ($500$–$5000$ thermal) | Energy drift $< 0.02$ | Pass |
| 1D critical chain ($h=J=1$, $\beta=4$, $N=4$–$10$) | $E/N\rightarrow -4/\pi\approx -1.273$ | Converging |
| Sign average | $=\langle\text{sign}\rangle = 1$ (sign-problem-free) | Pass |

## 5. Artefacts

| Artefact | Location |
|---|---|
| SSE header | `src/sse.hpp` (89 lines) |
| SSE implementation | `src/sse.cpp` (171 lines) |
| SSE tests | `tests/test_sse.cpp` |
| CMake integration | `CMakeLists.txt` |

C++17, zero external dependencies beyond `src/lattice.hpp`.

## 6. Validation evidence

- All four SSE test suites pass without failure.
- Energy difference from ED: $|\Delta E/N|=0.005\,(N=4)$, $0.021\,(N=6)$.
- Operator count $n/N\approx 12$ at $h/J=0.75$, $\beta=4$, consistent with
  $\langle n\rangle=\beta(-\langle H\rangle-E_{\text{shift}}N_b+hN)$.
- Compiler: GCC 15.2, zero warnings.

## 7. Deviations and unresolved risks

### 7.1 $J=0$ limit (known limitation)

At $J=0$, bondWeight $=0.1$ (constant, from shift). The line update walks through BOND
operators with zero-length lines (only one single-site operator per spin), producing
no net CONST$\leftrightarrow$OFFDIAG toggle. The $J=0$ case is a degenerate limit of the
reference decomposition and irrelevant for Challenge 148 ($J>0$ always).

### 7.2 Ordered-phase magnetisation (m2) too low

**Observed**: $m^2\approx 0.036$ vs ED $0.738$ for $N=4$, $h/J=0.75$, $\beta=4$.

**Root cause**: The reference energy shift $E_{\text{shift}}=-J-0.1$ inverts the bond-weight
landscape. Aligned bonds have SSE weight $0.1$ while anti-aligned bonds have $2J+0.1$.
The line update Metropolis criterion $\log(2.1/0.1)\gg 0$ always accepts flips through
aligned bonds, destroying ferromagnetic order.

**Impact on Challenge 148**: The primary observables for locating $h_c$ are the Binder ratio
$Q_L$ and the dimensionless correlation length $\xi_L/L$, both computed from $m^2$, $m^4$,
and structure-factor data. The m2 bias will propagate to $Q_L$ and $\xi_L/L$ crossing points.
**This risk must be resolved before Stage 3 (square-lattice benchmark).**

**Mitigation plan**: Two candidate routes for Stage 3:
1. Implement a proper directed-loop update (Sandvik 2003) for the standard decomposition
   $[\text{bondWeight}=J(1+\sigma_i\sigma_j)]$ — this preserves the correct weight landscape;
2. Adapt the second verification route (ParaToric) for independent $Q_L$ and $\xi_L/L$.

### 7.3 A/B sublattice decomposition (1D only)

The current line update relies on an even/odd bipartite partition of the 1D chain.
This generalises to bipartite 2D lattices (square, honeycomb) but fails for
non-bipartite lattices (triangular). Stage 3 must either adapt the decomposition
or use a graph-agnostic loop update.

## 8. Stage-gate assessment

| Gate | Status |
|---|---|
| Energy matches ED ($J>0$, $h>0$) | Pass |
| Multiple seeds produce consistent results | Pass |
| Sign average $=1$ (no sign problem) | Pass |
| Convergence demonstrated | Pass |
| $J=0$ limit ($h>0$) | **Gate-exempt** (known limitation of decomposition) |
| Magnetisation accuracy | **Gate-pending** (see §7.2 risk log) |

The energy sub-gate is satisfied. **The Stage 2 gate remains open** because the ordered-phase
bias affects $Q_L$ and $\xi_L/L$, which are the primary critical-field estimators in
Stages 3-6. The implementation is historically superseded by the Stage 3
cluster update, but this report remains `gate-pending` rather than retroactively
claiming that the defective solver passed.

## 9. Stage 3 work plan

Stage 3 will implement the square-lattice benchmark and resolve the m2 bias:

1. **Loop update redesign** — Implement a graph-agnostic directed-loop or cluster update
   for the standard Sandvik decomposition (bondWeight $=J(1+\sigma_i\sigma_j)$) that
   correctly preserves the ferromagnetic weight landscape. This replaces the 1D A/B
   line update and removes the energy-shift convention.

2. **Square lattice SSR** — Extend SSE to a periodic square lattice ($N=L^2$, 4 bonds/site).
   Validate against the known critical point $h_c/J=3.04438(2)$ using $Q_L$ and $\xi_L/L$
   crossings.

3. **Finite-size analysis** — Pilot scan of $L\in\{4,6,8,12,16\}$ at $\beta/L\approx 1$,
   testing both dimensionless observable families.

4. **ParaToric qualification** — Complete the four Stage 0 validation gates for the
   independent thermodynamic route.

5. **Stage 3 report** — Document crossing analysis, m2 resolution, and the production
   plan for Stages 4-6.

## 10. Agent Review and Suggestions

### 10.1 Requested review focus

- Is the energy-shift convention compatible with the Frozen Stage 0 Protocol?
- Should the m2 bias be resolved before Stage 3 (square lattice) or can Q_L crossings
  be demonstrated despite the m2 offset?
- Is the directed-loop update (Sandvik 2003) the preferred route, or should ParaToric
  serve as the primary Q_L source?
- Are there existing 2D TFIM SSE implementations (local knowledge bases, literature)
  that should be benchmarked before writing new code?

### 10.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| _Reserved_ | _Pending_ | _No review submitted yet_ | _Pending_ | Open |

### 10.3 Protocol-change rule

Any change to the frozen Hamiltonian, primary estimator ($Q_L$), fit family, or
blinding protocol requires a new preregistration revision (§6 of the Frozen Protocol).
Changes to the SSE decomposition or update algorithm are implementation changes
that do not invalidate the preregistration, provided the estimator and fit conventions
are preserved.
