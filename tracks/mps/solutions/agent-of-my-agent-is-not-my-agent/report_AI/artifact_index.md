# Artifact index

> Status: audit index. “Human” means suitable for concise reviewer-facing
> synthesis; “AI” means retained for technical provenance or diagnosis.

## Canonical accepted result sets

| Result set | Role | Presentation |
|---|---|---|
| `../results/phase6_sigma1.75/validated-local-reproduction/` | K=24/K=32 and χ=128/256 uncertainty | Human summary + AI detail |
| `../results/phase7-crossover/broad/` | Exploratory Γx(σ) trend and brackets | AI; optional human context |
| `../results/phase7-crossover/minimal-validation/` | χ validation of broad crossings | AI; human uncertainty summary |
| `../results/phase8-scaling/sigma-1.75/analysis/` | Self-consistent finite-size crossing-field branch | Human sensitivity comparison + AI detail |
| `../results/phase8-scaling/sigma-1.75/sensitivity-Gamma-ST/analysis/` | σ=7/4 external-field gap scaling | Human primary scaling figure/table |
| `../results/phase9-validation/final-report/` | NN, σ=2/3, and σ=2.0 validation | Human validation figure/table |
| `../results/phase9-validation/sigma1.8-z/report/` | σ=1.8 external-field gap scaling | Human primary scaling figure/table |

## Important existing figures

| Artifact | Audit decision |
|---|---|
| `../results/phase8-scaling/sigma-1.75/sensitivity-Gamma-ST/analysis/phase8-field-sensitivity.png` | Strong source for Human Figure 3; restyle/copy only after approval |
| `../results/phase9-validation/sigma1.8-z/report/gap-scaling.png` | Strong source for Human Figure 4; match Figure 3 style |
| `../results/phase6_sigma1.75/validated-local-reproduction/local-uncertainties.png` | AI diagnostic only; Human Table 4 replaces the redundant figure |
| `../results/phase9-validation/final-report/validation-gaps.png` | Source for Human Figure 2; remove excluded σ=0.4 empty panel |
| `../results/phase5_mpo_validation/coupling_error.png` | AI technical validation; human text/table unless space permits |
| `../results/phase5_mpo_validation/observable_errors.png` | AI technical validation |

## Important numerical tables

- `../results/phase6_sigma1.75/validated-local-reproduction/mpo-uncertainty.csv`
- `../results/phase6_sigma1.75/validated-local-reproduction/mps-uncertainty.csv`
- `../results/phase8-scaling/sigma-1.75/sensitivity-Gamma-ST/analysis/gaps-comparison.csv`
- `../results/phase8-scaling/sigma-1.75/sensitivity-Gamma-ST/analysis/z-eff-comparison.csv`
- `../results/phase8-scaling/sigma-1.75/analysis/uncertainty-budget.csv`
- `../results/phase9-validation/final-report/nn-gaps.csv`
- `../results/phase9-validation/final-report/mean-field-sigma-2over3-gaps.csv`
- `../results/phase9-validation/sigma1.8-z/report/gaps.csv`

## Superseded or diagnostic-only material

| Material | Reason retained | Human-report treatment |
|---|---|---|
| Phase 2 unconstrained and shorter-window fits | Motivated the α=0.5 tail constraint | Omit |
| Phase 6 cluster/L=256 production plans | Records planned but unexecuted scope | Omit |
| Phase 7 provisional χ=64 odd-sector gaps | Convergence flags triggered selective reruns | Omit |
| Phase 7 `gamma-over-nu.csv` and corresponding report label | Computes equal-time S_eq(0) exponent, not susceptibility γ/ν | Explicitly exclude/correct |
| σ=7/4 self-consistent Γc=1.5738504887 branch | Demonstrates critical-field finite-size drift | Include only as sensitivity |
| σ=0.4 fit and qualification artifacts | K=32 finite-ring bias remained above the 1% gate | AI limitation; no claimed benchmark |
| Raw checkpoints, per-cell summaries, runtime logs | Full provenance and recovery | AI only |

## Method and decision documents

- `../docs/methodology.md`
- `../docs/mpo-design.md`
- `../docs/phase5-mpo-validation-design.md`
- `../docs/phase6-validated-local-reproduction-design.md`
- `../docs/phase7-crossover-scan-design.md`
- `../docs/phase8-finite-size-scaling-design.md`
- `../docs/phase9-validation-design.md`

The paired `*-plan.md` files retain execution details and belong only in the
technical archive.
