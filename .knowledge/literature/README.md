# Methodology Literature

Rendered methodology references for the quantum many-body physics harness.

`ref.bib` is the human-edited source of truth for which references belong to
which method (entry `keywords = {mps-based-algorithm, …}`). The per-method JSON
manifest consumed by `fetch_metadata.py` / `render.py` is derived via
`skills/download-ref/helpers/bibtex_to_manifest.py` and is not
committed. The rendered Markdown entries under each method folder are the
agent-facing cite targets — agents cite the rendered Markdown path when one
exists.

Each method folder has its own `INDEX.md` and rendered markdown entries. Raw
PDFs, Semantic Scholar metadata, and extracted figures live in ignored `.raw/`
and `.figures/` directories inside each method folder.

## Folders

- `mps-based-algorithm/` - DMRG, TEBD, and matrix-product-state references.
- `peps-based-algorithm/` - CTMRG and PEPS-based references.
- `ltrg/` - linearized tensor renormalization group (finite-temperature) references.
- `quantum-monte-carlo/` - quantum Monte Carlo references.
- `variational-monte-carlo-neural-quantum-states/` - variational Monte Carlo and neural quantum state references.
- `quantum-circuit-simulation/` - tensor-network / VQE-style circuit simulation references.
- `anderson-impurity/` - Anderson/Kondo impurity solver references.
- `dmft/` - DMFT references mentioned as adjacent/future methodology.
- `ed/` - exact diagonalization references.

`ref.bib` lives at this directory's root. To regenerate it from the rendered
markdown (e.g. after a manual edit drift) run
`python3 skills/download-ref/helpers/md_to_bibtex.py` from the repo root.
