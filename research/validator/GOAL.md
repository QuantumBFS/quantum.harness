# Goal: Finite-Abelian Symmetry Reduction

Accept a generic finite-abelian character-projector reducer only when it passes all 30 development and 20 sealed private invariant-Hermitian instances.

- Dense versus reduced minimum eigenvalue and full sorted spectrum: error ≤1e-7×(1+|reference|).
- Projector action, orthonormality, candidate block consistency, reconstruction, and commutator residuals: ≤1e-10.
- Z₂ family: cubic eigensolver cost proxy D³/Σₖdₖ³ ≥3× (the mathematical maximum is 4×).
- Product-cyclic families: at least four populated characters and proxy reduction ≥10×.
- Reject dense passthrough, lookup/corpus-aware output through a runtime probe, wrong answers, environment escape where practical, and executions exceeding 8 seconds.

This is a self-contained core linear-algebra precursor/proxy for NPA symmetry block diagonalization, not a general moment-SDP solver. Nonabelian permutation symmetry and SU(2) are deferred.
