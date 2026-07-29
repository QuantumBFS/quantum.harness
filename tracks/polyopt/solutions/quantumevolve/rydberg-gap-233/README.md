# #233 Certified Spectral Gaps for Blockaded Rydberg Chains

> Catalog issue: QuantumBFS/quantum.harness#233
> Track: polyopt (SDP hierarchy) + ed (verification)
> Difficulty: ★
> Released by: Jie Wang (AMSS CAS) & Jin-Guo Liu (HKUST-GZ)

## Objective

Adapt the gap-certificate hierarchy to the Pauli/projector algebra of
blockade-constrained (PXP-type) Rydberg chains:

1. Express blockade constraints as localizing constraints in the SDP
2. Exploit translation invariance for efficiency
3. Produce certified gap lower bounds across parameter space

## Verification gate

- Certified gap lower bounds contain the ED gap for all n ≤ 20
- Bounds remain bounded away from zero in the thermodynamic-limit relaxation
  over a stated parameter window
- Exportable, independently checkable certificates

## Approach

- SDP hierarchy via NCTSSoS.jl (or QMBCertify.jl for structured models)
- ED verification via XDiag.jl / QuSpin
- Translation-invariant moment reduction for scaling

## Status

- [x] Challenge registered (PR #181)
- [ ] Baseline SDP setup for PXP n=4..8
- [ ] ED gap reference for n ≤ 20
- [ ] First certified gap bound
- [ ] Parameter sweep (blockade regime → criticality)
