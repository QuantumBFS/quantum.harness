# Seed-61 exact short-word protocol

## Scope

`oracle.exterior_seed61_short_words` is the finite half of a prospective
seed-61 theorem.  It replays the frozen
`exact5-shear-loop-pair`/seed-61 card, clears the common denominator, and
checks

```text
det(I + B_w) > 0
```

with integer arithmetic for every binary word in the requested length
range.  The production target is lengths 1 through 23.

The only quotient symmetries used are:

1. cyclic rotation, by `det(I + XY) = det(I + YX)`;
2. `w -> complement(reverse(w))`, induced by transposing the product.

Do not add a global bit-complement quotient.  The exact frozen oracle gives
different values for `001011` and its complement `110100`; that shortcut
already fails at length six.

Binary necklaces are generated directly and paired under the twisted
reflection.  At length 23 this leaves 182,362 exact classes instead of
8,388,608 raw words.  The collector verifies that orbit sizes sum to
`2^length` at every length.

## Two-machine production

Use one common shard count and disjoint shard IDs.  With 14 WSL processes
and 62 CPU-machine processes:

```bash
export PYTHONPATH=/path/to/repo/tracks/qmc/solutions/no-negative-vibes
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

python -m oracle.exterior_seed61_short_words scan \
  --min-depth 1 --max-depth 23 \
  --shard-id ID --shard-count 76 \
  --run-dir /path/to/run
```

Launch IDs `0..13` on WSL and IDs `14..75` on the CPU machine.  Each process
writes exactly one atomic file named
`shard-ID-of-0076.json`.  Copy the CPU files into the WSL run directory and
assemble:

```bash
python -m oracle.exterior_seed61_short_words collect \
  --shard-count 76 \
  --run-dir /path/to/run
```

Accept the finite certificate only when `collect.json` has:

```text
status = strictly-positive
complete = true
covered_word_count = sum(2^n, n=1..23) = 16,777,214
```

The collector also reports the global exact minimum and its canonical word.
`--stop-on-nonpositive` may be added during exploratory runs; such a shard is
intentionally incomplete, but its exact witness is already enough to reject
the candidate.

## Focused verification

```bash
python -m pytest tests/test_exterior_seed61_short_words.py -q
```

The two tests independently check:

- the safe symmetry classes partition every raw word through length seven;
- a three-shard exact scan has the same minimum as the existing SymPy exact
  determinant oracle through length seven.

A Windows smoke benchmark of one of 76 length-23 shards took about 15
seconds, including replaying the card and enumerating all necklace indices.
This is a throughput estimate, not production evidence.
