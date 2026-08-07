# SCNet environment check 6754912

- State: `FAILED`, exit `2:0`, elapsed 4 s
- Node: `gpu1`
- Cause: Docker 19.03.10 client panicked inside Go `text/template` while evaluating the requested formatted `docker info` fields.
- This does **not** establish that Docker daemon access is unavailable; a new job must test unformatted `docker info`.
- Module catalog established the presence of `anaconda3/2023.09`, `python/3.8.10`, `apptainer/1.2.4`, and `singularity/3.7.3`.
- Raw logs: `/work/home/hesicheng5/quantum-harness-ch66/slurm/env-check-6754912.{out,err}`.

This infrastructure probe is not an autoresearch candidate attempt. It is retained as a failed environment experiment and is not silently relabeled or overwritten.
