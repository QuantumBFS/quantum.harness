# Challenge #28 Result Layout

Small, reviewable outputs are stored here. Formal cells use one directory per
bond dimension and seed, each with `manifest.json`, `summary.json`, compact
training/evaluation JSON, and a small checkpoint. Raw Markov chains are never
written here.

The `parameter-scan` collector must retain failed and missing cells in its CSV.
Figures under `figures/` are generated only from committed summary CSV/JSON.
