# Exact full-spin nontrivial-character cone reduction

## Route

The full spin-axis permutation quotient identifies scalar moments under all
six proper-rotation lifts of S3, but its first implementation conservatively
retains every PSD cone from the earlier order-two spin-axis model. Three of
those cones are redundant.

The three nontrivial V4 characters form one transitive S3 orbit. For each
positive-matrix family, and for the facially reduced gap matrix, a signed row
permutation maps the retained 81-side orbit-representative character block to
the stable nontrivial character block before realification. The fixed
computational-basis conjugation gauge contributes an exact row phase in
`{±1,±i}`. Although the row parities vary, the source-to-target phase changes
all lie in one real/imaginary class for each related block. Every pairwise
transport factor is therefore real, leaving an exact unitary congruence
between the real symmetric blocks.

The stable character already has an exact invertible involution basis. Its
plus/minus cross block is exactly zero after invariant-moment projection.
Consequently:

```text
orbit representative PSD
    iff stable unsplit character PSD
    iff stable plus block PSD and stable minus block PSD.
```

The same argument applies when one eigenspace is empty, as in the one-row gap
block. Removing the two 81-side positive cones and one redundant gap scalar
therefore preserves the finite relaxation in both directions.

## Fail-closed truth gate

Before a derived model is accepted, the implementation checks over exact
rationals:

1. all three expected orbit-representative cones have dimensions `[1,81,81]`;
2. every orbit entry equals its direct full-S3 source projection;
3. all 6,643 orbit entries match the signed-permutation congruence to the
   stable character with their exact realification phases;
4. every retained stable-character combination basis has exact full rank;
5. every plus/minus cross entry is exactly zero; and
6. transport phases lie in one class per related block, so the exact
   mixed-phase pair count is zero.

The expected retained cone dimensions are
`[72,36,36,45,73,36,36,45]` plus one `1 x 1` gap block: nine real PSD cones,
10,064 packed triangle coordinates, and maximum side 73.

## Immutable solver-free inputs

Slurm job `22988604` built and independently reloaded the two derived MOFs
from clean source commit
`2f87e7a0ba7fe4cf61266087d3505bc4e3b2e990`. Each reload verified 3,250
variables, 10 constraints, the nine named real PSD cones, and the expected
side dimensions.

| gamma | model SHA-256 | runmeta SHA-256 |
|---|---|---|
| 0 | `a34c629a502b515fc615467bc876f691c0494d523c32f4e1dc5323d84b235d26` | `0b2942005c4bae13019508484d7af35106b67fbc978b067b99e484e7b588d086` |
| 1/2 | `ce3f4030afdc19d90b0f3a1bd2e8a2d6f3f06c19aad6c61e3b0bbbfe68de17a9` | `3c880055c1728faeda17c49301819b41272c5fcac0654c19db3e85da0e528ca3` |

The bundles live under the corresponding
`results/ss-full-spin-cone-real-g0p8-*-builder-20260729-r1/` directories and
are immutable solver inputs.
