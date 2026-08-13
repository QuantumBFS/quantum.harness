# Third-party provenance

The issue-92 implementation is original code built against the interfaces
listed below.  Algorithms adapted from an upstream project are identified so
that numerical and licensing provenance remains reproducible.

| project | pinned revision | license | use in this directory |
|---|---|---|---|
| [wangjie212/SpectralGap](https://github.com/wangjie212/SpectralGap) | `a1171c906ff2cc2901e58c2426397a2f68c32bb7` (2026-07-24) | MIT, Copyright 2025 Jie Wang | reference Ising driver, comparison of state-monomial/block conventions; no source file is vendored into the Julia core |
| [QuantumSOS/NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl) | `5b355f10baf582a88c9a2ee8f553fc285944d839` (2026-06-27) | MIT | support-graph, chordal-closure, and symmetry-reduction design reference |
| [wangjie212/NCTSSOS](https://github.com/wangjie212/NCTSSOS) | `f26780d9dbc4c05e2cf3c64e988689426378a783` (2026-06-26) | MIT | round/project certificate workflow and exact rational-bound design reference |
| [jump-dev/MosekTools.jl](https://github.com/jump-dev/MosekTools.jl) / [MOSEK/Mosek.jl](https://github.com/MOSEK/Mosek.jl) | releases `0.15.10` / `11.2.0`, tree hashes pinned by `julia/Manifest.toml` | MIT interfaces; Mosek solver requires its own license | production JuMP backend and dual-ray access |

`SpectralGap.jl` is Pauli-specific and its pinned solver path imports
`MosekTools`; it is not used as the truncated-boson backend.  The reproduction
script installs the exact revision in an isolated Julia environment and
records the upstream block sizes and solver/Mosek metadata.

The term-sparsity implementation was compared specifically with
`NCTSSoS.jl/src/optimization/sparsity.jl` at the pinned revision.  The
certificate design was compared with
`NCTSSOS/src/certification/{sparse,dense,helpers}.jl`.  The code here is an
original adaptation of those published algorithmic ideas for canonical finite
matrix units, general affine Farkas identities, and the
`Q(sqrt(2),sqrt(3))` coefficient field; no upstream source file is copied
verbatim.  If that changes, the exact upstream path and revision plus the MIT
notice must be retained here.

The regression suite fixes one small upstream structural oracle from
`NCTSSoS.jl/test/data/expectations/relaxations_sparsity.toml`: dense
order-one moment matrices for one and two unipotent generators have
`(side,nuniq)=(2,2)` and `(3,4)`.  The cutoff-one projector coordinates
`u=1-2E11` reproduce both counts and the corresponding exact idempotent moment
entries.

The paper PDFs in `ref/` are research inputs, not redistributed software.
