# Initial independent-seed confirmation: job 23002898

Status: failed during the pre-simulation contract gate; no simulation result or
scientific claim was produced.

Job `23002898` was submitted to xh5 `xhacnormalb` as one consolidated
allocation with 40 CPUs, 64 GiB memory, and a six-hour wall limit. It has no
dependency on the SCNet discovery array and uses the preregistered
`q66-confirmation-seed-v1` domain.

The frozen initial design contains 8 physical groups, 5 paired policies per
group, and 20,000 shots per cell: 40 cells and 800,000 total simulated shots.
The allocation runs the confirmation and experiment-core contracts plus the v2
sandbox contract and all five negative controls before simulation. It then
executes the 40 cells concurrently and performs an exact replay of every run
before atomically publishing the result root.

## Frozen identities

```text
orchestration commit:
bdcd78b46c956bf25bc5968775a08b5a6c079f55

orchestration archive SHA-256:
bfcedd8e4f8688d2899f204184ed0162bd0f7fc5b511abee9702647d25a38c4b

orchestration snapshot:
bundle-confirm-bdcd78b

orchestration snapshot manifest SHA-256:
aa3166e96246bf94ae676a7d10b68db506c312fbd68c3f55c2e8266cb92e36fa

candidate commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

candidate tree SHA-256:
829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482

candidate archive SHA-256:
d171b434c425cb9ee4772db9b83016da3fb22cdaea806f94cca98e7777b00167

candidate snapshot manifest SHA-256:
755fdd4cf14a77f7ad3d7e2d729df76daa08ea8744e5463b0434a19635bc8165

confirmation family file SHA-256:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a

environment lock SHA-256:
f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8
```

The orchestration snapshot manifest covers 138 files and the candidate
snapshot manifest covers 114 files. Both manifests passed full verification
after atomic extraction on xh5. The candidate tree is independently checked by
the allocation before and after all simulations.

## Failure record

Slurm reported `FAILED`, exit `1:0`, after 66 seconds. The contract run produced
15 passes and 8 failures. All eight failures had the same root cause: the job
set `Q66_INSTANCE_FILE` to
`bundle-confirm-bdcd78b/research/database/surface_code_instances.jsonl`, but
that generated database was not present in the orchestration snapshot. The
simulation, negative controls, matrix generation, candidate execution, and
exact replay never started. This is an orchestration-input path defect, not an
observed candidate correctness failure or a scientific result.

The generated database remained unchanged on both clusters with its previously
frozen SHA-256
`25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751`.
A replacement allocation must explicitly verify this hash before running the
same frozen contracts.

Completion requires Slurm exit `0:0`, successful negative controls, 40
validated cell records, 8 paired group manifests, 800,000 exact-replayed shots,
and a verified top-level result checksum manifest. Initial completion alone
does not authorize a headline claim; the preregistered stopping analysis must
still decide whether further paired shots are required.
