---
title: "Challenge 73: Stage 0 Preregistration — Parameterisation and Protocol Freeze"
date: 2026-07-28
tags:
  - quantum-harness
  - challenge-73
  - preregistration
  - berry-phase
  - berry-curvature
  - protocol-freeze
status: frozen
source:
  - https://github.com/QuantumBFS/quantum.harness/issues/73
related:
  - Harnessing Quantum 2026/Challenge 73 - 2D TFIM Berry Phase.md
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Report.md
  - Harnessing Quantum 2026/Challenge 73 - Protocol Revision 1.md
---

# Challenge 73: Stage 0 Preregistration

This document freezes the parameterisation conventions, discretisation protocol, and cross-validation rules for the Berry curvature computation of the 2D TFIM. No production data may be generated before the protocol is frozen.

> **Protocol revision:** The FHS sign/area convention, finite-size
> Jordan-Wigner oracle, and convergence gates are superseded by
> [[Challenge 73 - Protocol Revision 1]]. Original clauses below remain as the
> preregistration record.

## 1. Literature audit snapshot

The audit was conducted on 2026-07-28 and covered:

- The official issue #73 and its 11 named references;
- Web searches for "Berry curvature transverse field Ising PEPS QMC 2023-2026";
- Crossref citations to Kolodrubetz (2014) [Phys. Rev. B 89, 045107];
- The Kolodrubetz et al. (2017) review [Physics Reports 697, 1-87];
- Local knowledge bases (`.knowledge/` and `notes/文献库/`).

**Finding**: No post-2017 work has superseded the Kolodrubetz (2014) 1D/2D TFIM Berry curvature QMC results. The Kolodrubetz (2014) paper remains the state-of-the-art numerical determination of $F_{\theta\Omega}$ for the 2D TFIM under global spin rotation. The PEPS community has not published Berry curvature results for this specific parameterisation. This confirms the challenge as genuinely open.

The 2017 review [5] provides the theoretical framework (quantum geometric tensor, adiabatic gauge potential, non-adiabatic response) but reports no new numerical values.

## 2. Frozen parameterisation

### 2.1 Hamiltonian

The square-lattice TFIM under global x-axis rotation:

$$
H(\theta,\Omega) = R_x(\theta) H_0(\Omega) R_x^\dagger(\theta), \qquad
H_0(\Omega) = -J\sum_{\langle i,j\rangle} Z_i Z_j - \Omega\sum_i X_i,
$$

with $R_x(\theta) = \exp(-i\theta/2 \sum_i X_i)$, $J=1$, $\Omega\ge 0$, $\theta\in[0,2\pi)$.

Under $R_x$: $Z\to \cos\theta\,Z - \sin\theta\,Y$, $Y\to\sin\theta\,Z+\cos\theta\,Y$, $X\to X$.

### 2.2 Primary method

Fukui-Hatsugai-Suzuki (2005) gauge-invariant discretisation of the Berry curvature:

$$
F_{\theta\Omega}(\theta_i,\Omega_j) = \arg\big[U_\theta(\lambda)\,U_\Omega(\lambda+\hat\delta_\theta)\,
U_\theta^{-1}(\lambda+\hat\delta_\Omega)\,U_\Omega^{-1}(\lambda)\big],
$$

where $U_\mu(\lambda) = \langle\psi_0(\lambda)|\psi_0(\lambda+\hat\delta_\mu)\rangle / |\cdots|$
are U(1) link variables on the parameter-space plaquette.

### 2.3 Discretisation grid

The frozen production grid conventions are:

| Parameter | Range | Step (pilot) | Step (production) |
|---|---|---|---|
| $\theta$ | $[0, 2\pi)$ | $\Delta\theta = 0.05$ | TBD from pilot convergence |
| $\Omega$ | $[0.5, 4.0]$ | $\Delta\Omega = 0.05$ | TBD from pilot convergence |

At the critical region $\Omega\approx\Omega_c\approx 3.044$, the grid should be refined by a factor of 2-4.

### 2.4 Finite-size convention

For exact diagonalisation on the square lattice:
- $N = L^2$ sites, periodic boundary conditions.
- Pilot sizes: $L = 2, 3$ ($N=4,9$).
- The Berry curvature density $\bar F_{\theta\Omega} = F_{\theta\Omega}/N$ is the primary thermodynamic-limit quantity.

## 3. Cross-validation protocol

Three routes must agree within combined uncertainties before any result is accepted:

| Route | Method | Max size | Role |
|---|---|---|---|
| ED + FHS | Exact diagonalisation + overlap | $N\le 9$ ($3\times 3$) | Exact oracle; finite-size baseline |
| SSE + Kolodrubetz | QMC non-adiabatic response | $N\le 256$ ($16\times 16$) | Primary finite-size scaling route |
| PEPS + FHS (future) | iPEPS overlap discretisation | Thermodynamic limit | Extrapolation target |

### 3.1 ED cross-check

The ED result at $\theta=0$ for the standard TFIM must match the known ground-state energy $E_0$ from the Jacobi solver in the shared ED module (Challenge 148, `src/ed.{hpp,cpp}`).

### 3.2 Gauge invariance

Every computed $F_{\theta\Omega}$ must be verified gauge-invariant: applying independent random U(1) phases $e^{i\alpha_{ij}}$ to each of the four ground states must leave $F_{\theta\Omega}$ unchanged to within $10^{-8}$.

### 3.3 Grid convergence

Doubling the grid resolution must change $\bar F_{\theta\Omega}$ by less than 10 % at all grid points.

### 3.4 Finite-size convergence

The Berry curvature density $\bar F_{\theta\Omega}(L)$ must approach a constant as $L$ increases (no divergence, no sign oscillation in the thermodynamic limit).

## 4. Energy benchmark cross-check

At $\theta=0$, the Hamiltonian reduces to the standard TFIM:

$$
H(0,\Omega) = -J\sum_{\langle i,j\rangle} Z_i Z_j - \Omega\sum_i X_i.
$$

The ground-state energy $E_0(N,\Omega)$ must match the ED oracle from Challenge 148 for every $N,\Omega$ used.

## 5. References checked

1. M. Kolodrubetz, "Measuring Berry curvature with quantum Monte Carlo," Phys. Rev. B 89, 045107 (2014).
2. M. Kolodrubetz, D. Sels, P. Mehta, A. Polkovnikov, "Geometry and non-adiabatic response," Phys. Rep. 697, 1 (2017).
3. T. Fukui, Y. Hatsugai, H. Suzuki, "Chern Numbers in Discretized Brillouin Zone," JPSJ 74, 1674 (2005).
4. M. V. Berry, "Quantal phase factors accompanying adiabatic changes," Proc. R. Soc. A 392, 45 (1984).
5. A. C. M. Carollo, J. K. Pachos, "Geometric Phases and Criticality in Spin-Chain Systems," PRL 95, 157203 (2005).
6. J. Vovrosh et al., "Simulating dynamics of the 2D TFIM," PRR 8, 023311 (2026).

## 6. Frozen verdict

This preregistration is frozen at the notes commit containing it. The parameterisation, grid convention, and cross-validation rules may not be changed without creating a new preregistration identifier. Pilot evidence may select numerical budgets and grid refinements, but it may not change the target Hamiltonian or primary discretisation formula.
