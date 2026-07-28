# SCNet job submission — runbook + traps

> For the next agent. Lessons earned the hard way during the certificate-pipeline
> runs (jobs 22979470 → 22983014). Read this before your first `sbatch`.
> Companion to `handoff-status.md` (project state) — this file is **how to drive
> the cluster**, not what to compute.

## Connection profile

- `ssh scnet` → host `xh5.hpccube.com:65061`, user `iint_sjds`, home `/work/home/iint_sjds`.
- **Connect is slow (30–60 s) and intermittently flaky** ("No route to host",
  `gnutls_handshake()`). GitHub HTTPS git-push from this laptop is also often
  broken even when `gh api` works — the `gh` REST transport is the more reliable
  probe for "does ref X exist on remote."

Always wrap ssh with both a connect-timeout and an overall `timeout`, or the
120 s tool budget vanishes into the TCP handshake:

```bash
timeout 60 ssh -o ConnectTimeout=50 scnet 'cd ~/quantum.harness && <cmd>'
```

On failure, retry once — most misses are transient.

## The hard rule

**Never run the SDP stack locally.** WSL OOM-kills at ~15 GB resident when
SpectralGap+MosekTools+Clarabel load. SDP/ED compute → SCNet via `sbatch`,
always. Local is for <1 min, <1 GB sanity checks only.

## Two-channel code sync (the #1 trap)

SCNet holds a bare repo + working clone:

```
~/quantum.harness.git       (bare)
~/quantum.harness           (working clone on branch challenge/polyopt-sdp-gap)
```

Code reaches SCNet through **two different channels** — getting this wrong means
SCNet silently runs stale code:

| What | Channel | Command |
|---|---|---|
| git-tracked source (scripts, ledger, spec, patch file) | git | `git push scnet <branch>` then `ssh scnet 'cd ~/quantum.harness && git pull'` |
| `.external/SpectralGap/**` (gitignored — the solver itself) | scp | `scp .external/SpectralGap/src/sdp.jl scnet:~/quantum.harness/.external/SpectralGap/src/sdp.jl` |

After scp, **SHA-256 verify both sides** — never trust the copy:

```bash
sha256sum .external/SpectralGap/src/sdp.jl                          # local
ssh scnet 'sha256sum ~/quantum.harness/.external/SpectralGap/src/sdp.jl'   # remote
```

GitHub is **blocked on SCNet**, so you cannot `git fetch` there — everything
routes through the local→SCNet bare-repo push. (Push to origin/GitHub separately
from the laptop, when its HTTPS cooperates.)

## Submit + monitor — two phases, never fire-and-forget

A "RUNNING" queue entry or a 0 ssh-exit is **not** success. Only verified output
is. Use two ssh rounds:

**Phase A — submit + confirm it queued:**

```bash
timeout 60 ssh -o ConnectTimeout=50 scnet 'cd ~/quantum.harness
git pull 2>&1 | tail -1
rm -f gap_cert_export.out gap_cert_export.err     # clear last run's logs
JOB=$(sbatch tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_cert_export.sh)
echo "sbatch: $JOB"
sleep 6
squeue -u $USER -o "%.10i %.14j %.8T %.6M" | head -3'
```

Note the JOBID. PENDING (PD) right after submit is normal; under cluster load jobs
sit PD for minutes (`AssocGrpJobsLimit` / saturation) — that is queueing, not
broken.

**Phase B — wait the settle-time, then verify output + exit markers:**

```bash
timeout 118 ssh -o ConnectTimeout=50 scnet 'sleep 105; cd ~/quantum.harness
echo "=== job (empty = finished) ==="; squeue -u $USER | head -3
echo "=== log tail ===";             tail -30 gap_cert_export.out
echo "=== err tail ===";             tail -6 gap_cert_export.err'
```

The `sleep` goes **inside** the ssh so the wait happens on SCNet (one round-trip),
not as separate calls that each burn the connect latency. Tune `sleep` to the
expected runtime; if the job is still RUNNING, do another Phase-B round.

Success = the script's own exit markers (`echo "verifier exit: $?"` etc.) are 0
**and** `squeue` is empty **and** the log shows the expected RESULT line. All
three, not just one.

## Slurm script env — the `set -u` trap

The driver scripts use `set -euo pipefail`. Under `set -u`, referencing an
undefined variable aborts the script. `LD_LIBRARY_PATH` is often unset on login,
so the default-empty form is **mandatory**:

```bash
export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"   # :- is load-bearing
export JULIA_NUM_THREADS=4
```

Mosek license lives at `~/mosek/mosek.lic`. Without `MOSEKBINDIR` or the license,
Mosek either isn't found or returns a license error.

Partition: `xhacnormalb` (CPU, 64–128 cores, ~500 GB). The SBATCH `--output=` /
`--error=` paths are relative to the launch cwd (`~/quantum.harness`).

## Output buffering — or, "the log looks hung"

When stdout is redirected to a slurm log (not a TTY) it is block-buffered, so a
long Julia job prints nothing until it exits — indistinguishable from a hang.
Every Julia script must `flush(stdout)` after each `println` (the current
`gap_cert_export.sh` heredoc does this). Pair with `stdbuf -oL`/`srun --unbuffered`
only if a script you don't control buffers.

## Trap summary (quick table)

| Trap | Symptom | Fix |
|---|---|---|
| Forgot to scp `.external/SpectralGap` | SCNet runs stale solver, "impossible" results | scp + SHA-256 verify both sides |
| `LD_LIBRARY_PATH` without `:-` under `set -u` | script aborts instantly, empty log | `${LD_LIBRARY_PATH:-}` |
| Declaring success on "RUNNING" / ssh-exit 0 | false positives | check exit markers + `squeue` empty + RESULT line |
| Waiting via many short ssh calls | burns all time budget on connect latency | one `sleep N` inside one ssh |
| Tool timeout eaten by TCP handshake | ssh "fails" spuriously | `timeout 60 ssh -o ConnectTimeout=50 …`, retry once |
| Buffered Julia stdout | log looks empty/hung | `flush(stdout)` after each println |
| `git pull` on SCNet fetching from GitHub | fails (GitHub blocked) | route via `git push scnet` from laptop |
| Brute-force local SDP | WSL OOM-kill (~15 GB) | SCNet only |

## Minimal end-to-end template

```bash
# 1. sync code (git channel)
git push scnet challenge/polyopt-sdp-gap
# 2. sync gitignored solver (scp channel) + verify
scp .external/SpectralGap/src/sdp.jl scnet:~/quantum.harness/.external/SpectralGap/src/sdp.jl
sha256sum .external/SpectralGap/src/sdp.jl
# 3. submit + confirm queued
timeout 60 ssh -o ConnectTimeout=50 scnet 'cd ~/quantum.harness && git pull &&
  rm -f gap_cert_export.out gap_cert_export.err &&
  sbatch tracks/polyopt/solutions/sdp-gap-seekers/scripts/gap_cert_export.sh &&
  sleep 6 && squeue -u $USER | head -3'
# 4. wait + verify (repeat if still RUNNING)
timeout 118 ssh -o ConnectTimeout=50 scnet 'sleep 105; cd ~/quantum.harness &&
  squeue -u $USER | head -3 && tail -30 gap_cert_export.out && tail -6 gap_cert_export.err'
# 5. fetch artifacts back
scp scnet:~/quantum.harness/<artifact> tracks/polyopt/solutions/sdp-gap-seekers/evidence/
```
