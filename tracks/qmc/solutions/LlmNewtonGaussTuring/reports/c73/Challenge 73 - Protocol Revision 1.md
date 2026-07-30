---
title: "Challenge 73: Protocol Revision 1 - FHS and Finite-Size Oracle"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-73
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 73 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 73 - 2D TFIM Berry Phase.md
---

# Challenge 73: Protocol Revision 1

This append-only revision supersedes the FHS normalization and convergence
clauses of the Stage 0 preregistration. The Hamiltonian, primary observable,
and requirement for an independent QAQMC or other response route are unchanged.

## 1. FHS convention

For the oriented Wilson product

$$
W=U_\theta(\lambda)U_\Omega(\lambda+\delta_\theta)
U_\theta^{-1}(\lambda+\delta_\Omega)U_\Omega^{-1}(\lambda),
$$

and $A_\mu=i\langle\psi|\partial_\mu\psi\rangle$, the physical plaquette flux is

$$
\Phi_{\theta\Omega}=-\arg W,
$$

and the local curvature estimate is

$$
F_{\theta\Omega}=\frac{\Phi_{\theta\Omega}}
{\Delta\theta\,\Delta\Omega}.
$$

Wilson phase, physical flux, and curvature are different reported quantities.
A plaquette with a non-finite or unconverged corner state, zero area, or
near-zero link overlap is invalid.

## 2. Finite-size Jordan-Wigner oracle

For an even periodic chain of $N$ spins in the antiperiodic fermion sector,

$$
k_m=\frac{(2m+1)\pi}{N},\qquad m=0,\ldots,N-1,
$$

and the curvature density in the local convention is

$$
\frac{F_{\theta\Omega}^{(N)}}{N}
=-\frac{J^2}{2N}\sum_{m=0}^{N-1}
\frac{\sin^2 k_m}
{\left(J^2+\Omega^2-2J\Omega\cos k_m\right)^{3/2}}.
$$

This same-$N$ oracle, not the thermodynamic integral, is the direct reference
for finite-chain FHS plaquettes.

## 3. Revised gates

1. Compare centered plaquettes to the same-$N$ oracle while halving both grid
   steps. The error must decrease under refinement and meet a declared finite
   discretization budget; machine-precision agreement at nonzero step is not
   required.
2. Away from $|\Omega|=J$, the finite-size density converges to a finite
   thermodynamic integral.
3. At $|\Omega|=J$, the thermodynamic curvature density diverges
   logarithmically. The old blanket requirement that the density approach a
   finite constant at every parameter point is withdrawn.
4. A fixed random seed makes the eigensolver deterministic but does not define
   a smooth wavefunction gauge. Gauge invariance is established by the Wilson
   loop, not by the seed.
