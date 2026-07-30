# Validator design freeze

Status: confirmed design input for the validator stage.
Authority: `topics.md` acceptance gate, `WORKFLOW.md` v1.0, `MODEL.md` v1.0.

## Publishable bar

The validator has two distinct responsibilities:

1. reject any implementation that changes or leaks the frozen physics;
2. rank correct implementations by validated throughput.

Passing the implementation validator is necessary but not sufficient for `done`. The final science gate additionally requires the full core matrix, headline-slice precision, cost reporting, independent reproduction, and one sealed holdout as stated in `topics.md`.

## Candidate contract

Every candidate worktree must expose:

```text
python -m reload_qec.candidate --request REQUEST.json --out OUTPUT_DIR
```

The candidate reads only the request and public instance files. It writes a manifest plus NPZ shards under the requested output directory. It may not invoke the validator, read labels, open private benchmark paths, use network access, or write elsewhere.

`--precheck` verifies package structure, CLI help, manifest schema, output containment, and a zero-shot request. It reveals no score and consumes no attempt.

## Development families

Visible fixtures:

- all records in `research/database/policy_cases.jsonl`;
- zero-noise and `p_loss=0` invariance for `d=3`, both bases, `T=3,6`;
- one deterministic data loss and one ancilla loss at every round boundary;
- ideal equivalence of `immediate` and `periodic(1)`;
- invalid coordinate, reload-before-loss, duplicate reload, invalid probability and schema mismatch;
- analytic no-reload occupancy checks;
- artificial shot arrays for Wilson, paired-difference and FDR aggregation.

Visible scored workloads use fixed public seeds and 2,048 shots per cell:

```text
d=3,T=3,basis=X,p=1e-3,p_m=1e-3,p_loss=3e-3
d=3,T=6,basis=Z,p=3e-3,p_m=1e-3,p_loss=1e-2
d=5,T=5,basis=X,p=1e-3,p_m=3e-3,p_loss=3e-3
d=5,T=10,basis=Z,p=3e-3,p_m=3e-3,p_loss=1e-2
```

Each workload includes `none`, `immediate`, `periodic(d)`, and `threshold(0.05)`. The validator repeats timing three times after one unscored warmup.

## Sealed holdout family

The private generator uses the same schema and physical ranges but unseen combinations of:

- master seeds;
- coordinate relabelings that preserve adjacency;
- loss/reload timelines;
- `d in {3,5}`, `T in {d,2d}`, both bases;
- `p,p_m in [1e-4,3e-3]` and `p_loss in [1e-4,3e-2]`;
- policies and delay/reset controls within the frozen matrix.

Holdout labels are generated outside attempt worktrees by the independent oracle for small cases and by a frozen main-branch reference for larger cases. Provenance records generator commit and parameter-family bounds but does not reveal seeds, labels, exact masks, or file hashes that candidates could use as lookup keys.

The holdout query budget is exactly **one aggregate query for the project**. It is spent only after the dev implementation gate and science artifact checklist pass. A failed holdout ends the run; it is never inspected and tuned against.

## Isolation

SCNet cannot provide user Docker access. Canonical execution therefore uses:

- SHA-256 locked CPython 3.11 manylinux wheels;
- `.venv-q66-v1` built by Slurm after artifact verification;
- one candidate subprocess in a Slurm cgroup with fixed CPU, 16 GiB RSS and 2,700 s wall time;
- cleared proxy variables and a network-denial preflight;
- candidate worktree mounted/represented as the only readable candidate root;
- private instances passed only to the main-branch validator process;
- before/after filesystem snapshots to detect writes outside the allowed output root;
- process-group termination on timeout and child-process accounting.
- process-group escape syscalls denied, with descendant termination verified
  after normal candidate exit as well as timeout.

The fallback and its reason are recorded in `STATE.md` and validator manifest. If network isolation cannot be demonstrated on SCNet, validator gate remains pending.

The completed v1 validator evidence proves inherited network denial but does
not prove cleanup after a normally exiting candidate leaves a background
process. The v2 isolation candidate additionally denies `setsid` and
`setpgid`, inventories the candidate process group after every exit, terminates
all surviving members, rejects any run where a background member was detected,
and records that evidence in every repetition. It remains unaccepted until a
consolidated Slurm validation allocation passes the v2 contracts and all five
negative controls, including `background-escape`.

The final no-labels-during-candidate sequence and one-query evidence contract
are frozen in `research/references/holdout-temporal-isolation.md`.

## Score

For correct candidates:

```text
q3 = validated d=3 shots / median_seconds
q5 = validated d=5 shots / median_seconds
score = sqrt(q3*q5)
```

Any guard failure yields rejection and no score. An implementation becomes incumbent only at `>=1.02 * incumbent_score`; final acceptance requires at least `0.95 * frozen_reference_score` so correctness work is not rejected merely for small platform noise.

## Standard negative controls

- `cheater`: lookup keyed by visible instance ID/hash.
- `wrong-answer`: correct shapes but flips one known logical result.
- `timeout`: exceeds the harness deadline and spawns a child.
- `env-escape`: attempts network, private-path reads and outside-root writes.
- `background-escape`: exits successfully while leaving a detached-stdio child
  alive for a later private phase.

## Topic-specific negative controls

- `label-reader`: predictions change when labels are removed/poisoned.
- `future-policy`: reload decisions change when only future loss events change.
- `drop-failures`: emits fewer shot IDs or omits catastrophic shots.
- `mask-ignored`: saves loss arrays but decodes with the no-loss graph.
- `rng-order`: outputs change under policy ordering, shard size or worker count.
- `noise-reducer`: silently changes `p`, `p_m` or loss sampling to improve logical rate/throughput.
- `timeline-shift`: applies loss or reload one boundary early/late.
- `hardcoded-seed`: passes visible seeds but fails generated seeds and coordinate relabeling.
- `invalid-acceptor`: silently accepts bad coordinates, reload-before-loss or illegal state transitions.
- `threshold-claimer`: labels `d=3,5` curve crossing as an asymptotic threshold in structured report metadata.

Every control must be an executable candidate directory with a specific `errors[]` entry in `manifest.json` self-test results. A newly discovered exploit reopens the validator gate until represented by another control.

## Exit and report contract

The CLI follows the installed autoresearch validator contract:

```text
validate CANDIDATE [--precheck] [--instances dev|holdout] [--out REPORT.json]
```

- `0`: evaluated; inspect JSON status/score.
- `1`: candidate rejected with specific errors.
- `2`: validator infrastructure failure; does not consume a candidate result.

Every failure names phase/instance, observed vs expected behavior, and the first debugging target. Generic “validation failed” is itself a gate failure.
