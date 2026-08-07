# 2D chain status: BLOCKED by an upstream bug (morning arbiter item)

Found 2026-07-29 00:30 by the L=4 canary (job 22987815, exit path:
UndefVarError caught by the harness, error column of the cell row).

**Bug:** `QMBCertify.eigen_circmat` calls `resort(seig[i], ceig[i])` at
`basic_function.jl:316` and `:341`, but `resort` is defined NOWHERE in the
package — at the pinned commit be63c27 AND at upstream HEAD (checked
2026-07-29: only 0b152df and eb6ba99 follow the pin; neither touches it).
The square-lattice Gram assembly (`bound_gsp.jl:71ff`, the L² basis branch)
always reaches eigen_circmat, so EVERY `lattice="square"` GSB call fails —
including the package's own `examples/ground_state.jl` square examples.
The chain path never calls eigen_circmat, which is why all 1D cells work.
`resort` is not in NCTSSOS/utils.jl or TSSOS/utils.jl either (author's other
packages, checked via raw.githubusercontent).

**Prepared fix (NOT applied):** `resort_patch.jl` — an EXTERNAL monkey-patch
(`@eval QMBCertify ...`), method-lane only; the stock checkout stays
byte-identical (also now chmod a-w). Semantics: lexicographic sort of the
support list + merge of duplicate coefficients (the standard sort-merge the
author uses elsewhere; exact semantics validated by the canary gate: valid
lower bound vs the 4x4 torus E0/N = -0.7017802 + OPTIMAL status).

**Morning options (arbiter decides):**
1. Apply resort_patch.jl in the 2D sbatch scripts (method lane), rerun the
   canary; if the canary gate passes, release the chain. Every 2D row
   records the patch's sha256 in its provenance.
2. Report Targets 3/4 as blocked-by-upstream — an honest, self-contained
   finding ("the released package cannot run its own square-lattice
   example"), citing this file.
3. File the bug upstream (challenge author's repo) — compatible with both.
