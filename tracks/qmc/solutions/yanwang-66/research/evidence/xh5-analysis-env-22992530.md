# xh5 locked analysis environment and rejected snapshot: job 22992530

Job `22992530` prepared the independent xh5 analysis environment on
`xhhgnormal`. It completed `0:0` in 2 minutes 35 seconds on 2026-07-29. This
infrastructure and contract job does not consume an autoresearch attempt.

The job performed one combined preparation sequence:

1. verified all 29 files in `environment/wheels.sha256`;
2. installed exclusively from the offline wheelhouse with `--no-index`,
   `--require-hashes`, and the frozen requirements lock;
3. completed `pip check` with no broken requirements;
4. ran the discovery and 182-task bundle contract (`4 passed`);
5. verified discovery matrix SHA-256; and
6. staged an analysis snapshot that was rejected by the subsequent audit.

```text
requirements lock SHA-256:
f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8

discovery matrix SHA-256:
75490cff0949dc128221bf9168138d4d813c07014f26c1c9cacac9b2ec6b9b18

analysis orchestration commit:
cb8e5384b6942df48f7c9f81c4bbf3325e4f1405

rejected snapshot manifest file SHA-256:
94aa4a9a98f0c9c7387ef5a9afaa5ae81d17145b8901b24ef5514683aaba1ee9

installed venv size:
572 MiB
```

The interrupted 11 MiB cross-cluster venv copy was moved to
`.venv-q66-v1.incomplete-before-22992530`; it is retained for auditability and
is not referenced by any job. The installed environment was rebuilt locally
on xh5 from verified wheels instead of trusting that partial copy.

## Snapshot rejection

Post-run inspection found that `bundle-analysis-cb8e538` generated
`snapshot-checksums.sha256` inside the directory being traversed by `find`.
The manifest therefore contains a hash entry for itself. Its outer file hash
above is retained only as an identity for the rejected artifact; it is not a
valid snapshot trust root, and no analysis job may use this snapshot.

Correction job `22992778` reuses the valid locked venv, runs the experiment-core
and discovery contracts together, writes the checksum manifest outside the
snapshot staging tree, moves it into place only after hashing is complete, and
then executes `sha256sum --check` from the final snapshot. Its intended snapshot
ID is `bundle-analysis-50fd265`.

Job `22992778` ultimately failed `1:0` before snapshot staging. Seven contracts
passed and seven experiment-core tests raised `FileNotFoundError` because the
generated `surface_code_instances.jsonl` had not been placed at its frozen xh5
absolute path. This is an infrastructure input-layout failure, not evidence
against the simulator, and `bundle-analysis-50fd265` was not created.

The generated database was transferred from SCNet rather than regenerated or
hand-written. Both clusters report SHA-256
`25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751`.
Replacement job `22992910` uses source commit
`55ffeb1fa9a389d032e299f979e44465a33ad678`, includes the phase-2 continuation
bundle contract, and targets snapshot `bundle-analysis-55ffeb1`.

Job `22992910` failed `2:0` during test collection because Python imported an
older, misplaced top-level `reload_qec/` directory before the intended
`src/reload_qec/`. It did not create `bundle-analysis-55ffeb1`. The stale
top-level package and other misplaced root files were moved to
`results/quarantine/misplaced-root-sync/`, and the scripts now run tests outside
the submission directory and analysis from the immutable snapshot root.

Replacement job `22993003` targets `bundle-analysis-55ffeb1-r2` with hardened
import isolation from orchestration commit
`afdf8fd57b058b0b9a1b2194eeb35ce72186a52b`.

Job `22993003` completed `0:0` in 18 seconds. All 29 wheel hashes and
`pip check` passed; the combined experiment-core, discovery, initial-bundle, and
phase-2 continuation-bundle suite reported `15 passed`. The job generated the
checksum manifest outside the staging tree, moved it into the snapshot, and
successfully ran `sha256sum --check` from the final location. A separate audit
confirmed that the manifest has no entry for itself.

```text
accepted analysis snapshot:
bundle-analysis-55ffeb1-r2

accepted snapshot manifest SHA-256:
b82a909424f3703c50f015fde5590cf180e87cf255c4241ffa17e637fc898e9d
```
