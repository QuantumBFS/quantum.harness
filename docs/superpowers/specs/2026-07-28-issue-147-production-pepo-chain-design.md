# Issue 147 Production PEPO Chain Design

## Context

Challenge #147 already has a tested finite-PEPO representation, a palindromic
second-order Trotter schedule, boundary-MPS thermodynamic contractions, and a
JAX variational compressor with ordinary and thermodynamic objectives. The
missing vertical slice is a resumable 10x10 evolution chain that turns those
components into comparable thermodynamic curves.

The queued 4x4 symmetry-resolved ED job is an independent calibration. This
design can be implemented and tested while that job waits; it does not treat a
scheduler state as scientific evidence.

## Goal

Build one production-ready comparison at `h=3.0` and `D=4`:

- evolve matched ordinary and thermodynamic PEPO chains from beta 0 to 1;
- checkpoint every `delta_beta=0.025` step and resume without rewriting an
  accepted point;
- separate evolution from measurement so measurement `chi` can change without
  repeating optimization;
- measure both chains at `chi=16` and `chi=32` under identical settings; and
- produce auditable dense-grid thermodynamic data and a ten-point public table.

Supporting all three fields and all three bond dimensions is deliberately out
of scope for this slice. The configuration and command interfaces must remain
parameterized so the later 3x3 grid is a dispatch change, not a redesign.

## Physical Setup

The target is the 10x10 open-boundary transverse-field Ising model in the Pauli
operator convention,

```text
H = -J sum_<ij> Z_i Z_j - h sum_i X_i,
J = 1, h = 3.0.
```

The represented thermal operator is `R(beta) = exp(-beta H)`. Evolution starts
from the identity at beta 0 and uses the existing palindromic second-order
Trotter schedule with `delta_beta=0.025`. Every accepted step is retained;
published output points are beta 0.1 through 1.0 in increments of 0.1.

The production student bond dimension is fixed at `D=4`. A full Trotter step is
applied to a copy of the previous student with a temporary teacher bond cap
`D^2=16`, after which the teacher is globally compressed back to `D=4`.

## Matched Compression Modes

The two chains differ only in their loss terms.

- `ordinary`: normalized relative Frobenius loss.
- `thermodynamic`: the same Frobenius term plus scaled penalties for
  `z=log(Z)/N`, internal-energy density `u`, and Hermiticity.

The approved thermodynamic objective uses:

```text
epsilon_z = 1e-5
epsilon_u = 1e-4
contraction_noise = 1e-7
lambda_z = lambda_u = lambda_hermiticity = 1
```

Both modes use the same identity initialization, Trotter gate order, teacher
cap, student seed procedure, boundary contraction `chi=16`, contraction cutoff,
L-BFGS-B optimizer, and maximum of 50 iterations per step. Actual iteration
counts and optimizer stop reasons are recorded. Each mode advances from its own
previous accepted PEPO, so the trajectories may diverge while the computational
contract remains matched.

The boundary contraction cutoff is `1e-10`, and the optimizer convergence
tolerance is `1e-8` in both modes.

No QMC, ED, or externally supplied thermodynamic value may enter either loss.

## Components

### Checkpoint codec

`qh147/checkpoint.py` serializes a `FinitePEPO` without pickle. Tensor arrays are
stored in NPZ under a deterministic site ordering. JSON metadata records lattice
shape, beta, mode, accumulated log scale, tensor indices and tags, diagnostics,
configuration hash, Git commit, package versions, and the NPZ SHA-256.

A checkpoint directory has the form:

```text
<run>/<mode>/checkpoints/beta-0.025000/
  tensors.npz
  metadata.json
```

`metadata.json` is written last with an atomic file replacement and is the
completion marker. A missing marker, malformed metadata, configuration mismatch,
or tensor hash mismatch makes that directory ineligible for resume. Successful
checkpoint files are immutable.

### Evolution state machine

`qh147/evolve.py` owns `ChainConfig`, latest-checkpoint discovery, one-step
evolution, validation, and progress records. It restores the latest complete
checkpoint or constructs the identity PEPO, then repeats:

1. copy the accepted student;
2. apply one complete second-order Trotter step with teacher cap 16;
3. seed and optimize a fixed-`D=4` student in the selected mode;
4. renormalize tensors and accumulate the removed log scale;
5. validate the candidate; and
6. commit the checkpoint and update the run manifest.

Every step prints one flushed JSON progress line containing mode, beta,
iteration count, wall time, peak memory, loss components, maximum bond, and
Hermiticity residual.

### Measurement pass

`qh147/measure.py` never mutates a checkpoint. It contracts all 40 accepted
checkpoints independently at `chi=16` and `chi=32`, recording `z`, free-energy
density `f=-z/beta`, internal-energy density `u`, Hermiticity residual, and
contraction settings.

Specific heat is reconstructed as `C=-beta^2 du/dbeta` from the dense 0.025
grid using a local polynomial derivative, with one-sided endpoint treatment.
The dense measurements are preserved; a public table selects beta 0.1 through
1.0. Results for distinct mode and `chi` values live in distinct paths and may
not overwrite one another.

### Command entry point

`qh147/run.py` provides three modes:

- `evolve`: run or resume one ordinary or thermodynamic chain;
- `measure`: read an existing chain at one requested measurement `chi`; and
- `dry-run`: validate the exact configuration and report step count, tensor
  shape estimates, checkpoint size estimate, and requested compute budget
  without constructing the 10x10 network.

The first production configuration fixes the parameters in this document while
retaining explicit command fields for `h`, `D`, evolution `chi`, measurement
`chi`, and paths. A canonical configuration hash prevents accidental resume
under changed physics or numerical settings.

## Acceptance and Failure Rules

A step is accepted only when:

- all reported losses and thermodynamic diagnostics are finite;
- final objective loss does not exceed its initial value by more than the
  absolute acceptance tolerance `1e-10`;
- every virtual bond is at most 4;
- the contracted partition function is positive; and
- the Hermiticity residual is at most `1e-6`.

On failure, the runner writes a failure record, leaves the previous successful
checkpoint untouched, and exits nonzero. It does not silently increase the
iteration budget, change `delta_beta`, change `chi`, or substitute a local loss.
Resubmission resumes from the last complete step under the same configuration.

## Testing

Focused tests cover:

- exact PEPO tensor/index/tag round trips through NPZ plus JSON;
- rejection of corrupt hashes, incomplete checkpoints, and configuration drift;
- deterministic resume without byte changes to prior checkpoints;
- failure injection proving that a rejected step is never resumable;
- matched ordinary and thermodynamic budget metadata;
- 2x2 one-step and short-chain values of `z`, `u`, `C`, and Hermiticity against
  dense `exp(-beta H)` results;
- local-polynomial derivatives against an analytic polynomial; and
- dry-run reporting of 40 steps, two modes, and estimated storage.

The complete solution test suite runs with warnings treated as errors. No 10x10
optimization runs locally. After implementation passes locally, SCNet receives
one 10x10, one-step timing probe; the measured wall time and peak memory determine
the later Slurm request before either 40-step chain is submitted.

## Completion Criteria

This slice is complete when:

1. all existing and new tests pass with warnings treated as errors;
2. both modes pass the 2x2 exact short-chain test under identical budgets;
3. interrupted runs resume from the latest accepted beta without rewriting it;
4. dense and public measurement artifacts are produced independently for
   `chi=16` and `chi=32`; and
5. the 10x10 dry run reports the ratified physical setup and resource estimate.

The queued ED result, a full 3x3 `(h,D)` scan, QMC comparison, and final challenge
report are later milestones rather than completion requirements for this slice.
