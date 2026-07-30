# Phase 6 Local Campaign Implementation Plan

**Goal:** Complete the bounded L=32/64 sigma=1.75 pilot locally with
checkpointed sector cells and auditable crossing analysis.

## Constraints

- Fixed Gamma values: `1.555,1.560,1.565`.
- Direct chi 128 only; no staged base cells.
- ED remains limited to L<=12 and is not part of this campaign.
- Exact-zero pruning and HDF5 checkpoint gates must remain enabled.
- No cluster command or full production grid.

### Task 1: Local sector-cell command

- [ ] Add a sector-selectable direct cell command.
- [ ] Write a failing L=4 CLI test.
- [ ] Preserve complete convergence, observable, checkpoint, fit, MPO, and
  code provenance.
- [ ] Verify even and odd resume independently.

### Task 2: Campaign ledger and collector

- [ ] Enumerate the exact eight sector cells.
- [ ] Import the compatible completed L=32, Gamma=1.560 checkpoint records.
- [ ] Run missing cells serially and update the ledger atomically.
- [ ] Collect R_xi curves, gaps, timings, and memory records.

### Task 3: Analysis and feasibility

- [ ] Apply fixed neighboring-point crossing interpolation when bracketed.
- [ ] Write CSV/JSON summaries and plots.
- [ ] Estimate L=128 runtime and memory from measured scaling.
- [ ] Run focused tests, full tests, and diff hygiene.
