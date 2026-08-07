# Route D+ Phase 1 job 23005626

Date: 2026-07-29

## Submission

- Job ID: `23005626`
- Partition: `xhhgnormal01`
- Accelerator request: `gpu:NVIDIAGeForceRTX3090:1`
- Resources: one node, 2 CPU, 6 GiB, 15 minutes
- Remote commit: `182fe7742241ee2b8a1aad0bb019725a6b700c94`
- Run ID: `route-d-plus-phase1-20260729-06`

This retry reused the run containing the installed dependency lock and
therefore corrected the run-ID mismatch from job `23005566`.

## Scheduler outcome

`sacct` reported:

```text
State=FAILED
ExitCode=6:0
Elapsed=00:00:36
NodeList=c05r05
MaxRSS=91912K
```

The JAX device query aborted before a manifest was written. Standard error
reported:

```text
Unable to load any of {libcudnn_graph.so.9.5.0, libcudnn_graph.so.9.5,
libcudnn_graph.so.9, libcudnn_graph.so}
Invalid handle. Cannot load symbol cudnnCreate
```

## Diagnosis

The installed `nvidia-cudnn-cu12==9.5.0.50` wheel contains
`libcudnn_graph.so.9`, but its directory was absent from the compute-job
dynamic-loader path. A login-node `ldd` check also showed that the cluster
system `libstdc++.so.6` is too old for this cuDNN build: it lacks
`GLIBCXX_3.4.20`, `GLIBCXX_3.4.21`, and `CXXABI_1.3.9`.

This is a CUDA runtime-loader failure, not a physics result. It does not
establish whether JAX can use the RTX 3090 once the pinned wheel libraries are
made visible.

## Prepared runtime correction

The cluster provides an isolated conda `libstdcxx-ng 11.2` runtime containing
`libstdc++.so.6.0.29`. It was copied to:

```text
/work/home/jiabohan5/.cache/route-d-plus/runtime-libs/libstdc++.so.6.0.29
```

Its source and copied SHA-256 are identical:

```text
4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4
```

With only that compatibility directory added to `LD_LIBRARY_PATH`, `ldd`
resolves cuDNN 9.5 without missing versioned symbols. A corrected compute job
must prepend this directory and the installed `nvidia/*/lib` wheel directories
to `LD_LIBRARY_PATH`, then rerun the unchanged manifest gate.

The loader check is preparatory evidence only. The correction is not validated
until a scheduled GPU job writes and validates `environment-manifest.json`.
