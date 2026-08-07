# VQETape VQE time-to-solution findings

All candidates ran in fresh processes. Time to target includes compilation, first execution, every synchronized value-gradient evaluation, and optimizer overhead.

## Audited workload

- Target: open-chain TFIM, 4 qubits, depth-2 RZZ-RX ansatz, energy error at most 0.1.
- Initialization seed: 3; Adam/natural-gradient learning rate: 0.08; natural-gradient damping: 0.01.
- Recycled source: 3 qubits, depth 1, independently converged with L-BFGS-B.

## Results

| ID | program | optimizer | start | converged | calls | compile (s) | target (s) | final error |
|---|---|---|---|---:|---:|---:|---:|---:|
| optimizer-adam-zeros | spatial-transfer-greedy-b2-default-u1 | adam | zeros | no | 81 | 2.484 | — | 0.758771 |
| optimizer-adam-random | spatial-transfer-greedy-b2-default-u1 | adam | random | yes | 32 | 3.267 | 3.356 | 0.098981 |
| optimizer-adam-recycled | spatial-transfer-greedy-b2-default-u1 | adam | recycled | yes | 20 | 2.292 | 2.315 | 0.087474 |
| optimizer-lbfgs-zeros | spatial-transfer-greedy-b2-default-u1 | lbfgs | zeros | no | 1 | 3.134 | — | 0.758771 |
| optimizer-lbfgs-random | spatial-transfer-greedy-b2-default-u1 | lbfgs | random | yes | 23 | 2.441 | 2.831 | 0.098451 |
| optimizer-lbfgs-recycled | spatial-transfer-greedy-b2-default-u1 | lbfgs | recycled | yes | 5 | 2.394 | 2.750 | 0.098660 |
| optimizer-natural-gradient-zeros | spatial-transfer-greedy-b2-default-u1 | natural-gradient | zeros | no | 81 | 2.565 | — | 0.758771 |
| optimizer-natural-gradient-random | spatial-transfer-greedy-b2-default-u1 | natural-gradient | random | yes | 4 | 2.440 | 6.958 | 0.088884 |
| optimizer-natural-gradient-recycled | spatial-transfer-greedy-b2-default-u1 | natural-gradient | recycled | yes | 3 | 2.982 | 7.875 | 0.053441 |
| program-statevector | scan-default-u1 | lbfgs | random | yes | 23 | 1.204 | 1.739 | 0.098454 |
| program-z2-native | spatial-transfer-greedy-b1-default-u1-z2-native | lbfgs | random | yes | 23 | 2.501 | 2.962 | 0.098453 |

## What the measurement supports

- Fastest converged run: `program-statevector`. This is workload- and machine-specific.
- Zero initialization does not converge here: the RZZ-RX circuit starts at a stationary point, so Adam, L-BFGS-B, and natural gradient cannot leave it.
- Natural gradient reaches the target in very few value-gradient calls from random or recycled starts, but exact QGT construction makes wall time larger on this small CPU run.
- Recycling reduces target-workload calls. Its source cost is 1.639 s and is reported separately; it should only be amortized when a continuation schedule actually reuses that solution.
- Statevector wins this tiny workload. Spatial and Z2-native programs remain exact scalable candidates; their asymptotic memory advantages are not expected to dominate at four qubits.

## Interpretation boundary

The report establishes a reproducible end-to-solution method and exposes optimizer/initialization failure modes. It does not claim that one optimizer or tensor representation is universally best.
