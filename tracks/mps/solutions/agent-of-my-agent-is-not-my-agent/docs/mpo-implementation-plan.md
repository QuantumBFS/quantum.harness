# Periodized Exponential MPO Implementation Plan

**Goal:** Build and coefficient-validate the custom finite TeNPy MPOGraph.

**Architecture:** `lrtfim.mpo` owns graph/MPO construction. Tests inspect
channel labels and contract small MPOs to dense matrices for independent
Pauli-coefficient reconstruction.

**Tech Stack:** Python 3.11, NumPy, TeNPy 1.1.0, pytest.

## Global constraints

- Use Pauli `Sigmax` and `Sigmaz`.
- Represent periodicity inside a finite OBC MPO.
- Use two graph states per exponential and no inverse lambda.
- Do not invoke DMRG or construct an MPS.

## Task 1: Graph construction

- [ ] Add failing tests for direct/wrapped edge conventions, field operator,
      input validation, and bond dimension `2K+2`.
- [ ] Confirm failure because `lrtfim.mpo` is absent.
- [ ] Implement `build_periodized_mpo_graph` and `build_periodized_mpo`.
- [ ] Run focused tests and the complete suite.

## Task 2: Coefficient reconstruction

- [ ] Add a failing small-L test that contracts the MPO and projects every
      `Sigmaz_i Sigmaz_j` and `Sigmax_i` coefficient.
- [ ] Compare reconstructed couplings with
      `periodized_exponential_couplings`.
- [ ] Report maximum relative error and verify it is near machine precision.
- [ ] Update methodology and run the final scope audit.
