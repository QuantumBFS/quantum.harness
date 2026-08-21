# Human Report Feasibility Revision Design

## Purpose

Refocus the reviewer-facing report on the feasibility of using DMRG to study
the long-range TFIM universality-class crossover.

## Approved changes

- Use the project title:
  **Feasibility Validation of Exploring Universality-Class Crossover in the
  Long-Range Transverse-Field Ising Model Using DMRG**.
- Delete Figure 5 because Table 4 already reports its numerical content.
- Merge the two MPS rows in Table 4 and report only the largest validated
  size, L=128, and the maximum observed gap shift, 4.53×10⁻⁷.
- Delete the finite-size correction-coordinate row because Sections 3.1–3.2
  already present that sensitivity.
- Add an evidence-based computational-feasibility discussion:
  all calculations were local on a 32 GB PC; observed memory use was normally
  below 16 GB; recorded conservative per-cell values were 1.3 GiB at chi=128
  and 2.66 GiB at chi=256; no individual campaign exceeded eight hours; and
  the complete sigma=1.8, L=16–128 gap campaign required 1.76 hours.
- Compare the local L=128 result with Shiratani–Todo's L=362 QMC calculation
  as evidence of headroom, not proof that DMRG already surpasses L=362.
