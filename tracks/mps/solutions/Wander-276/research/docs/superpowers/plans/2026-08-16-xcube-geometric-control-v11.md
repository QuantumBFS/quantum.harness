# X-Cube Geometric Control v11 Implementation Plan

**Goal:** Supply a commuting-projector/subsystem-code negative control for exact-degeneracy geometry without constructing the exponentially large Hilbert space.

**Registered model:** Periodic X-cube stabilizer code on an `L x L x L` cubic lattice with qubits on edges.  Opened sizes are `L = 2, 3, 4, 5`; `L = 6` is prospective.  Binary symplectic algebra must reproduce `log2(D) = 6L - 3`.

**Two deformation classes:** Positive coefficient reweighting leaves every stabilizer eigenspace and the ground projector fixed, so the quantum metric and Berry curvature vanish exactly.  A local two-parameter unitary transport uses `G = X_e/2` and `K = (i X_e S_v)/2`, where `S_v` is a neighboring Z-type vertex-plane stabilizer.  It preserves the full spectrum and gap while giving scalar code-space curvature `F = -I/2`, hence deterministic rather than random geometry.

- [ ] Generate the full binary-symplectic stabilizer table and verify mutual commutation.
- [ ] Verify rank `3L^3 - (6L - 3)` and degeneracy `2^(6L-3)` at every opened size.
- [ ] Certify exactly zero geometry for coefficient-only reweighting.
- [ ] Certify local support, exact isospectral transport, and scalar transported curvature algebraically and against a dense toy code.
- [ ] Produce machine-readable JSON/NPZ summaries without allocating the encoded Hilbert space.
- [ ] Register the result as a structured negative control in cross-model inference.
