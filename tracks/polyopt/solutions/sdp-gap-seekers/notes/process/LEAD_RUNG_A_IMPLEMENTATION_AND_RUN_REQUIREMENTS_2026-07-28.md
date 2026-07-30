# Square J1-J2 Rung A implementation and run requirements

Date: 2026-07-28

Status at this revision: implementation and solver-free validation complete;
SCNet gamma-zero solve not yet submitted.

This note is the authoritative review/requirements handoff for the first
smaller-basis experiment. It supersedes any instruction to retry the
703-by-7 `one_symbol_lift/v1` model on a larger-memory node.

## 1. Fixed scientific setup

The Rung A experiment must keep all physical choices unchanged:

```text
model             = Square J1-J2 Heisenberg
Hamiltonian       = (1/4) sum_J1 (XX+YY+ZZ)
                  + (g/4) sum_J2 (XX+YY+ZZ)
J1 sign           = +1 antiferromagnetic
g=J2/J1           = 1/2
patch             = L=1 local-consistency window
outer / inner     = 9 / 1 sites
physical boundary = none
degree            = d=2
state class       = unrestricted
sector projection = none
stationarity      = bare_inner_pauli/v1
first threshold   = gamma=0
target            = feasibility only
```

Only the declared basis is reduced. A worker or future agent must not change
the Hamiltonian normalization, sign, coupling, patch, degree, state class, or
stationarity selector while calling the result "Rung A."

## 2. Versioned basis rule

The new selector is `bare_weight_one/v1`.

- Positive basis: identity and every one-site bare Pauli word on the nine
  outer sites, dimension `1 + 9*3 = 28`.
- Gap basis: identity and `X,Y,Z` on the actual inner-site ID, dimension `4`.
- There are no state-symbol rows and no symmetry quotient.
- The declared maximum degree remains part of the manifest hash even though
  the row set is constant once the degree reaches one.
- Both manifests are incomplete.

This is a literal row subset of `one_symbol_lift/v1` for both PSD roles.
Therefore its constraints are principal submatrices of the corresponding
larger-basis constraints. Removing rows enlarges the pseudo-moment feasible
set: a validated infeasibility result remains a sound exclusion candidate,
while feasibility remains only a finite-relaxation sanity result.

Pinned identities at `g=1/2`, `L=1`, `d=2`, `gamma=0`:

```text
positive basis SHA-256 =
  82566b1d19312b0bd2b2fe78a62b12289021ecf3304a8c95610db40dc223ecbe

gap basis SHA-256 =
  28f324d2b785f58928fc0cbcfa4ac71df0f168efad1120ff71b576ff9795d8c4

problem SHA-256 =
  0943a4f7c3786e927f71e5f122c5256ced291fed08f5ea1c884eb59f92f7f687

moment inventory SHA-256 =
  25ca49cbb527bd2d531469a26f9f5fcbd84d3d35c666fb27b8cb46819c544e5c

coefficient-map SHA-256 =
  16fca8dbad3e2cfd6a0c47bfa8e4c6fa9c39710caeb07ff974009e919edcb051

exact assembly SHA-256 =
  4ffed703ab3d84660bf03fd5bf7f524ec0bd697560f304b9cb5a08de863125a5
```

## 3. Implemented safeguards

The implementation adds a new family; it does not mutate the existing
`one_symbol_lift/v1` selector or its pinned hashes.

The solver-free builder is separate:

```text
scripts/build_square_rung_a_mof.jl
```

It is locked to `gamma=0` and records the extra builder source in the run
metadata. The generated run metadata explicitly states:

```text
positive family/dimension = bare_weight_one/v1, 28
gap family/dimension      = bare_weight_one/v1, 4
moments                   = 352
stationarity equalities   = 3
Hamiltonian terms         = 60
```

The solve runner now requires the caller to state the expected basis family
and both dimensions. `square_rung_a_smoke.sbatch` supplies
`bare_weight_one,28,4`; the pre-existing large-basis script supplies
`one_symbol_lift,703,7`. A stale or wrong bundle is rejected before MOF reload
or optimizer attachment.

The Rung A batch script has its own source path, run ID, and Slurm log names.
It cannot overwrite the prior Gate B bundle or large-basis run directories.

## 4. Completed solver-free validation

The complete Julia test suite passed:

```text
1429 passed
0 failed
```

New coverage includes:

- exact 28/4 dimensions and ordered manifest hashes;
- no state-symbol rows;
- gap rows contained in positive rows;
- both Rung A roles contained in the corresponding
  `one_symbol_lift/v1` roles;
- family/version rejection;
- degree-nesting behavior;
- exact problem, moment, coefficient-map, and assembly hashes;
- all 28-by-28 positive and 4-by-4 gap coefficient-map Hermiticity
  relations;
- optimizer-free JuMP cone dimensions and constraint count;
- explicit solve-launch family/dimension parsing.

A solver-free validation bundle was exported and independently reloaded:

```text
MOF variables                 = 352
constraints excluding varsets = 6
Hermitian PSD dimensions      = 28 and 4
MOF size                      = 60,006 bytes
MOF SHA-256                   =
  fda495a30aca5f662131331fc42c20a0a5fd0e8074a719659ba43be6b8aff84c
reload checks                 = passed
optimizer attached            = false
solver invoked                = false
```

All bundle, runmeta, and MOF checksum checks passed. The validation build was
made before the implementation commit, so its runmeta honestly lists the
changed source files as dirty. It is not the artifact to ship to SCNet. A
fresh final bundle must be generated after the implementation commit so the
source commit and file hashes describe the committed implementation.

## 5. SCNet launch requirements

The first solve uses:

```text
partition       = xhacnormalb
CPUs            = 4
memory          = 4 * 3800 MB = 15.2 GB
wall limit      = 10 minutes
Mosek threads   = 4
Mosek solve form= forced dual
```

This is deliberately conservative. The solver-free construction peaked near
626 MiB resident, the real PSD embeddings are only 56 and 8 dimensional, and
their total packed affine-conic row count is 1,632. There is no evidence that
this rung needs the 64-core/243.2-GB allocation used by the failed Rung C
jobs.

Required sequence:

1. Commit the implementation without staging the pre-existing `Ion.lock` or
   advisor-note changes.
2. Generate the final
   `results/square-rung-a-g0-20260728-r1` bundle from that commit.
3. Verify both the parent and point `SHA256SUMS` locally.
4. Push the code to the SCNet bare remote and fast-forward the SCNet working
   checkout.
5. Copy the ignored result bundle to the identical repository-relative path
   on SCNet and verify its parent and point checksums remotely.
6. Submit `scripts/square_rung_a_smoke.sbatch`.
7. Monitor through terminal Slurm state, not merely `RUNNING`.
8. Fetch the complete `results/square-rung-a-smoke-<jobid>` directory and
   verify its `SHA256SUMS` locally.
9. Record raw MOI/Mosek statuses, exit code, wall time, and peak RSS in a new
   Markdown result note.

## 6. Interpretation and stop gates

For `gamma=0`, the expected coherent outcome is a decisive feasible status.

- A feasible result confirms only that the tiny finite relaxation, MOF
  transport, Mosek bridge, and artifact path operate end to end.
- It is not a positive lower bound on the bulk gap.
- An infeasible result at `gamma=0` is scientifically suspicious and stops
  the threshold scan. Investigate formulation, sign, status, and residuals.
- An unknown, numerical-error, time-limit, or exception status also stops the
  scan.

Do not generate or submit a positive-gamma Rung A bundle until the gamma-zero
job is terminal, fetched, checksum-verified, and reviewed. If gamma zero is
coherently feasible, the next note should choose one modest positive gamma
and one deliberately high gamma before any bracketing.

No solver status from Rung A should be called "certified" without a decisive
raw status and, for infeasibility, an exported witness plus independent replay
under the common verifier or a stronger rigorous post-processing step.
