# Route D+ Phase 1 job 23005815 result

Date: 2026-07-29

## Outcome

Slurm job `23005815` completed successfully on compute node `c05r05` and
produced the required Route D+ Phase 1 environment manifest.

```text
JobID|JobName|Partition|State|ExitCode|Elapsed|MaxRSS|NodeList|AllocTRES
23005815|route-d-plus-phase1-loader|xhhgnormal01|COMPLETED|0:0|00:00:33||c05r05|billing=2,cpu=2,gres/gpu=1,mem=6G,node=1
23005815.batch|batch||COMPLETED|0:0|00:00:33|211488K|c05r05|cpu=2,gres/gpu=1,mem=6G,node=1
23005815.extern|extern||COMPLETED|0:0|00:00:33|2732K|c05r05|billing=2,cpu=2,gres/gpu=1,mem=6G,node=1
```

The standard error contains only locale warnings. It contains no Python, JAX,
CUDA, schema-validation, or application error.

## Manifest

The compute-node manifest records:

```json
{
  "created_at_utc": "2026-07-29T09:59:55.767004+00:00",
  "cuda_visible_devices": "0",
  "device_count": 1,
  "device_kinds": [
    "NVIDIA GeForce RTX 3090"
  ],
  "device_platforms": [
    "gpu"
  ],
  "git_commit": "182fe7742241ee2b8a1aad0bb019725a6b700c94",
  "git_dirty": false,
  "hostname": "c05r05",
  "jax_enable_x64": true,
  "jax_version": "0.4.38",
  "jaxlib_version": "0.4.38",
  "machine": "x86_64",
  "python_executable": "/work/home/jiabohan5/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3.11",
  "python_version": "3.11.15",
  "requested_platform": "gpu",
  "requirements_lock_path": "/work/home/jiabohan5/quantum.harness-collab/tracks/qmc/results/route-d-plus-phase1-20260729-06/requirements-lock.txt",
  "requirements_lock_sha256": "f77cad4f76b1b086c06a2953a448e1d48e230205a74da561b12d019fde86589c",
  "schema_version": "challenge-15-route-d-plus-environment-v1",
  "slurm_cluster_name": "xhcs3",
  "slurm_job_id": "23005815",
  "system": "Linux"
}
```

An independent remote read-only validation loaded the saved JSON and
`manifest.schema.json`, checked the Draft 2020-12 schema, and validated the
manifest with a format checker. It returned:

```text
schema_validation=PASS
```

The remote checkout remained clean at commit
`182fe7742241ee2b8a1aad0bb019725a6b700c94`.

## Pinned evidence

```text
eabc1a4d3fae12e2fbbe7f54813acb83102495bd6004b7ab30b390d9b6cdecc6  tracks/qmc/results/route-d-plus-phase1-20260729-06/environment-manifest.json
f77cad4f76b1b086c06a2953a448e1d48e230205a74da561b12d019fde86589c  tracks/qmc/results/route-d-plus-phase1-20260729-06/requirements-lock.txt
1249c548c3727cb1ec31a597e716efc095a658caa4d019399025eee2cbc3c6d7  tracks/qmc/solutions/BOTS-848/route_d_plus/environment/manifest.schema.json
eabc1a4d3fae12e2fbbe7f54813acb83102495bd6004b7ab30b390d9b6cdecc6  tracks/qmc/results/route-d-plus-phase1-20260729-06-loader-retry-slurm-23005815.out
70c52dfb68bd07c86210cdc799d75c56c7a7e4761f134dd295ca3fdfda19eb80  tracks/qmc/results/route-d-plus-phase1-20260729-06-loader-retry-slurm-23005815.err
4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4  /work/home/jiabohan5/.cache/route-d-plus/runtime-libs/libstdc++.so.6.0.29
```

## Gate assessment

All six conditions in `route-d-plus-phase1.md` pass:

1. Python is 3.11.15.
2. JAX x64 is enabled.
3. The requested platform is GPU, with one NVIDIA GeForce RTX 3090 visible;
   there is no CPU fallback.
4. The source checkout is clean at a pinned 40-character commit.
5. The installed dependency lock exists and its digest matches the manifest.
6. The saved manifest independently validates against the pinned schema.

This result resolves the cuDNN/libstdc++ loader failure observed in job
`23005626`. Phase 1 is complete. Phase 2 may begin only as a separate,
explicitly scoped workflow.

No repository project code, test, JAX import, training job, or ED job was run
on the local development host.
