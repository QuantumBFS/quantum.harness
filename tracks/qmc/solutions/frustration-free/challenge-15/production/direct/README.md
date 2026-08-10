# Direct Qdeshell runner

The direct N=6 run reserves one complete Qdeshell node: one Slurm task on one
node with 64 CPUs, 480000M memory, and eight A800 GPUs. It is not an array job.
The batch script starts the five immutable seed tasks concurrently, pins seeds
0 through 4 to `CUDA_VISIBLE_DEVICES` 0 through 4, and gives each runner 12 CPU
threads. Per-seed stdout and stderr are written deterministically under
`RUN_DIR/logs/seed-N.log`. The batch job waits for every runner and exits
nonzero if any runner fails.

After preparing an absolute `RUN_DIR/run.json` on Qdeshell, test the exact
tracked batch script without submitting it:

```bash
sbatch --test-only /work/share/giggleliu/jiangweiqi/quantum.harness/tracks/qmc/solutions/frustration-free/challenge-15/production/direct/n6_train_qdeshell.sbatch /ABSOLUTE/RUN_DIR/run.json
```

After inspecting the feasibility result and deciding to run, submit through
the provenance validator:

```bash
/work/share/giggleliu/jiangweiqi/quantum.harness/tracks/qmc/solutions/frustration-free/challenge-15/production/direct/submit_run.sh /ABSOLUTE/RUN_DIR/run.json
```
