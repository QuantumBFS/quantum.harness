# Exact GF(2) tensor-network route

This is a train-only, exact finite-field tensor-train route for OCCAM issue 71.
It consumes the frozen discovery manifests produced by the sibling
`symbolic_hybrid` route, computes exact GF(2) cut ranks, serializes explicit TT
cores, compiles them to challenge gates, and performs exhaustive full-domain
audits.

The Slurm entry point is `slurm_exact_tn.sh`.  It uses canonical seed 42 and
writes durable results under `results/occam71/routes/exact-tn-seed42`.
