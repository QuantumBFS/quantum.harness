# Research Catalog

| Algorithm or software | Source | Status | Notes |
|---|---|---|---|
| NPA symmetry block diagonalization | Ioannou & Rosset, arXiv:2112.10803 | paper-only | Verified fact supplied by user; no web fetch performed. |
| Finite-abelian character projectors | Standard finite-abelian representation fact supplied by user | reproduced | Implemented with NumPy; generic reducer passed the deterministic development corpus. |
| Dense reconstruction and spectrum oracle | User-approved issue #229 specification | reproduced | Independently implemented in the validator; checks projector, basis, block, reconstruction, commutator, minimum eigenvalue, and full spectrum. |
| General moment-SDP solver | Out of scope | paper-only | The finite-Abelian baseline is intentionally limited to real order-1/2 moment matrices; general localizing constraints and non-Abelian symmetry remain deferred. |
| Finite-Abelian NC moment-SDP baseline | Independent implementation | reproduced | Julia/JuMP/Mosek builder constructs NC words and a shared affine moment pencil; the dense hierarchy retains all real moments without symmetry zeros, while the group-averaged character-block hierarchy removes non-invariant moments; both agree on deterministic Z₂ and Z₂×Z₂ instances. |
