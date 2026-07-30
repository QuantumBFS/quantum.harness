# Challenge 194 references

Downloaded on 2026-07-29 for the long-range random-cluster/percolation
challenge. The PDF hashes below bind the local copies to the cited inputs.

## Local papers

- `papers/gori-2017-long-range-percolation-arxiv1610.00200.pdf`
  - G. Gori et al., *One-dimensional long-range percolation: A numerical study*
  - <https://arxiv.org/abs/1610.00200>
  - SHA256 `95fb2bbc00550f6d500cfa45b6149223bd2e43cbb1d2ded12e196c45c0066584`
- `papers/duminil-copin-2024-long-range-1d-arxiv2011.04642.pdf`
  - H. Duminil-Copin, C. Garban, and V. Tassion,
    *Long-range models in 1D revisited*
  - <https://arxiv.org/abs/2011.04642>
  - SHA256 `44d0d458832ac87e1bb62599c9d378b2993da2ef41d061d82a0fccd8b1eec7b0`
- `papers/luijten-2001-inverse-square-criticality-cond-mat0104175.pdf`
  - E. Luijten and H. Meßingfeld,
    *Criticality in one dimension with inverse square-law potentials*
  - <https://arxiv.org/abs/cond-mat/0104175>
  - SHA256 `127e1879b631663e7b8ca0157bb5474bf3b7ea346d9b4b466ca3c7b2d9b1fa33`
- `papers/aizenman-newman-1986-inverse-square-percolation.pdf`
  - M. Aizenman and C. M. Newman,
    *Discontinuity of the percolation density in one dimensional
    1/|x-y|^2 percolation models*
  - DOI <https://doi.org/10.1007/BF01205489>
  - SHA256 `07fc91386b60a8b364e779c2145880b3dcca7e5a00dea3d89c0dfd9ffcc1e051`

The Gori arXiv source archive is stored as
`sources/gori-2017-arxiv-source.tar`, SHA256
`a56b61aefa9cfad5be88138c397eda735f8264497e81d72a84c03b64e740669e`.

## Citation-only inputs

The following publisher copies were not downloaded because an open PDF was
not confirmed:

- J. L. Cardy, *One-dimensional models with 1/r^2 interactions*,
  DOI <https://doi.org/10.1088/0305-4470/14/6/017>.
- C. M. Newman and L. S. Schulman,
  *One dimensional 1/|j-i|^s percolation models: The existence of a
  transition for s <= 2*, DOI <https://doi.org/10.1007/BF01211064>.

## External code

No official implementation for Gori et al. was found. A related GPL-3.0
long-range Monte Carlo implementation was cloned for algorithm study only:

- repository: <https://github.com/sadeqismailzadeh/ONMC>
- revision: `28d4b5d85e80590460ec1d80c73ea5337d2fcf93`
- local ignored path:
  `tracks/qmc/results/frustration-free/challenge-194/external-code/ONMC`

ONMC does not implement the pinned q=1 periodic-image percolation model and
must not be treated as an independent scientific oracle. No code is copied
from it into the solution without a separate license and algorithm review.
