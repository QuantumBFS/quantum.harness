# 🔭 WangTheoPhys: machine-certified local-logarithm Trotter bounds

## Team

| | |
|---|---|
| **Team name** | WangTheoPhys |
| **Members** | Junkai Wang, WangTheoPhys@outlook.com |
| **Challenge** | [#128 — Tighter provable Trotter error bounds for a concrete 2D Hamiltonian](https://github.com/QuantumBFS/quantum.harness/issues/128) |
| **Track** | `qcs` — selected from the issue's `Method: Quantum Circuit Simulation` field |

## Result

For the periodic spin-1/2 square-lattice Heisenberg Hamiltonian

```text
H = Σ_<i,j> (X_i X_j + Y_i Y_j + Z_i Z_j) / 4
L = 12, N = 144, T = 1, operator-norm tolerance = 1e-6
```

we certify the same five-copy fourth-order Suzuki circuit with 136 Trotter
steps, compared with 393 steps from the pinned published
Childs–Su–Tran–Wiebe–Zhu high-order commutator-bound instantiation.

| Resource | Published rigorous baseline | This certificate |
|---|---:|---:|
| Trotter steps | 393 | 136 |
| Merged group exponentials | 11,791 | 4,081 |
| Bond propagators | 848,952 | 293,832 |
| CNOT upper bound (3 per bond) | 2,546,856 | 881,496 |

The exact resource improvement is

```text
11791 / 4081 = 2.889242832639059...
```

At 136 steps the certified global operator-norm error is
`9.910917811853245e-7`. At 135 steps the bound is
`1.033576466170403e-6`, so 136 is the smallest integer accepted by this
certificate.

## What is new

The circuit, fragmentation, and cost model are identical on both sides. The
gain comes entirely from changing where norm inequalities enter the proof.

The published baseline expands partial Hamiltonian sums into individual
degree-five nested commutators and takes local Pauli-l1 norms term by term.
Our proof instead:

1. computes the homogeneous free-associative-word logarithm of the complete
   fourth-order formula;
2. applies the Dynkin–Specht–Wever projection to recover the degree-five and
   degree-seven Lie elements;
3. maps those Lie elements into the concrete four-matching Heisenberg
   representation;
4. combines identical local Pauli strings before taking a norm bound;
5. converts the logarithm into the exact right generator; and
6. closes every degree at finite step size with a rational geometric locality
   tail.

Writing

```text
log S4(t) = t A + t^5 B + t^7 C + O(t^9),
```

the right logarithmic generator obeys

```text
S4'(t) S4(t)^(-1) - A
  = 5 t^4 B
  + 2 t^5 [A,B]
  + t^6 (7 C + 2/3 [A,[A,B]])
  + t^7 (3 [A,C] + 1/6 [A,[A,[A,B]]])
  + R_{>=8}(t).
```

The remainder is not discarded. Local support growth, conjugation Taylor
factorials, and the Duhamel integration factor reduce it to an explicitly
summable rational geometric series.

## Error ledger at 136 steps

| Right-generator degree | Global contribution |
|---:|---:|
| 4 | `4.340985168056117e-7` |
| 5 | `3.830281030637750e-8` |
| 6 | `2.230486607644384e-7` |
| 7 | `2.933476798355164e-8` |
| 8 and above | `2.663070253253453e-7` |
| **Total** | **`9.910917811853245e-7`** |

All certificate values are stored as exact rational numerators and
denominators in
[`issue128/certificates/issue128-certificate.json`](issue128/certificates/issue128-certificate.json).

## Published baseline control

The baseline instantiates the higher-order commutator theorem of:

- A. M. Childs, Y. Su, M. C. Tran, N. Wiebe, and S. Zhu,
  [*A Theory of Trotter Error*](https://arxiv.org/abs/1912.08854);
- E. Schubert and C. B. Mendl,
  [*Trotter error bounds for the Fermi-Hubbard model*](https://arxiv.org/abs/2306.10603).

The verifier expands partial sums before applying local Pauli-l1 bounds and
checks all coefficients with rational intervals. All 31 allowed theorem
centers were scanned; center 20 gives the smallest published-baseline
instantiation, with site-density upper bound `164.97591695274392` and 393
steps.

We separately audited the standard recursive Suzuki orders 2, 4, 6, and 8
with a generic locality-tail theorem. Their merged group counts are 269,677,
36,361, 83,101, and 377,251 respectively, so simply raising the recursive
Suzuki order does not provide a closer rigorous competitor at this benchmark.

Optimized/processed formulas ranked empirically on random matrices are not
treated as deterministic worst-case bounds for this instance. Adapting their
coefficients to an interval-certified comparison is a useful follow-up, but
their empirical constants cannot replace the pinned rigorous baseline.

## Independent checks and negative results

- A deep verifier regenerates the published baseline, local degree-five
  coefficient, degree-seven majorant, finite tail, integer step boundary, and
  resource arithmetic.
- A degenerate 2x2 periodic-algebra sanity check gives actual spectral-norm
  error `2.3625152178806053e-10`, below its outward-rounded certificate
  `2.7555555555555555e-8`.
- The degree-three Lie representation of the four matching fragments has
  exact rank 20, equal to the free-Lie dimension `(4^3-4)/3 = 20`. Thus the
  current fragmentation has no free model-specific reduction in fourth-order
  order conditions.
- A three-site SU(2)-cluster decomposition improves local block counts but not
  the conservative compiled CNOT bound once the three-site propagator cost is
  included.

## Reproduce

From this directory:

```bash
python -m pip install -e '.[test]'
pytest -q
PYTHONPATH=src python scripts/verify.py \
  certificates/issue128-certificate.json
```

The fast verifier checks the submitted exact-rational certificate. The deep
mode regenerates the expensive local algebra:

```bash
PYTHONPATH=src python scripts/verify.py \
  certificates/issue128-certificate.json --deep
```

Regenerate the certificate:

```bash
PYTHONPATH=src python scripts/build_v3_certificate.py
```

The default test suite excludes explicitly marked research-reproduction tests.
The submitted run completed with 57 passing tests; the deep verifier also
completed successfully.

## Files

```text
issue128/
├── certificates/       exact certificate and verification summaries
├── scripts/            certificate builder, verifier, dense cross-check
├── src/trottercert/    exact Pauli/Lie/interval/locality implementation
├── tests/              fast and marked slow regression tests
└── pyproject.toml
```

The trusted verification path uses integers, `Fraction`, rational interval
arithmetic, exact symplectic Pauli multiplication, and outward rounding.
Floating point is used only for discovery and dense sanity checks.
