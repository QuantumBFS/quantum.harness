# Periodized Exponential MPO Design

## Scope and convention

Construct only the finite-chain TeNPy MPO for

`H = -sum_(i<j) J(i,j) Sigmaz_i Sigmaz_j - Gamma sum_i Sigmax_i`,

where sites are zero-indexed and

`J_k(i,j) = A_k [lambda_k^(j-i) + lambda_k^(L-j+i)]`,

`A_k = c_k/(1-lambda_k^L)`.

The MPS and MPO have finite open boundaries; periodicity is contained in the
coupling coefficients. Pauli `Sigmax` and `Sigmaz`, not spin `Sx` and `Sz`,
fix the normalization.

## Graph channels

For each exponential k, a direct graph state opens with
`lambda_k Sigmaz`, propagates with `lambda_k Id`, and closes with
`-A_k Sigmaz`. A wrapped graph state opens on site i with
`lambda_k^i Sigmaz`, propagates with `Id`, and closes on site j with
`-A_k lambda_k^(L-j) Sigmaz`. All factors are at most one except the physical
Hamiltonian coefficient A_k; no inverse decay is propagated.

The field is a direct `IdL -> IdR` edge carrying `-Gamma Sigmax`. With K
exponentials the bulk bond dimension is at most `2K+2`, hence 50 for K=24.

## Validation

For small L, contract the actual MPO into a dense operator. Recover each pair
coefficient by `Tr(H Sigmaz_i Sigmaz_j)/2^L` and each field coefficient by
`Tr(H Sigmax_i)/2^L`. Compare all recovered pair couplings with the fitted
periodized table and report the maximum relative error. This validates direct
channels, wrapped channels, signs, Pauli normalization, and field terms
without running DMRG.
