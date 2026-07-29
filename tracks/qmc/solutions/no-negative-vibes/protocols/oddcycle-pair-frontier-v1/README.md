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
and numerical time orientation. Scientific gate failures are saved as
successful computations; only exceptions are marked `compute_success: false`
and retried on resume.

Run numerical work only on an approved remote host. Configure the host BLAS
libraries to one thread per process and reserve two logical cores. For a
virtual worker shard, use:

```bash
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m oracle.oddcycle_pair_domain_runner run_spec.json \
  --workers 1 --worker-index 14 --worker-count 76
```

The selected cells satisfy `cell_position % worker_count == worker_index`.
Each manifest is atomically written to `cells/<cell_id>/manifest.json`; only
a manifest with `compute_success: true` is reused.
