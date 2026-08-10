# Challenge 15 Production Execution Design

## 1. Scope and claim boundary

The formal variational calculation is JAX x64 coordinate-space VMC sampling

```text
|Psi_{L,M=0}(z)|^2 product_i dOmega_i/(4 pi),  L in {0,2},
```

on Qdeshell A800 GPUs. Exact occupation-space ED and determinant-coefficient
evaluation are acceptance oracles only. The existing
`train_joint_sectors` routine uses generated coordinate batches and remains a
smoke/API test; it cannot produce a production result.

All `N=6,7,8` results remain pending until every immutable scientific,
statistical, provenance, runtime, and prerequisite gate passes. Acceptance
establishes finite-size lowest-`L=2` sector gaps only. It is not a
chiral-graviton, thermodynamic-limit, or scalability claim.

## 2. Immutable policy

One canonical policy payload in an envelope whose sole `schema` value is
`challenge15.production-policy.v1` is generated from code-owned constants and
canonicalized as sorted, finite JSON. Its exact payload fields are:

```text
physics
model
estimator
seed_policy
rank_policy
exact_acceptance
vmc_diagnostics
artifact_schemas
runtime_roles
transfer_policy
finalization_policy
claim_policy
```

The payload contains:

- `physics`: `two_q_formula="3*(N-1)"`, chord Coulomb distance,
  `energy_unit="E_C"`, and sectors `[0,2]`;
- `model`: one shared parameter tree, exact `M=0` carriers, exact projector,
  and prohibition of determinant-indexed trainable arrays;
- `estimator`: score-covariance finite-chain estimator, bare-potential
  sampling variance label, and prohibition on calling it `Var(H_LLL)`;
- `seed_policy`: exact seeds `[0,1,2,3,4]`, complete coverage at every expected
  rank, identical paired seed sets at adjacent ranks, and at least four
  accepted final-rank seeds;
- `rank_policy`: consecutive doubling, two final passing transitions,
  `|delta E_L|+2 sigma_diff <= 1e-4 E_C`,
  `|delta Delta_2|+2 sigma_diff <= 0.002 |Delta_2|`, and overlap change at
  most `1e-3`;
- `exact_acceptance`: all gates from `DESIGN.md` Section 12, including exact
  error below `min(1e-4 E_C,0.01 Delta_2)`, gap agreement within `1%`, overlap
  at least `0.99`, quadrature change at most `1e-11`, target-`L` residual at
  most `1e-10`, and every Hilbert/gauge/Hamiltonian/model structural gate;
- `vmc_diagnostics`: values in Section 7.4 below;
- `artifact_schemas`: every schema name and version in Section 5;
- `runtime_roles`: exact role set `training`, `coordinate`, `oracle`, `exact`,
  and `reducer`;
- `transfer_policy`: create-only bundle/import rules and approved roots;
- `finalization_policy`: expected-rank versioning and immutable selection;
- `claim_policy`: prerequisite order `N=6 -> N=7 -> N=8`, pending behavior,
  and prohibited chirality/thermodynamic wording.

`policy_sha256` is SHA256 of the canonical payload bytes, not a hand-entered
identifier. Every source manifest, runtime attestation, configuration,
generation, evaluation, reduction, prerequisite, and report records this exact
digest. Unknown policy fields or configurable acceptance thresholds fail
closed.

## 3. Runtime lifecycle

### 3.1 Candidate runtime, before implementation

The first implementation task creates candidate CPython 3.12 wheelhouses and
local compatibility tests only. It does not create an allowed-runtime
attestation and does not claim cluster compatibility.

Both profiles pin:

```text
CPython ABI: cp312
Python version: 3.12
platform: manylinux2014_x86_64
jax==0.4.38
jaxlib==0.4.38
flax==0.10.2
optax==0.2.4
numpy==1.26.4
scipy==1.12.0
sympy==1.13.3
h5py==3.10.0
pytest==8.3.4
```

The CUDA profile is resolved from
`jax-cuda12-plugin[with-cuda]==0.4.38`; its lock explicitly includes
`jax-cuda12-plugin`, `jax-cuda12-pjrt`, and every resolved NVIDIA CUDA 12
runtime wheel with exact versions and SHA256 hashes. No system CUDA toolkit is
assumed.

Wheel download is constrained by:

```text
--platform manylinux2014_x86_64
--implementation cp
--python-version 312
--abi cp312
--only-binary=:all:
```

The builder rejects sdists, unrequested extras, non-cp312/non-abi3 Python
wheels, wheels outside the manylinux2014 compatibility floor, duplicate
projects, and files absent from the hash lock. Offline install uses
`pip --no-index --require-hashes --only-binary=:all:`.

### 3.2 Source freeze and final attestation

All implementation source tasks, tests, runtime scripts, schemas, CLI, Slurm
profiles, and local smoke tests complete before final attestation. A source
manifest then hashes:

```text
src/**/*.py
production/**/*.py
production/**/*.json
production/**/*.sh
production/**/*.sbatch
production/runtime/**/*.txt
production/runtime/**/*.in
tests/**/*.py
pyproject.toml
uv.lock
```

Generated wheel binaries, target smoke receipts, and allowed-runtime manifests
are excluded to avoid self-reference. The manifest records the Git revision,
requires a clean tracked tree, and is immutable.

CPU and CUDA target-node smoke then run against that exact source manifest.
Each creates an envelope with
`schema="challenge15.allowed-runtime.v1"` and these payload fields:

```text
profile
role
controller
python_version
python_abi
platform_tag
minimum_glibc
packages
wheel_sha256
source_manifest_sha256
policy_sha256
backend
x64_enabled
device_platforms
cuda_driver
smoke_payload_sha256
attestation_test_members
attested_hostname_class
attested_at_utc
```

`role` is exactly one of `training`, `coordinate`, `oracle`, `exact`, or
`reducer`; `controller` is exactly `qdeshell`, `lasg02`, or `wuzh02`. The
attested profile/controller/role combination is immutable and validators reject
missing, swapped, or copied controller identities.

`attestation_test_members` is an ordered nonempty list of
`{nodeid,test_file_sha256,result_sha256}` for every compatibility/smoke test
required by that role. Immediately before any production execution,
`VERIFY_INPUTS` rehashes every source-manifest member and each listed test file,
validates every recorded test result against the allowed-runtime envelope, and
rejects a missing/extra member or any digest mismatch.
Every Slurm wrapper repeats the same verification immediately before invoking
its scientific CLI, using its controller-local runtime-set path.

CPU requires backend `cpu`; CUDA requires backend `gpu` and an
`NVIDIA A800 80GB PCIe` device. Smoke covers imports, `jax.jit`, complex128,
Pfaffian value/JVP, projection, batched amplitudes, rank embedding, optimizer
serialization, shard verification, and a tiny VMC update/final evaluation.

Any tracked source change after source-manifest creation invalidates every
role/controller attestation and requires rebuilding the source manifest and
rerunning every target smoke. Deployment and scientific execution are
forbidden before the required role/controller attestations validate.

## 4. Cluster profiles and resource placement

### 4.1 Qdeshell GPU profile

The tracked profile and every GPU wrapper use exactly:

```text
partition=dzagnormal
account=giggleliu
qos=user_jiangweiqi
nodes=1
ntasks=1
gres=gpu:NVIDIAA80080GBPCIeLC:1
cpus_per_task=8
mem=60000M
time=24:00:00
array training=0-4%5
DefMemPerCPU=7897M
approved project=/work/share/giggleliu/jiangweiqi/quantum.harness
approved results=/work/share/giggleliu/jiangweiqi/results/challenge15
```

Formal VMC training and independent post-training coordinate evaluation run
here. `sacctmgr` verifies account `giggleliu`, partition `dzagnormal`, and QOS
`user_jiangweiqi`; the exact GPU shape above passes `sbatch --test-only`.
CPU-only jobs on `dzagnormal` are rejected by QOS. Oracle, exact, reducer, and
report CPU roles therefore run only on LASG02 or an attested WUZH02, with
create-only cross-cluster transfer between controllers.

### 4.2 LASG02 CPU profile

The tracked profile and every LASG02 wrapper use exactly:

```text
partition=ihicnormal
account=chenkun2025
qos=user_student090
nodes=1
ntasks=1
cpus_per_task=24
mem=80000M
time=24:00:00
array exact evaluation=0-14%1
approved project=/public/home/student090/quantum.harness
approved results=/public/home/student090/results/challenge15
```

LASG02 is the first target for `N=6` and `N=7` oracle/exact work.

### 4.3 WUZH02 profile gate

No audited WUZH02 scheduler profile currently exists in the repository.
Before any WUZH02 command is generated, an implementation task must collect
`scontrol`, `sacctmgr`, filesystem, CPU, memory, wall-time, and offline-runtime
facts; create `production/slurm/profiles/wuzh02.json`; validate it against
`challenge15.cluster-profile.v1`; and commit it before source freeze. The
profile must expose at least 128 cores and approximately 515 GB for `N=8`.
Until that exact profile passes tests and final CPU attestation, WUZH02 and
`N=8` are blocked. No partition, account, QOS, root, or memory request is
guessed.

### 4.4 Threading and scratch

GPU jobs export `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`,
`OPENBLAS_NUM_THREADS=8`, and `NUMEXPR_NUM_THREADS=8`. LASG02 jobs export each
as `24` and set
`XLA_FLAGS=--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=24`.
Every wrapper validates the scheduler fields at runtime.

Scratch uses `$SLURM_TMPDIR/challenge15-$SLURM_JOB_ID-$SLURM_ARRAY_TASK_ID`
when `$SLURM_TMPDIR` exists and is writable. Otherwise it uses a create-only
directory beneath the profile's approved results root:
`scratch/job-$SLURM_JOB_ID-task-$SLURM_ARRAY_TASK_ID`. `realpath` must remain
under the approved root; existing paths, symlinks, `/tmp`, `$HOME`, and
unapproved roots are rejected. Verified outputs are never deleted by traps.

Every wrapper must pass `sbatch --test-only` before real submission.

Every production wrapper accepts one validated deployment receipt, extracts
its absolute `interpreter` path, requires `realpath` beneath the receipt's
deployment root, recomputes the interpreter SHA256 plus Python/package/backend
fingerprint, and compares all values with the receipt and required role
attestation. It then executes `"$INTERPRETER" -m challenge15.cli ...`. Bare
`python`, `python3`, and `python3.12` are forbidden in production wrappers.

Deployment itself is create-only: upload to
`<deployment>.partial.<bundle_sha256>.<uuid>`, verify the bundle and
`SHA256SUMS`, install offline, fingerprint the absolute interpreter, then
atomically rename to the final content-addressed deployment root and publish a
deployment receipt. After all target attestations, the orchestrator repeats
`git status --porcelain --untracked-files=all`, rejects any output, and
recomputes every source-manifest member hash before deployment.

## 5. Artifact model

All scientific artifacts are strict finite canonical JSON plus
content-addressed blobs. Artifact payloads bind `policy_sha256`,
`source_manifest_sha256`, role/controller-indexed `runtime_attestations`,
`base_configuration_sha256`, and all parent/input hashes.

`runtime_attestations` is controller-indexed under exactly these role keys:

```text
training:   {qdeshell: <sha256>}
coordinate: {qdeshell: <sha256>}
oracle:     {<cpu_controller>: <sha256>}
exact:      {<cpu_controller>: <sha256>}
reducer:    {<cpu_controller>: <sha256>}
```

Values are allowed-runtime envelope SHA256 values. A per-size attestation set
selects Qdeshell for `training`/`coordinate`, LASG02 for all CPU roles at
`N=6,7`, and WUZH02 for all CPU roles at `N=8`; it retains controller names and
does not copy a CPU hash between controllers. A producer verifies the exact
role/controller pair that created every input. A singular runtime digest or
role-only map is forbidden.

### 5.1 Schema inventory

```text
challenge15.production-policy.v1
challenge15.source-manifest.v1
challenge15.allowed-runtime.v1
challenge15.runtime-attestation-set.v1
challenge15.runtime-set-copies.v1
challenge15.runtime-set-publication-receipt.v1
challenge15.attestation-bootstrap-transfer.v1
challenge15.cluster-profile.v1
challenge15.production-oracle.v1
challenge15.seed-owner.v1
challenge15.rank-extension.v1
challenge15.rank-extension-decision.v1
challenge15.training-attempt.v1
challenge15.training-snapshot.v1
challenge15.training-generation.v1
challenge15.recovery-receipt.v1
challenge15.resource-override.v1
challenge15.identity-map.v1
challenge15.submission-receipt.v1
challenge15.orchestration-state-key.v1
challenge15.orchestration-attempt-intent.v1
challenge15.orchestration-transition.v1
challenge15.orchestration-state-manifest.v1
challenge15.output-promotion.v1
challenge15.export-bundle.v1
challenge15.import-bundle.v1
challenge15.transfer-receipt.v1
challenge15.dry-run-receipt.v1
challenge15.deployment-receipt.v1
challenge15.exact-evaluation-shard.v1
challenge15.coordinate-evaluation-shard.v1
challenge15.evaluation-receipt.v1
challenge15.size-result.v1
challenge15.reduction-receipt.v1
challenge15.reduction-finalization.v1
challenge15.terminal-selection.v1
challenge15.cross-size-manifest.v1
challenge15.final-report.v1
challenge15.report-receipt.v1
```

Every artifact uses the exact envelope:

```text
schema, payload, payload_sha256
```

`schema` exists only at envelope level. It is forbidden inside `payload` or
any nested payload object. Every single-size scientific payload begins with:

```text
policy_sha256, source_manifest_sha256, runtime_attestations,
base_configuration_sha256, particles
```

Aggregate `cross-size-manifest`, `final-report`, and `report-receipt` payloads
are explicitly exempt from singular `particles` and
`base_configuration_sha256`. They instead require
`particles=[6,7,8]` and `base_configuration_sha256_by_size` with exactly keys
`"6"`, `"7"`, and `"8"`. They still carry `policy_sha256`,
`source_manifest_sha256`, and the controller-indexed runtime provenance
specified by their schema.

Schema-specific fields are exact:

- `production-oracle`: `sphere_spec`, `physical_conventions`,
  `coulomb_builder_diagnostics`, `sector_summaries`, `low_energy_scan`,
  `array_manifest`, `gate_metrics`;
- `runtime-attestation-set`: `set_name`, `particles`, `roles`; `roles` contains
  exactly `training`, `coordinate`, `oracle`, `exact`, `reducer`, and each role
  contains exactly `controller`, `allowed_runtime_sha256`,
  `deployment_receipt_sha256`, `backend`;
- `runtime-set-copies`: `particles`, `payload_sha256`, `role_map_sha256`,
  `local_path_identity`, `local_sha256`, `cpu_controller`,
  `cpu_remote_path_identity`, `cpu_remote_sha256`,
  `cpu_resolving_receipt_sha256`, `gpu_controller`,
  `gpu_remote_path_identity`, `gpu_remote_sha256`,
  `gpu_resolving_receipt_sha256`;
- `runtime-set-publication-receipt`: `controller`,
  `deployment_receipt_sha256`, `controller_local_path_identity`,
  `payload_sha256`, `role_map_sha256`, `source_manifest_sha256`,
  `policy_sha256`, `published_at_utc`;
- `attestation-bootstrap-transfer`: `source_controller`,
  `destination_controller`, `role`, `allowed_runtime_sha256`,
  `source_manifest_sha256`, `policy_sha256`,
  `source_deployment_receipt_sha256`,
  `destination_deployment_receipt_sha256`,
  `export_bundle_sha256`, `import_bundle_sha256`, `verified_at_utc`;
- `seed-owner`: `seed`, `experiment_id`, `base_configuration_sha256`,
  `expected_seed_set`, `owner_uuid`, `claimed_at_utc`, `claim_host`,
  `claim_process`, `claim_nonce_sha256`;
- `rank-extension-decision`: `seed`, `current_rank`, `new_rank`,
  `prior_expected_ranks_sha256`, `prior_reduction_sha256`,
  `prior_finalization_sha256`, `prior_import_receipt_sha256`,
  `prior_transfer_receipt_sha256`, `decision`, `reason`, `decision_metrics`;
- `training-attempt`: `seed`, `rank`, `attempt_id`, `owner_sha256`,
  `extension_sha256`, `started_from_snapshot_sha256`, `resource_override`,
  `status`;
- `training-snapshot`: `seed`, `rank`, `attempt_id`, `step`,
  `parameter_sha256`, `optimizer_state_sha256`, `walker_state_sha256`,
  `log_amplitude_sha256`, `prng_state_sha256`, `proposal_state`,
  `diagnostics`;
- `training-generation`: `seed`, `rank`, `attempt_sha256`,
  `extension_sha256`, `parent_generation_sha256`,
  `parent_parameter_sha256`, `parent_optimizer_state_sha256`,
  `parameter_sha256`, `optimizer_state_sha256`, `terminal_snapshot_sha256`,
  `training_metrics`;
- `resource-override`: `seed`, `rank`, `extension_sha256`,
  `base_configuration_sha256`, `attempt_sha256`, `reason`,
  `walker_microbatch`, `carrier_block`, `quadrature_block`,
  `fixed_schedule_sha256`;
- `recovery-receipt`: `seed`, `rank`, `attempt_sha256`,
  `stale_lock_sha256`, `scheduler_query`, `scheduler_state`,
  `recovered_by`, `recovered_at_utc`;
- `identity-map`: `stage`, `particles`, `expected_ranks`,
  `expected_ranks_sha256`, `expected_seeds`, `task_count`, `tasks`,
  `array_concurrency`; each task contains exactly `array_index`, `rank`,
  `seed`, `input_sha256`, `output_relative_path`;
- `submission-receipt`: `stage`, `identity_map_sha256`, `profile_sha256`,
  `interpreter_sha256`, `submitted_at_utc`, `controller`,
  `scheduler_job_id`, `array_spec`, `dependency_mode`, `correlation_id`,
  `scheduler_job_name`, `scheduler_comment`, `script_sha256`,
  `input_sha256s`, `remote_claim_sha256`;
- `orchestration-state-key`: all immutable state-key fields enumerated in
  Section 9, with null prerequisite allowed only for N6;
- `orchestration-attempt-intent`: `state_key_sha256`,
  `transition_identity_sha256`, `attempt`, `action_kind`, `correlation_id`,
  `source_controller`, `destination_controller`, `script_sha256`,
  `canonical_argv_sha256`, `input_sha256s`, `profile_sha256`,
  `deployment_receipt_sha256`, `runtime_set_sha256`,
  `source_manifest_sha256`, `policy_sha256`, `base_configuration_sha256`,
  `particles`, `seed`, `rank`, `parent_sha256s`,
  `expected_output_identities`, `create_only_namespace_identities`,
  `scheduler_job_name`, `scheduler_comment`, `remote_claim_path_identity`,
  `created_at_utc`;
- `orchestration-transition`: `state_key`, `state`, `attempt`,
  `input_sha256s`, `output_sha256s`, `output_promotion_sha256s`,
  `import_receipt_sha256s`,
  `transfer_receipt_sha256s`, `scheduler_receipt_sha256s`, `outcome`,
  `created_at_utc`;
- `orchestration-state-manifest`: `state_key_sha256`, `source_revision`,
  `transition_receipt_sha256s`, `completion_marker_sha256s`,
  `attempt_intent_sha256s`, `output_promotion_sha256s`,
  `expected_remote_output_sha256s`,
  `previous_state_manifest_sha256`, `backup_uri_identity`,
  `mirror_root_identity`, `created_at_utc`;
- `output-promotion`: `state_key_sha256`, `transition_identity_sha256`,
  `output_schema`, `output_payload_sha256`, `output_absolute_path_identity`,
  `producer_intent_sha256`, `selector_kind`, `selector_namespace_identity`,
  `candidate_computed_sha256`, `candidate_count`, `promoted_at_utc`;
- `export-bundle`: `bundle_role`, `source_controller`, `source_root`,
  `source_artifact_sha256`, `member_manifest`, `sha256sums_sha256`,
  `bundle_sha256`, `created_at_utc`;
- `import-bundle`: `bundle_sha256`, `destination_controller`,
  `destination_root`, `member_manifest`, `imported_artifact_sha256`,
  `verified_at_utc`;
- `transfer-receipt`: `direction`, `export_bundle_sha256`,
  `import_bundle_sha256`, `source_controller`, `destination_controller`,
  `source_identity`, `destination_identity`, `partial_path`,
  `final_path`, `bytes`, `attempt_intent_sha256`, `correlation_id`,
  `remote_claim_sha256`, `started_at_utc`, `verified_at_utc`;
- `dry-run-receipt`: `profile_sha256`, `bundle_sha256`, `destination`,
  `interpreter`, `interpreter_sha256`, `scheduler_test`, `validated_at_utc`;
- `deployment-receipt`: `dry_run_receipt_sha256`, `profile_sha256`,
  `bundle_sha256`, `deployment_root`, `interpreter`,
  `interpreter_sha256`, `installed_wheel_sha256`, `deployed_at_utc`;
- `exact-evaluation-shard`: `seed`, `rank`, `generation_sha256`,
  `oracle_sha256`, `parameter_sha256`, `block_layout`, `primitive_metrics`,
  `metric_equivalence`, `gate_metrics`;
- `coordinate-evaluation-shard`: `seed`, `rank`, `generation_sha256`,
  `parameter_sha256`, `evaluation_prng_sha256`, `sampler_configuration`,
  `sector_diagnostics`, `paired_gap_diagnostics`, `gate_metrics`;
- `evaluation-receipt`: `stage`, `identity`, `shard_sha256`,
  `started_at_utc`, `finished_at_utc`, `hostname`, `controller`, `device`,
  `peak_rss_mib`, `compile_seconds`, `elapsed_seconds`, `cache_counters`;
- `size-result`: `expected_ranks`, `expected_seeds`, `oracle_sha256`,
  `generation_sha256_by_identity`, `exact_sha256_by_identity`,
  `coordinate_sha256_by_identity`, `prerequisite`, `primitive_metrics`,
  `rank_transitions`, `seed_gate`, `missing_identities`, `failed_gates`,
  `production_accepted`, `claim`;
- `reduction-receipt`: `canonical_payload_sha256`, `started_at_utc`,
  `finished_at_utc`, `hostname`, `slurm_job_id`, `devices`, `peak_rss_mib`,
  `stage_elapsed_seconds`, `cache_counters`;
- `reduction-finalization`: `particles`, `base_configuration_sha256`,
  `expected_ranks`, `expected_ranks_sha256`, `selected_reduction_sha256`,
  `selected_reduction_path`, `production_accepted`, `finalized_at_utc`,
  `finalized_by`;
- `terminal-selection`: `particles`, `base_configuration_sha256`,
  `selected_expected_ranks_sha256`, `selected_finalization_sha256`,
  `selected_reduction_sha256`, `production_accepted`, `selected_at_utc`,
  `selected_by`;
- `cross-size-manifest`: `n6_sha256`, `n7_sha256`, `n8_sha256`,
  `n6_terminal_selection_sha256`, `n7_terminal_selection_sha256`,
  `n8_terminal_selection_sha256`, `particles`,
  `base_configuration_sha256_by_size`, `runtime_attestation_sets_by_size`,
  `lineage`, `production_accepted_n6_n8`, `claim`;
- `final-report`: `cross_size_manifest_sha256`, `size_summaries`,
  `particles`, `base_configuration_sha256_by_size`,
  `runtime_attestation_sets_by_size`, `source_manifest_sha256`, `policy_sha256`,
  `resource_summary`, `statistical_summary`, `failed_gates`,
  `production_accepted_n6_n8`, `statement`;
- `report-receipt`: `particles`, `base_configuration_sha256_by_size`,
  `final_report_sha256`, `markdown_sha256`, `cross_size_manifest_sha256`,
  `runtime_attestation_sets_by_size`, `source_manifest_sha256`,
  `policy_sha256`, `started_at_utc`, `finished_at_utc`, `hostname`,
  `interpreter_sha256`.

Unknown or omitted fields fail validation. Runtime receipts may use null
`slurm_job_id` only outside Slurm.

### 5.2 True append-only training generations

There is no mutable `shard.json`, latest pointer, symlink, or rewritten index.
One seed root contains only create-only objects:

```text
training/N=6/seed=0/
  owner/<owner_payload_sha256>.json
  extensions/<extension_sha256>.json
  attempts/<attempt_sha256>/attempt.json
  attempts/<attempt_sha256>/snapshots/<update>-<snapshot_sha256>.json
  generations/<generation_sha256>/manifest.json
  blobs/<sha256>
```

`claim-seed` creates the seed root and `owner/` with atomic `mkdir`, then
creates the `challenge15.seed-owner.v1` envelope as
`owner/<payload_sha256>.json` using `O_CREAT|O_EXCL`. The seed root is claimed
exactly once. `vmc-train` may never create or replace ownership; it verifies
the owner hash and creates child attempts, snapshots, blobs, and generations
only. One deterministic attempt identity owns one rank. Mid-rank snapshots and
attempt receipts are create-only and content-addressed. Coordination locks live
outside the artifact tree and use `O_CREAT|O_EXCL`; stale lock recovery
requires scheduler-liveness validation and emits a create-only
`challenge15.recovery-receipt.v1` before removing only the coordination lock.

Generation discovery:

1. enumerate sorted `generations/*/manifest.json`;
2. validate every discovered object; malformed objects hard fail;
3. require exactly one root generation and one valid child for each declared
   extension;
4. reject forks, duplicate ranks, gaps, stale source/runtime/policy hashes, and
   parent mismatches;
5. return the unique terminal generation with the greatest rank.

Incomplete attempt snapshots are not generations and cannot shadow a valid
generation. Two valid children of one parent are an ambiguity and hard fail;
the reducer does not choose one.

### 5.3 Rank extension schema

Each seed and new rank has one canonical envelope whose schema is
`challenge15.rank-extension.v1` and whose content-addressed filename is
`extensions/<payload_sha256>.json`. Its exact payload fields are:

```text
particles
seed
experiment_id
base_configuration_sha256
policy_sha256
source_manifest_sha256
runtime_attestations
expected_seed_set
previous_rank
new_rank
parent_generation_sha256
parent_parameter_sha256
parent_optimizer_state_sha256
rank_extension_decision_sha256
embedding_algorithm
rank_growth_prng
reason
created_by_git_revision
```

`expected_seed_set` is exactly `[0,1,2,3,4]`. `new_rank` is `1` for the root
or exactly twice `previous_rank`. A root rank-extension decision has
`current_rank=null`, `new_rank=1`, null prior reduction/finalization, and
null prior import/transfer receipts, and `reason="initial"`; its root extension
has null parent state but binds that decision hash. Every extension requires
`rank_extension_decision_sha256` and
CLI `--decision PATH`. Validation binds the decision's seed, current/new ranks,
prior reduction/finalization when non-root, source, policy,
controller-indexed runtime set, and base configuration hash before reading
parent state. Non-root reasons are
`"scheduled_initial_ladder"` or `"rank_convergence_pending"`.
`embedding_algorithm="copy-old-append-zero-gates-v1"`. The extension changes
neither the base configuration nor its hash. The CLI accepts `--output-dir`,
computes the canonical payload hash, and exclusively creates that hash-derived
filename; rank aliases such as `rank-8.json` are forbidden. `vmc-train`
requires the resulting `--extension`; no rank is accepted directly from a
command-line integer.

### 5.4 Evaluation shards

Exact evaluation publishes one immutable
`challenge15.exact-evaluation-shard.v1` per `(rank,seed)`. Independent
post-training coordinate evaluation publishes one immutable
`challenge15.coordinate-evaluation-shard.v1` per `(rank,seed)` using fresh
PRNG streams and no optimizer state mutation. Both bind the generation,
parameter, oracle, policy, source, runtime, and configuration hashes.

Coordinate evaluation records per sector and paired gap:

- chain estimates and standard errors;
- integrated autocorrelation times and convergence flags;
- effective sample sizes;
- split `Rhat`;
- local/rigid/total acceptance rates;
- frozen proposal widths;
- paired covariance;
- 95% confidence intervals;
- within-seed and between-seed inputs;
- elapsed and resource telemetry in a separate receipt.

### 5.5 Cross-controller export, transfer, and import

Qdeshell cannot run CPU-only jobs. Training and coordinate artifacts move from
Qdeshell to LASG02/WUZH02; oracle/exact/reduced/finalized CPU results move back
to Qdeshell for continued training decisions and final collation.

`export-bundle` creates a new content-addressed directory containing:

```text
export.json
members/<content-addressed files>
SHA256SUMS
```

`SHA256SUMS` is sorted by relative POSIX path and hashes every member except
itself; `sha256sums_sha256` binds it. The bundle payload binds the source
controller, canonical source root, source artifact identities, role/controller-indexed
runtime attestations, source/policy hashes, and member manifest.

Transfer uploads to a unique destination sibling
`.partial.<bundle_sha256>.<transfer_uuid>` opened with exclusive creation.
The destination verifies bytes, `SHA256SUMS`, export envelope, source identity,
destination profile/root, and stale-policy/source/runtime rejection. Only then
does it atomically rename the partial directory to
`imports/<bundle_sha256>`. Existing partial or final paths fail; corrupt or
duplicate bundles are never merged.

`import-bundle` verifies every member and publishes a create-only import
envelope. A transfer is complete only when a
`challenge15.transfer-receipt.v1` binds both export and import envelope hashes.
No Slurm `afterok` crosses controllers. A local orchestrator waits for the
source stage, performs transfer, synchronously fetches and validates the
transfer receipt, and only then submits the downstream job to the destination
controller.

Attestation exchange uses a separate bootstrap path because a completed
runtime-attestation set does not yet exist. An
`challenge15.attestation-bootstrap-transfer.v1` authenticates exactly one
allowed-runtime envelope using the common source manifest, policy, source and
destination deployment receipts, and the envelope's own hash. Bootstrap
export/import verifies those objects directly and never accepts
`--runtime-attestations`. After Qdeshell GPU envelopes and each CPU
controller's envelopes are exchanged, `runtime-attestation-set` validates all
five role/controller entries and publishes the per-size set. Bootstrap bundles
cannot carry scientific artifacts or satisfy scientific transfer policy.

## 6. Reducer semantics

`reduce_size` receives an explicit `--expected-ranks` list and the complete
five-seed identity map. It never infers expected work from files present.
`expected_ranks_sha256` is SHA256 of canonical JSON bytes for the ordered rank
list. Results are published create-only beneath
`reductions/<expected_ranks_sha256>/<payload_sha256>.json`; rerunning a
different expected-rank set cannot overwrite an earlier reduction.

Input classification is strict:

- malformed, duplicate, unexpected, forked, stale, wrong-policy,
  wrong-runtime, wrong-source, wrong-parent, or semantically inconsistent
  input: hard fail and publish no payload or receipt;
- valid but missing expected identities: publish a deterministic pending
  canonical payload listing sorted missing identities;
- complete valid identities with failed gates: publish deterministic pending;
- complete valid identities with every gate passed: publish accepted.

The reducer recomputes every gate from primitive metrics. It preserves current
seed semantics exactly: all five seeds at every expected rank, identical paired
seed sets for every adjacent rank, current per-seed transition rules, and at
least four accepted final-rank seeds.

The canonical `challenge15.size-result.v1` contains scientific inputs, metrics,
gate outcomes, sorted missing/failed identities, prerequisite lineage, and
claim text. It excludes hostname, device text, Slurm IDs, start/end times,
elapsed times, RSS, compilation time, and cache counters.

`challenge15.reduction-receipt.v1` separately records those execution facts and
the canonical payload SHA256. Only the canonical payload is required to be
byte-identical under input ordering and repeated execution. Receipts are not
expected to be byte-identical.

Immutable provisional `challenge15.reduction-finalization.v1` objects are keyed
by `(particles, base_configuration_sha256, expected_ranks_sha256)`. Multiple
provisional finalizations may coexist when they have different selected
reduction hashes; publication never overwrites or aliases one. A provisional
finalization validates the selected payload, expected-rank hash, source,
policy, role/controller attestation set, and acceptance state. Only an accepted
provisional finalization is eligible for terminal selection; a prerequisite is
satisfied only through the terminal selection that names it.

```text
finalizations/N=<N>/base=<base_sha256>/expected=<expected_ranks_sha256>/<payload_sha256>.json
terminal-selections/N=<N>/base=<base_sha256>/<payload_sha256>.json
```

Every non-root rank-extension decision binds its prior reduction and
provisional-finalization hashes. The lifecycle is therefore reduction and
provisional finalization at rank 1, decision to rank 2, reduction/finalization
at ranks 1,2, decision to rank 4, reduction/finalization at ranks 1,2,4, and—if
pending—decision to rank 8. A pending provisional finalization may authorize
the next doubling but cannot satisfy a size prerequisite.

An immutable `challenge15.terminal-selection.v1` chooses one canonical accepted
provisional finalization for `(particles, base_configuration_sha256)`. It hard
fails for pending finalizations, mismatched keys, or a second selection.
`N=7`, `N=8`, cross-size reduction, and the final report consume terminal
selections only.

Each stage uses a validated `challenge15.identity-map.v1` to derive
`task_count`, array upper bound, and concurrency. No wrapper hard-codes
`0-14`. Rank 8 is a new five-task identity map and new array; it is not appended
to or aliased onto a previous array.

Blocked-kernel implementations must agree on every primitive metric, not merely
gate booleans. Exact metrics use the existing numerical tolerances; stochastic
metrics require bitwise-identical deterministic accumulation for the same
sample stream. If two valid layouts straddle a threshold, disagree beyond
tolerance, or produce a value too close to classify consistently at stored
precision, the corresponding identity and aggregate remain pending.

## 7. Production VMC contract

### 7.1 `ProductionVMCConfig`

The frozen configuration has these exact fields:

```python
optimizer: Literal["adam"] = "adam"
learning_rate: float = 1e-3
steps: int = 10_000
weight_l0: float = 0.5
weight_l2: float = 0.5
chains_per_sector: int = 32
walkers_per_chain: int = 32
pilot_sweeps: int = 500
burn_in_sweeps: int = 2_000
draws_per_update: int = 16
thinning_sweeps: int = 2
reequilibration_sweeps_after_update: int = 4
refresh_log_amplitudes_after_update: bool = True
checkpoint_interval_steps: int = 100
final_evaluation_chains_per_sector: int = 32
final_evaluation_burn_in_sweeps: int = 5_000
final_evaluation_draws_per_chain: int = 4_096
final_evaluation_thinning_sweeps: int = 4
walker_microbatch: int = 64
carrier_block: int = 8
quadrature_block: int = 64
```

Weights must be positive and sum to one. The derived
`walkers_per_sector=chains_per_sector*walkers_per_chain=1_024`. Counts are
positive integers. Final evaluation uses a disjoint,
deterministically derived PRNG namespace and does not update parameters,
optimizer state, or training walkers.

`base_configuration_sha256` covers every field above except the three
execution-only fields `walker_microbatch`, `carrier_block`, and
`quadrature_block`. It includes total walkers, chains, all draw/sweep counts,
steps, optimizer, learning rate, sector weights, checkpoint cadence, and PRNG
schedule version. An OOM retry supplies a content-addressed
`challenge15.resource-override.v1`; changing any other field is a new base
configuration and experiment.

### 7.2 Batched amplitude interface

```text
apply_batched(
  variables,
  spec,
  spinors: complex128[walker,N,2],
  sectors: int32[2] = [0,2],
  valid_walkers: bool[walker],
  carrier_block: int,
  quadrature_block: int
) -> BatchedLogAmplitude
```

`BatchedLogAmplitude` contains:

```text
log_amplitude: complex128[walker,2]
finite_nonzero: bool[walker,2]
```

The real component is `log|Psi_{L,M=0}|`; the imaginary component is the
principal phase in `(-pi,pi]`. Exact zero is represented by
`(-inf+0j,false)`. Padded walkers are masked and cannot contribute. For finite
nonzero values, `exp(log_amplitude)` matches scalar `model.apply` in value and
parameter derivatives to the declared metric tolerance.

### 7.3 Score pytree and finite-chain estimator

The coordinate state has exact shape
`[sector, chain, walkers_per_chain, particle, spinor]`, therefore
`[2,32,32,N,2]`. Every chain owns an independent proposal state and PRNG
substream. A retained update has
`D=chains_per_sector*walkers_per_chain*draws_per_update=16_384` flattened
gradient samples per sector. Checkpoints preserve this full state, matching
log-amplitude shape `[2,32,32]`, proposal state `[2,32]`, and PRNG state per
chain. Independent final evaluation has the same layout but disjoint PRNG,
fresh burn-in, frozen parameters/proposal widths, and no optimizer state.

For `D` retained draws, each real parameter leaf with shape `S` has a score
leaf `complex128[D,2,*S]` equal to `d log Psi_L / d theta`. The returned
gradient has the same real pytree structure and leaf shapes as parameters.
Gradient samples flatten chain, walker, and draw axes in fixed lexicographic
order. Diagnostics retain chain grouping: each retained chain observation is
the mean over that chain's walkers, and split-Rhat/autocorrelation are computed
across the 32 independent chain time series, never across flattened walkers.

For each sector and `D>1`, deterministic accumulation computes:

```text
C_OV = D/(D-1) * (mean(conj(O) V) - mean(conj(O)) mean(V))
gradient = 2 Re(C_OV)
```

This is the score-covariance/consistent finite-chain estimator, not an unbiased
estimator: samples are correlated, amplitudes are normalized by finite-chain
estimates, and parameter updates change the target distribution. The
`D/(D-1)` correction is required for sample covariance where appropriate.

After every parameter update, all walker log amplitudes are refreshed under
the new parameters, then exactly four re-equilibration sweeps run before the
next retained draw. PRNG splitting and accumulation order are fixed by policy.

### 7.4 Code-owned VMC diagnostic gates

An optimization update is valid only if all amplitudes, potentials, scores,
gradients, parameters, optimizer values, and estimates are finite; each sector
has at least two retained values; and total acceptance lies in `[0.20,0.80]`.
Invalid updates stop the attempt.

An independent coordinate-evaluation shard passes only when:

```text
chains_per_sector >= 4
autocorrelation_converged == true for E0, E2, and paired gap
effective_sample_size >= 1000 for E0, E2, and paired gap
split_Rhat <= 1.01 for E0, E2, and paired gap
0.20 <= local_acceptance_rate <= 0.80
0.20 <= total_acceptance_rate <= 0.80
all estimates, errors, intervals, and covariances finite
confidence_interval lower <= estimate <= upper
```

These constants live only in the production policy/code and cannot be supplied
by config or CLI.

### 7.5 Gap uncertainty

Within a seed, final `E_0` and `E_2` coordinate evaluations use independent
chain ensembles and PRNG namespaces, so their Monte Carlo covariance is
exactly zero by construction:

```text
Delta_s = E2_s - E0_s
Var_MC(Delta_s) = Var_MC(E2_s) + Var_MC(E0_s)
```

Across the same `K` paired seed/optimizer identities, optimizer-induced
covariance is estimated from paired samples:

```text
s02 = sum_s (E0_s-mean(E0)) (E2_s-mean(E2)) / (K-1)
Var_seed(mean(Delta)) = (s22 + s00 - 2*s02) / K
```

For a rank change, define `d_s=Delta_{r2,s}-Delta_{r1,s}` on the identical
paired seed set and use
`SE(mean(d))=sqrt(sample_variance(d_s)/K)`. Unpaired seeds, reused final chains
between sectors, `K<2`, or a non-finite covariance make the uncertainty
pending.

### 7.6 Ownership and OOM behavior

`train_rank(config, extension, destination, owner)` requires:

- `destination` is the existing uniquely claimed seed root named by
  `(N,seed,base_hash)`; `train_rank` must not create or replace it;
- `owner` matches the permanent seed owner;
- `extension` is canonical and either roots the seed or names the unique
  highest generation;
- initial parameters/optimizer exactly match the declared parent hashes;
- only child attempt, snapshot, blob, and terminal-generation objects are
  create-only outputs.

OOM retry may change only `walker_microbatch`, `carrier_block`, and
`quadrature_block`. Total walkers, chains, draws, thinning, PRNG keys, update
schedule, accumulation order, and scientific configuration remain fixed.
Deterministic chunk accumulation must reproduce every metric within tolerance.
Changing total walkers creates a new base configuration and experiment
identity; it is never an OOM override.

## 8. Exact batching and cache

Exact evaluation uses static padded blocks over determinants, carriers,
sectors, and quadrature nodes. It caches determinant blocks, occupation
indices, orbital groups, projection grids, beta rotations, and alpha phases by
content hash. It never materializes a full determinant-square Gram matrix.

Tests compare normalized coefficients, energies, `Var(H_LLL)`, overlaps,
target-`L` residuals, quadrature changes, span singular values, and span ranks
across scalar and multiple blocked layouts. Metric equivalence is mandatory;
gate equivalence alone is insufficient.

## 9. Sole production entry point and state machine

The only operator-facing size command is:

```text
challenge15 production-orchestrate-size
  --particles N --rank-ladder 1,2,4,8 --seeds 0,1,2,3,4
  --base-config PATH --policy PATH --source-manifest PATH
  --runtime-set-local PATH --runtime-set-local-sha256 HEX
  --cpu-runtime-set-remote PATH --cpu-runtime-set-receipt PATH
  --gpu-runtime-set-remote PATH --gpu-runtime-set-receipt PATH
  --cpu-controller {lasg02,wuzh02} --gpu-controller qdeshell
  --cpu-profile PATH --gpu-profile PATH
  --cpu-deployment-receipt PATH --gpu-deployment-receipt PATH
  --cpu-results-root PATH --gpu-results-root PATH
  --state-root-base PATH --state-backup-uri SSH_URI
  [--state-mirror-root PATH]
  [--prerequisite-terminal-selection PATH]
  --create-only
```

The command runs locally and synchronously. N6 omits the prerequisite;
N7/N8 require an accepted predecessor terminal selection. Slurm submission
scripts and all low-level CLI commands are internal state-machine contracts and
are never production entry points.

The local envelope/hash and both controller-local paths are mandatory. The
remote paths must be returned by validated deployment/bootstrap import
receipts. All three envelopes must have byte-identical canonical payload hashes
and identical role/controller maps; path-string equality is neither required
nor sufficient.

Each controller-local runtime-set publication creates a
`challenge15.runtime-set-publication-receipt.v1`. The exact receipt hash is
`cpu_resolving_receipt_sha256` or `gpu_resolving_receipt_sha256`; a deployment
receipt, bootstrap receipt, transfer receipt, or directory path alone cannot
substitute for it.

The immutable state key is SHA256 of canonical
`challenge15.orchestration-state-key.v1` payload fields:

```text
particles
base_configuration_sha256
policy_sha256
source_manifest_sha256
rank_ladder
rank_extension_policy_sha256
seed_set
runtime_set_local_sha256
runtime_set_local_path_identity
cpu_runtime_set_remote_sha256
cpu_runtime_set_remote_path_identity
cpu_runtime_set_receipt_sha256
gpu_runtime_set_remote_sha256
gpu_runtime_set_remote_path_identity
gpu_runtime_set_receipt_sha256
prerequisite_terminal_selection_sha256
cpu_controller
gpu_controller
cpu_profile_sha256
gpu_profile_sha256
cpu_deployment_receipt_sha256
gpu_deployment_receipt_sha256
cpu_results_root_identity
gpu_results_root_identity
durable_state_root_base_identity
state_backup_uri_identity
state_mirror_root_identity
canonical_path_identities
```

The prerequisite hash is null only for N6. Root identities are
`controller:realpath` strings validated against profile-approved roots;
`canonical_path_identities` records only paths whose location is semantically
bound by policy. Changing any field creates a different state key.

`--state-root-base` is a durable local persistent directory, by default
`${XDG_STATE_HOME:-$HOME/.local/state}/challenge15`; `/tmp`, `/var/tmp`,
symlinks, relative paths, and nonpersistent mounts are rejected. To avoid
self-reference, its canonical identity is hashed into the state key and the
actual create-only run root is then derived as
`<base>/source=<revision>/state=<state_key>`. Scientific output remains only
under profile-approved remote result roots. Disposable compilation/job scratch
may use `/tmp` under the existing scratch rules, never orchestration state.

`--state-backup-uri` is mandatory and uses canonical
`ssh://host/absolute/profile-approved/results/path` syntax. It must resolve to a
different host/failure domain from the local state base; local `file://`,
sibling paths, the same device/filesystem, symlinks, and unapproved remote
roots are rejected. Production defaults are
`ssh://lasg02-student090/public/home/student090/results/challenge15/orchestration-backups`
for N6/N7 and the WUZH02 profile-approved
`ssh://wuzh02${WUZH_RESULTS_ROOT}/challenge15/orchestration-backups` for N8,
where `WUZH_RESULTS_ROOT` is read from the committed profile.
`--state-mirror-root` may name a create-only local duplicate, but it is a
mirror, never the disaster backup, and its canonical identity is state-keyed.

Each transition publishes a content-addressed transition receipt and then
atomically creates a completion marker containing that receipt hash. Restart
validates completed receipts and resumes at the first absent transition.
Conflicting output for an existing transition hard fails; repeated execution
with identical inputs returns the same accepted terminal selection or pending
state without resubmission.

Canonical publishers retain their native atomic create-only behavior and may
publish the canonical content-addressed artifact before orchestration metadata.
Recovery never requires an unknown expected payload hash. Every publisher
implements
`select_published(intent, create_only_namespace) -> None | ValidatedCandidate`.
The selector is derived from the immutable attempt intent and binds output
identity, parent hashes, source/policy/runtime/base hashes, particles, seed,
rank, controller, and exact create-only namespace. It enumerates only filenames
permitted by that intent; recursive/global scans and newest-file inference are
forbidden.

For every permitted candidate, the selector reads bytes, parses the exact
schema, canonicalizes the payload independently, computes SHA256 from those
canonical bytes, checks the envelope's claimed hash and content-addressed
filename against the computed hash, then validates all identity, provenance,
parent, ownership, PRNG, and path-locality fields. A candidate's self-declared
hash is never evidence by itself. Zero valid candidates means not published;
exactly one is adopted; two or more valid candidates hard fail even if their
bytes match. Any candidate occupying a permitted identity but failing schema,
hash, provenance, or parent validation is tampering and hard fails rather than
being ignored.

Selectors are split exactly:

- stochastic selectors cover `training-snapshot`, `training-generation`,
  `coordinate-evaluation-shard`, and `exact-evaluation-shard`; intent fixes
  seed/rank/stage, owner/attempt/parent generation, PRNG schedule, source/
  policy/runtime/base hashes, and the one seed/rank create-only namespace while
  allowing the resulting numerical payload hash to be learned after
  publication;
- deterministic selectors cover `seed-owner`, `rank-extension`,
  `training-attempt` metadata, `size-result/reduction`, export/import/transfer,
  `reduction-finalization`, and `terminal-selection`; intent and parent hashes
  determine the permitted identity namespace and all canonical non-execution
  fields.

The publisher registry supplies these concrete enumerators:

- owner: only `<seed-root>/owner/*.json`, with the intent's particles/base/
  seed tuple and no parent;
- extension: only `<seed-root>/extensions/*.json`, with the exact prior
  decision/finalization/reduction and parent parameter/optimizer hashes;
- attempt: only `<seed-root>/attempts/<attempt-identity-sha256>/attempt.json`;
- snapshot: only `<that-attempt>/snapshots/<update>-*.json`, with the exact
  update, attempt, preceding snapshot/generation, and PRNG state fixed by
  intent;
- generation: only `<seed-root>/generations/*/manifest.json`, filtered by the
  exact intended rank, attempt, extension, parent generation, parameter/
  optimizer hashes, and PRNG schedule;
- coordinate/exact evaluation: only `*.json` directly in the intent's exact
  stage/N/rank/seed output namespace, with generation and evaluation-input
  hashes fixed by intent;
- reduction/finalization/terminal selection and export/import/transfer: only
  `*.json` directly in their intent-declared output namespace, with the exact
  identity map and all ordered parent/input/receipt hashes fixed by intent.

Wildcards above range only over content-address suffixes whose payload is not
known until publication; they never cross the declared namespace. The selector
derives `attempt-identity-sha256`, update, stage/N/rank/seed namespace, and every
filter from the canonical attempt-intent payload, never from candidate data.

The registry is exhaustive:
`seed-owner`, `rank-extension`, `training-attempt`, `training-snapshot`,
`training-generation`, `coordinate-evaluation-shard`,
`exact-evaluation-shard`, `size-result/reduction`, `export/import/transfer`,
`reduction-finalization`, and `terminal-selection`.

After canonical publication, the orchestrator publishes
`challenge15.output-promotion.v1` as the promotion receipt. If a crash occurs
between those operations, the selector computes the unique candidate payload
hash and records it in the synthesized promotion receipt with selector and
attempt-intent hashes. Existing invalid or ambiguous canonical output hard
fails; recovery never republishes it.

Every transition executes `recover_before_act` before any submission, transfer,
or computation:

1. derive exact publisher selector, permitted namespace, and promotion-receipt
   path from the attempt intent;
2. invoke the registered selector and apply the zero/one/multiple rules;
3. validate an existing promotion receipt, or synthesize only that receipt
   from a valid canonical output and durable scheduler/transfer evidence;
4. validate an existing completion marker, or exclusively create only the
   missing marker from the receipt hash; then return recovered without acting;
5. if no promoted output exists, inspect deterministic job/transfer intent:
   wait for an active attempt, hard fail on successful completion without its
   declared output, or create a new immutable attempt only after a failed/
   absent attempt is proven inactive.

This applies independently to every state and actual publisher, including
transfer/import publication,
scheduler completion, artifact publication, receipt publication, and terminal
states. OOM retry follows the existing block-size-only policy. A crash after
canonical artifact or transfer/import publication therefore never resubmits,
republishes, or recopies bytes.

Before any external action, the orchestrator create-only persists
`challenge15.orchestration-attempt-intent.v1` locally and at the target
controller. The exact local envelope bytes are transferred create-only; the
remote copy must have the same envelope SHA256 and is never regenerated.
`correlation_id` is SHA256 of state key, transition identity,
attempt, action kind, controllers, script hash, canonical argv hash, and input
hashes.

Slurm actions use remote `submit-once`:

1. return an existing validated remote submission receipt immediately;
2. atomically claim `claims/$CORRELATION_ID/` with `mkdir`/`O_EXCL`;
3. before `sbatch`, query the receipt, then `squeue` and `sacct` using exact
   deterministic job name `c15-${CORRELATION_ID:0:24}`, scheduler comment equal
   to the full correlation ID, script SHA256, and input hashes;
4. if any matching scheduler evidence exists, wait/query and synthesize the
   remote receipt; never call `sbatch`;
5. only the claim owner with proven no evidence calls `sbatch` exactly once,
   captures the parsable job ID, fsyncs a unique partial receipt, and atomically
   renames it before returning.

A crash after `sbatch` but before receipt publication is recovered from
`squeue`/`sacct`. Accounting propagation ambiguity waits or hard fails for
operator reconciliation; it never authorizes resubmission.

Transfers use equivalent remote `transfer-once`: persist the same intent,
claim the deterministic correlation ID at the destination, check remote
transfer receipt and canonical imported output first, then copy/promote bytes
exactly once and atomically publish the transfer/import receipt. Existing
destination evidence synthesizes only missing receipts; ambiguous evidence
waits or hard fails and never recopies.

After every marker, the orchestrator publishes a content-addressed state
manifest and transfers it once beneath `state_backup_uri` at
`source=$SOURCE_REVISION/state=$STATE_KEY/`. The backup contains
state key, intents, receipts, markers, and expected remote hashes, but never
mutable scientific copies. Recovery on another local host restores only
verified metadata, validates all promoted remote outputs, and resumes through
`recover_before_act`; a marker with missing local manifest/backup synthesizes
only those metadata copies. Missing/corrupt bytes in an existing backup hard
fail.

States are:

```text
VERIFY_INPUTS
VERIFY_RUNTIME_SET_COPIES
ENSURE_ORACLE
CLAIM_SEEDS
PREPARE_RANK
TRAIN_RANK
COORDINATE_EVALUATE
EXPORT_GPU_IDENTITY_MAP
TRANSFER_GPU_TO_CPU
IMPORT_GPU_RESULTS
EXACT_EVALUATE
REDUCE_EXACT_INPUTS
PROVISIONAL_FINALIZE
CLASSIFY_FINALIZATION
DECIDE_EXTENSION
SELECT_TERMINAL
EXPORT_ACCEPTED_TERMINAL
STOP_ACCEPTED
STOP_PENDING
HARD_FAIL
```

Transition contracts are exact:

- `VERIFY_INPUTS` consumes command arguments and emits verified policy/source/
  base/profile/deployment/set hashes plus an accepted prerequisite hash or null;
- `VERIFY_RUNTIME_SET_COPIES` consumes the local envelope/hash plus both
  receipt-resolved controller-local paths and emits one equality/locality
  verification hash;
- `ENSURE_ORACLE` consumes CPU runtime/profile paths and emits oracle path/hash
  plus evaluation receipt;
- `CLAIM_SEEDS` consumes the five-seed identity map and emits five owner hashes;
- `PREPARE_RANK` consumes owners and either null prior cycle (rank 1) or
  imported prior reduction/finalization/receipt paths, and emits five decision
  and extension hashes;
- `TRAIN_RANK` emits exactly five `new_rank` generation hashes and receipts;
- `COORDINATE_EVALUATE` emits exactly five `new_rank` coordinate-shard hashes
  and receipts;
- `EXPORT_GPU_IDENTITY_MAP` emits an exact new-rank-only generation/coordinate
  identity map and export-bundle hashes;
- `TRANSFER_GPU_TO_CPU` and `IMPORT_GPU_RESULTS` emit transfer/import hashes and
  CPU-local `import-member` paths;
- `EXACT_EVALUATE` emits exactly five `new_rank` exact-shard hashes and
  evaluation receipts;
- `REDUCE_EXACT_INPUTS` consumes a cumulative identity map containing verified
  prior-cycle coordinate/exact hashes plus the five new-rank hashes and emits
  the fresh reduction absolute path and SHA256;
- `PROVISIONAL_FINALIZE` consumes exactly that pair and emits one provisional
  finalization path/hash;
- `CLASSIFY_FINALIZATION` emits `accepted`, `extend`, or `pending`;
- `DECIDE_EXTENSION` emits five next-rank decision hashes;
- `SELECT_TERMINAL` emits one terminal-selection path/hash and is reachable only
  from `accepted`;
- `EXPORT_ACCEPTED_TERMINAL` emits the four-member identity map, bundle, import,
  and transfer hashes;
- stop states emit the final immutable orchestration-transition receipt.

`run_rank_cycle(previous_cycle,new_rank)` accepts no caller-derived expected
rank list. Rank 1 requires `previous_cycle=null` and
`previous_expected_ranks=[]`; every later cycle reads and validates
`previous_expected_ranks` from the exact prior `CycleOutcome`, then appends
only `new_rank`. The only valid trace is:

```text
new_rank=1 previous_expected_ranks=[]
new_rank=2 previous_expected_ranks=[1]
new_rank=4 previous_expected_ranks=[1,2]
new_rank=8 previous_expected_ranks=[1,2,4]
```

Arithmetic, range construction, rank division, and operator-supplied
previous/expected rank CSVs are forbidden. The cycle first verifies the per-size
controller-indexed runtime set on the local machine, CPU controller, and
Qdeshell, validates equal payload hashes/role maps and both resolving receipts,
and gives wrappers only their controller-local path. It ensures the CPU
oracle, claims all five seed roots, creates one root decision then rank-1
extensions, and for every new rank runs only five-seed `new_rank` training and
independent coordinate evaluation. A new-rank identity map names exactly those
five generations and five coordinate shards; `export-bundle` creates that
bundle, then transfer,
import, and `import-member` resolve CPU-local inputs for exact evaluation.

The prior `CycleOutcome` carries the verified cumulative reducer map and exact
`expected_ranks`. The next
cycle reuses all prior coordinate/exact shard hashes and appends exactly five
new coordinate and five new exact hashes. Old ranks are never retrained,
reevaluated, transferred, or republished. The cumulative map has exactly
`len(expected_ranks) * 5` coordinate and exact identities and rejects a
duplicate, replaced prior hash, or old-rank publication attempt.

The reducer returns an exact `(reduction_path,reduction_sha256)` pair. The next
transition finalizes that exact pair; directory discovery and
`select-unique-reduction` are forbidden. If accepted, the machine selects the
terminal result, creates an accepted-terminal identity map containing exactly
the terminal selection, selected provisional finalization, selected reduction,
and per-size runtime set, exports/transfers it, and stops accepted. If pending
and the next doubling is policy-allowed, the machine transfers the prior
reduction/finalization, resolves both with destination `import-member`, verifies
their import/transfer receipts, creates five decisions and extensions, and
runs the next cycle. Otherwise it stops pending. Rank 8 performs the full
coordinate/export/import/exact/reduce/finalize/classify/select path.

Malformed/stale provenance, controller mismatch, corrupt/duplicate transfer,
forked generation, conflicting completion receipt, non-retryable scheduler
failure, or
unresolved imported member hard fails. Missing expected scientific identities,
failed immutable gates, exhausted rank ladder, or valid non-accepted
finalization stops pending. Pending never invokes terminal selection.

## 10. Cross-size reduction and final report

`submit-cross-size` requires:

```text
--n6-terminal-selection PATH --n7-terminal-selection PATH
--n8-terminal-selection PATH --runtime-attestation-set-n6 PATH
--runtime-attestation-set-n7 PATH --runtime-attestation-set-n8 PATH
--n8-provisional-finalization PATH --n8-reduction PATH
--n8-import-receipt PATH --n8-transfer-receipt PATH
--policy PATH --source-manifest PATH
--deployment-receipt PATH --output-dir PATH --receipt-dir PATH
```

Before invocation, the local orchestrator exports the accepted N8 terminal
selection and selected provisional finalization on WUZH02, imports them to
LASG02, and verifies the transfer receipt. The CLI validates three distinct
accepted terminal selections, exact `N=6,7,8` lineage, identical policy/source
hashes, each size's controller-indexed attestation set, every required role,
and prerequisite hashes. It retains all LASG02, WUZH02, and Qdeshell hashes in
the aggregate payload and exclusively creates
`cross-size/<payload_sha256>.json` and a separate submission receipt. Missing
accepted terminal selections create a deterministic pending cross-size
manifest; provisional-only, malformed, duplicate, stale, or mismatched input
hard fails with no output.

`reduce-cross-size` consumes the same four N8 destination-local
finalization/reduction/import/transfer arguments and rejects a remote-origin
path.

`report` requires:

```text
--cross-size-manifest PATH --policy PATH --source-manifest PATH
--runtime-attestation-set-n6 PATH --runtime-attestation-set-n7 PATH
--runtime-attestation-set-n8 PATH --output-dir PATH --receipt-dir PATH
--n8-provisional-finalization PATH --n8-reduction PATH
--n8-import-receipt PATH --n8-transfer-receipt PATH
```

It builds both files in a unique exclusive partial directory, verifies their
hashes, and atomically renames it to `reports/<payload_sha256>/`, containing
`report.json` and `report.md`. The JSON is the canonical
`challenge15.final-report.v1`; Markdown is a rendering whose hash is recorded
in `challenge15.report-receipt.v1`. Accepted wording is exactly
`Production accepted for finite-size lowest-L=2 sector gaps at N=6,7,8 only; no chiral response or thermodynamic-limit claim is made.`
Pending wording is exactly
`Production pending; no N=6..8 production claim is made.`
The report cannot infer acceptance or strengthen the finite-size claim.

## 11. Submission ordering

The only valid order is:

1. candidate CPython 3.12 locks/wheelhouses and local compatibility;
2. policy, append-only schemas, rank extensions, reducer, VMC, exact kernels,
   CLI, cluster profiles, Slurm scripts, and local smoke;
3. clean source freeze;
4. final role/controller target-node attestations;
5. `sbatch --test-only` for every final frozen-source wrapper;
6. content-addressed deployment and deployment receipts, followed by bootstrap
   attestation exchange and per-size runtime-attestation sets;
7. `N=6` CPU oracle, transfer to Qdeshell, GPU training/coordinate evaluation,
   transfer to LASG02, CPU exact/reduction, provisional finalization, and
   terminal selection;
8. synchronous transfer and terminal-selection validation of accepted `N=6`;
9. the same controller-local/transfer lifecycle for `N=7`;
10. synchronous terminal-selection validation of accepted `N=7`;
11. WUZH02-backed `N=8`, including a separate rank-8 five-task array,
    transfers, reduction, provisional finalization, and terminal selection;
12. explicit WUZH02-to-LASG02 N8 accepted-result transfer, then
    terminal-selection-only cross-size manifest and report.

A scheduler exit code of zero is not acceptance.
`production-orchestrate-size` synchronously
validates the predecessor terminal selection, selected finalization and
canonical payload, SHA256, policy, source, controller-indexed attestations,
semantic `production_accepted=true`, and exact particle number
before submitting any child job. A successful reduction that is pending
submits no child jobs.

## 12. Stop rules

- Any source change after attestation invalidates all role/controller
  attestations and every set containing them.
- Any malformed, duplicate, unexpected, stale, forked, or wrong-parent input
  hard fails without reducer output.
- Missing expected valid inputs produce deterministic pending, not acceptance.
- Fewer than five covered seeds, nonidentical paired seed sets, fewer than four
  accepted final seeds, or fewer than two passing final doublings is pending.
- Failed coordinate diagnostics, exact gates, or metric-equivalence checks are
  pending.
- Repeated OOM after block-only fallback is pending.
- `N=7` is never submitted without an accepted N6 terminal selection; `N=8`
  is never submitted without an accepted N7 terminal selection and an attested
  WUZH02 profile.
- Any ambiguity at an acceptance threshold is pending.
- The report remains pending unless all three sizes pass.
