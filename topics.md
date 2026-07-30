# Research Topics

## Finite-abelian invariant-Hermitian symmetry reduction

Build and machine-check a core linear-algebra precursor to NPA symmetry block diagonalization. This prototype is not a general moment-SDP solver; permutation groups and SU(2) are deferred.

### Metrics

- **Cubic eigensolver proxy reduction** (primary): D³/Σₖdₖ³ from dense dimension D and populated sector dimensions dₖ; compute from emitted orthonormal bases; reject any Z₂ case below 3× and any product-cyclic case with at least four populated characters below 10×. The Z₂ ceiling is 4×, so 10× would be mathematically impossible.
- **Spectral exactness** (guard): dense and reconstructed minimum eigenvalue and full sorted spectrum agree within 1e-7×(1+|reference|); independently diagonalize dense and candidate sector matrices; catches wrong blocks and wrong character conventions.
- **Algebraic residuals** (guard): projector action, orthonormality, block consistency, reconstruction, and input commutators are at most 1e-10 in Frobenius norm; catches invalid bases and non-invariant inputs.
- **Genericity** (guard): process every supplied matrix, including a deterministic runtime-only probe, with character-projector output; reject lookup tables, missing IDs, dense passthrough, sandbox escape, and timeout.

### Acceptance gate

A generic reducer passes all 30 visible development and 20 sealed private instances: eigenvalue tolerances 1e-7×(1+|reference|), all residuals ≤1e-10, Z₂ cubic proxy reduction ≥3×, and product-cyclic reduction ≥10× with at least four populated characters. It must beat dense diagonalization by structural block-cost proxy while emitting reconstructible character sectors.

- **Visible-corpus overfit or lookup** — closed by private seeds plus an independently generated runtime probe and exact supplied-ID matching.
- **Dense passthrough** — closed by requiring populated character sectors, dimensions, basis projection, and the reduction thresholds.
- **Wrong answer** — closed by independent dense spectrum, sector-block, projector, and reconstruction checks.
- **Timeout** — closed by an 8-second validator-owned subprocess limit.
- **Environment escape** — closed where practical by fallback guards on file reads, network sockets, and child processes; this is not claimed to be an OS security boundary.
