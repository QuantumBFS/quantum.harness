## Team

| | |
|---|---|
| **Team name** | Born Critical |
| **Members** | Yansheng Tu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can Born-rule sampling and transfer-matrix finite-size scaling reproduce the effective central charges of the Nishimori and weak self-dual critical points in open quantum matter, going beyond the clean Ising benchmark? |
| **Catalog issue** | `Addresses #122` — “Criticality in open quantum matter,” released by Guo-Yi Zhu, Hong Kong University of Science and Technology (Guangzhou). |
| **Track** | `tracks/qmc/` — selected from the issue’s Quantum Monte Carlo, Monte Carlo sampling, and finite-size-scaling methods; tensor-network contraction remains part of the planned calculation. |

## Frozen stage-0 setup

The small-system reference implementation uses a square-lattice cylinder with
periodic transverse and open propagation-direction boundaries.

| Model | Convention |
|---|---|
| Clean Ising | `Kc = 0.5 * log(1 + sqrt(2))`, target `c = 0.5` |
| Nishimori RBIM | `P(tau=-1)=p`, `exp(-2K)=p/(1-p)`, `p=0.1092212` |
| Weak self-dual | `theta=pi/4`, `beta=beta'=log(1+sqrt(2))`, Born weight proportional to `abs(Z(s,t))^2` |
| Cylinder sector | Reference-row Wilson loop `prod_x s[x,y=0]=+1`; fermion parity is explicit for the periodic Jordan–Wigner bond |

The circumference-two oracle intentionally treats periodic horizontal links as
two directed bond slots (a two-edge multigraph). This removes a common
small-size ambiguity and makes direct enumeration and row transfer use exactly
the same lattice.

## Stage-0 implementation

Implemented:

- frozen coupling and normalization definitions;
- exact spin summation for clean, random-bond, and signed self-dual weights;
- stabilized row-by-row transfer contraction;
- exact tiny-system Born distribution and bitwise conditional sampler;
- dense Jordan–Wigner/Majorana oracle, including the periodic parity sign;
- tests for enumeration/transfer equivalence, RBIM gauge invariance, Born
  normalization, Wilson-loop filtering, and Majorana gate equivalence;
- pinned Nishimori baseline source metadata.

The dense oracle is deliberately exponential. It is a correctness reference
for the later Gaussian sampler and must never be used for production sizes.

Stage-0 tests are not run on `ws0`. After the scientific setup and Slurm
resources are ratified, submit `slurm/stage0-tests.sbatch`; it copies this
directory from `ws0` to node-local storage and returns a manifest plus logs.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The command above is the compute-node rerun command, not permission to execute
on the login node.

## Stage-0 verification

Stage 0 completed on Slurm job `17167` (`ws4`, CPU-only, 2 CPUs, 4 GiB
requested). All 20 tests passed. The largest recorded oracle discrepancy was
`6.661338147750939e-16` in the signed transfer contraction; the periodic
Majorana boundary-gate error was `2.118352371637509e-16` in each parity sector.
Born normalization and Wilson-loop violations were exactly zero at recorded
precision.

See `STAGE0-REPORT.md` for the verification record. Machine-readable artifacts
are returned under
`tracks/qmc/results/born-critical/stage0-tests/job-17167/` and are gitignored.

## Stage-1 numerical kernel

Implemented:

- order-independent keyed random streams and exact RNG state restoration;
- streaming complete-block means and block-based standard errors;
- real/complex Householder QR Lyapunov accumulation with positive diagonal
  convention and orthogonality diagnostics;
- atomic, compressed, pickle-free checkpoint/resume for RNG, blocks,
  Lyapunov basis, optional Gaussian state, and cell metadata;
- weighted M0 (`1, L^-2`) and M1 (`1, L^-2, L^-4`) Casimir fits with
  free-energy/Shannon sign conventions, covariance support, fit diagnostics,
  and visible bootstrap failures.

Stage 1 completed on Slurm job `17173` (`ws5`, CPU-only, 2 CPUs, 4 GiB
requested). All 43 tests passed. QR intervals 1, 2, and 5 agreed within
`1.4148838350935833e-17`; the 100,000-layer smoke remained finite with maximum
orthogonality error `1.1934897514720433e-15`. Checkpoint/resume errors were
exactly zero, and both synthetic M1 central charges were recovered within
`7e-14`.

See `STAGE1-REPORT.md`. Machine-readable artifacts and the stability plot are
under `tracks/qmc/results/born-critical/stage1-tests/job-17173/`.

## Stage-2 clean Ising benchmark

Implemented:

- a positive symmetric clean-Ising row transfer matrix using the frozen
  directed-bond convention;
- residual-controlled explicit Perron-root calculations through \(L=10\);
- an independent critical free-fermion dispersion and analytic bulk limit;
- direct tiny-torus enumeration against \(\log\operatorname{Tr}T^N\);
- exact finite-size data for \(L=4\) through 64;
- predeclared M0/M1 \(L_{\min}\) scans and a dependency-free stability plot.

Stage 2 completed on Slurm job `17178` (`ws5`, CPU-only, 2 CPUs, 4 GiB
requested). All 48 tests passed. The explicit transfer matrix and
free-fermion expression agreed within `8.881784197001252e-16` in
`log(lambda_0)`. The main large-size M0 fit gives
`c = 0.5011803410374673`; the M1 correction fit gives
`c = 0.4999790413568287`, compared with the exact `c = 0.5`. All declared
accuracy, window-stability, sign, and conditioning gates passed.

See `STAGE2-REPORT.md`. Machine-readable artifacts and the Casimir stability
plot are under
`tracks/qmc/results/born-critical/stage2-clean-ising/job-17178/`.

## Stage-3 Nishimori RBIM

Implemented:

- an independent finite-cylinder Gaussian RBIM oracle and pinned-upstream
  comparison;
- an optimized C++17/Eigen/MKL infinite-strip kernel with periodic QR;
- immutable pilot/production run specifications, keyed replica seeds,
  complete-block output, SHA-256 manifests, and atomic result return;
- 10,000-sample replica bootstrap over all declared M0/M1 fit windows;
- clean-limit, \(p_c\)-sensitivity, P/AP-defect, and complete-distribution
  upstream cross-checks;
- a per-node Slurm audit that reserves four CPU cores for every unallocated
  GPU and enforces the per-user GPU-task limit.

The final production run contains 320/320 successful cells and
60,192,288,000 measured rows. The predeclared main M1 fit gives
`c_eff = 0.4597565`, with bootstrap 68% interval
`[0.4592914, 0.4602097]` and 95% interval
`[0.4588332, 0.4606509]`. The latter intersects the historical
`0.464 +/- 0.004` interval at its lower edge. Fit quality, adjacent-window
stability, large-size signal, \(p_c\) propagation, upstream agreement, and all
cross-check gates passed.

See `STAGE3-REPORT.md`. Machine-readable production artifacts and plots are
under `tracks/qmc/results/born-critical/rbim-production-v1/`; the combined
verdict is `tracks/qmc/results/born-critical/stage3-acceptance.json`.

## Stage-4 weak self-dual Born critical point

Implemented:

- normalized sequential Born sampling with pure Majorana covariance updates;
- Rao–Blackwell conditional-entropy blocks and QR-stabilized transfer
  diagnostics;
- dense spin enumeration and an independent dense-contraction local
  Metropolis sampler for \(L\le8\);
- immutable 512-cell production, checksum validation, 10,000-sample replica
  bootstrap, and all predeclared M0/M1 fit windows;
- per-submission Slurm CPU/GPU reserve auditing for the non-shared-storage
  cluster.

The production run contains 512/512 successful cells and 171,966,464 measured
circuit cycles. The primary M1 fit gives
`c_Casimir = 0.4477179838`, with bootstrap 68% interval
`[0.4472843, 0.4481650]` and 95% interval
`[0.4468820, 0.4485672]`. The reduced chi-squared is 0.8111. All Shannon
precision, \(e/m=3/8\), isotropy, exact-enumeration, Metropolis, fit-window,
bootstrap, probability, QR, and regression gates passed.

See `STAGE4-REPORT.md`. Machine-readable production data and plots are under
`tracks/qmc/results/born-critical/selfdual-production-v1/`; the combined
verdict is `tracks/qmc/results/born-critical/stage4-acceptance.json`.
