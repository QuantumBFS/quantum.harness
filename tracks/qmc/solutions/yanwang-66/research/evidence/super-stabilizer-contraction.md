# Super-stabilizer contraction contract

Date: 2026-07-29

The frozen model requires same-type checks adjacent through missing data sites to
be multiplied into super-stabilizers. The implementation represents the same
quotient without materializing a variable-width syndrome array:

1. Relevant stabilizer checks are detector nodes; the compatible code boundary
   is one additional node.
2. Every revealed missing data site is the graph edge joining its adjacent
   checks, or joining its single adjacent check to the boundary.
3. Giving that edge zero matching weight contracts its endpoints. For each
   component not connected to the boundary, the only invariant syndrome bit is
   the XOR of all check outcomes in the component. This is the outcome of the
   product super-stabilizer after internal missing-site factors cancel.
4. A boundary-connected component has no independent check parity; this is the
   graph representation of deforming the compatible boundary around the loss.
5. A zero-syndrome product of erased edges with odd logical parity is marked
   `catastrophic_loss` and remains in the denominator.

`test_erasure_contraction_matches_super_stabilizer_quotient` exhausts all 512
data-loss subsets of the exported `d=3`, memory-X geometry on SCNet. For every
subset it independently enumerates the syndrome span, checks the component
parity invariants, and compares the decoder's parity-union catastrophic flag
with exhaustive odd-logical-cycle detection.

This contract validates the fixed-shape graph representation; it does not claim
that individual raw check bits inside a contracted component are physical
super-stabilizer measurements. Consumers must use the revealed erasure history
with those bits, as required by the decoder input contract.
