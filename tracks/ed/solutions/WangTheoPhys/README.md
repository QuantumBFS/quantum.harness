# Rewrite It In Rust! — Exact-Diagonalization Workbench

## Submission

| Field | Value |
|---|---|
| Challenge | [#129 — Exact diagonalization workbench in Rust for electronic structure method development](https://github.com/QuantumBFS/quantum.harness/issues/129) |
| Track | `ed` |
| Team | Rewrite It In Rust! (RIIR 2607 Hefei) |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Workbench | [`JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust) |
| Validated workbench revision | [`006aae252e50a469934d11d0d12e1cb05a57477c`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust/tree/006aae252e50a469934d11d0d12e1cb05a57477c) |
| Calculation revision | [`c5a3aa698c26826b5feae470caea9c4b47680268`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust/tree/c5a3aa698c26826b5feae470caea9c4b47680268) |
| Release | [`v0.1.0`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust/releases/tag/v0.1.0) |
| License | GNU Affero General Public License v3.0 |
| Reproduction instructions | [reproduction-prompt.md](reproduction-prompt.md) |

The implementation is Rust. Python/PySCF is used only to generate and audit
independent oracle fixtures; the checked production calculations do not
import Python.

## Design

The workbench is deliberately layered so that every large calculation is
preceded by an exhaustive small-system check.

### Level 0 — independent oracle and dense reference

- A pinned PySCF 2.14.0 harness generates RHF, FCI, CCSD, FCIDUMP, geometry,
  settings, and SHA-256 provenance.
- Rust parses Mulliken-ordered FCIDUMP records, enumerates lexical alpha/beta
  strings, applies fermionic operators, builds tiny dense Hamiltonians, and
  diagonalizes them.
- H2 and H4 tests exhaustively compare determinants, signs, matrix elements,
  and energies with independent dense/PySCF values.

### Level 1 — string-based direct FCI

- Precomputed signed `E_pq` links drive the spin-free
  Knowles–Handy/Olsen-style sigma-vector contraction.
- The diagonal is computed independently.
- A restarted Davidson solver uses diagonal residual preconditioning and
  reports energy, residual, subspace, and restart history.
- Dense and matrix-free `H C` agree on small systems before the
  245,025-determinant primary problem is attempted.

### Level 2 — arbitrary-order determinant CC(n)

- One runtime-configurable solver covers every excitation rank; CC(2) means
  CCSD here, not the approximate method named CC2.
- Amplitudes are phase-normalized determinant substitutions satisfying
  `tau_mu |HF> = |mu>`.
- Production `exp(T)|HF>` uses an exact excitation-rank subset-convolution
  recurrence. The independent finite Taylor implementation remains as an
  oracle and matches every H2/H4 coefficient through full rank below
  `1e-12`.
- Orbital-denominator Jacobi steps, DIIS, and determinant-indexed warm starts
  solve the projected equations through CC(8).
- Targets at equal excitation rank run in parallel while each target's
  reduction order remains deterministic.

### Level 3 — CI(n), MBPT(n), and unitary CC(n)

- CI(n) is a rank-projected matrix-free Davidson problem and warm-starts from
  CI(n-1).
- MBPT uses canonical RHF Fock-diagonal `H0` recursion and exposes every
  correction and partial sum through arbitrary order.
- Unitary CC applies `exp(T-T†)` and minimizes the normalized variational
  energy with deterministic BFGS for small-system reference values.

### Level 4 — direct integrals

- Rust calls `libcint` directly for overlap, kinetic, nuclear-attraction, and
  electron-repulsion integrals.
- Rust RHF implements symmetric orthogonalization, Coulomb/exchange Fock
  construction, DIIS, and convergence checks.
- A staged AO-to-MO transformation feeds the shared matrix-free FCI solver.
- H2 and H2O/STO-3G tests compare every AO/MO integral and final energy with
  PySCF; Python is not a production runtime dependency.

## Units and primary Hamiltonian

The primary target is H2O/6-31G with canonical RHF orbitals, oxygen 1s
frozen, `R(O-H)=0.967 Å`, and `angle(H-O-H)=107.6°`. The active problem has
12 spatial orbitals, 8 electrons, and 245,025 determinants.

Committed input coordinates are in Angstrom and are converted internally to
Bohr by PySCF/libcint. Total energies, orbital energies, nuclear repulsion,
and integrals are in Hartree. Overlap, MO coefficients, CI coefficients, and
CC amplitudes are dimensionless.

Primary FCIDUMP SHA-256:

```text
826dd373a8b6047dff8136168431a803b59d9ef029a074da3b8f74f22603db3e
```

## Primary numerical results

The committed FCI energy is:

```text
-76.12117420414197 hartree
```

The direct Davidson residual is `5.044e-8`; the result matches the PySCF
oracle and the Hirata 2000 Table 2 caption value `-76.121174`.

Hirata and Bartlett Table 2 prints six digits after the decimal point. The
published checks compare `E(method)-E(FCI)` only after rounding both values to
integer microhartree; they do not invent precision absent from the paper.

### CC(1)-CC(8)

| Rank | Rust total energy | `E(CC)-E(FCI)` | Table 2 | Residual |
|---:|---:|---:|---:|---:|
| 1 | -75.984502842520712 | 0.136671361621254 | 0.136671 | 1.080e-9 |
| 2 | -76.119629519205702 | 0.001544684936263 | 0.001545 | 7.892e-8 |
| 3 | -76.120725652588177 | 0.000448551553788 | 0.000449 | 2.040e-7 |
| 4 | -76.121162423556896 | 0.000011780585069 | 0.000012 | 4.067e-7 |
| 5 | -76.121170991020350 | 0.000003213121616 | 0.000003 | 1.756e-7 |
| 6 | -76.121174144494702 | 0.000000059647263 | 0.000000 | 1.142e-7 |
| 7 | -76.121174198217162 | 0.000000005924804 | 0.000000 | 9.512e-8 |
| 8 | -76.121174196144139 | 0.000000007997826 | 0.000000 | 8.650e-7 |

All eight rows pass. CC(2) differs from the independent PySCF CCSD value by
`3.025e-10` hartree; full-rank CC(8) differs from FCI by `7.998e-9`
hartree. The full series took 186.94 seconds with 10 Rayon workers on an
Apple M4 and used at most 155,680,768 bytes resident memory.

### CI(1)-CI(8)

| Rank | Determinants | `E(CI)-E(FCI)` | Table 2 | Residual |
|---:|---:|---:|---:|---:|
| 1 | 65 | 0.136671361621538 | 0.136671 | 1.044e-9 |
| 2 | 1,425 | 0.006857789058358 | 0.006858 | 3.214e-8 |
| 3 | 12,625 | 0.005853940551802 | 0.005854 | 3.860e-8 |
| 4 | 55,325 | 0.000174843492616 | 0.000175 | 3.279e-8 |
| 5 | 135,069 | 0.000103257047385 | 0.000103 | 7.133e-8 |
| 6 | 208,765 | 0.000001416471065 | 0.000001 | 5.601e-8 |
| 7 | 240,125 | 0.000000369418771 | 0.000000 | 5.060e-8 |
| 8 | 245,025 | -0.000000000002004 | 0.000000 | 4.078e-8 |

All eight rows pass, the sequence is variationally non-increasing, and CI(8)
agrees with the committed FCI value within `2.004e-12` hartree.

### MBPT(1)-MBPT(20)

The computed `E(MBPT)-E(FCI)` partial-sum differences are:

```text
0.136671361621538  0.008214955387700  0.006577356213612
0.001299545129385  0.000582527596691  0.000178442636724
0.000084838275626  0.000022489352006  0.000013644732491
0.000003004694747  0.000002247016397  0.000000374837001
0.000000394209707  0.000000029304132  0.000000075118919
-0.000000004699885 0.000000015783101 -0.000000003661626
0.000000003714234 -0.000000001489667
```

All 20 partial sums pass the corresponding Hirata 2000 Table 2 entries.
Together, the primary CC, CI, and MBPT acceptance covers all 36 equilibrium
values printed in that table.

## tenferro-rs findings

The workbench maps every #129 tensor need to tenferro-rs 0.2.0. Dense tensors,
strided views, gather/scatter, division, reductions, and contractions are
present. The main determinant-workload gap is indexed scatter-add when indices
collide, including explicit deterministic semantics. The report also records
mutable/output-buffer, BLAS-1, layout, numerical, dispatch, and parallel
reduction friction with proposed minimal reproducers:

[`reports/tenferro-gap-list.md`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust/blob/v0.1.0/reports/tenferro-gap-list.md)

## Reproduce

The standalone [reproduction prompt](reproduction-prompt.md) pins the source
revision, toolchain, input checksum, units, commands, tolerances, complete
expected series, and failure-report format. A minimal build and primary CC
run is:

```bash
git clone \
  https://github.com/JunkaiWang-TheoPhy/quantum-harness-129-workbench-rust.git
cd quantum-harness-129-workbench-rust
git checkout v0.1.0
cargo build --release --locked

RAYON_NUM_THREADS=10 target/release/ed_workbench_rs cc-series \
  fixtures/h2o-631g-fc/FCIDUMP \
  fixtures/h2o-631g-fc/reference.json \
  --published-reference fixtures/h2o-631g-fc/hirata2000-table2.json \
  --max-rank 8 --residual-tolerance 1e-6 --max-iterations 100
```

Detailed reports and machine-readable result records are versioned alongside
the implementation.

## Scope note

The mandatory 6-31G frozen-core Level 0-2 target is complete. All three
Level 3 method families and Level 4 are also implemented and checked. The
Kállay 2001 DZ/DZP systems are extended targets and were not run; no 6-31G
result is presented as validation of those distinct Hamiltonians.

## Companion Rust registrations

- #214 — `tenferro-rs` verification from ED/FCI workloads.
- #215 — Rust port of the #71 Occam's Circuit verifier workflow.
- #216 — Rust-inspired certified tensor DSL design.
