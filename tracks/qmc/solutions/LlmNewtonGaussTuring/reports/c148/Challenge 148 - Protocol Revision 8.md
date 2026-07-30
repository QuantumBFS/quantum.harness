---
title: "Challenge 148: Proposed Protocol Revision 8 - L=4 Equilibration Repair"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
  - equilibration
status: proposed
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 7.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 7 Report.md
---

# Challenge 148: Proposed Protocol Revision 8

Proposed protocol identifier:
`c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7+rev8`.

This revision is not frozen until the rerun setup is explicitly ratified. It
does not alter the Hamiltonian, target fields, direct-SSE critical estimator,
ParaToric critical estimator, finite-size fit, blinding rule, or sealed
verdict. It repairs an equilibration gap discovered while reviewing the
honeycomb-target $L=4$ normalization comparison.

## 1. Triggering evidence

The stored direct-SSE chains in
`results/c148-paratoric-sse-honey-l4-v2/sse-raw.csv` use two hot and two cold
starts but Revision 6 did not impose a numerical start-agreement gate.
Re-analysis of the four chain means gives:

| Component | Hot/cold standardized difference | Diagnostic threshold |
|---|---:|---:|
| Exchange energy | 3.2523 | 5.0 |
| Transverse-field energy | 10.1535 | 5.0 |

The transverse-field component therefore retains a visible start dependence.
The previous cross-method tag remains a literal Revision 6 result, but it is
not sufficient evidence for final physical acceptance.

## 2. Proposed repair run

Use the same periodic target TFIM and dual mapping as Revision 6:

$$
H=-\sum_{\langle ij\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
$$

with honeycomb target lattice, triangular ParaToric gauge lattice, $L=4$,
$h=2.1325$, $\beta h=L$, $\mu=64$, and four independently seeded chains.

ParaToric retains the qualified cadence per chain:

- 200,000 thermalization updates;
- 50,000 stored samples;
- 100 updates between samples.

Direct SSE uses two hot and two cold chains with:

- 100,000 thermalization sweeps;
- 4,000 stored bins;
- 25 sweeps per bin.

The run ID is `c148-paratoric-sse-honey-l4-v3`. No result from this rerun may
change a critical-scan axis or enter the sealed ratio directly.

## 3. Proposed gates

For both direct-SSE Hamiltonian components:

1. the hot/cold chain-mean standardized difference is at most 5.0;
2. all raw values are finite and the average sign remains exactly one;
3. base-block, doubled-block, and independent-chain errors are reported, and
   their maximum is the comparison uncertainty;
4. ParaToric and direct SSE agree within five combined uncertainties.

The component-sum versus expansion-order identity must pass within five
standard errors. ParaToric must emit no warnings and every sampled star must
remain $+1$.

Failure leaves the honeycomb-target finite-volume qualification unresolved.
No discrepant estimates are averaged.

## 4. Ratification state

**Proposed, not yet frozen.** No Revision 8 repair data have been generated.
The exact setup above must be confirmed before compute.
