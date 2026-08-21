# Tests

Phase 1 tests cover the exact coupling formula, periodic symmetry, positivity,
input validation, direct-image agreement, and its command-line interface.
Phase 2 tests cover deterministic variable-projection fitting, strict lambda
bounds, relative error metrics, analytical periodization, periodic symmetry,
K convergence on the fitted kernel, and CSV/JSON output schemas.
MPO tests inspect direct, wrapped, and Pauli-field graph edges, verify the
`2K+2` bond dimension, and reconstruct every small-L pair coefficient from
the dense contraction of the actual MPO.

DMRG tests reconstruct the periodic nearest-neighbor Pauli TFIM MPO, compare
ground and orthogonally targeted excited states with ED, and check the
benchmark command's diagnostics and plot outputs.

Phase 6 tests add rotated-basis even/odd ED gates at L=8,10,12, reduced
per-sigma fitting fixtures, a resumable L=4 raw-observable cell, and pure
crossing/gap analysis. They cannot select the L=32,64,128,256 production grid.
