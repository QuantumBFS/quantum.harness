# Circuit portfolio for non-monotone optimization

This file records verified parent topologies that should remain available even
when they are not the current gate-count winner. A candidate may be retained
as a search parent when it offers a different internal-function fingerprint,
lower depth, or a denser population of large low-boundary tensor regions.

## Current winners

- A: `mystery-A.txt`, 37 gates.
- B: `mystery-B.txt`, 49 gates.
- C: `mystery-C.txt`, 156 gates, depth 36, internal fingerprint
  `03122b67bee3524e`.
- D: `mystery-D.txt`, 113 gates, depth 27.

## Representative C search parents

- `abc-work/sergeev-158/mystery-C.txt`: the direct 158-gate realization of
  Sergeev's encoded-pair multiplier.
- `abc-work/pre-sergeev-165/mystery-C.txt`: the previous verified 165-gate
  winner, retained because its topology is unrelated to the Sergeev network.
- `abc-work/c-island-091.txt`: 166 gates, depth 31, fingerprint
  `4f09ee59951167b0`.
- `abc-work/c-island-041.txt`: 166 gates, depth 36, fingerprint
  `a55b864b8df0a04f`.
- `abc-work/mystery-C-mfs2-xextract-global.txt`: 166 gates, depth 55,
  fingerprint `f11be4914a808b4b`.
- `abc-work/mystery-C-buffree.txt`: 166 gates, depth 58, fingerprint
  `0413dde1c9a9f25f`. This is the regular parent from which the verified
  165-gate low-product replacement can be replayed.
- `abc-work/mystery-C-seedopt2-098.txt`: 167 gates, depth 34, fingerprint
  `f1dc8162fd362744`. This is a deliberately non-monotone parent.

The portfolio scanner found 29 distinct verified 166-gate internal
fingerprints and many verified 167- and 168-gate parents.

## Representative B and D search parents

- B has at least 54 verified internal topologies at or below 55 gates.
  Multiple independent 49-gate parents exist at depths 16 through 21.
- D has a 113-gate winner, retained 114- and 115-gate predecessors, and several
  distinct 117-gate parents. The 113-gate winner was obtained by replacing a
  27-gate, eight-input, six-output joint region of the 114-gate parent with a
  verified 26-gate realization. The 114-gate predecessor is retained at
  `abc-work/parallel/bd_tensor/mystery-D-114-candidate.txt`.

## Promotion policy

1. Never overwrite a retained parent during exploration.
2. Store each line of work under its own `abc-work/parallel` directory.
3. Verify every local replacement over its complete boundary tensor.
4. Embed with `embed_tensor_region.py`, which re-topologically sorts the
   result and performs complete-domain verification.
5. Promote to a formal `mystery-*.txt` file only when the complete candidate
   has fewer gates than the current winner.
6. Keep equal-count and up-to-three-gate-worse candidates only when their
   internal fingerprint or tensor-cut profile is new.

Run `scan_circuit_portfolio.py` to refresh the verified topology inventory.
