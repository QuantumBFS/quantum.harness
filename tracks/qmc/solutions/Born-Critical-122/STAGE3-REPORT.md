# Stage 3 report: Nishimori random-bond Ising model

## Outcome

Stage 3 is complete. The machine-readable verdict in
`tracks/qmc/results/born-critical/stage3-acceptance.json` is `passed`, with
all 13 declared gates true.

Final regression job `17307` then reran all 52 tests and the fixed upstream
baseline on `ws1`; it completed in 11 seconds with exit code 0 and all gates
passing.

The production calculation used 320 independent cells: 32 replicas at each of

\[
L=6,8,10,12,14,16,20,24,30,32.
\]

The predeclared main fit,

\[
\phi_L=\phi_\infty+\frac{\pi c_{\rm eff}}{6L^2}+\frac{a_4}{L^4},
\]

selected the smallest quality-passing M1 window, \(L_{\min}=6\), without using
the target value:

| Quantity | Result |
|---|---:|
| fitted \(c_{\rm eff}\) | 0.4597565 |
| replica-bootstrap median | 0.4597601 |
| 68% interval | [0.4592914, 0.4602097] |
| 95% interval | [0.4588332, 0.4606509] |
| \(\chi^2/\mathrm{dof}\) | 0.9477 |
| valid bootstrap fits | 10,000 / 10,000 |

The 95% interval intersects the historical target
\(0.464\pm0.004=[0.460,0.468]\), near the lower edge. This is compatibility,
not a claim that the central estimate equals 0.464. The declared adjacent M1
and large-size M0 checks are stable at 0.145 and 0.568 combined standard
deviations, respectively.

## Frozen model and implementation

The simulated square-lattice cylinder has iid bonds

\[
\Pr(\tau_{ij}=-1)=p,\qquad
K_N=\frac12\log\frac{1-p}{p},
\]

with

```text
p = 0.1092212
K_N = 1.0493604763025683
```

The production observable is the quenched positive log-partition density

\[
\phi_L=\lim_{N\to\infty}\frac{\mathbb E[\log Z]}{LN}.
\]

Each random row is applied as local real-fermion transfer layers. Periodic
Householder QR accumulates the log-volume growth without multiplying an
unstable long matrix product. The optimized C++17/Eigen/MKL kernel is an
independent production implementation of the same Gaussian transfer
convention used by the NumPy oracle.

The implementation added:

- finite-cylinder and streaming RBIM Gaussian transfer code;
- a fixed-commit upstream compatibility build;
- a C++ streaming production kernel;
- keyed replica seeds and complete-block output;
- immutable pilot and production run specifications;
- checksum-validated, atomic no-shared-storage result return;
- replica bootstrap, predeclared M0/M1 windows, residual diagnostics, and
  dependency-free SVG plots;
- a per-node Slurm CPU/GPU resource audit.

## Stage 3A: independent baseline

Slurm job `17185` passed all 52 repository tests and all baseline gates.

| Check | Samples | Maximum absolute error |
|---|---:|---:|
| explicit spin transfer vs internal fermionic \(\log Z\) | 64 | \(1.78\times10^{-14}\) |
| pinned upstream driver vs internal \(\log Z\) | 16 | \(3.55\times10^{-15}\) |
| QR interval 1 vs 5 | 1,000 | \(2.03\times10^{-10}\) |

The QR comparison tolerance is \(5\times10^{-10}\); the largest recorded
orthogonality error is \(1.33\times10^{-15}\). The pinned upstream source is
commit `814c24775b6b46cab77f3b4829c9c3802cab2146` of
`Zhouquan-Wan/fermionic-transfer-matrix-rbim`.

The cluster lacked MPI, PFAPACK, MKL headers, and a system Eigen installation.
The retained compatibility layer supplies a single-process MPI shim, explicit
LAPACKE declarations, and a stub only for the unused midpoint-magnetization
path. The upstream `logZ` implementation remains intact and links against the
MKL runtime from the node-local `torch` environment.

## Stage 3B: pilot and frozen production budget

The corrected pilot run `rbim-pilot-v2` contains 40/40 successful cells:
eight replicas for each \(L=4,6,8,10,12\). Aggregate job `17231` found:

- at least 504 complete blocks per size;
- maximum absolute adjacent-block correlation below 0.1;
- no size requiring block doubling;
- QR interval 1/5 mean difference \(7.77\times10^{-14}\);
- maximum orthogonality error \(1.78\times10^{-15}\).

Production therefore froze `qr_interval=5`, burn-in \(20L\), output
superblocks of 2,600 rows, 32 replicas per size, and per-replica lengths
derived from the pilot precision target.

The optimized-kernel benchmark job `17233` measured approximately 2.77 million
rows/s at \(L=4\), 0.90 million at \(L=12\), and 0.21 million at \(L=32\)
without concurrent load.

## Stage 3C: production data

The final run ID is `rbim-production-v1`. All 320 manifests are successful,
all artifact SHA-256 values match, all parameter/settings payloads agree with
the run specification, and all 320 RNG fingerprints are unique.

In total the calculation retained:

- 60,192,288,000 measured rows;
- 23,150,880 complete 2,600-row blocks;
- maximum absolute per-cell adjacent-block correlation 0.01287;
- maximum orthogonality error \(2.89\times10^{-15}\).

| \(L\) | replicas | mean \(\phi_L\) | replica SE | signal / SE |
|---:|---:|---:|---:|---:|
| 6 | 32 | 1.7378736589 | \(1.78\times10^{-6}\) | 3785 |
| 8 | 32 | 1.7348775882 | \(1.45\times10^{-6}\) | 2609 |
| 10 | 32 | 1.7335043644 | \(1.76\times10^{-6}\) | 1384 |
| 12 | 32 | 1.7327625597 | \(1.91\times10^{-6}\) | 885 |
| 14 | 32 | 1.7323125810 | \(2.11\times10^{-6}\) | 587 |
| 16 | 32 | 1.7320280158 | \(2.46\times10^{-6}\) | 386 |
| 20 | 32 | 1.7316840722 | \(1.59\times10^{-6}\) | 383 |
| 24 | 32 | 1.7315045245 | \(1.95\times10^{-6}\) | 216 |
| 30 | 32 | 1.7313521646 | \(2.06\times10^{-6}\) | 131 |
| 32 | 32 | 1.7313176823 | \(2.03\times10^{-6}\) | 117 |

The largest-size Casimir signal is therefore 117 times its replica standard
error, well above the declared factor-of-five gate.

## Stage 3D: fit stability and cross-checks

All declared windows are retained in `fit-summary.csv`; no result was hidden
or selected by proximity to the target.

| Model/window | bootstrap median | 95% interval | \(\chi^2/\mathrm{dof}\) |
|---|---:|---:|---:|
| M1, \(L_{\min}=6\) | 0.459760 | [0.458833, 0.460651] | 0.948 |
| M1, \(L_{\min}=8\) | 0.459605 | [0.457688, 0.461468] | 1.101 |
| M0, \(L_{\min}=14\) | 0.460315 | [0.458200, 0.462439] | 1.354 |
| M0, \(L_{\min}=20\) | 0.458159 | [0.452792, 0.463655] | 1.616 |

Cross-check job `17301` completed in 31 minutes 45 seconds:

- \(p=p_c\pm4\times10^{-7}\), with paired seeds at
  \(L=12,16,20,24,32\), gives an absolute central-charge half-span
  \(2.51\times10^{-5}\), only 5.43% of the production bootstrap standard
  deviation;
- the clean \(p=0\), \(K=K_c\) limit gives \(c=0.4999392\);
- 128 complete-distribution samples at \(L=6,N=12\) agree with the pinned
  upstream implementation to a maximum paired \(\log Z\) difference
  \(8.53\times10^{-14}\);
- P/AP defect runs at \(L=4,6,8\) are finite, predominantly positive, and
  have consistent mean \(\log Z_P-\log Z_{AP}\) values near 7.95.

## Slurm resource correction and retained failures

The first production submission incorrectly interpreted the CPU/GPU reserve
globally. It placed four 4-CPU tasks on each of `ws1` and `ws3`, consuming all
16 schedulable CPUs while both GPUs on each node were idle. This violated the
node-level requirement to leave four CPUs per unallocated GPU.

The run was corrected without hiding the incident:

1. the array was throttled and cross-check submission held;
2. tasks `17237_1`, `_3`, `_7`, and `_8` were cancelled, releasing eight CPUs
   on each node;
3. 80 already complete replica directories were recovered from node-local
   scratch and individually checksum-validated;
4. task `17237_9`, which was later placed as a third CPU-only task on `ws3`,
   was cancelled after 94 seconds before producing data;
5. only missing cells were resubmitted with explicit nodes and no overwrite;
6. `audit_slurm_resources.py` was changed to check every node's `CPUAlloc`,
   configured/allocated GPUs, and the per-user four-GPU-task limit.

The corrected placement never exceeds eight CPU cores on a node with two idle
GPUs. The final production data are composed of original successful groups,
the 80 recovered checksum-valid cells, and retry jobs `17254`, `17257`, and
`17294`.

Other retained operational attempts include:

- job `17184`: numerical baseline passed, but the original QR tolerance
  \(2\times10^{-10}\) was narrower than the observed
  \(2.029\times10^{-10}\) rounding envelope; the evidence-backed tolerance
  was frozen at \(5\times10^{-10}\) for job `17185`;
- pilot v1: valid scientific output but only 12 blocks because of an LCM block
  rounding mistake; immutable pilot v2 corrected it to 63 blocks per cell;
- job `17251`: two retry tasks failed in one second because a local environment
  variable was not exported through SSH; no compilation or cell computation
  occurred, and job `17254` used the explicit harness command field.

## Artifacts and reproduction

Machine-readable results are gitignored and live under:

```text
tracks/qmc/results/born-critical/stage3a-baseline/job-17185/
tracks/qmc/results/born-critical/rbim-pilot-v2/aggregate/
tracks/qmc/results/born-critical/rbim-production-v1/
tracks/qmc/results/born-critical/stage3-crosschecks/job-17301/
tracks/qmc/results/born-critical/stage3-acceptance.json
```

Important production artifacts:

- `run_spec.json`: immutable axes, settings, and provenance;
- `cells/cell-*/manifest.json` and `block-phi.npy`: raw replica evidence;
- `parameter-scan.csv`: 320-cell collection table;
- `aggregate/size-summary.csv`: finite-size means and errors;
- `aggregate/fit-summary.csv` and `fits.json`: every declared fit window;
- `aggregate/finite-size-fit.svg` and `fit-stability.svg`: report plots;
- `aggregate/metrics.json`: headline production verdict.

Re-aggregate on a compute node with:

```bash
PYTHONPATH=src python scripts/aggregate_rbim_production.py \
  --run /path/to/rbim-production-v1 \
  --declaration configs/rbim-fit-declaration.json \
  --output /path/to/recomputed-aggregate
```

## Stage boundary

Stage 3 establishes the disordered transfer implementation, QR stability,
replica-level uncertainty, finite-size fits, upstream agreement, and
Nishimori result required before the weak self-dual Born calculation. Stage 4
must retain the corrected per-node Slurm audit and may not revert to a global
CPU/GPU reserve calculation.
