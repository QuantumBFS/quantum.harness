# THEORY CONTRACT — DIRECT-CG MVP (FINAL CUT scope; size ruling 15:50)

2026-07-30. Model: periodic spin-1/2 Heisenberg chain, J2=0. PRIMARY SIZE
N=10 (arbiter ruling after the G0 finding that the N=8 partition is
DEGENERATE: closure(G_r=2) refills every separation on the 8-ring, so
|W_D| = 0 and A ≡ B). N=8 is retained as the degenerate-boundary control
row. At N=10: |W_full| = 527, |W_R| = 472, |W_D| = 55. All
quotient operations are QMBCertify reduce! at be63c27 (translation, mirror,
S3, sign). Dual/SOHS side throughout (GSB convention); "variable" below
means a canonical moment class y_w (fine) or a coarse coordinate x_k.

## 1. Gram-induced partition (PATCH §1; allowlist = only source of truth)

G_retained := the reach-r(8)=2 Gram word basis of the stripped chassis
(d=4, rdm=false, pso=0, lso=false, three_type=[1,1]). Reach GENERATES the
candidates; the frozen allowlist emitted to BASIS_PARTITION.json (with
sha256) is the source of truth thereafter.

  W_R = closure(G_retained) ∪ {objective word} ∪ admitted interface words
  W_D = W_full \ W_R,   W_full = the r=N/2=4 comparator basis.

Deletion = the words of W_D are never generated (word-generation-time
truncation). No Gram entry is ever zeroed.

## 2. Variables per arm

  A FullFine      : y_full (r=4 basis)                      — comparator
  B RetainedCore  : y_retained only
  C DirectCG      : y_retained ⊕ x_coarse
  D DirectCG+B    : y_retained ⊕ x_coarse ⊕ z_bundle
                    (FIXED_CORRECTION_BUNDLE_NO_SELECTION)

Machine assertions (G1): for C, created_words ∩ W_D = ∅,
deleted_variables = 0, deleted_rows = 0 (equivalently seam_newwords = 0
and post-extension tsupp ≡ W_R). For D, created_words ∩ W_D = W_bundle
exactly; unexpected_deleted_words = 0; no closure expansion outside the
declared bundle registry.

## 3. Coarse representation (one level, D=2 dual parity)

Map: the persisted 2-site VUMPS pair As = (A_odd, A_even), D=2
(cg_hybrid/vumps_A_D2.json). Machine certificate (G-map, recomputed at
load; a VUMPS energy or trap-avoidance is NOT the certificate):
  (i) per-parity isometry  ‖Σ_μ A†μ Aμ − I‖ ≤ 1e-10 (CP/normalization);
  (ii) dual-parity flow identity compat_residual(As) ≤ 1e-12
       (W_{k+1}^{(q)} = right-extension of W_k^{(q)} — the B2C1T3 = T3'C2
       echo, both parities, k ≤ 4).

Coarse variables: for each window parity p ∈ {1,2}, x^p = real Hermitian
coordinates (hermbasis) of the compressed 4-site window block
Ω_4^p = C_p ρ_4 C_p† with C_p built from chainmap2(As,2,p+1) — dω = 16,
real embedding ≤ 32-dim. Constraint Γ_coarse(x) ⪰ 0 = real-embedded
Ω_4^p ⪰ 0, two blocks.

## 4. Link family (minimal, T2-type only)

For each parity p, the two boundary compressions of the 4-site window onto
3-site marginals give exact linear identities

  B · y_retained = T · x_coarse

where the y-side coefficients live on 3-site window words (rho3_groups —
window-anchored canonical classes) and the x-side on hermbasis coordinates
of Ω_4^p. VALIDITY: each row is a CP-map/partial-trace identity that holds
for the moments of ANY global state (the map enters only as a fixed linear
compression); therefore appending these rows plus Γ_coarse ⪰ 0 to the
retained relaxation preserves the lower-bound property. No deeper level,
no T3 family, no ω tower ladder is constructed.

INTERFACE ADMISSION (P0 rule): every y-word appearing in a link row must
lie in W_R (checked by bfind against the frozen allowlist; logged in
COARSE_INTERFACE_AUDIT.csv). A coarse operator whose fine pullback leaves
W_R is REJECTED — deleted moments are never reintroduced to support the
coarse layer.

## 5. Objective exactness (G2)

The Hamiltonian objective is the single canonical class canon([1,4]) with
coefficient 3/4 (SU(2)-collapsed bond term). Machine check: the class is
present in W_R and carried with the exact coefficient; missing ⇒ blocking.

## 6. Bundle exception (arm D only)

W_bundle := closure(B_half at N=8, s=4) ∪ {Γ-product classes of the O-row
block that fall outside W_R}, entering ONLY through the retained-Gram
mechanism (gamma2_block real embedding). z_bundle are correction
variables, not a restoration of the deleted pool; the assertion in §2
pins created_words_D ∩ W_D = W_bundle exactly.

## 7. Soundness gates (G0–G5, all must pass before any arm solves)

  G0 partition + hashes emitted (BASIS_PARTITION.json, allowlist sha256)
  G1 deleted-object-zero assertions (machine, per §2)
  G2 exact objective (per §5)
  G3 ED feasibility at N=8: coarse blocks Ω_4^p(y_ED) ⪰ 0; link residuals
     ≤ 1e-10 row-by-row; retained-Gram witness (mandatory O-row Γ at y_ED)
     ⪰ 0; lower-bound ceiling L ≤ E_ED/8 + 5e-7 on every accepted solve
  G4 targeted mutation (sign-flip one link coefficient) turns the gate red
  G5 structural cost: C_DirectCG < C_FullFine at N=8 (preferred ≤ 0.7×),
     recorded with realized wall/RSS beside it (success axes split; an N=8
     structural failure is reportable, not fatal to the architecture axis)

## 8. Stop laws (verbatim adopted)

Deleted objects materialized · inexact objective · coarse pullback needs a
deleted moment · ED infeasibility · mutation not red ⇒ STOP, preserve
evidence. No additive-tower fallback.
