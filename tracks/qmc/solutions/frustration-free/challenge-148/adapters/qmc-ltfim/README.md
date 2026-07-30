# Challenge 148 independent QMC_LTFIM adapter

This owned Julia wrapper calls QMC_LTFIM revision
`524860b9c0e212ac630b0d9754075bb24198da3b` directly. QMC_LTFIM is distributed
under the `Apache-2.0` license. The wrapper does not use the upstream CLI or its
general constructor.

Run with Julia 1.11.6:

```text
julia --project=. run_independent.jl --request REQUEST.json --output-directory RUN
```

The simulation RNG is Julia 1.11.6 `Random.Xoshiro`. All 256 seed bits are
derived as `SHA256("qmc-ltfim-seed-v1" || request_seed_u64_be)`, a namespace
separate from QMC_SSE. Restart reconstructs and replays the direct thermal API;
no opaque QMC_LTFIM state is serialized.

The adapter uses a QMC_LTFIM-specific descriptor-retained `flock` in
`.qmc-ltfim-lock-state/` as its cooperative local and shared-filesystem lock.
Its immutable content-addressed run-lock anchor binds the request, absolute
output namespace, and lock-state/file device and inode identities. A durable
same-inode hard-link pin makes canonical-anchor unlink/recreate substitution
observable across process restarts. Control inputs reject symbolic links and
are opened component-by-component from retained directory descriptors with
`O_NOFOLLOW`. Kernels without `openat2` (`ENOSYS` only) use a direct `openat`
syscall over the same validated single components; every other `openat2` error
fails closed. Immutable objects use direct Linux
`renameat2(RENAME_NOREPLACE)`, file and directory fsync, and byte validation of
an existing content-addressed winner.
