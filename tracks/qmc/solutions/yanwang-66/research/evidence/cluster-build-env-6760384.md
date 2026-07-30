# SCNet offline locked-environment build 6760384

- Date: 2026-07-29
- Slurm state: `COMPLETED`
- Exit code: `0:0`
- Elapsed: `00:01:43`
- Script: `slurm/build-env.sbatch`
- Lock file SHA-256: `f3449956d0a6674eb657a529a32122258953799692a38a666ef77250485f82a8`
- Environment fix commit: `5df9c9ad0247d0f65e27392b5b720de1d5921cab`
- Raw logs: `/work/home/hesicheng5/quantum-harness-ch66/build-env-6760384.{out,err}`

The compute node verified all 29 entries in `environment/wheels.sha256`,
installed exclusively from the offline wheel directory with `--no-index` and
`--require-hashes`, and completed `pip check` with no broken requirements.
The previously missing transitive requirement is frozen as
`typing-extensions==4.12.2`, wheel SHA-256
`04e5ca0351e0f3f85c6853954072df659d0d13fac324d0072316b67d7794700d`.

The resulting environment reports Python-provided `pip==23.2.1` and
`setuptools==65.5.0`; all research packages are the exact versions named in
`environment/requirements.lock`, including `stim==1.15.0`,
`PyMatching==2.2.2`, `numpy==2.1.3`, `scipy==1.14.1`, `pandas==2.2.3`, and
`pyarrow==18.1.0`.
