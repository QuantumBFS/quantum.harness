# Challenge 81 CT-HYB Production Design

## 1. Purpose and claim boundary

This document specifies the missing production CT-HYB reference for Challenge
#81. The reference is an independent, continuous-bath calculation at
\(\beta=16\) for

\[
D=1,\quad U=0.8,\quad \Gamma=0.1,\quad
\epsilon_d=-0.4,\quad \mu=0,
\]

with reported values on the shared grid
\(\tau=[0,4,8,12,16]\). It uses the locked Python 3.12, TRIQS 4.0.0, and
TRIQS/cthyb 4.0.0 environment already recorded by `environment.yml` and
`conda-linux-64.lock`.

This reference has one scientific role: estimate the observables of the
continuous semicircular bath, with explicit Monte Carlo uncertainty, so the
finite-bath MPS calculation can be compared against an independent method. It
is not part of the MPS implementation.

`finite_bath_ed.py` has a different role. It exactly solves a small,
discretized Hamiltonian and establishes that the finite-bath MPS code,
fermionic signs, purification, and observable conventions are correct. It
cannot validate the continuous bath. Conversely, CT-HYB does not replace the
finite-bath MPS-versus-ED \(10^{-6}\) acceptance gate.

The following errors remain distinct:

* CT-HYB standard errors are Monte Carlo sampling uncertainty.
* MPS bath-discretization and finite-chain errors arise from replacing the
  continuous bath by a finite Hamiltonian.
* MPS bond-truncation and time-step/residual errors are deterministic solver
  errors.
* The observed MPS-minus-CT-HYB difference can contain all of the above. It is
  not itself an estimate of any one component.

In particular, no report may rename MPS bath error as CT-HYB Monte Carlo error
or subtract one from the other.

## 2. Selected architecture

The production path consists of seven narrow components:

1. `make_input.py` creates and verifies one deterministic canonical input
   artifact.
2. `hybridization.py` evaluates the analytic continuous semicircular
   hybridization and installs it in a TRIQS solver.
3. `run_chain.py` executes one serial CT-HYB Markov chain and writes a raw HDF5
   archive plus a canonical chain manifest.
4. `reduce.py` validates four independent chain bundles, computes standard
   errors and gates, and constructs a canonical aggregate summary.
5. `publication.py` implements immutable, atomic publication and restart-safe
   reuse.
6. `compare_mps.py` compares the aggregate against a converged MPS result and
   adds the CT-HYB sampling term to the existing error budget without merging
   error categories.
7. `cthyb_slurm_array.sh` runs chain indices 0 through 3 independently on a
   POSIX cluster.

Each chain is a separate one-rank process with its own seed and HDF5 file. A
single `mpirun -np 4` solver call is deliberately not used: TRIQS would reduce
rank-local accumulators, making the four independent chain means and raw
chain-level diagnostics unavailable to the reducer.

## 3. Authoritative scientific input

### 3.1 Canonical artifact

The authoritative input is `cthyb-input.json`, encoded as UTF-8 canonical JSON:
keys sorted lexicographically, separators `(",", ":")`, no NaN or infinity,
and one final newline. Its top-level shape is:

```json
{
  "payload": {
    "artifact_type": "cthyb_production_input",
    "schema_version": 2,
    "model": {
      "model_id": "challenge-81-spinful-anderson-semicircular",
      "D": 1.0,
      "U": 0.8,
      "Gamma": 0.1,
      "epsilon_d": -0.4,
      "mu": 0.0,
      "beta": 16.0
    },
    "conventions": {
      "green_function": "G_sigma(tau) = -Tr[exp(-(beta-tau)K) d_sigma exp(-tau K) d_sigma^dag] / Z",
      "hybridization_spectrum": "Gamma(omega) = -Im Delta^R(omega)",
      "matsubara_transform": "Delta(z) = integral_-D^D d epsilon Gamma(epsilon) / (pi * (z-epsilon))",
      "noninteracting_inverse": "G0_sigma^-1(z) = z + mu - epsilon_d - Delta(z)"
    },
    "hybridization": {
      "kind": "analytic_semicircle",
      "formula": "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))",
      "dtype": "complex128",
      "n_iw": 2049,
      "matsubara_omega": ["<all ordered float64 mesh values>"],
      "delta_iw": {
        "real": ["<all ordered float64 real parts>"],
        "imag": ["<all ordered float64 imaginary parts>"],
        "sha256": "<SHA256 of canonical {real,imag} bytes>"
      },
      "common_real_frequency": {
        "omega": [-1.0, 0.0, 1.0],
        "Gamma": [0.0, 0.1, 0.0],
        "sha256": "d424a7438f1b7da8938256f2cae9812a2b52c737d34f6026453ca4aa15f55b0f"
      }
    },
    "meshes": {
      "n_tau": 4001,
      "reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0]
    },
    "chains": {
      "count": 4,
      "random_generator": "mt19937",
      "master_seed": 810000,
      "seeds": [810001, 810002, 810003, 810004]
    },
    "monte_carlo": {
      "warmup_cycles": 50000,
      "measurement_cycles": 1000000,
      "cycle_length": 50,
      "measure_G_tau": true,
      "measure_density_matrix": true,
      "use_norm_as_weight": true,
      "measure_pert_order": true
    },
    "gates": {
      "minimum_average_sign": 0.99,
      "require_autocorrelation_converged": true,
      "maximum_integrated_autocorrelation_cycles": 5.0,
      "minimum_effective_samples_per_chain": 100000,
      "minimum_effective_samples_total": 400000,
      "maximum_spin_asymmetry": 0.005,
      "maximum_half_filling_error": 0.005,
      "minimum_completed_chains": 4
    },
    "runtime": {
      "mpi_ranks_per_chain": 1,
      "threads_per_rank": 1
    },
    "calibration": {
      "artifact_sha256": "<accepted calibration payload SHA256>"
    },
    "provenance_inputs": {
      "source_manifest": {
        "<repository-relative source or schema path>": "<64 lowercase hexadecimal digits>"
      },
      "source_manifest_sha256": "<SHA256 of canonical source_manifest bytes>",
      "conda_lock_sha256": "<64 lowercase hexadecimal digits>",
      "environment_yml_sha256": "<64 lowercase hexadecimal digits>",
      "model_json_sha256": "<64 lowercase hexadecimal digits>"
    }
  },
  "sha256": "<SHA256 of canonical payload bytes>"
}
```

The literal digests are filled by `make_input.py`; angle-bracket text is not
accepted by the schema or verifier. Schema 1 remains a non-production
scaffold. Schema 2 is a separate fail-closed production contract and requires
all values above exactly. There is no `production_ready` boolean that a caller
can flip. Schema 1 permanently retains
`production_ready=false` and `scientific_comparison=false`; it must never be
relaxed or version-mutated into production. All production evolution occurs
under the separate schema-2 filename and artifact type.

`model.json` remains the model authority. `make_input.py` must load it and
reject any disagreement rather than copying caller-supplied physics.

The `source_manifest` is complete rather than runner-only. It contains every
transitive executable source and schema that can affect input generation,
chain execution, calibration, reduction, validation, publication, or
comparison: `artifacts.py`, `make_input.py`, `hybridization.py`,
`source_manifest.py`, `run_chain.py`, `calibrate.py`, `reduce.py`,
`publication.py`,
`validate_existing.py`, `compare_mps.py`, both Slurm wrappers, all three
schema-2 schemas, `smoke_test.py`, `model.json`, `environment.yml`,
`conda-linux-64.lock`, permanent scaffold
`cthyb-production.schema.json`, `bath.py`, `chain_mapping.py`,
`finite_bath_ed.py`, `acceptance.py`, `convergence.py`,
`convergence.schema.json`, `triqs/tests/test_lock.py`, Julia `Project.toml` and
`Manifest.toml`, and the finite-bath Julia runner, checkpoint, purification,
and observables sources that `acceptance.py` authenticates. The manifest maps
repository-relative POSIX paths to file-byte SHA256 values. Its own digest is
over canonical map bytes.
Production input generation fails if any required path is absent; downstream
validation recomputes the complete map and rejects additions, omissions, or
changed bytes.

The production input is generated only after calibration and binds the
accepted calibration payload SHA256. Calibration plans bind the same model,
environment, source manifest, formulas, and mesh contract but use a distinct
`cthyb_calibration_plan` artifact and nonproduction seed namespaces; they do
not require a circular production-input digest.

The schema-2 input also serializes the complete ordered Matsubara mesh and
\(\Delta(i\omega_n)\) as complex128 split into canonical float64 `real` and
`imag` arrays. JSON never uses implementation-specific complex-number text.
The `delta_iw.sha256` is computed over canonical
`{"imag":[...],"real":[...]}` bytes and is rechecked against the formula before
TRIQS receives the values.

The real-frequency comparison surface is exactly the one currently emitted
by schema-2 MPS convergence bath artifacts:

```json
{"Gamma":[0.0,0.1,0.0],"omega":[-1.0,0.0,1.0]}
```

Its canonical SHA256 is
`d424a7438f1b7da8938256f2cae9812a2b52c737d34f6026453ca4aa15f55b0f`.
The CT-HYB verifier recomputes the values from
\(\Gamma(\omega)=0.1\sqrt{1-\omega^2}\) on \([-1,1]\). The comparator requires
the MPS schema-2 bath artifact's `frequency_grid` and
`target_continuum_hybridization` arrays to equal these arrays exactly and
requires the same digest. A future denser common grid is a schema/input change,
not an unbound plotting choice.

The reported tau points are exact nodes of the 4001-point uniform TRIQS
imaginary-time mesh: indices 0, 1000, 2000, 3000, and 4000. The reducer selects
those indices; it does not interpolate production values.

### 3.2 Continuous hybridization

For \(z=i\omega_n\), the exact transform of
\(\Gamma(\epsilon)=\Gamma\sqrt{1-(\epsilon/D)^2}\) is

\[
\Delta(z)=\frac{\Gamma}{D}\left(z-\sqrt{z^2-D^2}\right),
\]

where the square-root branch obeys \(\sqrt{z^2-D^2}\sim z\) as
\(|z|\rightarrow\infty\). On the fermionic Matsubara axis the implementation
uses the unambiguous real-frequency expression serialized in the input:

\[
\Delta(i\omega_n)=i\frac{\Gamma}{D}
\left[\omega_n-\operatorname{sgn}(\omega_n)
\sqrt{\omega_n^2+D^2}\right].
\]

This is an analytic continuous-bath input. It does not consume `bath.json`,
finite \(\epsilon_k\), finite \(V_k\), or a star-to-chain mapping. Independent
tests compare it both with 4096-node Gauss-Chebyshev quadrature of the second
kind, using the same semicircular weight as `bath.py`, and with an 80-decimal
`mpmath` integral. Neither quadrature is used by production.

For both spin blocks the runner sets

\[
G_{0,\sigma}^{-1}(i\omega_n)
=i\omega_n+\mu-\epsilon_d-\Delta(i\omega_n),
\]

and passes only
\(h_{\mathrm{int}}=U n_\uparrow n_\downarrow\) to `Solver.solve`. This avoids
counting the impurity one-body term twice.

## 4. Chain execution and raw retention

Each chain constructs a fresh `Solver(beta=16, gf_struct=[("up", 1),
("down", 1)], n_iw=2049, n_tau=4001)`, installs the input above, and invokes
`solve` with:

* the chain's unique `random_seed`;
* `random_name="mt19937"`;
* `n_warmup_cycles=50000`;
* `n_cycles=1000000`;
* `length_cycle=50`;
* `measure_G_tau=True`;
* `measure_density_matrix=True`;
* `use_norm_as_weight=True`;
* `measure_pert_order=True`;
* `performance_analysis=False`.

The density matrix and `trace_rho_op` produce
\(n_\uparrow\), \(n_\downarrow\), and
\(\langle n_\uparrow n_\downarrow\rangle\). The raw archive retains enough
state for independent re-extraction:

* `G0_iw`, `Delta_iw`, `G_iw`, and full `G_tau`;
* `density_matrix` and `h_loc_diagonalization`;
* perturbation-order histograms;
* `average_sign`, `auto_corr_time`, and `auto_corr_time_converged`;
* `solve_parameters`, `solve_status`, and `last_configuration`;
* the exact canonical input bytes and input payload digest;
* seed, chain index, timestamps, hostname, Slurm identifiers, CPU/thread
  settings, wall time, peak RSS, and package/runtime versions.

`chain-summary.json` contains extracted scalar values and references
`raw.h5` by byte SHA256. HDF5 is retained as primary raw evidence, but HDF5
bytes are not called canonical across HDF5 versions. The canonical JSON
manifest is the integrity and provenance layer.

The runner writes only inside a unique attempt staging directory. A zero exit
is insufficient: the runner reloads `raw.h5`, recomputes observables, verifies
all exact input bindings and gates that can be checked per chain, writes
`completion.json`, fsyncs files and directories, and atomically renames the
attempt to its immutable chain destination.

## 5. Monte Carlo and statistical gates

### 5.1 Warmup and production calibration

The fixed production values above are admitted only after a calibration
artifact passes:

1. Run four chains with 100,000 measurement cycles at warmups 12,500, 25,000,
   and 50,000 cycles. Each warmup level uses a distinct independent seed set;
   no chain is paired across levels.
2. For each static scalar and genuine-interior spin Green-function point, let
   \(\Delta=\bar x_{50k}-\bar x_{25k}\). If
   \(\mathrm{SE}_{25k}\) and \(\mathrm{SE}_{50k}\) are the standard errors of
   the two independent four-chain means, the difference error is exactly
   \[
   \mathrm{SE}_{\Delta}=
   \sqrt{\mathrm{SE}_{25k}^2+\mathrm{SE}_{50k}^2}.
   \]
   With \(a=\mathrm{SE}_{25k}^2\) and
   \(b=\mathrm{SE}_{50k}^2\), use Welch degrees of freedom
   \(\nu=(a+b)^2/(a^2/3+b^2/3)\). A simultaneous two-sided family-wise 99%
   Bonferroni interval
   \[
   \Delta\ \pm\ t_{1-0.01/(2m),\nu}\,\mathrm{SE}_{\Delta}
   \]
   must lie wholly inside `[-5e-4,+5e-4]` for `n_d` and double occupancy and
   inside `[-1e-3,+1e-3]` for every genuine-interior spin Green value, where
   \(m=8\): two static scalars plus three interior tau points for each of two
   spins. Zero-variance identical means pass only when their degenerate
   interval lies inside the bound.
3. Run four 100,000-cycle pilots at cycle lengths 10, 25, 50, and 100. Select
   the smallest candidate for which every chain reports converged
   autocorrelation time no larger than 5 cycles. The production artifact is
   intentionally fixed to 50, so calibration fails if 50 is insufficient; it
   does not silently rewrite the production input.
4. For each of four calibration groups, run eight independent fixed-size
   increments of 62,500 measurement cycles. Every increment performs the full
   selected warmup and uses a unique deterministic sub-seed outside the
   production namespace. Its directly measured mean is \(B_{c,k}\);
   increment means are never reconstructed by subtracting normalized
   cumulative estimators.
5. Use the 32 direct increment means for batch-means uncertainty. For each
   scalar, compare each group's first-half and second-half means as four paired
   differences \(d_c\). With
   \(\bar d=\sum_c d_c/4\),
   \(\mathrm{SE}_{d}=s_d/\sqrt{4}\), and three degrees of freedom, construct
   the simultaneous two-sided family-wise 99% Bonferroni interval
   \[
   \bar d\ \pm\ t_{1-0.01/(2m),3}\,\mathrm{SE}_{d}.
   \]
   The complete interval must lie wholly inside `[-5e-4,+5e-4]` for `n_d` and
   double occupancy and `[-1e-3,+1e-3]` for every genuine-interior spin Green
   value, again with \(m=8\). Merely containing zero is insufficient. This is
   an equivalence gate, not a failure-to-reject-drift gate.
6. Estimate the variance of a 62,500-cycle batch separately within each group,
   pool those four variances without pooling chain means, and project the
   standard error of the final four-chain mean at 1,000,000 cycles per chain.
   With eight batches in each of four groups, the pooled within-group variance
   has \(\nu=4(8-1)=28\) degrees of freedom and the production mean has 64
   batch-equivalents. Its one-sided 99% upper error bound is
   \[
   \sqrt{\frac{\nu s_p^2}{\chi^2_{0.01,\nu}\,64}}.
   \]
   This bound must be at most `5e-4` for `n_d` and double occupancy and `1e-3`
   for each genuine-interior spin Green-function value. The artifact stores
   batch identities and means, pairing, degrees of freedom, multiplicity
   correction, quantiles, pooled variance, projected error, and confidence
   bound. No gate compares two raw SE point estimates or demands monotone SE
   reduction.

The calibration uses distinct seeds derived in a separate seed namespace and
is never pooled into production.

### 5.2 Production gates

TRIQS reports `auto_corr_time` in units of measurement cycles and whether that
estimate saturated. For chain \(c\), define the conservative diagnostic

\[
N_{\mathrm{eff},c}
=\left\lfloor\frac{N_{\mathrm{cycles}}}
{2\max(1,\tau_{\mathrm{int},c})}\right\rfloor.
\]

Production is rejected unless all of the following hold:

* exactly four chain indices and four unique expected seeds are present;
* every solve completed normally, with no max-time or signal termination;
* every chain has `auto_corr_time_converged=true`;
* every chain has finite `auto_corr_time <= 5.0`;
* every chain has \(N_{\mathrm{eff},c}\ge100000\), and their sum is at least
  400000;
* every chain has finite average sign at least 0.99;
* all observables and diagnostics are finite;
* the aggregate satisfies
  \(|n_\uparrow-n_\downarrow|\le0.005\) and
  \(|n_d-1|\le0.005\);
* the endpoint identities
  \(G_\sigma(0)=-(1-n_\sigma)\) and
  \(G_\sigma(\beta)=-n_\sigma\) hold within
  `max(3.182446305284263 * endpoint_residual_standard_error, 0.002)`;
* no chain mean is omitted or manually down-weighted.

TRIQS's autocorrelation diagnostic is based on configuration observables and
is not claimed to be a per-tau Green-function autocorrelation measurement. It
is therefore used as a conservative run-quality gate, while final standard
errors are computed from independent chain means.

### 5.3 Standard errors

For each reported scalar \(x\), let \(x_c\) be the completed mean from chain
\(c\). The published estimate and standard error are

\[
\bar x=\frac{1}{4}\sum_{c=1}^4 x_c,\qquad
\operatorname{SE}(\bar x)=
\sqrt{\frac{\sum_c(x_c-\bar x)^2}{4(4-1)}}.
\]

The same unweighted formula applies pointwise to \(G_\uparrow(\tau)\) and
\(G_\downarrow(\tau)\). Four chains give only three degrees of freedom, so the
summary also reports the raw four means and a 95% Student interval using
\(t_{0.975,3}=3.182446305284263\). Standard errors are never inferred from the
deterministic seed or from a single accumulated `G_tau`.

Endpoint uncertainty preserves the covariance between \(G\) and occupancy.
For every chain and spin, the reducer first forms

\[
r_{c,\sigma,0}=G_{c,\sigma}(0)+(1-n_{c,\sigma}),\qquad
r_{c,\sigma,\beta}=G_{c,\sigma}(\beta)+n_{c,\sigma}.
\]

It then applies the same four-chain mean and standard-error formula directly
to each residual vector. It is forbidden to combine separately estimated
errors for \(G\) and \(n\) in quadrature, because that discards their
chain-level covariance. The summary retains all residuals, their mean,
standard error, Student interval, and gate result.

## 6. Canonical aggregate summary

`cthyb-summary.json` is `{payload, sha256}` with SHA256 over canonical payload
bytes. Its payload includes:

* schema/generator versions and `input_sha256`;
* the exact model, conventions, beta, tau grid, common real-frequency arrays
  and digest, and complex128 Matsubara arrays and digest;
* four chain IDs, seeds, chain-summary digests, raw-HDF5 byte digests, solve
  status, sign, autocorrelation, effective samples, wall time, and peak RSS;
* means, standard errors, Student intervals, and the four chain means for
  `n_up`, `n_down`, `n_d`, `double_occupancy`, `G_up`, `G_down`, and their
  spin average;
* every gate threshold, measured value, and pass/fail result;
* lock-file digest, Python/TRIQS/cthyb/OpenMPI/HDF5 versions, source digests,
  host and scheduler information;
* `status="accepted"` only when every required gate passes.

Unknown keys, duplicate JSON keys, nonfinite values, wrong-length arrays,
unexpected seeds, stale source hashes, and any hash mismatch fail closed.

## 7. Publication and restart

The result root follows the existing acceptance/convergence convention:

```text
ROOT/
  current.json
  work/<input-sha256>/chain-000/...
  work/<input-sha256>/chain-003/...
  runs/cthyb-<first-16-summary-sha256>/
    cthyb-input.json
    chains/chain-000/{raw.h5,chain-summary.json,completion.json,stdout.log,stderr.log}
    chains/chain-001/...
    chains/chain-002/...
    chains/chain-003/...
    cthyb-summary.json
    completion.json
```

Chain and reducer advisory locks cover validation and publication. Symlinks
and non-regular files are rejected. Completed chain bundles are immutable and
reused only after full byte/hash/schema revalidation.

TRIQS/cthyb 4.0.0 does not provide a project-validated durable checkpoint that
captures the Markov configuration, RNG state, and all accumulators. The design
therefore makes no partial-chain resume claim. Interrupted or timed-out
attempts are archived as `.abandoned-*`; the same chain restarts from the
beginning with the same input and seed. Other completed chains are retained
and reused. This is deterministic restart scheduling, not deterministic Monte
Carlo output.

After all four bundles validate, the reducer constructs a unique staging tree,
revalidates it, fsyncs it, and same-filesystem renames it into `runs/`. Only
then does it atomically replace `current.json`. An existing identical run is
revalidated and reused. An existing run ID with different bytes is corruption
and blocks publication.

## 8. MPS comparator and error-budget integration

The comparator consumes:

1. one accepted `cthyb-summary.json`;
2. one immutable, freshly revalidated finite-bath MPS-versus-ED acceptance
   run whose hash-bound `acceptance.json` has `passed=true`,
   `global_max_error <= 1e-6`, and `effective_threshold <= 1e-6`;
3. one schema-valid completed MPS production cell on the same physical model
   and tau grid;
4. one MPS convergence analysis that separately reports bath discretization,
   chain-length/mapping, bond truncation/maxdim, and time-step/residual bounds.

The acceptance prerequisite is mechanical, not narrative. The comparison
artifact records the acceptance artifact payload SHA256, acceptance file
SHA256, completion SHA256, `ed-oracle.json` payload/file SHA256, and
`mps-result.json` file SHA256. Final publication reloads the immutable
acceptance directory through `validate_acceptance_run`, confirms its
completion manifest and binding threshold, and rejects stale paths, copied
JSON, or an acceptance failure. The CT-HYB production result may exist without
this prerequisite, but neither a comparator artifact nor final Challenge 81
publication may be accepted.

The comparator also requires exact equality of the schema-2 MPS bath
artifact's `frequency_grid=[-1.0,0.0,1.0]` and
`target_continuum_hybridization=[0.0,0.1,0.0]`, plus the canonical common-grid
digest from section 3. A matching model name without matching arrays and
digest is insufficient.

It compares `n_d`, double occupancy, `G_up`, and `G_down` pointwise. For each
scalar \(j\), it records

\[
\Delta_j=|x_j^{\mathrm{MPS}}-x_j^{\mathrm{CTHYB}}|,
\]

the CT-HYB standard error \(\sigma_j\), each named MPS deterministic error
component, and the conservative compatibility envelope

\[
B_j =
\delta_{j,\mathrm{bath}}+
\delta_{j,\mathrm{chain}}+
\delta_{j,\mathrm{bond}}+
\delta_{j,\mathrm{time/residual}}+
3.182446305284263\,\sigma_j.
\]

Compatibility requires \(\Delta_j\le B_j\) for every scalar. The report also
shows the Monte Carlo-normalized residual after subtracting no deterministic
terms, \(\Delta_j/\sigma_j\), as a diagnostic only. It may not be interpreted
as a bath-error estimate.

If the current MPS convergence schema cannot provide a named component for an
axis, the comparator records that component as unavailable and blocks the
combined production claim. It does not replace a missing component by zero or
by the MPS–CT-HYB discrepancy.

## 9. Environment bootstrap and offline execution

### 9.1 Lock regeneration required before implementation tests

The currently committed explicit lock contains the solver runtime, but it does
**not** contain direct `pytest`, `jsonschema`, or `mpmath` package entries.
Therefore it supports the existing smoke test only. This design does not claim
that the current lock can execute the planned test suite.

Task 0 has exactly three implementation files:
`environment.yml`, regenerated `conda-linux-64.lock`, and new
`triqs/tests/test_lock.py`. The test imports `jsonschema`, `mpmath`, `pytest`,
`triqs`, and `triqs_cthyb`, reads the active prefix's `conda-meta` JSON, and
asserts the TRIQS and cthyb package versions are 4.0.0. Task 0 adds the three
missing direct dependencies to
`environment.yml`, lets conda-forge solve them with the already exact
Python/TRIQS/cthyb constraints, and regenerates the complete explicit lock on
Linux x86-64. No package URL, build, or hash is written by hand:

```bash
export MAMBA_ROOT_PREFIX="$PWD/tracks/mps/results/frustration-free/lockgen-mamba-root"
export LOCK_ENV="$PWD/tracks/mps/results/frustration-free/lockgen-triqs"
rm -rf "$LOCK_ENV"
./micromamba create --yes --platform linux-64 --prefix "$LOCK_ENV" \
  --file tracks/mps/solutions/frustration-free/triqs/environment.yml
./micromamba run --prefix "$LOCK_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/smoke_test.py
./micromamba run --prefix "$LOCK_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_lock.py -q
./micromamba list --prefix "$LOCK_ENV" --explicit --md5 \
  > tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock.tmp
python3 - <<'PY'
from pathlib import Path
text = Path(
    "tracks/mps/solutions/frustration-free/triqs/"
    "conda-linux-64.lock.tmp"
).read_text(encoding="utf-8")
assert "@EXPLICIT\n" in text
for name in ("pytest", "jsonschema", "mpmath"):
    assert f"/{name}-" in text, name
assert all(
    line.startswith(("http://", "https://")) and "#" in line
    for line in text.splitlines()
    if line and not line.startswith(("#", "@"))
)
PY
mv tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock.tmp \
  tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
```

The generated lock is then tested from a second empty prefix:

```bash
export LOCK_VERIFY_ENV="$PWD/tracks/mps/results/frustration-free/lockverify-triqs"
rm -rf "$LOCK_VERIFY_ENV"
./micromamba create --yes --prefix "$LOCK_VERIFY_ENV" \
  --file tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
./micromamba run --prefix "$LOCK_VERIFY_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/smoke_test.py
./micromamba run --prefix "$LOCK_VERIFY_ENV" python -m pytest \
  tracks/mps/solutions/frustration-free/triqs/tests/test_lock.py -q
```

Only the solver constraints in the current lock are authoritative until this
regeneration task is committed. `environment.yml`, the generated lock, and
`test_lock.py` must be reviewed and committed together; no other implementation
file belongs to Task 0.

### 9.2 Runtime bootstrap

Run from the repository root on Linux x86-64. The online bootstrap is:

```bash
curl -fL \
  https://github.com/mamba-org/micromamba-releases/releases/download/2.8.1-0/micromamba-linux-64 \
  -o micromamba
echo "9689782d863c05a1bf5d2d371ba527104e7a4eb4310c1637d8653b751aed9c82  micromamba" \
  | sha256sum -c -
chmod 0755 micromamba
export MAMBA_ROOT_PREFIX="$PWD/tracks/mps/results/frustration-free/mamba-root"
export CTHYB_ENV="$PWD/tracks/mps/results/frustration-free/triqs-4.0.0"
./micromamba create --yes --prefix "$CTHYB_ENV" \
  --file tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
./micromamba run --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/smoke_test.py
```

To seed a cache for compute nodes without network access, perform one
download-only transaction on a connected Linux x86-64 host, then transfer the
micromamba binary, the lock file, and the complete `mamba-root/pkgs/` tree:

```bash
export MAMBA_ROOT_PREFIX="$PWD/cthyb-offline/mamba-root"
mkdir -p "$MAMBA_ROOT_PREFIX"
./micromamba create --yes --download-only \
  --prefix "$PWD/cthyb-offline/download-only-env" \
  --file tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$PWD/cthyb-offline" -cf cthyb-conda-cache.tar mamba-root
sha256sum micromamba \
  tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock \
  cthyb-conda-cache.tar > cthyb-offline.sha256
```

On the offline cluster:

```bash
sha256sum -c cthyb-offline.sha256
mkdir -p "$SCRATCH/challenge81-cthyb"
tar -C "$SCRATCH/challenge81-cthyb" -xf cthyb-conda-cache.tar
export MAMBA_ROOT_PREFIX="$SCRATCH/challenge81-cthyb/mamba-root"
export CTHYB_ENV="$SCRATCH/challenge81-cthyb/triqs-4.0.0"
./micromamba create --offline --yes --prefix "$CTHYB_ENV" \
  --file tracks/mps/solutions/frustration-free/triqs/conda-linux-64.lock
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/smoke_test.py
```

After implementation, generate the exact 60-cell calibration plan (12 warmup,
16 cycle-length, and 32 fixed-increment cells), submit it, and reduce it:

```bash
export CAL_ROOT="$SCRATCH/challenge81-cthyb/calibration-beta16"
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/calibrate.py plan \
  --output-root "$CAL_ROOT"
export CAL_RUN="$(python3 -c \
  'import json,os,sys; p=json.load(open(sys.argv[1])); print(os.path.join(sys.argv[2],p["relative_path"]))' \
  "$CAL_ROOT/current.json" "$CAL_ROOT")"
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/calibrate.py \
  validate-plan --plan "$CAL_RUN/calibration-plan.json"
sbatch --array=0-59 --ntasks=1 --cpus-per-task=1 --mem=4G --time=04:00:00 \
  --export=ALL,OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1,CTHYB_ENV="$CTHYB_ENV",CTHYB_CAL_PLAN="$CAL_RUN/calibration-plan.json",CTHYB_CAL_RUN="$CAL_RUN" \
  tracks/mps/solutions/frustration-free/triqs/cthyb_calibration_slurm_array.sh
```

After all 60 array cells finish, reduction is exactly:

```bash
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/calibrate.py analyze \
  --plan "$CAL_RUN/calibration-plan.json" --run-directory "$CAL_RUN"
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/calibrate.py \
  validate-existing --plan "$CAL_RUN/calibration-plan.json" \
  --run-directory "$CAL_RUN" \
  --calibration "$CAL_RUN/calibration.json"
export CALIBRATION_SHA256="$(python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' \
  "$CAL_RUN/calibration.json")"
```

`calibrate.py plan` fixes zero-based cell ordering in its schema; the Slurm
wrapper verifies that `SLURM_ARRAY_TASK_ID` identifies the same hash-bound cell
before running it. `analyze` refuses missing, duplicate, or extra cells and
publishes `calibration.json` atomically. Site account and partition flags may
be prepended to `sbatch`.

Only after accepted calibration, create the canonical production input and
submit the four-chain array with one rank and one thread per chain:

```bash
export CTHYB_ROOT="$SCRATCH/challenge81-cthyb/production-beta16"
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/make_input.py \
  --calibration "$CAL_RUN/calibration.json" \
  --expected-calibration-sha256 "$CALIBRATION_SHA256" \
  --output "$CTHYB_ROOT/cthyb-input.json"
sbatch --array=0-3 --ntasks=1 --cpus-per-task=1 --mem=4G --time=12:00:00 \
  --export=ALL,OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1,CTHYB_ENV="$CTHYB_ENV",CTHYB_INPUT="$CTHYB_ROOT/cthyb-input.json",CTHYB_ROOT="$CTHYB_ROOT" \
  tracks/mps/solutions/frustration-free/triqs/cthyb_slurm_array.sh
```

Site-specific account and partition flags may be prepended without changing
the scientific input. Once all array jobs finish:

```bash
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/reduce.py \
  --input "$CTHYB_ROOT/cthyb-input.json" --output-root "$CTHYB_ROOT"
./micromamba run --offline --prefix "$CTHYB_ENV" \
  python tracks/mps/solutions/frustration-free/triqs/validate_existing.py \
  --output-root "$CTHYB_ROOT"
```

## 10. Risks and mitigations

* **Only four chain means determine errors.** The summary publishes all four,
  uses a three-degree-of-freedom Student interval, and does not claim Gaussian
  precision from the effective-sample count.
* **Autocorrelation is a proxy.** TRIQS's converged autocorrelation diagnostic
  is gated and disclosed; independent-chain dispersion supplies reported
  errors.
* **HDF5 is not canonical across libraries.** Raw file bytes are hashed per
  run; canonical JSON binds their meaning and runtime.
* **No safe partial-chain checkpoint exists.** A failed chain restarts from its
  seed; no accumulator or RNG state is reconstructed.
* **A max-time exit can look superficially usable.** Any non-normal solve
  status is incomplete and cannot publish.
* **Endpoint conventions can differ by mesh handling.** Exact mesh-node
  extraction and covariance-preserving chain residuals are mandatory tests and
  gates.
* **Density-matrix reweighting is easy to omit.** The input and raw solve
  parameters require both `measure_density_matrix` and
  `use_norm_as_weight`.
* **The analytic square-root branch can be implemented incorrectly.** Tests
  cover positive/negative Matsubara symmetry, high-frequency moments, direct
  quadrature, and causality.
* **The comparator can obscure MPS systematics.** Missing named MPS error
  components block the claim; observed discrepancy is never reassigned.

## 11. Production stopping criteria

Implementation is complete only when:

1. focused tests and the complete Python suite pass in the locked environment;
2. input generation is byte-identical across two clean invocations;
3. analytic hybridization tests pass and every \(-\operatorname{Im}
   \Delta(i\omega_n)\) on positive frequencies is nonnegative;
4. warmup, cycle-length, paired-increment, batch-means, and projected
   confidence-bound calibrations pass;
5. exactly four production chains pass every solve, sign, autocorrelation,
   effective-sample, symmetry, and endpoint gate;
6. the raw HDF5 archives can independently regenerate every published chain
   value;
7. kill/restart and concurrent-reducer tests prove that partial state cannot
   advance `current.json`;
8. the accepted aggregate summary and completion manifest pass fresh
   hash/schema/provenance validation;
9. the digest-bound finite-bath MPS-versus-ED acceptance run freshly validates
   with maximum error and effective threshold at most \(10^{-6}\);
10. the MPS comparator either publishes a fully separated compatibility budget
   or fails closed with named missing MPS components; and
11. no document or artifact claims that finite-bath error is Monte Carlo
    error.

Increasing cycles beyond one million is not automatic. If a statistical gate
fails, the run is a recorded non-result. A new canonical input with explicitly
larger cycle counts, new input hash, and new run ID is required.
