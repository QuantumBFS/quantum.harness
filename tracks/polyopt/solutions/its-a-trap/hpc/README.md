# SCNet job bundle — Target-1 ladder + Target-2 J2 sweep (N=100)

Why: the local 24 GB WSL box hit its memory frontier at **N=50** (CONFIG A,
killed at 16.3 GB in the Mosek solve) — every Target-size cell needs more
memory than the laptop has. SCNet nodes: 128 cores / 510 GB (partition
`hx1hdnormal01`, DefMemPerCPU=3800M), live-probed 2026-07-26.

Payload (`cells.txt`, 12 array cells): CONFIG A ladder N = 50…200, then
J1-J2 N=100 × J2 ∈ {0.5, 0.2, 1.0, 0.4, 0.6, 0.8} with pso=0 (Remark 6.1).
Budgets per cell: 60 GB / 12 h / MOSEK_THREADS=8 (envelope: dense-Schur
estimate ~31 GB at N=200 + workspace).

## Order of operations

0. **Credentials (user, once)** — per `.claude/skills/using-slurm/profiles/scnet-setup.md`:
   SCNet console → SSH连接 → download key → `~/.ssh/scnet_key` (0600) →
   `~/.ssh/config` alias `scnet`. Verify: `ssh scnet 'echo ok && hostname'`
   (ignore the libcrypto RSA warning — known-harmless, see scnet.toml gotcha).
1. `bash hpc/ship.sh` — rsync working tree (excl. results/.git/.knowledge)
   + refs snapshot + Mosek licence (HOSTID=DEMO, portable, expires 2027-07).
2. `ssh scnet 'bash quantum.harness/tracks/polyopt/solutions/its-a-trap/hpc/bootstrap_remote.sh'`
   — juliaup 1.12.6, instantiate/precompile (login node has internet; compute
   nodes do NOT), licence check, N=10 end-to-end smoke. Expect `BOOTSTRAP OK`.
3. Submit (login node):
   ```
   cd ~/quantum.harness
   sbatch --export=ALL,RUN_NAME=scnet-$(date +%Y%m%d-%H%M%S) \
     tracks/polyopt/solutions/its-a-trap/hpc/submit.sbatch
   ```
4. Monitor: `squeue -u $USER`; per-cell logs `slurm-<jobid>_<task>.out`.
5. Fetch + merge (local):
   ```
   rsync -az scnet:quantum.harness/tracks/polyopt/results/scnet-*/ tracks/polyopt/results/<same-name>/
   bash tracks/polyopt/solutions/its-a-trap/hpc/merge_results.sh tracks/polyopt/results/<same-name>
   ```

## Provenance rules (unchanged)

* One CSV row per cell (per-cell outdirs; merge_results.sh concatenates).
* Scheduler state is not evidence — only fetched rows with
  `termination_status=OPTIMAL` and real Mosek residuals count.
* Killed/failed cells report status N/A, never inferred OPTIMAL.
* Reference of record: `refs/bethe_ref.json` (Target 1, incl. N=140/200);
  MG exact −0.375 at J2=0.5; other J2 points get Wednesday DMRG brackets.
