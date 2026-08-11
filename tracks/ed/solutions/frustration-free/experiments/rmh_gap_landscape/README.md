# rmh_gap_landscape — Three-Gap Landscape of the Rice-Mele-Hubbard Model

Compute three energy gaps across the (δ, Δ) plane at fixed large U:

- **Δ_MB** — many-body gap in half-filled S^z=0 sector
- **Δ_s** — spin gap (lowest triplet excitation)
- **Δ_c** — charge gap (single-particle addition/removal energy)

## Quick Start

```bash
cd experiments/rmh_gap_landscape

# Phase A: L=6 smoke test (~2-3 min, 221 points)
/opt/anaconda3/bin/python scripts/smoke_L6.py --validate

# Plot results
/opt/anaconda3/bin/python scripts/plot_landscapes.py \
    --input ../../results/rmh_gap_landscape/L6_smoke/gaps_L6_smoke.npz

# Run tests
/opt/anaconda3/bin/python -m pytest tests/ -v
```

## Phase B: L=10 Cluster Array Job

```bash
# 1. Submit array job (100 tasks, ~50 points each)
sbatch rmh_gap_landscape.slurm

# 2. After completion, merge checkpoints
/opt/anaconda3/bin/python scripts/merge_results.py \
    --checkpoints-dir ../../results/rmh_gap_landscape/L10/checkpoints

# 3. Plot
/opt/anaconda3/bin/python scripts/plot_landscapes.py \
    --input ../../results/rmh_gap_landscape/L10/gaps_L10_merged.npz
```

## Directory

```
rmh_gap_landscape/
├── src/           # library: model, eigensolver, gaps, I/O
├── scripts/       # executables: smoke_L6, scan_L10, merge, plot
├── configs/       # YAML: smoke_L6, production_L10
├── tests/         # Hamiltonian, dimensions, dense/sparse, gap definitions
└── results/ -> ../../results/rmh_gap_landscape/
```

## Gap Definitions

| Gap | Formula | Sectors |
|-----|---------|---------|
| Δ_MB | E₁(N/2,N/2) − E₀(N/2,N/2) | half-filling |
| Δ_s | E₀(N/2+1,N/2−1) − E₀(N/2,N/2) | triplet |
| Δ_c | E₀(N/2+1,N/2) + E₀(N/2−1,N/2) − 2E₀(N/2,N/2) | charge ±1 |
