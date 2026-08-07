# SCNet locked-environment build 6754984

- State: `FAILED`, exit `1:0`, elapsed 25 s
- Failure stage: first package resolution (`stim==1.15.0`).
- Cause: compute node returned `[Errno 101] Network is unreachable` for every PyPI attempt.
- No package version or ABI incompatibility was observed; no requested package was installed.
- Remediation: acquire CPython 3.11, manylinux2014 x86_64 wheels as immutable artifacts, record SHA-256, and install on the compute node with `--no-index --find-links` in a new Slurm job.
- Raw logs: `/work/home/hesicheng5/quantum-harness-ch66/slurm/build-env-6754984.{out,err}`.

This is an infrastructure experiment, not an autoresearch candidate attempt, and remains part of the audit trail.
