# VQETape contraction-aware ansatz findings

Each policy ran in a fresh process with complex128 arithmetic. Time to target includes every structure compilation, full-pool screening, synchronized value-gradient call, and optimizer overhead.

## Controlled comparison

- Four-qubit open TFIM; target energy error: `1e-10`.
- Fixed control: depth-two RZZ–RX, 14 active parameters.
- Adaptive seed: depth-one RZZ–RX, then at most seven additions.
- Pool: X, ZZ, YZ, and ZY rotations. YZ/ZY are the first local Lie-commutator closure and remain global-X symmetric with Schmidt rank two.

| policy | converged | final parameters | compiled structures | calls | compile (s) | screening (s) | target (s) | final error | max boundary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | no | 14 | 1 | 119 | 1.074 | 0.000 | — | 1.697e-07 | 48 |
| gradient-only | yes | 10 | 4 | 94 | 3.139 | 2.109 | 5.860 | 5.050e-11 | 48 |
| contraction-aware | yes | 10 | 4 | 94 | 3.621 | 2.572 | 6.865 | 5.050e-11 | 48 |

## Result

- The original X/ZZ-only pool was rejected during development because a fully optimized depth-one seed had vanishing insertion gradients. The commutator-complete YZ/ZY extension removes that false convergence.
- Both adaptive policies reached the target using 10 parameters; the 14-parameter fixed control did not reach the same target under its budget.
- Gradient-only selected: `yz-0-1 → yz-2-3 → zy-1-2`.
- Contraction-aware selected: `yz-0-1 → yz-2-3 → zy-1-2`.
- The two adaptive sequences are identical on this symmetric workload. The contraction penalty therefore causes no loss, but it does not earn a distinct performance claim here.
- The strongest supported ansatz result is the Lie-closed pool and adaptive parameter efficiency. Contraction-aware ranking remains a tested selector, not a universal winner.
