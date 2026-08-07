# Challenge #148 design

## Objective

Test the conjecture

`h_c(triangular) / h_c(honeycomb) = sqrt(5)`

for the ferromagnetic transverse-field Ising model with a reproducible,
sign-problem-free QMC calculation. The numerical target is the challenge gate
`sigma_R <= 1.2e-5`, including statistical and finite-size-scaling systematic
uncertainties. A result that does not reach that gate remains a feasibility or
pilot result and must not be presented as a verdict.

The first milestone is deliberately smaller: literature audit, exact
small-system oracle, two independently implemented QMC checks, and a measured
resource estimate. Production begins only after that milestone passes.

## Fixed physical conventions

The simulated Hamiltonian is

`H = -J sum_<ij> sigma_z[i] sigma_z[j] - h sum_i sigma_x[i]`

with:

- `J = 1`;
- Pauli matrices with eigenvalues `+1` and `-1`, not spin operators `S=1/2`;
- nearest-neighbor ferromagnetic bonds counted once;
- periodic boundary conditions in both spatial directions;
- triangular lattice with `N = L^2`, coordination number 6 and `3N` bonds;
- honeycomb lattice with `N = 2L^2`, coordination number 3 and `3N/2` bonds;
- magnetization density `m = sum_i sigma_z[i] / N`;
- paper Binder ratio `Q_L = <m^2>^2 / <m^4>`, not the alternative Binder
  cumulant `1 - <m^4> / (3 <m^2>^2)`;
- quantum critical scaling with `z = 1`, using `beta = c L` and an explicit
  convergence check in `c` before any ground-state claim.

The 2002 reference values under these conventions are
`h_c(triangular) = 4.76811(9)` and
`h_c(honeycomb) = 2.13250(4)`. They are comparison anchors, not inputs to the
fit.

## Source anchors

The primary numerical definition is Blote and Deng, Phys. Rev. E 66, 066110
(2002):

- Eq. (7)/(14): Pauli-matrix Hamiltonian convention;
- Eq. (21): `Q_L = <m^2>^2 / <m^4>`;
- Eq. (23): finite-size expansion of `Q_L`;
- Table I: published triangular and honeycomb critical fields;
- Sec. V: periodic boundaries, physical imaginary-time length proportional to
  `L`, and 3D Ising exponents.

The algorithm references are Sandvik, Phys. Rev. E 68, 056701 (2003) for SSE,
and Rieger and Kawashima, Eur. Phys. J. B 9, 233 (1999) for continuous-time
clusters. The primary implementation is pinned to QMC_SSE commit
`35f100af856f3273cc67d31962f3e67f801b0c37` (`GPL-3.0-only`). The independent
implementation is pinned to QMC_LTFIM commit
`524860b9c0e212ac630b0d9754075bb24198da3b` (`Apache-2.0`).

Raw PDFs and upstream source checkouts live in the ignored
`.external/challenge-148/` cache. Their hashes and exact repository revisions
will be copied into the committed provenance manifest, but the raw files and
nested repositories will not be committed.

## Implementation boundaries

All committed work for this challenge stays under:

`tracks/qmc/solutions/frustration-free/challenge-148/`

Run products stay under:

`tracks/qmc/results/frustration-free/challenge-148/<run-id>/`

The challenge owns its own Python, Rust and Julia project files and adapter
code. It does not modify either upstream checkout, the repository-root
`pyproject.toml`, `uv.lock`, common scripts, or the QMC team README.

The implementation is split into five independent components:

1. **Lattice contract**: deterministic triangular and honeycomb periodic graphs,
   canonical bond ordering, validation of degree, bond count, connectivity and
   duplicate-free edges.
2. **ED oracle**: sparse Hamiltonian plus exact thermal traces for small `N`,
   producing energy, transverse magnetization, `<m^2>`, `<m^4>` and `Q_L`.
3. **Primary QMC adapter**: an owned Rust executable linked to the pinned
   QMC_SSE revision, with explicit arbitrary-graph terms, seeded updates and
   immutable raw bins.
4. **Independent QMC adapter**: an owned Julia wrapper around the pinned
   QMC_LTFIM revision. It directly calls the current library API using
   `TFIM(UpperTriangular(Jmatrix), fill(field, N))`, `BinaryThermalState`,
   `Diagnostics`, and the current `mc_step_beta!` signatures. `Jmatrix` has
   `-coupling` only at strict upper-triangle canonical-edge entries, with zero
   diagonal and lower triangle. The wrapper bypasses the broken upstream CLI
   and general-constructor paths, adds no upstream modifications, and emits its
   own immutable raw-bin format.
5. **Analysis and publication**: autocorrelation/binning checks, bootstrap,
   finite-size fits, ratio propagation, figures and atomic, hash-bound result
   publication.

The two QMC routes may share generated graph data and comparison scripts, but
must not share update kernels or estimator implementations.

The Julia adapter independently checks canonical edge ordering, bounds,
self-loop and duplicate exclusion, connectivity, all lattice-specific
length/site/bond/degree invariants, and the embedded graph hash before creating
QMC_LTFIM objects. Its raw bins include nonidentity operator count,
operator-list capacity/time-slice count, cluster attempted/accepted counts, and
the cluster count/size diagnostics available from `Diagnostics`. Common
profiling fields are compared across adapters, while solver-specific
diagnostics remain explicitly adapter-specific.

Both executables expose exactly
`--request PATH --output-directory PATH`. The closed shared request binds its
`schema_version`, `adapter`, `graph_path`, `graph_sha256`, `beta`, `coupling`,
`field`, `seed`, `thermalization_sweeps`, `retained_samples`, `thinning`,
`bin_length`, `checkpoint_bins`, `expected_source_hash`, and
`expected_build_hash` fields, with no additional properties. An adapter
mismatch fails before model construction. Both `retained_samples` and
`bin_length` are positive, `retained_samples` must be divisible by
`bin_length`, and `checkpoint_bins` is a positive integer. Define
`total_bins = retained_samples / bin_length`.

Neither upstream library is assumed to support portable opaque-state
serialization. Restart uses a common deterministic replay checkpoint at
completed-bin boundaries, published under a per-run exclusive lock. Each
adapter independently implements its lock, but must durably publish an
immutable content-addressed run-lock anchor and retain its canonical SHA256 for
the lifetime of the run. The common checkpoint contract binds that
`anchor_sha256`; adapter-specific lock identities, paths and acquisition
mechanisms are not shared. Each completed bin is first written and fsynced,
then atomically renamed to the content-addressed immutable object
`bins/<sha256>.ndjson`. An existing same-hash object is byte-validated and never
overwritten; the `bins/` directory is fsynced after rename.

After its bin objects exist, the adapter publishes immutable checkpoint
generations after each interval of `checkpoint_bins` completed bins and once at
final completion when the final interval is shorter. Generation index `g`
records
`completed_bin_count = min((g + 1) * checkpoint_bins, total_bins)` and contains
exactly that many ordered bin-object hashes. Its shared closed
`qmc-checkpoint-generation-v2` manifest permits only `QMC_SSE` and
`QMC_LTFIM` and binds the adapter's durable run-lock `anchor_sha256`, request,
source and build hashes, seed, completed-bin count, ordered bin-object hashes,
`previous_generation_sha256`, and replay update count. Canonical generation 0
has `previous_generation_sha256 = null` and
`completed_bin_count = min(checkpoint_bins, total_bins)`; every later generation
names the canonical manifest SHA256 of its immediate predecessor.

This is a pre-production breaking contract migration. No v1 production
artifacts exist: `qmc-checkpoint-generation-v1` is unsupported prototype data
and every adapter and consumer rejects it. There is no implicit or automatic
v1-to-v2 migration.

The generation directory identity is the SHA256 of the canonical manifest.
Publication validates every referenced bin object, fsyncs the manifest and
staged generation directory, atomically renames it to
`generations/<generation-hash>/`, and fsyncs `generations/`. If that
content-addressed path already exists, the publisher byte-validates the
existing manifest and referenced generation contents, leaves the published
directory untouched, and archives only its own unpublished staging directory
as an identical loser. It then writes/fsyncs a closed
`qmc-current-generation-v2` temporary current pointer that binds the same
`anchor_sha256`, atomically replaces `current-generation.json`, and fsyncs the
run directory. Thus the current pointer cannot cross lock-anchor identity or
reference a missing generation or bin, and recovery sees at most one published
generation directory for each manifest hash.

A crash before generation publication can leave only unreferenced bin objects;
recovery audits them under the same lock and either adopts a byte-valid object
that deterministic replay identifies as the next expected bin or archives it
as an orphan. A crash after generation rename but before pointer replacement is
recovered by scanning for one unique valid contiguous descendant of current and
advancing the pointer.

If `current-generation.json` is absent, recovery under the exclusive lock scans
published generation directories for fully valid
`previous_generation_sha256 = null` genesis candidates whose request/source/build
bindings match. After deterministic replay byte-verifies each candidate's
ordered retained bins, zero valid manifest hashes means start fresh, exactly
one valid manifest hash is adopted, and more than one distinct valid genesis
manifest hash is a conflict that fails closed. Orphan staging directories are
archived independently and do not participate in genesis selection. Pointer
publication then uses the normal write/fsync/rename/fsync protocol. Conflicting
descendants, ancestry gaps, stale hashes, malformed generations, missing bin
objects, or any ambiguity fail closed and are archived or diagnosed rather
than guessed. Restart reconstructs the RNG and model from the same seed,
replays thermalization and every update through the selected generation's
replay update count, and verifies every retained bin byte-for-byte and by
content hash before continuation. Replay cost is paid only after interruption
and is measured during profiling. The adapters reuse Task 5's durable
publication primitives and invariants where applicable while retaining
independent update kernels, estimators, and adapter implementations.

### Rejected SSE.jl/Carlo.jl route

The earlier StochasticSeriesExpansion.jl/Carlo.jl architecture is rejected for
this challenge revision, not postponed. Its current four-leg abstract-loop
update inserts diagonal vertices and toggles two legs per scatter. For the
same-basis TFIM bond decomposition
`-J ZZ - (h/z)(XI + IX)`, a single-spin-flip off-diagonal vertex cannot be
reached from a diagonal vertex for any tested `energy_offset_factor`.
Independent probes observed zero off-diagonal/transverse counts and results
that disagreed with ED. Rotating the basis would avoid that transition
topology, but would require a new non-diagonal Binder estimator and therefore
would not validate the planned same-basis observables. No prototype from this
route is retained as implementation.

## Staged verification

### Stage 0: literature and software audit

- Search post-2002 work for the same nearest-neighbor ferromagnetic models and
  record whether any result improves the published precision.
- Verify the exact upstream commits and licenses; QMC_SSE arbitrary-graph term
  construction; QMC_LTFIM's direct current library API; estimator access,
  deterministic replay restart and random-seed control.
- Record the StochasticSeriesExpansion.jl/Carlo.jl topology blocker and the
  broken QMC_LTFIM CLI/general-constructor paths as software-audit decisions.
- Reject papers about antiferromagnetic, frustrated, long-range or spin-1
  variants as replacements for the target model.

### Stage 1: lattice and ED oracle

- Unit-test bond counts, degree distributions, periodic wrapping and graph
  isomorphism for small cells.
- Compare sparse ED against an independently constructed dense Hamiltonian.
- Check `h=0`, `J=0`, high-temperature and low-temperature limits.
- Keep exact thermal traces to dimensions that fit comfortably in local
  memory; no large dense calculation is permitted locally.

### Stage 2: two-code QMC acceptance

Before any pilot work, separately validate each finite-temperature QMC adapter
against full thermal ED on triangular
`L = 3` (`N = 9`) and honeycomb `L = 2` (`N = 8`). Validate larger small
systems with sparse ground-state ED on triangular `L = 4` and honeycomb
`L = 3`, without claiming an exact thermal trace. Triangular `L = 2` is
excluded because its tiny periodic cell produces parallel nearest-neighbor
bonds rather than the simple-graph contract used in production. Then run the
QMC-only crossing pilot at `L = 4, 6, 8`, selected `beta/L` values and fields
near the published critical points:

- compare the primary QMC_SSE and independent QMC_LTFIM thermal outputs
  separately with ED on the tractable cells;
- require the same Hamiltonian normalization and observable definitions;
- independently require acceptance for energy, transverse magnetization,
  `<m^2>`, `<m^4>` and `Q_L` from each code; passing one code cannot compensate
  for failure of the other;
- for every primary observable require an absolute normalized residual no
  larger than 4 combined standard errors, and require the median normalized
  residual across the acceptance matrix no larger than 1.5;
- require the retained bin length to be at least ten estimated integrated
  autocorrelation times; require independent-chain means and the first/second
  retained halves to agree within their combined 3-sigma intervals;
- verify `beta/L` convergence before interpreting crossing behavior.

Failure to match ED blocks all production runs.

### Stage 3: profiling

Profile `L = 8, 16, 24` and record:

- sweeps per second and common run/performance statistics, plus each adapter's
  available solver-specific operator and cluster diagnostics;
- integrated autocorrelation time and effective sample count;
- peak resident memory, generation/pointer size and interrupted-run replay time;
- MPI/independent-chain throughput;
- projected resources needed for the target uncertainty.

Any projected run longer than ten minutes or larger than 16 GiB is submitted
through the cluster profile. Cluster job names start with `ch148-`, and no
other challenge's jobs or result directories are touched.

### Stage 4: production and finite-size scaling

Only after profiling passes, generate a pre-registered grid with multiple
system sizes, fields, independent chains and `beta/L` values. The anticipated
upper range is `L <= 96`, but the measured profile determines the actual grid.

The primary fit follows the paper:

`Q_L(h) = Q + a1 delta_h L^yt + a2 delta_h^2 L^(2yt) + b1 L^yi + ...`

with `delta_h = h - h_c`, 3D Ising exponents as the fixed primary model, and
documented alternatives that vary the fit window, `L_min`, correction terms
and selected exponents. Crossing-point extrapolation is an independent
analysis, not a replacement for the global fit.

Bootstrap samples preserve complete Markov-chain bins. For every bootstrap
replicate, fit both critical fields and form
`R = h_c(triangular) / h_c(honeycomb)` directly. Statistical uncertainty and
fit-choice systematic uncertainty are reported separately and combined by a
declared rule.

## Pre-registered interpretation

- If `sigma_R > 1.2e-5`, report the achieved precision and no decisive verdict.
- If `|R - sqrt(5)| <= 2 sigma_R`, report that the conjecture survives the
  numerical test; do not claim an exact proof.
- If the difference is statistically decisive, report rejection with the
  signed deviation and significance.
- A conclusion requires both lattice fits to pass convergence, fit-window and
  independent-code checks. A precise ratio formed from individually unstable
  critical fields is invalid.

## Reproducibility and failure policy

Every run consumes canonical graph JSON whose embedded hash is verified before
model construction and records the Pauli Hamiltonian convention, graph hash,
executable and dependency versions, Git revision, upstream code revisions,
seeds, parameters, host/Slurm metadata and SHA256 hashes. The two adapters use
deterministic, distinct seeds. Raw bins are immutable and adapter-specific;
summaries and current pointers are published atomically only after schema and
semantic validation.

Jobs emit progress and diagnostics throughout the run. Partial, timed-out,
non-finite, unconverged or provenance-mismatched outputs are retained as failed
audit artifacts and are never silently treated as completed cells.

## Deliverables

- literature audit with model-matching exclusions;
- tested lattice generator and ED oracle;
- two QMC adapters with small-system acceptance evidence;
- profiling report and cluster resource plan;
- raw-bin and analysis schemas with integrity checks;
- critical-point crossing and finite-size-scaling figures;
- ratio verdict with statistical and systematic uncertainty;
- one-command environment setup, pilot reproduction and final analysis;
- concise README and challenge report that distinguish pilot evidence from a
  completed high-precision result.
