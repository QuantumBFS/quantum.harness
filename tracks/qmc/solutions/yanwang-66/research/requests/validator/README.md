# Development validator requests

`dev-matrix-v1.json` is generated on SCNet only after the core, oracle, pilot,
exact-replay validator, discovery contract, and dev-family contract gates pass.
It contains 16 public cells: four frozen workloads crossed with `none`,
`immediate`, `periodic(d)`, and `threshold(0.05)`.

The matrix is a development scoring input. It is not a holdout, does not consume
the one permitted holdout query, and cannot authorize a scientific claim.
