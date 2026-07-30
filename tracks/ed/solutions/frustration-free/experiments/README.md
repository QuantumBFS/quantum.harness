# Imported Experiment Families

This directory contains the experiment families imported from the partner
tree `quantum-2.harness-main/tracks/ed/hubbard-pump-2` at commit
`9ebcab9`. They are kept as auditable, runnable historical/extension
experiments alongside the canonical `src/` pipeline. Their source models are
not silently substituted for the production model in `src/model.py`.

## Registry

| Family | Purpose | Main entrypoint | Output namespace |
|---|---|---|---|
| `baseline-ed` | finite-size non-interacting Rice-Mele ED reference | `scripts/run_ed.py` | `results/baseline-ed/` |
| `rice-mele-chern` | standalone nested-grid FHS benchmark | `run_rice_mele_chern.py` | `results/rice-mele-chern/` |
| `u-scan-chern` | historical Chern-versus-U scan implementation | `u_scan_c_solver.py` | `results/u-scan-chern/` |
| `rmh_gap_landscape` | many-body, spin, and charge gaps in separate sectors | `scripts/smoke_L6.py` | `results/rmh_gap_landscape/` |
| `delta-crossing` | real-time passage through a dimerization crossing | `scripts/smoke_crossing_L6.py` | `results/delta-crossing/` |
| `gapless-point-split` | finite-size scans around a gapless point | `scripts/run_scan.py` | `results/gapless-point-split/` |
| `pump-correlation` | current, correlation, and coherence observables | `scripts/run_pump_correlation.py` | `results/pump-correlation/` |
| `single-hole-chern` | single-hole momentum sectors and topology utilities | `src/` modules | experiment-selected |
| `spin-charge` | spectrum and doublon-resolved spin/charge edges | `spin_charge_spectrum.py` | `results/spin-charge/` |
| `spinon-holon-pump` | spinon/holon defects and relative motion | `scripts/run_spinon_holon_pump.py` | `results/spinon-holon/` |
| `pinning` | pinned-state time-evolution utilities | `src/` modules | experiment-selected |
| `ssh` | non-interacting SSH ED baseline | `run_ssh_ed.py` | `results/ssh/` |

The imported tree had no tracked `results/` files. Existing local results are
therefore preserved as the result record; this merge adds the compatible
entrypoints and provenance without rerunning scans or inventing numbers.

## Running

Run commands from the selected family directory. For example:

```bash
cd experiments/rmh_gap_landscape
python scripts/smoke_L6.py --validate

cd ../rice-mele-chern
python run_rice_mele_chern.py
```

Cluster submission files are retained as source-specific templates. Adapt
partition, account, Python path, and working directory before submitting;
they contain no canonical result data and are not used by the local tests.
