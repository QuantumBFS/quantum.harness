# VQETape Exact Z2 Symmetry-Compression Findings

## Method

The TFIM Hamiltonian, the RZZ–RX ansatz, and the configured
\(|+\rangle^{\otimes n}\) state commute with global
\(X^{\otimes n}\). VQETape assigns charges

\[
q_{\mathrm{RZZ}}=(0,1),\qquad q_{\mathrm{MPO}}=(0,1,0)
\]

to each ket/bras operator-Schmidt leg and TFIM MPO channel. A spatial
boundary entry is active only when the XOR of all circuit-leg charges and
the MPO charge is zero. This removes exactly half of the exact boundary:

\[
D=3\cdot4^L
\quad\longrightarrow\quad
D_{\mathbb Z_2}=\frac{3\cdot4^L}{2}.
\]

Three fixed-path execution modes were compared:

- `none`: ordinary dense spatial carry;
- `z2-reference`: compressed scan carry with explicit dense
  expand/contract/gather inside each role;
- `z2-native`: BCOO sparse input carry plus a sparse one-hot output selector,
  directly producing canonical compressed data without reconstructing the
  dense carry via scatter or `todense`.

The native executor was validated role by role, including VJPs, then through
complete VQE gradients for depths one and two, block widths one through four,
default/remat/segmented adjoints, and both complex dtypes.

Each audited report uses depth two, `complex64`, five synchronized warm
repeats, a 2 GiB selection budget, and a 100-call horizon. For every path
strategy, block width, and chosen unroll, dense/reference/native use the same
serialized spatial path.

## Correctness

At eight qubits, all 63 spatial candidates were valid: 21 candidates in each
symmetry mode.

At twelve qubits, 70 of 72 candidates were valid. Two `greedy`, width-one
native candidates produced an energy error of \(1.0490\times10^{-5}\), just
above the \(10^{-5}\) `complex64` threshold, and were filtered. Their gradient
error remained \(4.05\times10^{-6}\). The other 22 native candidates were
valid.

| workload | mode | valid | max energy error | max relative gradient error |
|---|---|---:|---:|---:|
| \(n=8,L=2\) | dense | 21 | \(8.58\times10^{-6}\) | \(1.61\times10^{-6}\) |
|  | reference | 21 | \(8.58\times10^{-6}\) | \(1.61\times10^{-6}\) |
|  | native | 21 | \(7.15\times10^{-6}\) | \(1.62\times10^{-6}\) |
| \(n=12,L=2\) | dense | 24 | \(9.54\times10^{-6}\) | \(4.46\times10^{-6}\) |
|  | reference | 24 | \(9.54\times10^{-6}\) | \(4.47\times10^{-6}\) |
|  | native | 22 | \(8.58\times10^{-6}\) | \(4.59\times10^{-6}\) |

Every compressed candidate reports recurrent dimension 24 rather than the
dense dimension 48 at depth two. The active positions are deterministic,
disjoint from the forbidden positions, and exhaustive with them. Dense
recurrence tests confirm the forbidden norm remains zero after first and
every bulk transition.

## Fixed-triple measurements

Ratios are relative to the identical dense path. A value below one favors
the symmetry mode.

### Eight qubits: 21 complete triples

| mode | compile median | warm median | compiler-temp median | logical-tape median | paired compile/warm/temp dominance |
|---|---:|---:|---:|---:|---:|
| reference | 0.951 | 1.102 | 1.037 | 1.067 | 1 |
| native | 1.051 | 1.006 | 1.126 | 1.202 | 0 |

Native beat dense warm time in 10 of 21 pairs, but beat compiler temporary
memory in only two. Reference rebuilt the dense carry in each role, so its
slightly larger tape/temp is expected and is not a native-memory claim.

### Twelve qubits: 22 complete triples

| mode | compile median | warm median | compiler-temp median | logical-tape median | paired compile/warm/temp dominance |
|---|---:|---:|---:|---:|---:|
| reference | 1.044 | 1.112 | 1.030 | 1.044 | 1 |
| native | 1.049 | 0.999 | 1.102 | 1.146 | 4 |

Native beat dense warm time in 11 of 22 complete pairs and compiler temporary
memory in five. The exact recurrent state is half-sized, but BCOO coordinate
metadata, sparse selectors, and their reverse rules commonly offset that
storage benefit in JAX's small CPU executables.

This distinction is essential:

- recurrent carry and modeled checkpoint bytes are mathematically halved;
- logical JAX tape is an implementation property and increased in the
  median;
- compiler temporary memory is measured separately and also increased in the
  median.

## Pareto and horizon results

Using compile, warm, and compiler temporary bytes:

| workload | spatial frontier size | dense | reference | native |
|---|---:|---:|---:|---:|
| \(n=8,L=2\) | 10 | 6 | 2 | 2 |
| \(n=12,L=2\) | 5 | 3 | 1 | 1 |

Native therefore passes the nondominance gate on both workloads. The fastest
native kernels were:

| workload | native program | compile | warm | compiler temp | logical tape |
|---|---|---:|---:|---:|---:|
| \(n=8,L=2\) | random-greedy, b3, u2 | 2.163 s | 0.284 ms | 33,088 B | 30,608 B |
| \(n=12,L=2\) | auto-hq, b3, u3 | 4.193 s | 0.486 ms | 43,800 B | 41,984 B |

The 100-call selections remained dense because native compile cost outweighed
its best warm results:

| workload | selected dense program | compile | warm | 100-call objective |
|---|---|---:|---:|---:|
| \(n=8,L=2\) | random-greedy, b1, u1 | 0.979 s | 0.426 ms | 1.021 s |
| \(n=12,L=2\) | auto-hq, b1, u1 | 0.905 s | 0.489 ms | 0.954 s |

## Decision

1. The exact \(\mathbb Z_2\) sector analysis and compressed recurrent carry
   are promoted as verified compiler capabilities.
2. `z2-reference` remains an oracle and must not be described as a native
   workspace-memory optimization.
3. `z2-native` is retained as an optional search candidate. It is valid,
   directly consumes/emits compressed data, and is nondominated on both
   workloads, but it is not the default because median compiler temp and tape
   increased.
4. The result does not justify a general sparse-tensor claim. It applies to
   the supported global-\(X\) sector; `initial_state="zero"` and unsupported
   tensor charge patterns are rejected.
5. The next stage should optimize end-to-solution VQE behavior. Symmetry mode
   remains part of program selection so a longer optimization horizon can
   amortize native compilation where its warm kernel wins.
