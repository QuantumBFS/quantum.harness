# SCNet resource decision and local validation log

Date: 2026-07-28 (Asia/Shanghai)

## Scientific setup

- Input: `anderson_impurity_model_4i_28b_32e.fcidump`
- SHA-256: `9c8ceb3faa39ccb9cf2c15632cdc748e449cf26197ee1e8251092a6bb49ce4b6`
- System: 32 spatial orbitals, 32 electrons, `MS2=0`
- State sector: SU(2), singlet `spin=0`
- MPS geometry: finite open orbital chain after the saved GA orbital permutation
- Observable: normalized saved finite-M MPS expectation
  `⟨ψ_M|H|ψ_M⟩/⟨ψ_M|ψ_M⟩`
- Bond-dimension ladder: M=100, 200, 400, 600, 800, 1000
- Quantum-computing comparison anchor (SKQD): `−62.25668182839704 E_h`

## CPU/GPU conclusion

The block2 DMRG program is CPU-only in this environment. It does not use CUDA
or the allocated NVIDIA A800 GPUs.

The tested SCNet account currently exposes only the `dzagnormal` partition.
Its QOS requires at least one GPU per job (`QOSMinGRES`) and the node topology
binds approximately eight CPU cores to each requested GPU.
Therefore:

- a true CPU-only Slurm request is rejected by the current account policy;
- 32 CPU cores require four GPUs even though those GPUs remain unused;
- the correct long-term fix is a CPU-only partition or QOS from the cluster
  administrator, not GPU acceleration of this code.

## Slurm actions

- Old job `6754578`: 64 CPU, 8 GPU, 96 GB, 2 h.
  It remained pending and was cancelled after the replacement was confirmed.
- Replacement job `6754602`: 32 CPU, 4 GPU, 96 GB, 1 h.
  It entered `PENDING (Priority)` successfully.
- At 2026-07-28 12:13 CST, Slurm reported an estimated start at
  2026-07-28 13:07:41, with `TimeLimit=01:00:00` and `TimeMin=00:30:00`.
- Slurm `--test-only` estimates varied from hours to months during probing.
  They are volatile scheduling hints, not guaranteed start times.
- The interrupted 30-minute `--test-only` query did not create a job and did
  not execute GPU code.

## Existing local evidence

The local 8-thread GA-ordered run used the same FCIDUMP, sector, orbital
permutation, eight sweeps per M, and a 10 GB block2 memory pool.

| M | Saved-MPS energy (E_h) | Difference from SKQD (mE_h) | Interpretation |
|---:|---:|---:|---|
| 100 | −62.253929578507346 | +2.752249890 | Higher than SKQD |
| 200 | −62.259729630306744 | −3.047801910 | Lower than SKQD |
| 400 | −62.260015739771831 | −3.333911375 | Lower than SKQD |
| 600 | −62.260044743233664 | −3.362914837 | Lower than SKQD |
| 800 | −62.260050678669316 | −3.368850272 | Lower than SKQD |
| 1000 | −62.260052579366490 | −3.370750969 | Lower than SKQD |
| 1500 | −62.260053669390740 | −3.371840994 | Lower than SKQD |

The M=200 checkpoint was independently reloaded with normalized energy
`−62.259729630306740 E_h`, norm `1.000000000000002`, and a difference of
`7.105427357601002×10⁻¹⁵ E_h` from the recorded headline.

“Lower than SKQD” means a lower variational energy for the same Hamiltonian
and sector. It does not by itself prove that the full wavefunction or every
observable is more accurate, and the SKQD source did not provide an uncertainty
budget for a formal agreement test.

## Completed local continuation to M=800

- Result directory:
  `tracks/qcs/results/issue-119-20260728/anderson-ga-m800`
- Configuration:
  `configs/anderson-ga-m800-local.toml`
- Reused the verified M=200 checkpoint and exact saved GA permutation.
- Added stages M=400, 600, 800 using 8 CPU threads, a 10 GB block2 memory
  pool, and eight sweeps per M.
- Measured stage wall times were 65.783 s, 144.191 s, and 243.775 s,
  respectively; total DMRG continuation time was 453.749 s (7.56 min).
- Measured RSS at M=800 was 1934.438 MB; system swap remained unused.
- The independently reloaded M=800 checkpoint had normalized energy
  `−62.260050678669316 E_h`, norm `1.0000000000000007`, and zero difference
  from the recorded headline at the `1e-9 E_h` verification tolerance.
- The M=800 saved-MPS energy is 3.368850272 mE_h below the SKQD anchor.
  This is a lower variational energy for the same Hamiltonian and sector.
- The final sweep still changed by approximately `6.36e-7 E_h`; the fixed
  eight-sweep schedule did not satisfy the requested `1e-9 E_h` DMRG stop
  tolerance. The energy advantage over SKQD is nevertheless about three
  orders of magnitude larger than that last-sweep change.
- The formal cross-method tag remains unavailable because the SKQD result has
  no declared uncertainty budget. The supported statement is “lower
  variational energy,” not full wavefunction agreement.

Artifacts:

- `result.json` — complete finite-M result table
- `checkpoint-verification.json` — independent saved-MPS reload
- `skqd-comparison.csv` — per-M numerical comparison
- `convergence.png` — energy and discarded-weight trends

## Completed local continuation to M=1000

- Result directory:
  `tracks/qcs/results/issue-119-20260728/anderson-ga-m1000`
- Configuration:
  `configs/anderson-ga-m1000-local.toml`
- Reused the independently verified M=800 checkpoint and exact saved GA
  permutation; only the new M=1000 stage was computed.
- The M=1000 stage used 8 CPU threads, a 10 GB block2 memory pool, and eight
  sweeps. It took 381.273 s (6.35 min) and reached 3638.252 MB RSS.
- The saved-MPS energy is `−62.260052579366490 E_h`, 1.900697174 μE_h below
  M=800 and 3.370750969 mE_h below the SKQD anchor.
- Independent checkpoint reload reproduced the headline exactly:
  normalized energy `−62.260052579366490 E_h`, norm
  `1.000000000000001`, and zero difference at the `1e-9 E_h` verification
  tolerance.
- The final sweep energy was `−62.260053094694968 E_h`, changing by about
  `−2.57e-7 E_h`; the fixed eight-sweep run did not satisfy the strict
  `1e-9 E_h` DMRG stop tolerance. The reported headline is the normalized
  expectation value of the saved finite-M MPS, not the final local sweep
  value.
- The formal cross-method tag remains unavailable because neither the saved
  SKQD anchor nor this fixed-sweep DMRG run has a complete declared
  uncertainty budget. The supported conclusion is that M=1000 gives a lower
  variational energy for the same Hamiltonian and sector.

Additional M=1000 artifacts:

- `checkpoint-verification.json` — independently reloaded checkpoint
- `skqd-comparison.csv` — numerical comparison through M=1000
- `convergence.png` — finite-M energy and discarded-weight trends
- `skqd-comparison.png` — direct energy-difference plot relative to SKQD

## Completed local continuation to M=1500

- Result directory:
  `tracks/qcs/results/issue-119-20260728/anderson-ga-m1500`
- Configuration:
  `configs/anderson-ga-m1500-local.toml`
- Reused the independently verified M=1000 checkpoint and exact saved GA
  permutation; M=2000 was explicitly excluded.
- The M=1500 stage used 8 CPU threads, a 10 GB block2 memory pool, and eight
  sweeps. It took 888.421 s (14.81 min), reached 7838.953 MB RSS, and did not
  use swap during observed memory checks.
- The saved-MPS energy is `−62.260053669390740 E_h`, 1.090024250 μE_h below
  M=1000 and 3.371840994 mE_h below the SKQD anchor.
- Independent checkpoint reload gave normalized energy
  `−62.260053669390750 E_h`, norm `0.9999999999999981`, and a
  `−7.105427357601002e-15 E_h` difference from the recorded headline, well
  inside the `1e-9 E_h` verification tolerance.
- The final sweep energy was `−62.260053763176990 E_h`, changing by about
  `−8.93e-8 E_h`; the fixed eight-sweep run did not satisfy the strict
  `1e-9 E_h` DMRG stop tolerance. The reported headline remains the normalized
  expectation value of the saved finite-M MPS.
- The formal cross-method agreement tag remains unavailable because the SKQD
  result has no declared uncertainty budget. The direct numerical statement
  is that every M≥200 result lies below SKQD, with M=1500 lower by
  3.371840994 mE_h.

M=1500 comparison artifacts:

- `skqd-comparison.csv` — all local M values plus the SKQD anchor
- `skqd-comparison.png` — direct finite-M difference from SKQD
- `convergence.png` — energy and discarded-weight trends through M=1500
- `checkpoint-verification.json` — independent saved-MPS reload
