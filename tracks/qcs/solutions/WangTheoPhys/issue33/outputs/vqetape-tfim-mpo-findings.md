# VQETape Exact TFIM MPO Findings

## Outcome

The exact bond-dimension-3 TFIM MPO passed the executable decision gate on
both measured CPU workloads. The default direct-TN search can therefore use
the MPO as a production Hamiltonian representation while retaining
`pauli_sum` as the exact control.

The change is at the VQE-program level:

\[
E(\theta)
=
\sum_{\alpha=1}^{2n-1}
c_\alpha
\langle\psi(\theta)|P_\alpha|\psi(\theta)\rangle
\quad\longrightarrow\quad
\langle\psi(\theta)|H_{\mathrm{MPO}}|\psi(\theta)\rangle .
\]

The left program differentiates \(2n-1\) complete circuit contractions. The
right program differentiates one bra–MPO–ket contraction and therefore shares
the circuit tensors and their reverse-mode residuals across the complete TFIM
Hamiltonian.

## Experimental contract

Both reports were produced by the `vqetape --mode direct-tn` CLI. Every
candidate ran in a fresh subprocess and computed exact energy plus the
complete padded gradient. The search space was:

\[
\{\text{Pauli sum},\text{MPO}\}
\times
\{\text{greedy},\text{random-greedy},\text{auto-hq}\}
\times
\{\text{default AD},\text{three named-tape budgets}\}.
\]

This gives 24 candidates per workload. All timing calls were synchronized.
The state-vector implementation was the correctness reference. The reported
process RSS is not GPU peak memory; compiler temporary bytes and logical
reverse-mode tape bytes are separate quantities.

The raw reports are:

- [primary report](vqetape-tfim-mpo-report.json)
- [holdout report](vqetape-tfim-mpo-report-holdout.json)

## Primary workload

Configuration: \(n=3\), depth \(L=2\), \(J=g=1\), initial state
\(|+\rangle^{\otimes n}\), `complex64`, three warm repetitions, and an
expected VQE horizon of 100 value-and-gradient calls.

All 24 candidates passed correctness. Across the candidate set, the maximum
absolute energy error was \(7.15\times10^{-7}\), and the maximum relative
gradient \(L_2\) error was \(2.59\times10^{-7}\).

Default-AD rows:

| Hamiltonian | Path | Compile (ms) | Warm median (µs) | Compiler temp (B) | Logical tape (B) | Energy FLOPs | Tensor bindings |
|---|---:|---:|---:|---:|---:|---:|---:|
| MPO | auto-hq | 771.98 | 151.00 | 5,576 | 5,424 | 1,648 | 29 |
| MPO | greedy | 1,075.78 | 169.37 | 5,768 | 5,712 | 1,792 | 29 |
| MPO | random-greedy | 858.64 | 141.29 | 5,448 | 5,328 | 1,728 | 29 |
| Pauli sum | auto-hq | 7,452.34 | 261.67 | 7,812 | 20,260 | 4,560 | 145 |
| Pauli sum | greedy | 8,937.31 | 284.04 | 9,988 | 21,700 | 5,240 | 145 |
| Pauli sum | random-greedy | 10,568.47 | 303.21 | 10,052 | 22,660 | 5,680 | 145 |

The selected program was `dense + MPO + auto-hq + default AD`. Relative to
the horizon-optimal Pauli control (`auto-hq + default AD`), it had:

- 9.65× shorter compilation;
- 1.73× faster warm value-and-full-gradient execution;
- 1.40× fewer compiler temporary bytes;
- 3.74× fewer logical residual bytes;
- 2.77× fewer estimated energy-level FLOPs;
- exactly \(2n-1=5\) times fewer tensor bindings.

The measured Pareto frontier contained four candidates, all using MPO. One
named-tape MPO candidate reduced the logical tape from 5,328 B to 2,368 B for
the same random-greedy topology, showing that Hamiltonian sharing and
residual scheduling are composable. Its compiler temporary storage did not
fall, so logical tape and executable peak proxies must still be reported
separately.

## Holdout workload

Configuration: \(n=3\), depth \(L=1\), \(J=0.7\), \(g=0.3\), initial state
\(|000\rangle\), `complex64`, three warm repetitions, and the same 100-call
VQE horizon.

All 24 candidates passed correctness. The maximum absolute energy error was
\(2.38\times10^{-7}\), and the maximum relative gradient \(L_2\) error was
\(8.31\times10^{-9}\).

Default-AD rows:

| Hamiltonian | Path | Compile (ms) | Warm median (µs) | Compiler temp (B) | Logical tape (B) | Energy FLOPs | Tensor bindings |
|---|---:|---:|---:|---:|---:|---:|---:|
| MPO | auto-hq | 648.40 | 105.79 | 3,016 | 2,584 | 984 | 19 |
| MPO | greedy | 520.04 | 104.67 | 3,656 | 3,192 | 1,184 | 19 |
| MPO | random-greedy | 529.87 | 75.29 | 2,952 | 2,488 | 1,024 | 19 |
| Pauli sum | auto-hq | 3,241.52 | 208.58 | 4,228 | 8,780 | 2,040 | 95 |
| Pauli sum | greedy | 3,582.70 | 341.42 | 4,292 | 8,780 | 2,040 | 95 |
| Pauli sum | random-greedy | 2,256.86 | 198.38 | 4,228 | 9,100 | 2,160 | 95 |

The selected program was `dense + MPO + greedy + default AD`. Relative to the
horizon-optimal Pauli control (`random-greedy + default AD`), it had:

- 4.34× shorter compilation;
- 1.90× faster warm execution;
- 1.16× fewer compiler temporary bytes;
- 2.85× fewer logical residual bytes;
- 1.82× fewer estimated energy-level FLOPs;
- exactly \(2n-1=5\) times fewer tensor bindings.

Both holdout Pareto candidates used MPO.

## Decision-gate audit

| Gate | Result | Evidence |
|---|---|---|
| Exact MPO algebra | Pass | Dense reconstruction for \(n=2,3,4\), multiple \(J,g\), zero couplings, and `complex128` |
| Exact VQE energy and full gradient | Pass | Pauli sum, MPO, and state-vector comparisons across gate representations and workload variants |
| Hamiltonian-level residual sharing | Pass | MPO reduces total logical tape and repeated `_diag` gate residuals |
| Energy-level cost accounting | Pass | Pauli costs are multiplied by \(2n-1\); MPO costs by one contraction |
| Executable nondominance | Pass | All 12 MPO candidates per workload are nondominated by every Pauli candidate in warm time plus compiler temporary bytes |
| Cross-workload trend | Pass | MPO selected on both the primary and holdout workloads |

## Regression audit

The complete repository test suite passed after the benchmark and
documentation updates:

```text
137 passed in 317.93s (0:05:17)
```

This includes legacy state-vector and direct-TN behavior as well as the new
MPO algebra, template, binding, one-shot energy/full-gradient, residual,
fresh-worker, and candidate-search tests.

## Interpretation and boundary

This is a positive representation-level result, not evidence that every MPO
contraction is asymptotically cheap. The current implementation forms one
global bra–MPO–ket contraction graph. It removes Hamiltonian-term duplication,
but its general exact cost is still governed by the contraction width of the
circuit-plus-MPO network.

The next phase should preserve this exact MPO and lower it into a spatial
transfer recurrence for shallow one-dimensional VQE circuits:

\[
B_{i+1}=F_i(B_i;\theta_i),\qquad
\dim B_i=\chi_H r^{2L}.
\]

For the present TFIM ansatz, \(\chi_H=3\) and the exact RZZ operator-Schmidt
rank is \(r=2\), so the boundary dimension is \(3\cdot4^L\). This would change
the scaling from a monolithic global contraction to a scan that is linear in
qubit count at fixed depth. A custom adjoint with segmented checkpoints can
then target the remaining reverse-mode carry memory rather than
reintroducing \(O(n)\) saved boundaries.
