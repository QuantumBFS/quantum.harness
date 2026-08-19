# Exact full-spin trivial-character isotypic reduction

## Route

After the nontrivial-character cone orbit is removed, the largest remaining
positive blocks are the trivial-V4 blocks with spin-involution dimensions
`72+36` and `73+36`. Their rows are the identity, where present, and 36
three-row axis orbits of the form `{XX,YY,ZZ}` on a fixed spatial support.

For each three-row orbit, use the exact integer basis

```text
t = (1, 1, 1)
w = (1, 1, -2)
m = (1, -1, 0).
```

The `t` row is the trivial S3 irrep. The `w` and `m` rows are orthogonal
directions in the standard two-dimensional irrep. Full-S3 moment projection
makes all cross blocks vanish exactly and gives `W = 3M` entry by entry.
Therefore the full trivial-character source block is PSD if and only if its
`t` block and one retained `m` block are PSD.

The predicted equivalent representation keeps nine cones but changes the
positive side dimensions from
`[72,36,36,45,73,36,36,45]` to
`[36,36,36,45,37,36,36,45]`. This reduces packed PSD coordinates from
10,064 to 6,104 and the maximum side from 73 to 45 without changing the
finite relaxation.

## Required truth gate

Before this representation is used numerically, the exhaustive exact test
must establish:

1. the centered/scalar trivial source dimensions are `108` and `109`;
2. their row inventory is 72 three-row S3 orbits plus the scalar identity;
3. the combined `t,w,m` bases have exact full rank;
4. all 7,848 trivial/standard and standard/standard cross entries vanish;
5. all 1,332 upper-triangle standard entries obey `W = 3M`; and
6. two independent coefficient assemblies and the optimizer-free JuMP
   reconstruction agree.

## Passing result

Slurm job `22988781` passed all required gates: all 7,848 cross entries were
exactly zero, all 1,332 standard-block relations obeyed `W=3M`, both
combination bases had ranks 108 and 109, two coefficient builds agreed, and
the optimizer-free JuMP model reconstructed the expected nine cones.

The accepted exact representation has 3,250 moments, positive block
dimensions `[36,36,36,45,37,36,36,45]`, one `1 x 1` gap block, 6,104 packed
PSD coordinates, and maximum side 45. The passing `test.log` SHA-256 is
`1ec6ebdd77b6a94c04b1956c5cfd07f62ad780a2fb34f0fbed7c7351f12f2ee9`.
