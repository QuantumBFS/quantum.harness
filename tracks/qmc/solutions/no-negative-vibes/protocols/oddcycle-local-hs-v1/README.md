# Odd-cycle local-H first-batch protocol

This protocol freezes the first resumable search over word dictionaries of
maximum lengths 1, 2, 3, and 4.  Each length has five free-locality cells,
four target-family cells, and one discrete-transfer portfolio cell: 40 cells
in total.  The seed is `20260730`, numerical screening uses active tolerance
`1e-10` and residual tolerance `1e-9`.  Free-cell numerical survivors are
promoted separately on WSL, with exact promotion limited to 32 active rays.

Scientific tests and searches run only in the authorized WSL or CPU-machine
environments.  Do not run this protocol in the local Windows workspace.

## Continuous-time positive-history proof

The certified alphabet is

```text
A = {B0, B0.T, B1, B1.T}.
```

For a word `W` in `A`, define the Hermitian macro-field

```text
Phi_W = Gamma(W) + Gamma(W.T).
```

Every free-cell exact survivor has

```text
H = E0 I - sum_W q_W Phi_W,  q_W > 0.
```

Expanding `exp(-beta H)` in continuous time chooses one word or transpose-word
branch from each macro-event.  Concatenating those branches produces one word
in the original four-letter alphabet, so each Fock trace is

```text
Tr Gamma(W_n ... W_1) = det(I + W_n ... W_1) > 0
```

by the frozen arbitrary-word determinant theorem.  The scalar contributes
only the positive prefactor `exp(-beta E0)`.  Thus exact free-cell promotions
reuse the existing all-history proof; they do not make a new closure
assumption or repeat the completed frontier search.

Target-family cells are numerical Route-B membership screens.  A numerical
target survivor is not an exact target result until target-specific rational
weights and the complete Fock equality have been replayed exactly.

## Route-D boundary

Portfolio cells construct shifted positive-definite transfers

```text
T = c I + sum_W q_W Phi_W,
H_D = -log(T / T_vac).
```

Exact row dominance certifies `T > 0`, and the same word-concatenation
argument makes every discrete auxiliary-field history positive.  The
normal-ordered coefficients of `H_D` are numerical ranking diagnostics.
Small high-body or nonlocal coefficients are not exact zeros.  Route D
therefore supplies rigorous Hermitian interacting transfer Hamiltonians and
numerical locality profiles, but it does not establish the exact-local `L2`
claim.

## Cells and output schema

`settings.json` expands in lexicographic cell-ID order.  IDs have the forms

```text
free-l<length>-<locality>
target-l<length>-<family>
portfolio-l<length>
```

CPU workers publish numerical screening payloads only.  Each worker writes
one full payload to
`cells/<cell_id>.json.tmp`, flushes and `fsync()`s the file, and atomically
renames it to `cells/<cell_id>.json`.  Only the parent process appends the
corresponding canonical JSON record to `manifest.jsonl`, then flushes and
`fsync()`s the manifest.  A completed cell payload has:

- schema `oddcycle-local-hs-cell-v1`;
- the full normalized cell settings and dictionary column count;
- terminal status `survivor`, `infeasible`, or `inconclusive`;
- compact active indices and active weights plus solver diagnostics;
- a SHA-256 digest over the canonical payload excluding the digest field.

Manifest records use schema `oddcycle-local-hs-manifest-v1` and contain the
cell ID, mode, maximum word length, terminal status, canonical full-cell
settings digest, relative payload path, and payload SHA-256.  Resume requires
a verified final cell payload, restores a missing manifest entry from that
payload, skips completed IDs, and refuses orphan manifest records,
conflicting hashes, or changed cell settings.  An interrupted `.tmp` file is
never treated as complete.  A malformed unterminated final manifest line is
durably removed and reconstructed from verified final cell files; malformed
interior records remain hard errors.

The WSL promotion command reads immutable numerical free-cell payloads and
writes one `promotions/<cell_id>--scan-<index>.json` record per numerical
survivor.  Every record is either an exact certificate or an
`exact-promotion-inconclusive` record, including per-survivor exceptions.
Only the promotion parent appends `promotion-manifest.jsonl`, which carries
the source cell hash, full-cell settings digest, promotion payload hash, and
relative path.  Promotion resume has the same verified-payload, conflict, and
torn-final-line rules and never edits or deletes the CPU screening payload.

Progress is flushed after every parent-side manifest append and reports
completed/total cells, survivor/infeasible/inconclusive counts, elapsed time,
and the output directory.

## Exact pre-compute regression

From `tracks/qmc/solutions/no-negative-vibes` in the authorized WSL
environment:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest -q \
  tests/test_oddcycle_local_hs_runner.py \
  tests/test_oddcycle_word_operator.py \
  tests/test_oddcycle_local_hs_scan.py \
  tests/test_oddcycle_local_hs_exact.py \
  tests/test_oddcycle_local_targets.py \
  tests/test_oddcycle_transfer_portfolio.py \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_final_certificate.py \
  tests/test_oddcycle_robust_certificate.py
```

Stop before search execution if this command fails.

## Launch and resume

On the authorized CPU machine, from the archived source directory:

```bash
SOURCE_SHA="$(cat /home/jzb/nnv-local-h-source.sha)"
CPU_TOTAL="$(nproc)"
CPU_WORKERS="$(( CPU_TOTAL > 2 ? CPU_TOTAL - 2 : 1 ))"
cd "/home/jzb/code/nnv-local-h-$SOURCE_SHA/tracks/qmc/solutions/no-negative-vibes"
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/jzb/miniforge3/envs/quantum-harness/bin/python -u \
  -m oracle.oddcycle_local_hs_runner \
  --settings protocols/oddcycle-local-hs-v1/settings.json \
  --output "/home/jzb/runs/nnv-local-h-$SOURCE_SHA/length4" \
  --workers "$CPU_WORKERS" --resume \
  2>&1 | tee "/home/jzb/runs/nnv-local-h-$SOURCE_SHA/length4.log"
```

Run the identical command to resume.  Preserve the source archive, output
directory, manifest, cell files, and log.

Copy completed numerical survivor cell JSON files to the preserved WSL
incoming directory.  Then, from the exact same archived source SHA on WSL:

```bash
WSL_TOTAL="$(nproc)"
WSL_WORKERS="$(( WSL_TOTAL > 2 ? WSL_TOTAL - 2 : 1 ))"
SOURCE_SHA="$(git rev-parse HEAD)"
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -u \
  -m oracle.oddcycle_local_hs_runner \
  --promote-from \
  "/home/zibojin/code/nnv-local-h-runs/$SOURCE_SHA/incoming" \
  --output \
  "/home/zibojin/code/nnv-local-h-runs/$SOURCE_SHA/promoted" \
  --workers "$WSL_WORKERS" --resume
```

This command builds each dictionary once per source cell, emits a separately
hashed result for every numerical survivor, and can run while later CPU cells
continue.  Re-run the identical command as new immutable cell payloads arrive.

## Length-six decision gate

Do not start a length-six extension until all 40 length-four cells are
terminal and every length-four numerical free-cell survivor eligible under
the 32-ray limit has an exact promotion record.  Extend to length six only
when there is **no exact `L2` survivor after all length-four promotions
complete**.  Freeze and commit the extension settings before launch, and
reuse the length-four cache rather than repeating completed work.
