# Phase 9 Recommended Execution Order

No physics calculation starts until
`docs/phase9-validation-design.md` is reviewed and approved.

1. **Implement the resumable Phase 9 planner and report schemas.**
   Test exact cell counts, fixed fields, fixed sizes, provenance fields, and
   stop conditions without running DMRG.

2. **Complete the nearest-neighbor validation.**
   Reuse Phase 4 ED fixtures; run both parity sectors at all 9 fixed-grid
   `(L,Gamma)` points, for 18 independently resumable states. Treat the resulting
   `z` as a modest-size scaling-pipeline check, not a precision reproduction.
   Record convergence flags without launching `chi=128`.

3. **Regenerate and validate both mean-field exponential representations.**
   Independently fit `sigma=2/3` and `sigma=0.4` with `K=24`, `alpha=0.5`,
   and `r_fit=2048`. Verify the periodized coupling at `L=16,32,64,96`
   before any mean-field DMRG state.

4. **Apply the sigma=0.4 MPO qualification gate.**
   The K=32 maximum finite-ring errors are 5.9999% at `L=64` and 7.0564% at
   `L=96`, above the approximate 1% gate. Do not run sigma=0.4 DMRG and
   document this branch as an MPO-limited validation.

5. **Run only the qualified sigma=2/3 fixed-field gap benchmark.**
   At external `Gamma_c=3.673`, finish even then odd at each increasing size
   `L=16 -> 32 -> 64 -> 96`. Use `K=24`, `chi=64`, and report `z` against
   `1/3`. Record convergence flags without launching `chi=128`; do not
   calculate `beta/nu` or `gamma/nu`. This calculation tests gap scaling,
   not the critical-field location.

5. **Assemble the second published critical-field benchmark without new
   DMRG.**
   Compare the accepted sigma=2.0 Phase 7 crossing
   `Gamma_x(32,64)=1.428411` with Table II `Gamma_c=1.4208(2)`, including the
   `0.025` crossing resolution and existing `chi=64 -> 128` stability. Label
   it a finite-size crossing comparison, not an exact reproduction.

6. **Generate the final validation report.**
   Combine NN, mean-field, two published critical fields, the completed
   sigma=1.75 field-sensitivity result, MPO/MPS uncertainty, and limitations.
   Keep the external published fields visibly separate from DMRG crossing
   estimates.

7. **Stop.**
   Review all convergence flags only after the complete baseline report.
   Any `chi=128` refinement requires separate approval at that point.
   Do not add `L=256`, a new sigma, `K=32`, a Gamma refinement, or a broader
   production campaign. Any unresolved required benchmark returns to review.
