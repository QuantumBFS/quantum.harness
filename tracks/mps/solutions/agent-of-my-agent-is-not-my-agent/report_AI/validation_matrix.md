# Validation matrix

> Status: audited structure; final numerical transcription pending approval.

| Validation target | Comparison or gate | Status | Canonical evidence |
|---|---|---|---|
| Exact periodic coupling | Hurwitz-zeta formula versus image sum | Accepted | `../src/lrtfim/couplings.py`, `../tests/test_couplings.py` |
| Exponential representation | Kernel and finite-ring residuals; K and tail stability | Accepted for declared σ range | `../results/phase2_tail_stable/` |
| Periodized MPO coefficients | Direct/wrapped channel reconstruction | Accepted | `../tests/test_mpo.py`, `../results/phase5_mpo_validation/` |
| Small-system Hamiltonian | Exact pair ED versus dense MPO ED | Accepted | `../results/phase5_mpo_validation/` |
| Small-system observables | ED versus MPO ED versus DMRG | Accepted | `../results/phase5_mpo_validation/` |
| Rotated parity basis | NN and long-range ED fixtures | Accepted | `../results/phase6_sigma1.75/` |
| MPO convergence | K=24 versus K=32 coupling, Rξ, and gap | Accepted for production points | `../results/phase6_sigma1.75/validated-local-reproduction/` |
| MPS convergence | χ=128 versus χ=256 | Accepted for tested points | `../results/phase6_sigma1.75/validated-local-reproduction/` |
| NN critical benchmark | Γx≈1 and z≈1 at modest sizes | Accepted as pipeline validation | `../results/phase9-validation/final-report/` |
| Mean-field boundary | σ=2/3 at external Γc=3.673; z→1/3 | Accepted with finite-size qualification | `../results/phase9-validation/final-report/` |
| σ=7/4 scaling | Five sizes at self-consistent and external fields | Accepted as sensitivity study | `../results/phase8-scaling/sigma-1.75/` |
| σ=1.8 scaling | Five sizes at external Γc=1.5288 | Accepted as validation comparison | `../results/phase9-validation/sigma1.8-z/report/` |
| σ=2.0 Γc benchmark | Phase 7 Γx(32,64) versus publication | Accepted as finite-size comparison | `../results/phase9-validation/final-report/` |
| σ=0.4 mean-field point | K=32 finite-ring coupling error below 1% | Failed qualification; DMRG not run | `../results/phase9-validation/mean-field-fixed-fields/mpo-bias-qualification/` |
| Susceptibility γ/ν | Imaginary-time-integrated S(0,0) available | Not implemented; outside DMRG scope | decision record and Phase 8/9 reports |
