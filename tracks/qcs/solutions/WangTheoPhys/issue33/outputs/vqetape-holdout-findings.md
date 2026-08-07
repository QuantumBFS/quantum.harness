# VQETape symmetry-breaking holdout findings

## Workload

The holdout is the open longitudinal-field Ising chain

\[
H=-J\sum_i Z_iZ_{i+1}-g\sum_iX_i-h\sum_iZ_i,
\]

with a depth-two RZZ–RY–RX ansatz. Its ground energy comes from independent dense diagonalization, not the TFIM free-fermion oracle.

## Result

- Converged: `True`.
- Calls: `15`.
- Compile: `2.248` s.
- Time to target (including compile): `4.206` s.
- Final energy error: `0.00941175`.
- Global-X commutator Frobenius norm: `5.6`.

## Symmetry decision

Z2-native TFIM compression is explicitly inapplicable:

- longitudinal Z field breaks global-X symmetry
- RY ansatz generators break global-X symmetry

This holdout exercises a different conserved-charge regime and a symmetry-breaking ansatz family. It is a small exact generality check, not a claim of large-system longitudinal-Ising tensor performance.
