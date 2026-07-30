# Goal: Finite-Abelian NC Moment-SDP Baseline

Accept the finite-Abelian milestone only when an independent Julia builder starts from a noncommutative problem specification and passes all structural and numerical checks below. The older invariant-Hermitian matrix corpus remains a precursor test, not a substitute for this goal.

- Enumerate words through order 1–2 for self-adjoint ±1 generators; normalize by adjacent square cancellation and only declared cross-site commutations.
- Construct moment entries as `y_normalize(reverse(u) * v)` and use one shared affine pencil for both formulations.
- Lift Z₂^k generator signs to word/moment characters, reject non-invariant Hamiltonians, and fix non-invariant moments to zero under group averaging.
- Dense formulation: one full affine PSD constraint. Reduced formulation: character-diagonal affine PSD blocks from the same pencil, never blocks of a pre-evaluated numerical matrix.
- Deterministic Z₂ and Z₂×Z₂ instances: dense/reduced optimum difference ≤1e-7; reconstructed matrix minimum eigenvalue ≥−1e-7; normalization, symmetry, and objective residuals ≤1e-8.
- Solver path is Julia + JuMP + MosekTools/Mosek. NCTSSoS may be installed but must not construct the core model; Clarabel is excluded.

The earlier matrix-only precursor separately retains its 30 development + 20 sealed-instance spectral/reconstruction checks.

This goal completes the explicitly narrowed finite-Abelian NC moment-SDP milestone. It does not claim the full general scope of issue #229: non-Abelian permutation symmetry, SU(2), localizing matrices for general polynomial constraints, complex moment data, and higher-order scalability remain deferred.
