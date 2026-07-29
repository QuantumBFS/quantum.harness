# TP exterior extension v1

This remote-only protocol scans 51,840 exact rational cells in dimension five.
The ordered grade-two basis is

`01, 02, 03, 04, 12, 13, 14, 23, 24, 34`.

All rational axes are JSON strings so parameter identity is independent of
binary floating-point spelling.

## Exact construction

Let

`w0 = (0,1,2,3,0,1,2,0,1,0)`.

For positive `t`, form the ordered lower adjacent Jacobi product

`L = product_(i in w0) (I + t E_(i+1,i))`

and the reverse-word upper product

`U = product_(i in reverse(w0)) (I + t E_(i,i+1))`.

With `D = diag(1,1,1,1,r)`, the core `J = L D U` is in the strict
Loewner-Whitney totally-positive big cell. For the directed chord list
`(a_j,b_j)`, define

`S_p = product_j (I + p (-1)^j epsilon E_(a_j,b_j))`.

The two base atoms and the complete alphabet are

`A_plus = S_(+1) J`,

`A_minus = rho S_(-1) J`,

`(A_plus, A_plus^T, A_minus, A_minus^T)`.

The candidate hash is SHA-256 of the candidate schema and the complete
canonical reduced rational parameter object. Every manifest stores that
object and the deterministic replay function.

## Exterior-grade gauges

`Q1 = Q4 = I`. For half-angle `u`,

`c = (1-u^2)/(1+u^2)`, `s = 2u/(1+u^2)`,

and `Q2` inserts the exact block `[[c,-s],[s,c]]` in one declared grade-two
coordinate plane.

The fixed Hodge map uses positive orientation `01234` and

`01->+234, 02->-134, 03->+124, 04->-123, 12->+034,`

`13->-024, 14->+023, 23->+014, 24->-013, 34->+012`.

Writing its signed-permutation matrix as `H`, the grade-three gauge is
`Q3 = H Q2 H^T`. Every gate uses the exact declared formula
`Qk^T C_k(A) Qk`.

The non-induced witness is the largest columnwise `Gr(2,5)` Pluecker
residual

`p_ij p_kl - p_ik p_jl + p_il p_jk`

over `i<j<k<l`. The six protocol coordinate planes mix disjoint basis
bivectors, so a nonzero declared angle gives a nonzero witness.

## Frozen early-stop gates

1. Every atom is finite, invertible, has positive determinant, and condition
   number strictly below `1e10`.
2. Every transformed grade 1--4 compound has minimum-entry / maximum-absolute
   entry strictly above `1e-8`.
3. At least one original order-two minor is strictly below `-1e-6`.
4. The grade-two Pluecker residual is strictly above `1e-6`.
5. Only cells passing gates 1--4 receive exhaustive mixed-word determinant
   stress.

The zero-chord, zero-angle fixture passes the structural positive-compound
checks but is recorded as `known-tn-control`; it is never reported as a
novel survivor and never enters mixed-word stress.

The mathematical promotion theorem is separate from discovery stress:
entrywise nonnegativity is closed under products, and therefore
`det(I+W) = sum_k trace(C_k(W)) >= 1` for every word. Promotion still
requires exact rational compound replay and the existing positive-field
Hermitian interacting Fock-transfer construction.

## Remote execution

Create a generic `run_spec.json` with a deterministically ordered `cells`
list. Each cell requires `cell_id` and all seven parameter fields from
`axes.json`. The selected virtual shard satisfies
`cell_position % worker_count == worker_index`.

On the 64-core CPU host, reserve two logical cores and launch virtual workers
`0..61`, one single-threaded process per worker:

```bash
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m oracle.tp_exterior_extension run_spec.json \
  --workers 1 --worker-index 0 --worker-count 62
```

Each complete cell is atomically published at
`cells/<cell_id>/manifest.json`. A cell is resumed only when its existing
manifest is an object with the exact schema, cell ID, and cell fingerprint
and has `compute_success: true`. The fingerprint covers the schema, safe
single-component cell ID, canonical exact parameters, and fully resolved
settings. Malformed or stale manifests are replaced. A mixed-word resource
limit is an incomplete computation (`compute_success: false`) and is retried
rather than cached as a scientific rejection.
