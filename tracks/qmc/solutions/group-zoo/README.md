# Challenge #148 — group-zoo

**Submission status: gate-pending; no final √5 verdict is claimed.** We completed
326/328 tasks in a pre-registered continuous-time cluster-QMC campaign and built
an independent continuous-time worm implementation. The available data are
statistically precise, but the frozen triangular-lattice primary fit has
χ²/dof = 2.1416, above the declared acceptance limit 2.0. Choosing a different
window after seeing that failure would be post-selection.

Team: **group-zoo** — 张宸萁、陆应浙
Catalog: [QuantumBFS/quantum.harness#148](https://github.com/QuantumBFS/quantum.harness/issues/148)

## Result at the submission checkpoint

We study

```text
H = -J Σ_<i,j> σᶻ_i σᶻ_j - h Σ_i σˣ_i,    J = 1,
```

on periodic triangular and honeycomb rhombic tori. Route A uses sizes
`L=8,12,16,24,32,48,64`, primarily at `β/L=1`, with independent replicas and
registered finite-size windows. The old reference values are
`h_c^triangle=4.76811(9)` and `h_c^honeycomb=2.13250(4)`.

| Quantity | Submission-checkpoint value | Interpretation |
|---|---:|---|
| Completed Route A tasks | 326/328 | Two honeycomb `L=64`, 10000-warmup replicas remain queued |
| Frozen triangle primary fit | `h_c=4.76916603`, χ²/dof `2.1416` | **Rejected** by χ²/dof ≤ 2 gate |
| Frozen honeycomb primary fit | `h_c=2.13267312`, χ²/dof `0.1285` | Accepted |
| Diagnostic ratio | `R=2.23623864` | Not a verdict because one input fit is rejected |
| Diagnostic difference | `R−√5=+0.00017066` | Fit-covariance error alone is `0.00043343`; it excludes fit-window systematics |
| Accepted matched-window range | `2.23481215…2.24152628` | The spread is much larger than the requested `σ_R≲1.2×10⁻⁵` |
| Independent Route B ED gate | pass | 24 worm-QMC tasks, six lattice/β conditions |
| Route B universal regression | 78/200 complete | Target-lattice Route B ratio is not yet available |

The main figure is generated under
`tracks/qmc/results/group-zoo-challenge148-20260730/route-a/analysis/` and shows
the rejected frozen primary fit together with every matched accepted window.
It makes the central finding visible: several individually acceptable windows
do not yet support a stable high-precision ratio.

## Why this is useful

The useful output is not an overconfident decimal for √5. It is a reproducible
failure of a predeclared quality gate. Without that gate, the diagnostic
central value and its small fit-covariance error could easily be presented as
evidence about the conjecture, while the window dependence says otherwise.

The implementation also contributes reusable infrastructure:

- immutable task JSON with seeds, lattice, `h`, `β/L`, warmup and sampling;
- atomic checkpoint/resume and completion checksums;
- per-chain raw bins and provenance, including release and Julia manifest;
- independent triangular/honeycomb geometry and exact diagonalization checks;
- 48 registered fit variants (`M1/M2/M3`, four `L_min`, fixed/free `y_t`);
- a second, independently written Huang-style worm sampler with wrapping
  observables and ED validation.

## Reproduce the submitted analysis

Raw data and figures belong under `tracks/qmc/results/` and are intentionally
gitignored by the challenge repository. With the submitted run directory
present, one command reruns tests, validates every Route A JSON against its
task/provenance/checksum, rebuilds all fit windows, and regenerates the figure:

```bash
./tracks/qmc/solutions/group-zoo/reproduce.sh \
  tracks/qmc/results/group-zoo-challenge148-20260730
```

Set `RUN_TESTS=0` to repeat only the audited analysis. The analyzer writes:

```text
route-a/analysis/route_a_available_analysis.json
route-a/analysis/fit_windows_available.json
route-a/analysis/fit_window_stability.png
```

Dependencies are pinned in `route_a/Manifest.toml` and
`route_b/Manifest.toml`; the production runtime was Julia 1.12.6. Plotting uses
Python 3 plus matplotlib. With the repository's Python test dependencies
installed, the root harness test suite is run with:

```bash
make test
```

and produced `223 passed` at the submission worktree baseline.

## Reproduce the Route A campaign from tasks

The exact 328 task files and ordered `task_paths.txt` are committed under
`route_a/config/benchmark-tasks/`; `route_a/config/benchmark.json` fixes the
campaign checksum. A single task runs as:

```bash
task=$(sed -n '1p' \
  tracks/qmc/solutions/group-zoo/route_a/config/benchmark-tasks/task_paths.txt)
CHALLENGE148_RELEASE_COMMIT=69e02b31a5078afa531e2ff96d80cc35bd6a2124 \
julia --project=tracks/qmc/solutions/group-zoo/route_a \
  tracks/qmc/solutions/group-zoo/route_a/scripts/run_cluster.jl \
  --task "tracks/qmc/solutions/group-zoo/route_a/config/benchmark-tasks/$task"
```

For Slurm, `route_a/hpc/route_a_bundle.sbatch` is the audited wrapper actually
used on SCNet. It maps array index `b` to consecutive task rows
`b*BUNDLE_SIZE … b*BUNDLE_SIZE+BUNDLE_SIZE−1`, skips no silent failures, waits
for every child process, and propagates a nonzero exit if any child fails.

## Independent Route B

Route B does not import Route A's sampler. It has its own lattice builder,
worldline state, counter RNG, proposal ratios, updates, winding reconstruction,
statistics, checkpoint format and result checksums. Run its complete local test
suite with:

```bash
julia --project=tracks/qmc/solutions/group-zoo/route_b \
  tracks/qmc/solutions/group-zoo/route_b/test/runtests.jl
```

Its completed ED report has `status=pass` for honeycomb `L=2` and triangle
`L=3`, at `β/L=1,1.5,2`, using four replicas per condition. This establishes a
small-size correctness check, but it does **not** substitute for the unfinished
universal-regression and target-lattice production gates.

## Correctness and limitations

What is verified:

1. Every included Route A result has the frozen task hash, release commit,
   manifest hash, completed-bin count and completion checksum.
2. Small-lattice Hamiltonians and observables are checked by ED.
3. Route A and Route B are independent implementations.
4. Fit acceptance is automatic and preserves rejection reasons.
5. The two missing Route A tasks affect honeycomb `L=64` thermalization
   evidence, but cannot repair the already-failed triangular primary χ² gate.

What remains before a scientific verdict:

1. complete and audit Route A 328/328;
2. resolve the triangular fit-quality/window instability under a newly frozen,
   justified campaign rather than post-selecting this one;
3. finish Route B square regression and triangular/honeycomb production;
4. combine statistical, fit-window, finite-size and finite-temperature errors;
5. issue the √5 verdict only if both routes pass their frozen gates.

The submitted result is therefore deliberately labeled **gate-pending**, not
“√5 confirmed” or “√5 excluded.”
