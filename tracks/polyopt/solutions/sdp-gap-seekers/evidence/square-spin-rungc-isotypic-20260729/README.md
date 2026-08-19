# Square Rung C full-spin-isotypic evidence

Source branch: `experiment/square-spin-isotypic-scnet2`

- model-builder/solver commit: `e7c83b22b0930daf88e277bdd10369a038429a63`
- exact-witness runner commit: `7064ad0211330559d32a74cade4bdac65e7523a5`
- gamma-zero job: `118171007`
- gamma-two job: `118171150`
- exact rational replay job: `118171424`

This compact bundle preserves run metadata, solver results and logs, build
resource reports, the exact rational replay, and the 3,250-coordinate rational
witness. The generated MOFs and exported floating-point value tables are
omitted from Git, but their hashes are bound by the preserved metadata:

| Artifact | SHA-256 |
|---|---|
| gamma-zero MOF | `847ab1e7bbcee5476f2f8f01eb2ade3283094a3f733dcf37d0c25bdf73b9d84c` |
| gamma-zero floating values | `7dbddd8edca306847760255fa90d0a15fe0391470071e8f4bb8bb4c7d4f9f687` |
| gamma-two MOF | `3310ea7c41b857223fe001e6bb3f9a64c75f187a33788585accbb10091055e68` |
| gamma-two floating values | `5b4a9c8b93fc51d0033997e82404809b09136f0804ae3d987f48d2bcae3a43e2` |

The exact replay rebuilds the gamma-two assembly from source and proves all
nine rational PSD matrices strictly positive by exact no-pivot LDL.
