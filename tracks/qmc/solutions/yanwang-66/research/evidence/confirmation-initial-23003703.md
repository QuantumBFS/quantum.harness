# Initial independent-seed confirmation: job 23003703

Status: failed at the formal candidate-identity gate; no simulation result or
scientific claim was produced.

Job `23003703` runs the unchanged preregistered initial confirmation design in
one `xhacnormalb` allocation: 40 CPUs, 64 GiB, 8 physical groups, 5 paired
policies per group, 20,000 shots per cell, and 800,000 total shots. It includes
the read-only-control-copy regression contract and all five v2 negative
controls before simulation.

```text
orchestration commit:
0ddb2c2aa6c2e4f1c7023a03c47d087097aa8aef

orchestration tree:
671fe3ff75832cda7d79cee1065a80109b2a7583

orchestration archive SHA-256:
0d8c3bad0bb4c697e179c5061af9162d6d3c94293f27570cc78a7c369ccacf14

orchestration snapshot:
bundle-confirm-0ddb2c2

orchestration snapshot manifest SHA-256:
54f0714a1bc07dc0662944d8387d28e0ba788b4aea990d5a6b5bcdda76b73522

candidate commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

candidate snapshot manifest SHA-256:
755fdd4cf14a77f7ad3d7e2d729df76daa08ea8744e5463b0434a19635bc8165

confirmation family file SHA-256:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a

surface-code instance database SHA-256:
25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751

environment lock SHA-256:
f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8
```

The immutable snapshot contains 143 files and passed its full checksum
manifest plus both database-input checks before submission. Completion requires
Slurm exit `0:0`, all contract and negative-control gates, 40 validated cell
records, 8 paired group manifests, 800,000 exact-replayed shots, and a verified
top-level checksum manifest.

## Failure record

Slurm reported `FAILED`, exit `1:0`, after 109 seconds. All 24 contracts and all
five v2 negative controls passed. The generated 8-group, 40-cell matrix also
passed before the runner rejected the formal xh5 candidate snapshot on its
tree hash. No simulation or exact replay started.

The xh5 archive reconstruction contained one extra non-executable file,
`src/README.md`, that was absent from the SCNet snapshot used for the accepted
reference validator. Every Python source checksum matched. Reconstructing the
candidate without that documentation file exactly reproduced the accepted
candidate-tree SHA-256
`829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482`.
The corrected candidate snapshot is `reference-0a73ba3-scnet-exact`, with
manifest SHA-256
`acdd7df0e4beb96b3ce3ccc8b618091b686bea62fe76811022df6893bf221851`.

A subsequent xh5 submission was rejected before job creation because account
`giggleliu` had reached its 200 submitted-job limit. No xh5 job ID or compute
allocation was created for that attempt.
