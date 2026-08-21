# Issue #147 Batched Energy Contraction Design

## Failure

The 10x10 thermodynamic probe timed out before entering the JAX optimizer.
`thermodynamic_point` contracted the complete network once for every one of
180 bond terms and 100 field terms. Teacher and initial-student diagnostics
therefore required more than 500 full boundary contractions before the first
optimizer iteration.

## Change

Build the scalar trace network once and compute reusable Quimb plaquette
environments for horizontal and vertical nearest-neighbor patches. Evaluate
all bond and field insertions by contracting only the corresponding local
patch with its environment. Normalize every local numerator by the matching
local partition estimate before summing the Hamiltonian terms.

The global trace contraction remains the source of z = ln(Z)/N. The batched
local calculation is the source of u. Degenerate one-dimensional lattices use
the existing direct contraction path.

## Probe

Emit flushed JSON stage events around gate application, seed compression,
teacher thermodynamics, initial diagnostics, JAX optimization, validation, and
checkpoint writing. Use a separate probe configuration with one L-BFGS-B
iteration; its checkpoint is diagnostic and must not be resumed as the
50-iteration production chain.

The accepted probe remains the confirmed 10x10 open TFIM at h=3, D=4,
teacher bond 16, chi=16, and delta_beta=0.025, ending at beta=0.025.

## Verification

The batched energy must match dense contraction on 1x1 and 2x2 tests and
remain JAX differentiable. Existing contraction, compression, evolution, and
checkpoint tests must pass. On SCNet, success requires stage logs plus
`thermodynamic/checkpoints/beta-0.025000/metadata.json`; scheduler completion
alone is not evidence.
