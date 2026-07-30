# Preregistered large-lattice benchmark plan

Status: proposed. No compute is authorized until the user ratifies this setup
once. Resources and final sweep counts remain proposed/TBD based on the pilot;
no Slurm partition is assumed.

## Fixed setup for ratification

- Periodic L by L triangular lattice with all elementary up and down triangles.
- Spinless fermions, one orbital per site, number conserving.
- epsilon=1/100, kappa=1/50, s=1/4, g_A=g_B=1/4, and mu=0.
- L=4,6,8,12,16, hence N=16,36,64,144,256.
- beta in {1/2,1,2,4}.
- Four chains per cell: two cold at order zero and two hot at round(beta*N).
- Fixed seed = 121000000 + 10000*L + 10*beta_index + chain_id, with beta
  indices 0,1,2,3 for 1/2,1,2,4. Failed chains are never reseeded.

Ordered CT times are analytically integrated into beta^m/m!, so hot starts do
not draw explicit times. At m=round(beta*N), resolved word labels are drawn
independently from q(a)=lambda_a/G_0: uniform among all 2*N triangles, equal A/B
probability, and uniform S3 labels at the frozen equal couplings. The RNG is
NumPy PCG64DXSM; its exact package version and full state are frozen in the
snapshot.

## Analytic numerical bound

For fixed s>0, let U be the sites touched by a word. Taking each row at the last
local factor that touches it gives

    ||T_U||_infinity <= q = exp(-kappa*s) < 1.

Here q=exp(-1/200), approximately 0.995012 (analytic). Thus every configuration
has strictly positive determinant weight, and

    ||(I+T_U)^(-1)||_infinity <= 1/(1-q),
    cond_infinity(I+T_U) <= (1+q)/(1-q), approximately 400.

Consequently a computed zero or negative weight is a hard numerical or
implementation failure, not an allowed exact-zero boundary case.

## Gates

1. G0 algebra tests: A/B and S3 embeddings, contraction and inverse bounds,
   Fock trace/determinant identities, and rank-3 versus rebuild ratios.
2. G1 N<=9 ED: isolated N=3 and periodic N=4,9 fixtures at every beta; compare
   energy, density, compressibility, equal-time Green function, and density
   structure factor within max(5*MCSE,1e-10).
3. G2 pilot: (L,beta)=(4,1/2),(8,2),(12,4); estimate tau_int, acceptance,
   update accuracy, timing, memory, sweep counts, and full-run resources.
4. G3 full: all 20 cells, four fixed chains; warmup at least
   50*max_tau_int and equal preregistered extensions for all chains.
5. G4 independent audit: recompute snapshot weights and observables, verify
   chain provenance, and rebuild scaling tables from raw logs.

Each gate requires a PASS from its predecessor. Cluster stages require durable
outputs, completion sentinels, and afterok dependencies. Inspect live sinfo,
squeue, and node allocation before submission.

## Metrics and stop rules

Record acceptance, expansion order, fast/rebuild error and speed, inverse
residual, sign and zero-weight counts, R-hat, ESS, tau_int, proposal/sweep time,
peak memory, energy, density, compressibility, G(r), and S_n(q).

- Fast/rebuild error <=1e-9; inverse residual <=1e-8.
- Negative and zero weight counts must both equal zero.
- Pilot acceptance target [0.2,0.7]; full insertion/deletion hard range
  [0.1,0.9].
- R-hat <=1.01, bulk ESS >=1000, tail ESS >=400.
- Withhold scalability if rank-3 speedup is not above 2 by N=144, update time
  scales worse than N^2.7, or memory worse than N^2.5 after excluding N=16.
- Do not start L>12 without a stable, faster rank-3 pilot path.

A nonpositive weight, ED discrepancy, update mismatch, or unstable residual is a
hard stop. Hot/cold disagreement or failed R-hat/ESS at the frozen extension cap
makes a cell inconclusive. OOM, timeout, or missing durable completion evidence
is failure. Never drop/reseed a chain or retune physics after inspecting full
results.

At mu=0 this positive-semidefinite construction has a low-temperature vacuum
ground state. This benchmark does not solve the open itinerant finite-density
problem. A pass supports only the fixed mu=0 correctness and scaling claim.
