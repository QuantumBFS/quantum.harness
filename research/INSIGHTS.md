# Research Insights

## Selected

### Character-projector sector construction
- **Technique**: For G=∏ᵢZₙᵢ, enumerate one-dimensional characters and form Pₖ=|G|⁻¹Σ_g conjugate(χₖ(g))ρ(g); retain the numerical rank-one eigenspace of each populated projector as an orthonormal sector basis.
- **Applies when**: The finite-group representation is unitary, the group is abelian, and the target Hermitian matrix commutes with every generator.
- **Limits**: Does not cover higher-dimensional nonabelian irreps, multiplicity-space refinements beyond each character sector, general NPA moment construction, permutation symmetry machinery, or SU(2).
- **Sources**: [ioannou_rosset_2021] and user-verified finite-abelian representation facts.

### Reconstruction-first validation
- **Technique**: Concatenate all sector bases, rebuild H as ΣₖBₖ(Bₖ†HBₖ)Bₖ†, and compare its full sorted spectrum with dense diagonalization.
- **Applies when**: Matrices are small enough for dense validation and candidate output includes bases and reduced blocks.
- **Limits**: Dense validation is a research-prototype oracle, not the scalable production path.
- **Sources**: [ioannou_rosset_2021] and the user-approved validation specification.

## Shelved

None. Permutation-group and SU(2) reductions are explicitly deferred.
