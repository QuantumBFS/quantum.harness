# Stage 0 verification report

## Outcome

Stage 0 is complete. The frozen conventions, exact spin and row-transfer
oracles, tiny-system Born sampler, and dense Majorana/Jordan–Wigner oracle were
validated on a Slurm compute node.

## Frozen setup

- Geometry: square-lattice cylinder, periodic transverse direction, open
  propagation direction.
- Clean Ising: `Kc = 0.5 * log(1 + sqrt(2))`.
- Nishimori RBIM: `P(tau=-1)=p`, `exp(-2K)=p/(1-p)`,
  `p=0.1092212`.
- Weak self-dual: `theta=pi/4`,
  `beta=beta'=log(1+sqrt(2))`, Born weight proportional to
  `abs(Z(s,t))^2`.
- Vacuum sector: reference Wilson loop `prod_x s[x,y=0]=+1`.
- Periodic Jordan–Wigner bond: fermion parity sector is explicit.

## Successful run

| Field | Value |
|---|---|
| Slurm job | `17167` |
| State | `COMPLETED`, exit `0:0` |
| Node | `ws4` |
| Resources | CPU-only, 2 CPUs, 4 GiB, 10-minute limit |
| Elapsed | 3 seconds |
| Python | 3.11.15 |
| NumPy | 2.4.3 |
| Tests | 20 passed |
| Source digest | `49407050f99cd9577054a82849d4fba5a16efb57db6c67d2de2e25a1b0ab55d5` |

Machine-readable evidence:

```text
tracks/qmc/results/born-critical/stage0-tests/job-17167/
├── manifest.json
├── metrics.json
├── runner.log
└── unittest.log
```

## Recorded numerical checks

| Check | Absolute error / count |
|---|---:|
| Clean direct enumeration vs row transfer, `log(Z)` | `0.0` |
| Signed self-dual enumeration vs row transfer, `log(abs(Z))` | `6.661338147750939e-16` |
| RBIM gauge-transformed partition function, `log(Z)` | `0.0` |
| Exact Born normalization | `0.0` |
| Conditional-chain `log(P)` | `0.0` |
| Vacuum Wilson-loop violations | `0` |
| Majorana Clifford residual | `0.0` |
| `MX` spin vs Majorana operator norm | `0.0` |
| Periodic `MZ`, odd parity operator norm | `2.118352371637509e-16` |
| Periodic `MZ`, even parity operator norm | `2.118352371637509e-16` |

These values satisfy the stage-0 thresholds of `1e-11` for exact partition
oracles, `1e-10` for the Majorana representation, and `1e-12` for normalized
probabilities.

## Startup failure retained in scheduler history

The first smoke job, `17165`, failed before tests because the example Conda
environment `test` did not exist on `ws4`, and the original failure callback
attempted rsync before creating the ws0 result parent directory. No physics
calculation ran in that job.

The fix:

- uses the existing `QC` environment, which supplies Python and NumPy;
- uses standard-library `unittest`, so no compute-node installation is needed;
- creates the remote parent before rsync;
- emits a fallback `startup-failed` manifest if Python never starts.

Jobs `17166` and `17167` then completed; `17167` is the final evidence-bearing
run after machine-readable metric collection was added.

## Scope note

The Majorana oracle uses dense spin matrices and is intentionally exponential.
It verifies the Jordan–Wigner signs and periodic parity sector but is not the
production Gaussian covariance-matrix algorithm. The latter belongs to the
next numerical-kernel stages and will be checked against this oracle.
