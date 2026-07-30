# Plasma-Team: chiral-graviton NQS

This directory implements Quantum Harness Challenge #15: the neutral spin-2 gap of
the fermionic `nu=1/3` Laughlin liquid on the Haldane sphere,

`Delta_N = E_N(L=2) - E_N(L=0)`,

at flux `2Q=3(N-1)` with chord-distance Coulomb interaction and energies in
`e^2/(epsilon*l_B)`.

## Result

This is a finite-size, full-Fock-enumerated benchmark. ED was completed for
`N=3..8`; the shared neural ansatz reaches `N=9` using a certified sparse
highest-weight projector. At `N=9`,

- NQS: `Delta_9 = 0.130509244209`;
- direct `|psi|^2` sampling: `0.1305092418 +/- 0.0000000066` (one standard
  error, 100,000 independent samples);
- `<L^2> = 6`, with `||L_+ psi||/||psi|| = 4.05e-11` for the excited state.

At the ED boundary `N=8`, the sparse NQS gap differs from ED by only
`2.42e-12`. At `N=7`,

- ED: `Delta_7 = 0.129198097822604`;
- NQS: `Delta_7 = 0.129198097823100`;
- direct `|psi|^2` sampling: `0.12919809694 +/- 0.00000000185` (one standard error,
  100,000 independent samples);
- `<L^2> = 6`;
- the five `M=-2,...,2` members have energy spread `4.44e-15`;
- a generic-axis rotation agrees with the spin-2 representation to `9.43e-12`.

These sampling standard errors diagnose the energy estimator at one optimized
parameter vector. They do not include ansatz bias, optimizer/restart variation,
or finite-size extrapolation uncertainty.

A linear fit in `1/N` for `N=4..9` gives
`Delta_infinity = 0.1289 +/- 0.0035`. Even/odd and quadratic alternatives imply
a much larger `0.0134` small-size model envelope, so the extrapolation remains
exploratory.

An ED evaluation of the rank-two `m=1<->3` parent-channel proxy shows the
predicted qualitative helicity asymmetry. For `N=7` Coulomb, the integrated
bright/dark ratio is `616`; the lowest `L=2` pole
carries `77.4%` of the bright weight and has a bright/dark ratio of `1443`. For
the `V1` Laughlin parent state the dark norm is zero to numerical precision.
The same proxy now has an NQS-native command; neither path is the full Coulomb
metric derivative used for a complete spectral-response reproduction.
The reviewed sparse `N=7` NQS path gives the same ratio `616.061`, bright-pole
fraction `0.774345`, and a projected-irrep error of `1.38e-14`.

See [REPORT.md](REPORT.md) for the full table, interpretation, and limitations.

## Design

- Fermionic antisymmetry is exact because amplitudes multiply ordered LLL Fock
  determinants.
- A shared one-hidden-layer MLP produces amplitudes for the `Lz=0` and `Lz=2`
  sectors.
- Orthogonal or certified sparse projection onto `ker(L_+)` makes the final
  output states numerical `L=0` and `L=2` highest weights; the residual is
  recorded and acceptance-gated.
- Production ED and NQS share the same Hamiltonian-building kernel. A separate
  first-quantized quadrature/determinant implementation independently checks
  `N=3,4`; `N=5..8` remain shared-kernel cross-checks.
- SO(3) symmetry is imposed on the output amplitudes by numerical highest-weight
  projection with recorded residuals. The input MLP is not a coordinate-space
  equivariant network.

The sparse projector removes the dense null-space bottleneck and reaches one
size beyond the completed production ED series. The implementation still enumerates the fixed-`M`
Fock sector and explicitly builds the sparse Hamiltonian; it is therefore a
certified `N=8--9` bridge, not a thermodynamic-scale autoregressive/MCMC NQS.
Its reported Monte Carlo error uses posterior IID draws from the fully
enumerated `|psi|^2` distribution; it is not a scalable Markov-chain VMC run.

All new command results fail closed on optimizer, non-finite, residual,
variance, and symmetry-gate failures. Successful JSON is marked
`status: complete` and embeds dependency, platform, Git, run-configuration,
and tolerance provenance. `requirements-lock.txt` records the reviewed local
environment snapshot.

## Quick start

From this directory in PowerShell:

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
$env:PYTHONPATH = 'src'
& '.venv\Scripts\python.exe' -m pytest -q
& '.venv\Scripts\python.exe' -m chiral_graviton ed --n 6 --output ed-n6.json
& '.venv\Scripts\python.exe' -m chiral_graviton oracle --n 3 --output oracle-n3.json
& '.venv\Scripts\python.exe' -m chiral_graviton nqs --n 6 --samples 100000 --output nqs-n6.json
& '.venv\Scripts\python.exe' -m chiral_graviton multiplet --n 7 --output multiplet-n7.json
& '.venv\Scripts\python.exe' -m chiral_graviton nqs --n 9 --projection sparse --samples 100000 --output nqs-n9.json
& '.venv\Scripts\python.exe' -m chiral_graviton chirality --n 7 --output chirality-n7.json
& '.venv\Scripts\python.exe' -m chiral_graviton nqs-chirality --n 4 --output nqs-chirality-n4.json
& '.venv\Scripts\python.exe' -m chiral_graviton nqs-equivariance --n 4 --output nqs-equivariance-n4.json
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_review.ps1
```

To regenerate the finite-size regression/reproduction suite, use
`scripts/run_acceptance.ps1`; the `N=8` ED and `N=9` NQS calculations are the
slow steps.

The separate official-MATLAB CPMC-Lab Figure 4(a-c) reproduction, including
all nine `U/t=0..8` points, blocking diagnostics, finite-difference systematic
errors, and digitized-ED provenance, is documented in
[`cpmc_lab_fig4/README.md`](cpmc_lab_fig4/README.md).

## Reference

S.-F. Liou, F. D. M. Haldane, K. Yang, and E. H. Rezayi,
*Chiral Gravitons in Fractional Quantum Hall Liquids*,
Phys. Rev. Lett. 123, 146801 (2019), arXiv:1904.12231.
