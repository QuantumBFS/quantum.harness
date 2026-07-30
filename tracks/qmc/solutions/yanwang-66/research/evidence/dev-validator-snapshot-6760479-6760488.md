# Frozen reference development validator: jobs 6760479-6760488

The immutable reference validator chain completed on SCNet on 2026-07-29.
These setup and public-development jobs do not consume an autoresearch attempt.

## Chain

- `6760479`: generated the frozen 16-cell public development matrix; completed
  `0:0`.
- `6760486`: staged snapshot `reference-0a73ba3`; completed `0:0`.
- `6760487`: ran all 16 exact-replay validator cells from the snapshot; every
  array task completed `0:0`.
- `6760488`: aggregated the public score; completed `0:0` with
  `status=passed`.

## Frozen identities

```text
source commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

snapshot manifest SHA-256:
c9d160988f8e509e6a576fd572876a870e8465c390d6b7b6b8bb9e0e89327acd

development matrix SHA-256:
fb23abe85b9ab1428ff55bfc8b0d6e660e7d0cb5bbe784fb5c9ac69c9d5de592

candidate tree SHA-256:
829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482
```

The matrix names environment lock
`f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8`.
Every timed repetition passed exact replay, seccomp socket denial, the 16 GiB
address-space guard, and candidate-tree before/after hashing.

## Public development score

```text
validated d=3 shots: 16384
validated d=5 shots: 16384
q3: 356.97269138783236 shots/s
q5: 96.89405708913844 shots/s
score: 185.979924557991
peak children RSS: 322072 KiB
```

The slowest median candidate cell was d=5, T=10, immediate reload at
`30.144567739218473 s / 2048 shots`. Its three timed repetitions were
`28.482926837634295`, `33.66078434698284`, and `30.144567739218473` seconds.
The maximum validated compressed storage rate was `67.30078125 bytes/shot`.

For the 20,000-shot, eight-policy discovery group, summing the four validated
policy rates, scaling from four to eight policies, and applying a 1.2 runtime
factor projects the slowest geometry at approximately 43.98 minutes per group.
Applying a separate 1.5 storage factor projects the complete 44.8-million-shot
initial phase at `4,522,612,500 bytes`. The executable resource gate must
reproduce these projections before discovery is authorized.
