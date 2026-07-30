# Challenge 194: long-range q=1 random-cluster model

This directory implements the pinned independent-edge finite-ring model from
QuantumBFS/quantum.harness issue #194. It does not use Gori et al.'s
minimum-image `C/r^(1+sigma)` convention.

## Scope

The validated production engine now supports the physical Pilot phase. Pilot
data are exploratory window-selection data only; they make no transition,
critical-point, critical-exponent, scaling, or universality claim.

## Setup

```bash
uv sync \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  --python 3.12
```

## Verify

```bash
uv run \
  --project tracks/qmc/solutions/frustration-free/challenge-194 \
  pytest -q
```

The accelerated sampler is accepted only when it agrees with analytic edge
probabilities and exact small-system partition distributions.

## Pilot P0 orchestration

Build the immutable 96-cell run spec on the target compute runtime:

```bash
uv run scripts/run_pilot.py build-spec \
  --validation-report /absolute/validation/report/report.json \
  --output-root /absolute/shared/pilot-p0 \
  --run-spec /absolute/shared/pilot-p0/run_spec.json
```

Inspect pending cells, run one zero-based cell, merge all completed cells, and
verify a downloaded tree:

```bash
uv run scripts/run_pilot.py pending --run-spec /absolute/shared/pilot-p0/run_spec.json
uv run scripts/run_pilot.py run-cell --run-spec /absolute/shared/pilot-p0/run_spec.json --cell-index 0
uv run scripts/run_pilot.py merge --run-spec /absolute/shared/pilot-p0/run_spec.json
uv run scripts/run_pilot.py verify --run-spec /downloaded/pilot-p0/run_spec.json
```

`scripts/pilot_array_slurm.sh` maps Slurm array IDs `1..96` to cell indices
`0..95`, requires one CPU, and isolates the Numba cache per cell. Task 10's
120-second/4-GiB capability gate and Task 11 optimization were explicitly
waived after correctness validation. The benchmark status is
`cancelled-without-capability-report`; this is not a passed performance gate.

Download a completed Pilot root with checksummed, partial-safe `rsync`, then
run the local semantic verifier:

```bash
scripts/download_pilot.sh \
  wuzh02-jiangweiqi \
  /work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-739880d \
  /absolute/local/results/challenge-194/pilot-p0-739880d \
  /absolute/path/to/challenge-194/.venv/bin/python
```

The local destination's real non-symlink parent must already exist, and the
destination must be absent, empty, or the same resumable download. Equivalent
absolute lexical spellings (repeated separators, `.` components, or trailing
slashes) share one normalized destination and sibling state; `/` is rejected.
The script never deletes source or destination files. It atomically claims a
sibling `<local-root>.download-claim` directory and stores no-clobber source,
verified-completion, and uniquely created transfer-log files under the real
non-symlink sibling `<local-root>.download-state` directory. A completed root
is only reverified: `rsync` is never invoked again. Unexpected claims are
preserved for diagnosis, and all transfer-generated logs remain outside the
immutable Pilot root.

Legacy roots with the former sibling `.download-source` marker are verified
before either normal source or completion state is published. Failed legacy
verification writes only a read-only diagnostic under the external state
directory; retries verify again without invoking `rsync`.

## P0 analysis and P1 publication boundary

Run the following commands from the solution directory. The paths below are
the current verified local evidence, not placeholders:

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194

uv run python scripts/run_pilot.py verify --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-739880d/run_spec.json

uv run python scripts/analyze_pilot.py analyze --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-739880d/run_spec.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json
```

The immutable analysis exists. Its embedded analysis-document SHA256 is
`e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`;
the SHA256 of the complete canonical file is
`44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`.
Inspect both without changing the artifact:

```bash
sha256sum /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json
uv run python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["analysis_document_sha256"])' \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json
```

The implemented P1 build command is:

```bash
uv run python scripts/analyze_pilot.py build-p1 --analysis \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json
```

For the current P0 evidence it exits nonzero with
`P0 extension required before P1 publication: 0.9, 1.0`.
`p1_protocol.json does not exist`; P1 has not been published or executed.
Do not run the verifier until a future successful build has created the
protocol. After that successful build, the implemented verification command
is:

```bash
uv run python scripts/analyze_pilot.py verify --analysis \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json \
  --p1-protocol /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json
```

## Frozen P0 extension construction and execution

The versioned P0 extension is fully preregistered, but no P0 extension data
exist yet. The extension samples only sigma `0.9` and `1.0`; it does not alter
the scientific engine, relax the selector, or authorize a claim.

The checked-in `pilot_correctness_approval.json` authenticates approval/source
revision `877ab9393f320bfe31ff74a26c3db1fb205d7ef3` and package
`validation-prod-877ab93`: report SHA256
`036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8`,
run-spec SHA256
`5b3eea4c460e14a57aec9df606447137d787a5c66dd7e98e1dffdcf566f430e2`,
protocol SHA256
`c7e980eeadaf8ed75e4d20cebb1e2c5d5f57a1cfc329afa7678ae586f5b7f488`,
check-registry SHA256
`6e25ea41899544f2a9de3589beb1ee94b1f3dc505638b8f8e5164a4322b56a1d`,
and scientific-engine SHA256
`457fa669da897e59b03681039db6121fde4d7be9295bb46a743c8448875b3ee9`.
Wuzh02 execution uses the repository-root interpreter proven by successful P0
job `41506576`:
`/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python`.

From the exact clean deployed repository, the compute-node build wrapper uses
`HARNESS_RUN_SPEC` as the canonical P0 analysis path and derives the protocol,
approved validation report, and output root from its parent:

```bash
sbatch \
  --export=ALL,HARNESS_RUN_SPEC=/absolute/results/challenge-194/p0_analysis.json,HARNESS_ENTRYPOINT=/absolute/deployed/quantum.harness,HARNESS_COMMAND=/absolute/offline/python \
  scripts/pilot_extension_build_slurm.sh
```

The wrapper verifies canonical analysis-file SHA256
`44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`
and runs these implemented commands:

```bash
/absolute/offline/python scripts/analyze_pilot.py build-p0-extension \
  --analysis /absolute/results/challenge-194/p0_analysis.json \
  --p0-evidence-root /absolute/results/challenge-194/pilot-p0-739880d \
  --output /absolute/results/challenge-194/p0_extension_v1_protocol.json

/absolute/offline/python scripts/run_pilot.py build-extension-spec \
  --protocol /absolute/results/challenge-194/p0_extension_v1_protocol.json \
  --validation-report /absolute/results/challenge-194/validation-prod-877ab93/report/report.json \
  --analysis /absolute/results/challenge-194/p0_analysis.json \
  --p0-evidence-root /absolute/results/challenge-194/pilot-p0-739880d \
  --output-root /absolute/results/challenge-194/pilot-p0-extension-v1 \
  --run-spec /absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json
```

`--p0-evidence-root` is mandatory at both construction stages. It must be an
absolute canonical non-symlink directory containing the frozen
`pilot-p0-739880d/run_spec.json` and `progress.json` bytes. These artifacts are
never inferred from a checkout-local, gitignored `results/` tree; the canonical
P0 analysis remains the separate explicit `--analysis` input.

After the build succeeds, submit the immutable worker root with exact
one-CPU, 1800-MiB, 40-minute resources. Slurm IDs `1..96` map to zero-based
cell indices. The wrapper accepts only canonical decimal IDs in that range
before performing arithmetic:

```bash
sbatch --array=1-2%2 \
  --export=ALL,HARNESS_RUN_SPEC=/absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json,HARNESS_ENTRYPOINT=/absolute/deployed/quantum.harness,HARNESS_COMMAND=/absolute/offline/python \
  scripts/pilot_extension_array_slurm.sh

sbatch --array=3-32,49-80%16 \
  --export=ALL,HARNESS_RUN_SPEC=/absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json,HARNESS_ENTRYPOINT=/absolute/deployed/quantum.harness,HARNESS_COMMAND=/absolute/offline/python \
  scripts/pilot_extension_array_slurm.sh

sbatch --array=33-48,81-96%8 \
  --export=ALL,HARNESS_RUN_SPEC=/absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json,HARNESS_ENTRYPOINT=/absolute/deployed/quantum.harness,HARNESS_COMMAND=/absolute/offline/python \
  scripts/pilot_extension_array_slurm.sh
```

The same schema-dispatched CLI reports pending cells, runs cells, merges all
96 results, and verifies a downloaded extension:

```bash
/absolute/offline/python scripts/run_pilot.py pending --run-spec /absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json
/absolute/offline/python scripts/run_pilot.py run-cell --run-spec /absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json --cell-index 0
/absolute/offline/python scripts/run_pilot.py merge --run-spec /absolute/results/challenge-194/pilot-p0-extension-v1/run_spec.json
/absolute/offline/python scripts/run_pilot.py verify --run-spec /absolute/download/pilot-p0-extension-v1/run_spec.json
```

After extension evidence exists and has been downloaded, run the immutable
local analysis workflow below from this solution directory.
Both source analyses must first be recomputed against their verified run roots.
The two analysis commands must return `verified-existing` before `combine`; a
newly `published` source analysis is not sufficient for that combine attempt.

```bash
uv run python scripts/run_pilot.py verify --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-739880d/run_spec.json

uv run python scripts/analyze_pilot.py analyze --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-739880d/run_spec.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json

uv run python scripts/run_pilot.py verify --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-extension-v1/run_spec.json

uv run python scripts/analyze_pilot.py analyze-extension --run-spec \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-extension-v1/run_spec.json \
  --protocol /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_extension_v1_protocol.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_extension_v1_analysis.json
```

Only after both recomputations return `verified-existing`, combine and select
the fully source-validated evidence:

```bash
uv run python scripts/analyze_pilot.py combine --p0-analysis \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json \
  --extension-analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_extension_v1_analysis.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_analysis_v2.json

uv run python scripts/analyze_pilot.py select --analysis \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_analysis_v2.json \
  --p0-analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json \
  --extension-analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_extension_v1_analysis.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_brackets_v2.json
```

The combined-v2 selector and builder never trust combined JSON alone. Both
commands require the exact P0 and extension analyses and recompute full source
validation. If every combined bracket is selected, build P1 with the same
three inputs:

```bash
uv run python scripts/analyze_pilot.py build-p1 --analysis \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_analysis_v2.json \
  --p0-analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json \
  --extension-analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_extension_v1_analysis.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json
```

`analyze-extension`, `combine`, `select`, and `build-p1` use bounded canonical
JSON reads and immutable no-clobber publication. A byte-identical retry returns
`verified-existing`; changed installed bytes, malformed canonical input, or a
scientific refusal exits nonzero without replacing or newly creating output.
The legacy P0-analysis-v1 `build-p1 --analysis ... --output ...` form remains
available only without either combined-source option. Mixed or extraneous
source arguments fail closed.

No P0 extension data exist yet, so there is no extension analysis or combined
analysis to select from. `p1_protocol.json` does not exist and P1 remains
blocked until the extension is executed, downloaded, verified, analyzed, and
all six frozen acceptance checks pass. Brackets must never be fabricated or
relaxed.

Publication is no-clobber. Repeating `analyze` or a future successful
`build-p1` against byte-identical output returns `verified-existing`.
Different installed bytes fail closed rather than being replaced. Pilot cell
restart preserves `.partial` and `.intent` diagnostics, resumes only verified
immutable batches, and deeply verifies an existing completed cell. A completed
download is reverified without rerunning `rsync`.

## Design and references

- `DESIGN.md` pins the scientific and statistical protocol.
- `PLAN.md` records the test-driven implementation sequence.
- `PILOT_PLAN.md` freezes P0, provenance, resource, restart, and P1 boundaries.
- `references/README.md` records source URLs and SHA256 hashes.
