# Oddcycle pair frontier v1

This frozen protocol scans the 12,325 two-point alphabets

`{B(p_low,q,r), B(p_low,q,r)^T, B(p_high,q,r), B(p_high,q,r)^T}`.

The axes are fixed in `axes.json`; `control-fixture.json` and
`run_spec.control.json` preserve the known successful control
`(0.001, 0.8, 1, 1)`. A production `run_spec.json` is a JSON object with
shared `settings`, shared `provenance`, and a deterministically ordered
`cells` list. Every cell has a stable `cell_id` and `params` containing
`p_low`, `p_high`, `q`, and `r`.

Each cell stops at its first failed gate: depth-six determinant words,
endpoint metrics, rejection of a joint common metric, path-metric inertia,
and numerical time orientation. Only an exact nonpositive word or a validated
scientific gate rejection is terminal (`compute_success: true`). Resource
limits, nonfinite or floating-resolution word results, solver-inconclusive
results, malformed results, and unknown statuses are incomplete
(`compute_success: false`) and are retried.

Depth six is a binding protocol constant: the runner rejects any shared or
per-cell `short_word_depth` other than `6`, rather than emitting a successful
manifest from a shallower screen. Cell IDs must be safe single path components,
and duplicate IDs are rejected before the virtual-worker shard is selected.

## Spec materialization and identity

`axes.json` is a frozen input catalog; the runner does not expand it. A
production launcher must materialize `cells` in this exact Cartesian order:
`p_low` outermost, then `p_high`, then `q`, with `r` innermost, preserving each
axis array's stored order. The serialized `cells` list is authoritative:
virtual sharding uses its zero-based position and never sorts it. Reordering
cells changes shard ownership.

A whole-file checksum, when retained by deployment tooling, is SHA-256 of the
exact UTF-8 `run_spec.json` bytes and therefore changes with whitespace or key
ordering; the runner neither reads nor verifies a sidecar checksum. Resume
identity is instead the manifest `cell_fingerprint`: SHA-256 of canonical JSON
containing the cell schema, safe cell ID, finite canonical float parameters,
and fully resolved settings. Canonical JSON sorts object keys and uses compact
separators, so equivalent numeric spellings, source whitespace, key order, and
omitted defaults do not change the fingerprint. Provenance, `run_dir`, and cell
position are deliberately excluded.

Run numerical work only on an approved remote host. Configure the host BLAS
libraries to one thread per process and reserve two logical cores. For a
virtual worker shard, use:

```bash
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m oracle.oddcycle_pair_domain_runner run_spec.json \
  --workers 1 --worker-index 14 --worker-count 76
```

The selected cells satisfy `cell_position % worker_count == worker_index`.
Each manifest is atomically written to `cells/<cell_id>/manifest.json`. A
manifest is reused only when it is a JSON object with the exact schema, cell
ID, fingerprint, and `compute_success: true`; legacy, malformed, stale, and
unsuccessful manifests are replaced. An omitted `run_dir` means the directory
containing `run_spec.json`; a relative `run_dir` is resolved once against that
directory. Each write uses a unique same-directory temporary file, so
simultaneous workers never share a temporary manifest name.

The CLI prints flushed progress to standard error and the final JSON summary
to standard output. It exits nonzero when any selected cell finishes with
`compute_success: false`.
