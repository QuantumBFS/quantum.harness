# Reviewer guide for the two-paper exact-degeneracy package

## What is established

Paper I establishes a finite-size operational result: exact spectral degeneracy does not make the protected subspace geometrically featureless. When a gapped projector (P(\lambda)) moves over coupling space, the covariant response (Q\partial_aP\,P), non-Abelian curvature, and Wilson transport distinguish frozen, structured, and random-matrix-like geometric behavior even though ordinary intrafiber level statistics are undefined.

Paper II establishes an exact algebraic result for independent centered response channels. Their complete fourth cumulants add with fourth powers of the deterministic weights. The familiar (1/N_{\mathrm{eff}}) suppression follows only after variance normalization and comparability of the single-channel standardized cumulants. The response-algebra commutant gives an independent irreducibility obstruction; it is not a proof of Gaussianity or ETH.

## What failed

The preregistered chiral-index specialization of the channel law did not pass. For the three validation sizes, the random-channel confidence intervals do not enter the development band. The failure demonstrates that (N_{\mathrm{eff}}) alone does not close the registered finite-size ensemble. It does not identify which of the following is responsible:

- dependence among response channels;
- noncomparable standardized single-channel cumulants;
- correlations between weights and channel statistics;
- finite-rank or finite-size geometry;
- the registered tangent population.

The title gate therefore rejects *The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles*. This is a prospective negative result with a conditional theorem, not an established Geometric ETH law.

## Fast review route

| Question | Evidence |
|---|---|
| Is the subspace exactly degenerate and gapped? | Paper I model/evidence tables and registry gates |
| Is the response gauge covariant? | Paper I formalism and Paper II Sec. II |
| Are spectral and geometric channels independent? | Paper I fixed-projector and moving-projector interventions |
| Does one random law fit every model? | No; Paper I mechanism comparison and rejected parent-transfer laws |
| Is the channel theorem exact? | Yes, under the assumptions stated in Paper II Theorem 1 |
| Does the physical (N_{\mathrm{eff}}) closure pass? | No; Paper II Fig. 6 and `theory_gate_v14.json` |
| Is Geometric ETH established asymptotically? | No |
| Is a black-hole or thermalization theorem claimed? | No |

## Machine-readable evidence

- Paper I audit: `01_task_folder/task_05/script/output/paper1_prb_v13/delivery_audit_v13.json`
- Paper II title gate: `01_task_folder/task_05/script/output/geometric_eth_theory_v14/theory_gate_v14.json`
- Paper II audit: `01_task_folder/task_05/script/output/geometric_eth_theory_v14/delivery_audit_v14.json`
- Combined manifest: `01_task_folder/task_05/script/output/two_paper_delivery_v14/two_paper_manifest_v14.json`

The combined manifest is the shortest integrity check. It binds the final documents to the two independent delivery audits and records the failed Paper II title gate as part of the release contract.

