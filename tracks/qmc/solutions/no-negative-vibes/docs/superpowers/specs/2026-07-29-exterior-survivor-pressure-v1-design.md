# Exterior Survivor Pressure v1 Design

Date: 2026-07-29

Status: approved by the standing autonomous discovery-loop instruction.

## Outcome

Run a second, immutable determinant screen over only the 1,713 Stage-1
`survivor-shallow-zero-failure` candidates.  For every two-atom exact card,
enumerate all mixed words of depths 5, 6, 7, and 8 in depth-then-lexicographic
order.  This is 472 words per candidate and 808,536 planned determinant
classifications before early stopping.

The 137 Stage-1 `uncertain-high-precision` candidates are not Stage-2
survivors.  They remain a disjoint high-precision replay queue.  The 454
stable negatives are terminal and are never repeated.

## Alternatives considered

1. **Extend the reviewed thin runner (selected).** Generalize its frozen
   protocol fields and add a parent-run survivor selector while preserving
   the exact Stage-1 default hashes and behavior.  This reuses candidate
   reconstruction, ownership, atomic resume, stale-manifest rejection, and
   collection.
2. Add a second runner.  This isolates files but duplicates the most
   failure-sensitive manifest and provenance logic.
3. Jump directly to random depth 4/8/16 histories.  This reaches long words
   sooner but leaves a complete, cheap depth-5..8 falsification gap and makes
   failures harder to compare.

## Protocol

- Run id: `exterior-survivor-pressure-v1`.
- Parent run id: `exterior-thin-first-v1`.
- Parent protocol hash:
  `e7d4a3223a383687db462b582f0c675a443a620cc16f74181df5782fbd21aa43`.
- Parent terminal population: 2,304 candidates with zero missing, stale,
  duplicate, or unresolved operational candidates.
- Selection: exactly the parent manifests whose status is
  `survivor-shallow-zero-failure`.
- Word order: all words over the fixed ordered atom alphabet, depths
  `[5,6,7,8]`, excluding pure repeated-single-atom words.
- Oracle: the unchanged `oracle.weights.classify_product`.
- Stop: first `negative`, `complex`, or `uncertain`.
- Terminal statuses:
  `rejected-negative`, `rejected-complex`,
  `uncertain-high-precision`, and `survivor-pressure-zero-failure`.
- Ownership: unchanged
  `int(candidate_id[:16], 16) % 76`; WSL owns shards 0--13 and the CPU
  machine owns shards 14--75.
- Concurrency: WSL 14 processes, CPU 62 processes; `OMP_NUM_THREADS`,
  `MKL_NUM_THREADS`, and `OPENBLAS_NUM_THREADS` are all `1`.

## Provenance and resume

The Stage-2 plan binds the new source commit, run id, depths, ordered selected
candidate identities, parent run id, parent plan hash, and parent protocol
hash into its plan/protocol hashes.  Planning fails closed unless the parent
collector proves all 2,304 candidates terminal and the selected identities
match validated exact cards.  Existing Stage-1 artifacts are read-only.

Every Stage-2 manifest binds the Stage-2 protocol hash and retains exact
candidate identity, first failure, tested-word count, minimum
`sigma_min(I+D)`, minimum-margin word, owner, and machine role.  Smoke results
live in a separate namespace.  Resume reuses only a fully matching terminal
manifest.

## Testing and launch gate

TDD must prove:

- the Stage-1 default plan/protocol hashes and 2,304-card behavior are
  unchanged;
- only parent survivors enter Stage 2;
- the 472-word order is exact and deterministic;
- parent missing/stale/operational/duplicate data fail planning;
- parent provenance or selected-card tampering fails closed;
- Stage-2 protocol tampering, wrong owner/role, stale resume, and smoke
  poisoning fail closed;
- collection accounts for every selected identity and preserves promotion
  evidence.

After focused and frozen-oracle regression tests, freeze one source commit
and complete bundle.  Require identical bundle hashes and exact clean commits
on Windows, WSL, and the CPU machine.  Run disjoint two-candidate smokes, then
launch all 76 shards.  Merge by candidate identity without overwrite and
record exact counts and strategy changes in Markdown.

## Claim boundary

Passing this finite screen means only “no negative or complex determinant was
found in all mixed words through depth 8.”  It is not an arbitrary-depth
theorem, an exterior-cone certificate, a novelty claim, or a physical HS
construction.
