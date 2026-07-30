# Challenge 15 reference sources

Raw PDFs and source archives are stored locally under `papers/` and `code/`.
They are gitignored; this manifest records their exact sources and SHA256
digests so another checkout can reconstruct the same reference set.

## Papers

- `1904.12231-chiral-gravitons.pdf`
  - Role: challenge physics and chirality definition.
  - Source: https://export.arxiv.org/pdf/1904.12231
  - SHA256: `8a8f5931f0ffeb6d5e072ea34414753cc7980fbf03d7e509f4b2893559c1648d`
- `1106.3375-geometrical-fqh.pdf`
  - Role: geometric description of fractional quantum Hall states.
  - Source: https://export.arxiv.org/pdf/1106.3375
  - SHA256: `f37601ee01371469823051f4bfdf389292c064e90837a38897b0d648a31995cf`
- `2109.08816-analytic-graviton-modes.pdf`
  - Role: analytic graviton-mode and pseudopotential reference.
  - Source: https://export.arxiv.org/pdf/2109.08816
  - SHA256: `fdbc4e2b7926ab96421995a1259c18281a6630e5924291198b602a96224f319a`
- `2412.14795-deephall.pdf`
  - Role: sphere-geometry neural VMC and fermionic wavefunction design.
  - Source: https://export.arxiv.org/pdf/2412.14795
  - SHA256: `d9b58eefd9207879283564a137817bd9114288b66cdd5972fe738c5d6189d1a0`
- `2412.00618-fqh-self-attention.pdf`
  - Role: Psiformer-style self-attention for fractional quantum Hall VMC.
  - Source: https://export.arxiv.org/pdf/2412.00618
  - SHA256: `a8f12a3107b862e03d1169ef026cbd84b9e97c1d0080ab40744d34e80d69bec2`
- `2607.01408-spin-weighted-equivariance.pdf`
  - Role: spin-weighted spherical harmonics and intrinsic equivariant layers.
  - Source: https://export.arxiv.org/pdf/2607.01408
  - SHA256: `737a8bfbfe1a7e26b35ba1e8dc040803691ddacb6c80c4181dda4e0275e72728`

## Code snapshots

- `DeepHall-9f47478.tar.gz`
  - Role: primary sphere FQH neural-VMC implementation.
  - Repository: https://github.com/bytedance/DeepHall
  - Commit: `9f47478dd36cf5e2b065e49184e58fce5cb88835`
  - Source: https://codeload.github.com/bytedance/DeepHall/tar.gz/9f47478dd36cf5e2b065e49184e58fce5cb88835
  - SHA256: `08d01a8f3a2f40c5d37757bc26f0c1540771b6f571d8f0a0713cc502981dddb6`
- `QuantumHallED-dc2480a.tar.gz`
  - Role: independent small-system sphere exact-diagonalization reference.
  - Repository: https://github.com/mishmash/QuantumHallED.jl
  - Commit: `dc2480a525a14c8cec1e1257cc06d971ef759eed`
  - Source: https://codeload.github.com/mishmash/QuantumHallED.jl/tar.gz/dc2480a525a14c8cec1e1257cc06d971ef759eed
  - SHA256: `6f9d5a56b57a1c7925f67ebeb921036166c75836ce37b11cac7d742ab77d68b5`
- `SpinGTP-c65aa86.tar.gz`
  - Role: spin-weighted spherical-harmonic tensor products and equivariant layers.
  - Repository: https://github.com/divelab/SpinGTP
  - Commit: `c65aa867d4a1de251b51a031d67fffc88c9285a8`
  - Source: https://codeload.github.com/divelab/SpinGTP/tar.gz/c65aa867d4a1de251b51a031d67fffc88c9285a8
  - SHA256: `a11f8104a4949e3b4fac900fb203c0b071d516f082a2d5d69199539dcd7b9f33`
