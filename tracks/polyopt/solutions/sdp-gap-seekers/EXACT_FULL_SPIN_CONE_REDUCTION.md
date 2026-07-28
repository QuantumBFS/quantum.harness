# Exact full-spin nontrivial-character cone reduction

## Route

The full spin-axis permutation quotient identifies scalar moments under all
six proper-rotation lifts of S3, but its first implementation conservatively
retains every PSD cone from the earlier order-two spin-axis model. Three of
those cones are redundant.

The three nontrivial V4 characters form one transitive S3 orbit. For each
positive-matrix family, and for the facially reduced gap matrix, a signed row
permutation maps the retained 81-side orbit-representative character block to
the stable nontrivial character block. The computational-basis conjugation
parity is constant inside each character block, so its fixed realification
phase cancels from this congruence.

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
   stable character;
4. every retained stable-character combination basis has exact full rank;
5. every plus/minus cross entry is exactly zero; and
6. conjugation parity is uniform in every related V4 character block.

The expected retained cone dimensions are
`[72,36,36,45,73,36,36,45]` plus one `1 x 1` gap block: nine real PSD cones,
10,064 packed triangle coordinates, and maximum side 73.
