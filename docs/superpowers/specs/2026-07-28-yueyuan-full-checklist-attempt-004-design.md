# YueYuan Full Checklist Attempt 004 Design

## Goal

Build `attempt-004` as the full challenge #113 research artifact: a reproducible sim-to-real quantum gate calibration pipeline that satisfies the checklist in `/Users/yueyuan/Downloads/challenge_113_codex_spec.md`, produces figures and a short report, updates PR #203, and verifies locally plus on HPC CPU/GPU resources when safe.

## Current Context

Attempt 003 is an accepted prototype, not a full checklist solution. It provides a toy two-qubit CZ model, finite-difference Hessian geometry, finite-shot noisy scalar evaluations, Nelder-Mead-style closed-loop search, five seeds, two mismatch gaps, and public validator score `3.235294117647059`.

The missing checklist items are the full differentiable open-loop model, automatic differentiation and gradient tests, strict query-only device boundary, model-only baseline, at least two system sizes, at least three mismatch gaps, at least three shot budgets, error bars, generated plots, reproducible run records, a short report, and HPC-scale verification.

## Scope

Create a new package under:

`tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/`

The package will include:

- one-qubit and two-qubit Hamiltonian models;
- piecewise-constant pulse parameterization;
- JAX-based differentiable dynamics, fidelity, gradients, Hessian, and HVPs;
- gradient-based open-loop model optimization;
- Hessian eigenspace extraction with spectrum output;
- strict noisy query-only true-device interface;
- derivative-free closed-loop methods and baselines;
- local smoke sweeps and full HPC-capable sweeps;
- machine-readable records, plotting scripts, Slurm scripts, and report text.

The package will not use real quantum hardware. HPC is a verification and parameter-scan accelerator only.

## Non-Goals

- No credential storage in files, commits, Slurm scripts, logs, or PR text.
- No uncontrolled HPC job fan-out.
- No hidden exact fidelity access inside derivative-free optimizers.
- No tuning on final reported seeds after inspecting results.
- No large raw result files committed to git.
- No replacement of existing attempts; attempt 003 remains as a historical prototype.

## Dependencies

The differentiable path requires JAX. Attempt 004 will include an explicit `requirements.txt`:

- `jax`
- `jaxlib`
- `numpy`
- `scipy`
- `matplotlib`
- `pytest`

Local tests will fail fast with a clear message if JAX is unavailable. The full checklist is considered incomplete until JAX-backed gradient and Hessian tests pass either locally or in a recorded HPC environment.

## Architecture

### Package Files

- `config.py`: immutable dataclasses for system, optimizer, sweep, shot, and mismatch configuration.
- `systems.py`: one-qubit and two-qubit target gates, Pauli bases, drift/control Hamiltonians, and controlled true-device perturbations.
- `pulses.py`: piecewise-constant pulse packing, unpacking, bounds, random initialization, and deterministic seed handling.
- `dynamics.py`: JAX time evolution using segment-wise matrix exponentials and phase-insensitive gate infidelity.
- `open_loop.py`: gradient-based model optimization with saved loss and gradient-norm history.
- `hessian.py`: dense Hessian, Hessian-vector product, leading eigenspace extraction, orthonormality checks, and small-system dense/HVP cross-checks.
- `device.py`: strict `QueryOnlyDevice.query(pulse_parameters, shots, seed=None) -> float` interface with private true model, finite-shot noise, query count, and shot count.
- `optimizers.py`: derivative-free optimizers, starting with common-budget Nelder-Mead and optional coordinate polling for robustness.
- `baselines.py`: model-only evaluation, full-space search, random-subspace search, and Hessian-subspace search.
- `experiments.py`: sweep runner that emits one JSONL record per method/system/gap/shot/k/seed combination.
- `analysis.py`: aggregation of median, interquartile range, success rate, query counts, shot counts, and failure labels.
- `plotting.py`: seven required figures using committed scripts and ignored generated image outputs.
- `run_local_smoke.py`: small deterministic run used in normal tests and PR verification.
- `run_full_sweep.py`: full sweep entry point for local or Slurm execution.
- `make_figures.py`: regenerate figures from ignored JSONL results.
- `run_candidate.py`: produce a compact `submission.json` compatible with the existing local validator when possible.
- `README.md`: reproduction instructions.
- `REPORT.md`: short report covering model, fidelity definition, Hessian extraction, black-box device, baselines, fairness, central result, failure case, limitations, and next steps.
- `slurm/cpu_sweep.sbatch`: conservative CPU array sweep.
- `slurm/gpu_verify.sbatch`: single-GPU verification job.
- `slurm/README.md`: HPC usage notes and resource caps.

### Test Files

Create:

- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py`
- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py`
- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py`
- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py`
- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py`
- `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

These tests will use tiny settings so they run locally without HPC.

## Data Flow

1. Load a system configuration for either `one_qubit_x` or `two_qubit_cz`.
2. Build the differentiable model Hamiltonian and target gate.
3. Optimize open-loop pulse parameters on the differentiable model with JAX gradients.
4. Save optimization history and final model fidelity into ignored run records.
5. Compute the model Hessian or HVP at the model optimum.
6. Extract leading eigenpairs and save the Hessian spectrum.
7. Build true-device variants by applying controlled model-truth perturbations.
8. Wrap each true device in `QueryOnlyDevice`.
9. Run model-only, full-space, random-subspace, and Hessian-subspace methods with identical target fidelity, seed sets, query budgets, shot budgets, and stopping rules unless explicitly justified in the report.
10. Record every submitted pulse as one query and every finite-shot evaluation as consumed shots.
11. Use a separate audit evaluator after each run to compute final exact true fidelity for reporting. This evaluator is not passed to derivative-free optimizers.
12. Aggregate results into tables and figures.

## Systems

### One-Qubit Target

- Target: `X` gate.
- Hilbert dimension: `d = 2`.
- Benchmark curvature rank: `d^2 - 1 = 3`.
- Pulse dimension: 16 raw parameters from 8 time segments and 2 controls.
- Required role: small-system gradient, Hessian, HVP, and rank sanity checks.

### Two-Qubit Target

- Target: `CZ` gate.
- Hilbert dimension: `d = 4`.
- Benchmark curvature rank: `d^2 - 1 = 15`.
- Pulse dimension: 48 raw parameters from 12 time segments and 4 controls.
- Required role: main headline sim-to-real calibration benchmark.

The implementation will measure effective Hessian rank from the spectrum using an explicit threshold rather than forcing the observed rank to equal `d^2 - 1`.

## Open-Loop Model Optimization

The model optimization will use gradient descent with Adam-style moments implemented directly in JAX/NumPy-compatible code. Each run records:

- optimized pulse parameters;
- final model fidelity and infidelity;
- loss history;
- gradient-norm history;
- final propagator;
- system configuration;
- optimizer configuration;
- seed.

Open-loop success for the model stage requires final model infidelity below `1e-4` for the smoke configuration and below `1e-3` for full sweep configurations.

## Hessian Extraction

For the one-qubit model, the package will compute both:

- dense Hessian with `jax.hessian`;
- HVP with `jax.jvp(jax.grad(loss), ...)`.

For the two-qubit model, the smoke path will compute a dense Hessian because the pulse dimension is 48. The full path may use dense Hessian or HVP plus `scipy.sparse.linalg.eigsh` depending on runtime.

Checks:

- dense Hessian symmetry;
- HVP matches dense multiplication on the one-qubit system;
- leading eigenvectors are orthonormal;
- eigenpairs satisfy `H @ v ~= lambda * v`;
- spectrum is saved for plotting.

## Strict Query-Only Device

`QueryOnlyDevice` exposes only:

```python
query(pulse_parameters, shots: int, seed: int | None = None) -> float
query_count -> int
shot_count -> int
```

The optimizer receives only the noisy scalar return value. It cannot inspect:

- true Hamiltonian;
- hidden perturbation parameters;
- true gradients;
- true Hessian;
- exact fidelity;
- audit evaluator.

The class will store hidden model-truth perturbations in private attributes, and tests will verify that the public interface does not expose them. Because Python privacy is conventional, the report will state this as a software boundary rather than a security boundary.

Finite-shot estimates use binomial sampling:

`n_success ~ Binomial(shots, F_true)`, `F_hat = n_success / shots`.

The main optimization objective will be noisy infidelity, `1 - F_hat`.

## True-Device Mismatch

Each system will support three mismatch levels:

- `small`: mild drift and control-amplitude perturbation.
- `medium`: larger drift, control-amplitude perturbation, and crosstalk.
- `large`: medium perturbations plus a rotated or new error channel that can move relevant directions outside the fixed Hessian subspace.

The full report will include at least one failure mode where fixed Hessian-subspace optimization fails or loses its advantage. The first planned failure case is the large two-qubit rotated-channel mismatch at too-small `k`.

## Closed-Loop Methods

All methods share:

- starting pulse: the model-optimized pulse;
- derivative-free optimizer family: Nelder-Mead for comparable continuous searches;
- maximum query budget;
- shots per query;
- target true-device infidelity threshold;
- seed set;
- stopping rule;
- parameter bounds.

Methods:

- `model_only`: evaluate the model-optimized pulse on the true device without closed-loop refinement.
- `full_space_nelder_mead`: optimize all raw pulse parameters.
- `random_subspace_nelder_mead`: optimize coefficients in a reproducible random orthonormal `k`-dimensional subspace.
- `hessian_subspace_nelder_mead`: optimize coefficients in the top `k` model-Hessian eigenvector subspace.

The random subspace baseline will be a true random orthonormal subspace, not tilted toward Hessian directions.

## Sweeps

### Search Dimension

One-qubit:

- `k = 0, 1, 2, 3, 4, 8, 16`

Two-qubit:

- `k = 0, 3, 5, 8, 10, 15, 20, 24, 32, 48`

The dimension sweep must identify too-small plateau behavior, the query-efficient regime, and degradation or loss of advantage when `k` is unnecessarily large.

### Model-Truth Gap

Run:

- `small`
- `medium`
- `large`

Each level maps to a reproducible numerical perturbation configuration recorded in each result row.

### Shot Budget

Run:

- `128`
- `512`
- `2048`

These are lower than the example in the checklist but still form three finite-shot regimes and keep local/HPC cost practical. The report will compare both queries-to-target and total shots-to-target.

### Seeds

Use:

- smoke: seeds `0, 1`;
- full local/HPC sweep: seeds `0, 1, 2, 3, 4, 5, 6, 7`.

The reported tables will use median and interquartile range, plus success rate. No best-seed-only reporting is allowed.

## Figures

Generated figures will be written under:

`tracks/qcs/results/YueYuan/attempt-004/figures/`

The script `make_figures.py` will produce:

1. `model_optimization_history.png`
2. `hessian_spectrum.png`
3. `queries_to_target_vs_k.png`
4. `shots_to_target_vs_k.png`
5. `advantage_vs_gap.png`
6. `success_rate_vs_shots.png`
7. `failure_mode.png`

The figures are generated artifacts and stay out of git. The committed report will describe the latest generated figures and their paths.

## Machine-Readable Results

Ignored generated data will live under:

`tracks/qcs/results/YueYuan/attempt-004/`

Records:

- `runs.jsonl`: one row per method/system/gap/shot/k/seed run.
- `open_loop_history.jsonl`: one row per open-loop iteration sample.
- `hessian_spectra.json`: eigenvalues and rank summaries.
- `summary.json`: aggregate medians, IQRs, success rates, and headline speedups.
- `hpc_environment.json`: environment metadata from successful HPC jobs, with no credentials.

Each run row includes:

- method;
- system size;
- target gate;
- pulse dimension;
- subspace dimension;
- mismatch name and numerical parameters;
- shots per query;
- query budget;
- seed;
- optimization history summary;
- queries to target;
- total shots to target;
- final fidelity;
- success/failure status.

## Report

`REPORT.md` will include:

- model and target gates;
- pulse ansatz;
- fidelity definition;
- open-loop optimization method;
- Hessian extraction method;
- black-box device construction;
- baselines;
- fairness rules;
- statistical protocol;
- central query and shot results;
- failure-mode analysis;
- limitations;
- next steps;
- local and HPC verification commands.

The report will distinguish clearly between:

- public validator score;
- simulated gate fidelity;
- query-speedup metrics;
- total-shot metrics.

## HPC Design

HPC usage happens only after local tests and smoke runs pass.

Before submitting jobs, inspect existing user Slurm examples without copying secrets:

- search for recent `.sbatch`, `.slurm`, and shell launch scripts under the user's home and project directories;
- read only scheduler options, module-loading style, environment setup, and output-path conventions;
- do not record credentials in any committed file.

Resource caps:

- CPU sweep uses Slurm arrays with throttling so total concurrent CPU cores never exceed 200.
- Default CPU array design: `--cpus-per-task=4` and `--array=0-N%25`, giving at most 100 concurrent CPU cores unless the script is edited deliberately.
- GPU verification uses `--gres=gpu:1` and `--array=0-N%1`, giving at most one GPU job at a time.
- The scripts will set conservative wall times and write logs/results under ignored result directories.

HPC outputs:

- raw sweep JSONL copied back into `tracks/qcs/results/YueYuan/attempt-004/`;
- logs kept in ignored result folders;
- summarized environment metadata committed only if it contains no account names, hostnames, paths containing usernames, tokens, or secrets.

The final PR will report whether HPC verification ran. If cluster access fails, the report will include local verification and a clear note that HPC verification was not completed.

## Validation and Testing

Local validation commands:

- `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q`
- `python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py --out tracks/qcs/results/YueYuan/attempt-004/smoke`
- `python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py --results tracks/qcs/results/YueYuan/attempt-004/smoke`
- existing validator tests and self-test must continue to pass.

Attempt 004 completion requires:

- model tests pass;
- gradient tests pass;
- Hessian tests pass;
- device boundary tests pass;
- reproducibility tests pass;
- local smoke sweep produces all required figure files;
- full or reduced full sweep produces at least one accepted evidence set for all required dimensions, gaps, shots, and seeds;
- PR #203 body is updated with checklist coverage and verification notes.

## Checklist Coverage

- Differentiable model implemented: `dynamics.py`.
- Open-loop pulse optimization works: `open_loop.py`.
- Gradient validated against finite differences: `test_attempt_004_gradients.py`.
- Hessian or HVP implemented: `hessian.py`.
- Leading Hessian eigenspace extracted: `hessian.py`.
- Strict query-only true device implemented: `device.py`.
- Finite-shot noise implemented: `device.py`.
- Query and shot counters implemented: `device.py`.
- Model-only baseline implemented: `baselines.py`.
- Full-space black-box baseline implemented: `baselines.py`.
- Random-subspace baseline implemented: `baselines.py`.
- Hessian-subspace method implemented: `baselines.py`.
- Search-dimension sweep completed: `experiments.py` and `summary.json`.
- Model-truth gap sweep completed: `experiments.py` and `summary.json`.
- Shot-budget sweep completed: `experiments.py` and `summary.json`.
- At least two system sizes tested: `one_qubit_x` and `two_qubit_cz`.
- Multiple seeds and error bars reported: `analysis.py`, `REPORT.md`, and figures.
- Queries-to-target headline plot produced: `queries_to_target_vs_k.png`.
- Total-shots-to-target reported: `shots_to_target_vs_k.png` and `summary.json`.
- At least one failure case analyzed: `failure_mode.png` and `REPORT.md`.
- Reproducible configuration and instructions provided: `README.md`, `config.py`, and Slurm scripts.
- Short report or notebook completed: `REPORT.md`.
- Pull request updated with final artifact: PR #203 update after verification.

## Risks and Mitigations

- JAX availability: include `requirements.txt`, fail fast in tests, and record environment metadata from local/HPC runs.
- Runtime cost: keep tests tiny, separate smoke/full sweeps, and use Slurm array throttling.
- Numerical instability near high fidelity: use phase-insensitive fidelity, unitarity checks, bounded pulse updates, and documented tolerances.
- Leaky device boundary: pass only the `query` callable to optimizers and keep exact audit evaluation outside optimizer objects.
- Unfair baselines: centralize method configuration so budgets, seeds, shots, targets, and stopping rules are shared.
- Weak scientific claim: report both wins and losses, including the large-mismatch failure case.
- Secret leakage: scan committed files and PR body for credential markers before push.

## Self-Review

- Placeholder scan: no placeholder text remains.
- Internal consistency: package path, result path, systems, sweeps, methods, and figure names are used consistently.
- Scope check: this is intentionally large but still one coherent research artifact centered on attempt 004.
- Ambiguity check: JAX is required for checklist completion; NumPy helpers do not replace autodiff requirements.
- HPC safety check: resource caps and no-credential rules are explicit.
