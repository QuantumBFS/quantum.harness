# Exact anti-diagonal spatial-reflection reduction

## Candidate symmetry

For the fixed level-1 Shastry--Sutherland window, the site map

```text
(x, y) -> (-y, -x)
```

preserves the 3-by-3 outer patch, its central inner site, both instantiated
dimer bonds, and every square-nearest-neighbor bond. It acts only on site
labels and therefore commutes with computational-basis conjugation and every
spin-axis permutation used in the preceding exact reductions.

## Fail-closed route

The implementation is deliberately a separate gate after the full-spin
isotypic model. Before it may produce a solver input, it must verify:

1. the exact site map is involutive and preserves the finite Hamiltonian term
   multiset;
2. the complete retained moment inventory is closed under the reflection;
3. every retained isotypic block row has a signed-permutation image in the
   same block;
4. every one of the 6,104 exact block coefficients is covariant;
5. the equality row space is invariant;
6. every plus/minus spatial cross block vanishes after moment projection; and
7. the combined spatial eigenspace bases have exact full rank.

The first Slurm truth attempt is an inventory run: it records the exact moment
count, split block dimensions, packed-coordinate count, and cross-check count.
Those counts are hardened only after the mathematical gates pass.

The first inventory attempt exposed one necessary composition in step 2.
The full-spin moment inventory stores one lexicographic representative per
spin-axis orbit. Reflecting such a representative need not itself be the
lexicographic representative of the reflected orbit. The spatial action must
therefore apply the site reflection and then the already-proved full-spin
representative map. This composition is exact because the two group actions
commute.
