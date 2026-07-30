# Compact evidence

This directory contains the machine-readable evidence needed by the public
report without the large Markov-chain archives.

| File | Role |
|---|---|
| `replay_strata.csv` | Per-path 4x4 PQMC weight, CP proposal probability, prefix barrier, overlap diagnostics, and local energies. |
| `sampling_efficiency_summary.json` | Worst-one-percent selection, correlations, and bottleneck-field summaries for the 976 unambiguous TI paths. |
| `worst_efficiency_1pct.csv` | The ten least efficiently sampled 4x4 paths. |
| `trace_dynamics_summary.json` | Full local heat-bath trace comparison for five low-proposal cases and five matched controls. |
| `selected_projection.json` | ALF free/UHF projection calibration and physical parameters. |
| `direct_reweight_summary.json` | Direct ratio-of-sums result from 1,920 independent chains and 96,000 paths. |
| `exhaustive_2x2_selection_summary.csv` | Exact counts in the worst-efficiency tail of each 2x2 trial. |
| `exhaustive_2x2_input_checksums.json` | Provenance hashes for the exhaustive enumeration inputs. |

The full 6,720-bit path archives and raw cluster logs are intentionally not
committed.  Their generators, binary format, replay code, Slurm scripts, and
tests are preserved under `../test/`.
