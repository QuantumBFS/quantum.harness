# Benchmark Database Provenance

The 50-instance corpus is synthetic and deterministic. `generate_corpus.py` maps explicit NumPy RNG seeds to random unitary changes of basis, finite product-cyclic generator representations, and Hermitian matrices assembled independently inside equal-multiplicity character sectors.

- Development: 30 visible specifications and NPZ inputs in `research/benchmark/dev/`.
- Private: 20 specifications and NPZ inputs in gitignored `research/benchmark/private/`.
- Labels: not stored. The validator regenerates matrices from specifications and computes dense spectra, character projectors, blocks, and residuals independently.
- Scope: Z₂ and products Z₂×Z₂, Z₂×Z₃, Z₃×Z₃, and Z₂×Z₂×Z₂ only.
