# Initial independent-seed confirmation: job 23003318

Status: failed during the negative-control gate; no simulation result or
scientific claim was produced.

Job `23003318` runs the unchanged preregistered initial confirmation design in
one `xhacnormalb` allocation: 40 CPUs, 64 GiB, 8 physical groups, 5 paired
policies per group, 20,000 shots per cell, and 800,000 total shots. It runs all
contract and v2 negative-control gates before simulation, executes 40 cells in
parallel, and exact-replays all outputs before publication.

## Frozen identities

```text
orchestration commit:
7d88654e9388c4b794faad75f5aeb19c89af1f77

orchestration tree:
ba67280398d407e64398a203461d91ed8a311790

orchestration archive SHA-256:
39bdd0a8f381dc3291cf7e9ab49116284941d1f1251dee67a2f15d52e337731c

orchestration snapshot:
bundle-confirm-7d88654

orchestration snapshot manifest SHA-256:
5461914b9c8978769458ca81e9fc76f99e3df7f82c264b0f96b61577a8738cc1

candidate commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

candidate snapshot:
reference-0a73ba3

candidate snapshot manifest SHA-256:
755fdd4cf14a77f7ad3d7e2d729df76daa08ea8744e5463b0434a19635bc8165

confirmation family file SHA-256:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a

surface-code instance database SHA-256:
25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751

environment lock SHA-256:
f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8
```

The orchestration snapshot contains 142 files including the generated instance
database. Its manifest and both frozen database inputs passed shell-level hash
verification before submission. Completion still requires Slurm exit `0:0`,
all gates, 40 validated cells, 8 paired group manifests, 800,000 exact-replayed
shots, and a verified top-level checksum manifest. The stopping analysis may
still require paired continuation up to the preregistered cap.

## Failure record

Slurm reported `FAILED`, exit `1:0`, after 17 seconds. All 23 selected Python
contracts passed. The v2 negative-control run then stopped at `env-escape`
because the ephemeral control copy inherited read-only modes from the immutable
snapshot and could not write its marker before emitting JSON evidence. The
validator therefore received empty stdout and rejected the evidence as
malformed. Matrix generation, simulation, and exact replay never started.

The correction is limited to restoring owner-write permission on ephemeral
negative-control copies. It leaves the immutable orchestration and formal
candidate snapshots read-only, and preserves the intended guard: the
`env-escape` control must mutate its disposable source tree so the validator
detects the before/after hash change while the kernel independently denies its
socket attempt.
