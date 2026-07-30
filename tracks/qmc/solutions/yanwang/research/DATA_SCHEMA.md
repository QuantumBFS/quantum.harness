# Data and Provenance Contract

Schema version: `yanwang148.run.v2`.

Every scientific number must trace to an immutable run manifest, raw
bin-level summaries, an environment manifest, a Git commit, an exact command,
and scheduler metadata. JSON instances are validated against
`research/schema/run-record.schema.json`.

## Record hierarchy

### Run record

One record describes one independent Markov chain at one
\((\text{lattice},L,h,\beta,\text{seed})\) cell.

- `identity`: stable run, experiment, and campaign identifiers; phase is one
  of `ed`, `synthetic`, `pilot`, `baseline`, or `production`.
- `provenance`: repository commit, dirty-worktree flag, command, configuration
  hash, code route, environment hash, host/cluster, and scheduler job/array
  identifiers.
- `model`: lattice, boundary conditions, Pauli normalization, \(J\), \(h\),
  \(\beta\), \(L\), site count, bond count, and edge-list hash.
- `sampler`: algorithm, update type, seed, replica, warmup, measurement
  sweeps, binning, and wall-time request.
- `observables`: bin-level or compact sufficient statistics. Baseline and
  production records must preserve separately named per-bin
  `equal_time_m2`, `equal_time_m4`, `spacetime_m2`, `spacetime_m4`, energy,
  operator-string length, sign, and update diagnostics. The nonlinear Binder
  ratios are derived from the paired bins so their covariance is retained;
  only aggregates are committed to Git.
- `diagnostics`: separately named equal-time/spacetime autocorrelation
  estimates and effective sample counts, thermalization comparisons, signs,
  finite-value checks, and completion state.
- `artifacts`: relative paths, byte counts, and SHA-256 hashes for raw output,
  stdout/stderr, scheduler accounting, and environment files.

### Fit record

`research/schema/fit-record.schema.json` records:

- exact input run IDs and hashes;
- explicit estimator identity and covariance estimator; equal-time and
  space--imaginary-time Binder estimators may coexist but may not share an
  alias or be substituted;
- scaling formula and exponent treatment;
- \(L_{\min},L_{\max}\), field/crossing window, beta policy, and discarded
  sizes with preregistered reason codes;
- optimizer and bootstrap seed;
- parameter estimates and covariance;
- goodness-of-fit, degrees of freedom, convergence, and coverage diagnostics;
- classification as primary, accepted systematic variant, or rejected variant
  with a value-independent reason.

### Verdict record

`research/schema/verdict-record.schema.json` contains both critical fields,
the ratio, \(R-\sqrt5\), statistical/systematic/total uncertainties, the joint
analysis-variant envelope, independent-route comparison, precision gates, and
the frozen rule outcome.

## Numeric and missing-value rules

- JSON numbers must be finite; `NaN`, `Infinity`, and stringified numbers are
  forbidden.
- Unavailable values are `null` only where the schema permits and require a
  neighboring reason field.
- Uncertainties are nonnegative and never inferred from displayed decimal
  places.
- Units are explicit; this project stores dimensionless \(h/J\) and \(J\beta\).
- Times are RFC 3339 UTC strings.
- Paths are repository-relative and may not contain `..`.
- Hashes use lowercase SHA-256 hex.

## Data tiers

| Tier | Contents | Git policy |
|---|---|---|
| raw | per-bin QMC output, full logs, checkpoints | downloaded locally under `data/raw/`, ignored |
| processed | reviewed compact tables, hashes, covariance inputs | committed |
| results | regenerable fits/plots/reports | ignored until promoted |
| frozen | final manifests, compact data, tables, figures, hashes | committed after review |

Production data must never overwrite pilot data. `phase` and `campaign_id`
are immutable after a run starts.

The current fit-record schema is `yanwang148.fit.v2`. Every fit must name one
of the frozen estimator IDs explicitly.
