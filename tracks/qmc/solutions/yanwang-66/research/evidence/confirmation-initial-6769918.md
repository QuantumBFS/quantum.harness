# Initial independent-seed confirmation: job 6769918

Status: completed and checksum-verified on SCNet. This is accepted initial
evidence, but it is not a final confirmation claim until the registered
stopping cycle finishes.

Job `6769918` runs the unchanged preregistered initial confirmation design as
one `dzagnormal` allocation: 8 CPUs, 32 GiB, 1 required GPU, 8 physical groups,
5 paired policies per group, 20,000 shots per cell, and 800,000 total shots.
The CPU allocation controls only process parallelism; it does not alter any
request, seed, shot, or validation rule.

```text
orchestration commit:
20fb57c8ae5d5e62901a0e346fe10ec745045c74

orchestration tree:
e3ee1e95a27d94b7044fbc6fcef3ef57c687ff77

orchestration archive SHA-256:
e52853134ff1c9a1b14c40c697fec7fd1dfa511a78e1e1e2eff9de247af29773

orchestration snapshot:
bundle-confirm-20fb57c

orchestration snapshot manifest SHA-256:
d6e70534b4691c85bea9005a017099a02cf97ca5bf6c099f4cff944970aeecf7

candidate commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

candidate snapshot:
reference-0a73ba3

candidate snapshot manifest SHA-256:
c9d160988f8e509e6a576fd572876a870e8465c390d6b7b6b8bb9e0e89327acd

accepted candidate tree SHA-256:
829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482

confirmation family file SHA-256:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a

surface-code instance database SHA-256:
25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751

environment lock SHA-256:
f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8
```

The immutable orchestration snapshot contains 144 files and passed its full
checksum manifest plus both database-input checks before submission. The
candidate is the exact SCNet snapshot whose 16-cell reference validator and
tree identity were accepted earlier.

Job `6769918` completed with exit `0:0` after 41 minutes 29 seconds. All 24
contracts and all five v2 negative controls passed. The allocation published 8
paired group manifests, 40 validated cells, and 800,000 exact-replayed shots.
The result checksum manifest passed and has SHA-256:

```text
a09a75d52f44825c878af47203c8b00c6ed0d259380a8327c12e873cf701cebd
```

The accepted artifact root is:

```text
/work/home/hesicheng5/quantum-harness-ch66/results/confirmation/initial/6769918
```

The initial counts are inputs to the stopping analysis and do not independently
authorize a headline conclusion.
