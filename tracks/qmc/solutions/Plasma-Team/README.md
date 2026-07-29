# Plasma-Team: chiral-graviton NQS

This directory implements Quantum Harness Challenge #15: the neutral spin-2 gap of
the fermionic `nu=1/3` Laughlin liquid on the Haldane sphere,

`Delta_N = E_N(L=2) - E_N(L=0)`,

at flux `2Q=3(N-1)` with chord-distance Coulomb interaction and energies in
`e^2/(epsilon*l_B)`.

## Result

ED was completed for `N=3..8`; the shared, exactly projected neural ansatz was
validated for `N=3..7`. At `N=7`,

- ED: `Delta_7 = 0.129198097822604`;
- NQS: `Delta_7 = 0.129198097823100`;
- direct `|psi|^2` sampling: `0.12919809694 +/- 0.00000000185` (one standard error,
  100,000 independent samples);
- `<L^2> = 6`;
- the five `M=-2,...,2` members have energy spread `4.44e-15`;
- a generic-axis rotation agrees with the spin-2 representation to `9.43e-12`.

A cautious linear fit in `1/N` for `N=4..8` gives
`Delta_infinity = 0.1274 +/- 0.0048`; this regression error does not include the
finite-size-fit systematic.

See [REPORT.md](REPORT.md) for the full table, interpretation, and limitations.

## Design

- Fermionic antisymmetry is exact because amplitudes multiply ordered LLL Fock
  determinants.
- A shared one-hidden-layer MLP produces amplitudes for the `Lz=0` and `Lz=2`
  sectors.
- Orthogonal projection onto `ker(L_+)` makes the final heads exact `L=0` and
  `L=2` highest-weight states.
- ED uses the same spherical Coulomb pseudopotentials and supplies an independent
  small-system oracle.

This is an exact-enumeration, small-system NQS baseline. It validates the physics
and acceptance criteria but does not claim the beyond-ED scaling of an
autoregressive or Markov-chain NQS.

## Quick start

From this directory in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
& '.venv\Scripts\python.exe' -m pytest -q
& '.venv\Scripts\python.exe' -m chiral_graviton ed --n 6 --output ed-n6.json
& '.venv\Scripts\python.exe' -m chiral_graviton nqs --n 6 --samples 100000 --output nqs-n6.json
& '.venv\Scripts\python.exe' -m chiral_graviton multiplet --n 7 --output multiplet-n7.json
```

To regenerate the complete acceptance suite, use
`scripts/run_acceptance.ps1`; the `N=8` ED calculation is the slow step.

## Reference

S.-F. Liou, F. D. M. Haldane, K. Yang, and E. H. Rezayi,
*Chiral Gravitons in Fractional Quantum Hall Liquids*,
Phys. Rev. Lett. 123, 146801 (2019), arXiv:1904.12231.
