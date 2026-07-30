---
title: "Challenge 148: Protocol Revision 1 - Imaginary-Time Aspect Ratio"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 1

This append-only revision clarifies the Blote-Deng continuous-time aspect
ratio. It does not change the Hamiltonian, estimators, fit family, blinding
rule, or ratio verdict gate.

## 1. Primary-source derivation

The MinerU conversion of Blote and Deng (2002) states:

- line 103: $M=\beta t/\epsilon$;
- line 196: $M_p=\epsilon M$;
- line 284: the physical length of the continuous direction is chosen equal
  to $L$.

Therefore

$$
M_p=\epsilon M=\beta t=L.
$$

In the local TFIM notation the transverse field is $h=t$, so the paper-matched
condition is

$$
\beta h=L,
\qquad
\beta=\frac{c_\tau L}{h}.
$$

The source is
`文献库/QMC/TFIM/Challenge-148/blote-deng-2002-cluster-monte-carlo-tfim.mineru.md`,
whose source PDF hash and MinerU import are recorded in the adjacent index.

## 2. Revised checks

1. The current reproduction uses $c_\tau=1$, hence $\beta=L/h$.
2. The doubled imaginary-time check uses $c_\tau=2$, hence $\beta=2L/h$.
3. Historical scans parameterized as $\beta=c_\beta L$ did not keep the
   physical aspect ratio fixed across field values. Their aspect-ratio and
   ground-state-convergence conclusions are withdrawn; their kernel tests
   remain separate evidence.
4. Every raw row must record $h$, $\beta$, and enough metadata to verify
   $\beta h/L=c_\tau$.
