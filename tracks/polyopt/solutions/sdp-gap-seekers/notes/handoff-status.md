# Handoff — SDP spectral-gap work status (for companion-agent review)

> Single-page brief of what the assistant has produced for challenge #88
> (sdp-gap-seekers). Read this first, then drill into the artifacts it points to.
> Branch: `challenge/polyopt-sdp-gap` on `iintSjds/quantum.harness`.
> Companion reviewer: your job is to **check** the claims below; each has a
> stated confidence and a "how to verify" line.

## Artifacts (all in both `notes/` and the repo at `tracks/polyopt/solutions/sdp-gap-seekers/notes/`)

| file | what it is | git commit |
|---|---|---|
| `theory-problems-for-offloading.md` | the original problem brief (not mine — the questions) | `e9abe11` |
| `theory-problems-offloading-crosscheck.md` | my independent cross-check (Problems A/B/C) | `e9abe11`, updated `b9a8e68` |
| `verify_identities.py` | script machine-verifying the Problem B identities | `b9a8e68` |
| `certify_Heisenberg_square_gap_SPEC.md` | implementation spec for the square gap function | `41ad381` (v1), **`910eb94` (v2, current)** |

GitHub view: `https://github.com/iintSjds/quantum.harness/tree/challenge/polyopt-sdp-gap/tracks/polyopt/solutions/sdp-gap-seekers/notes`

## Claims, by confidence — and how to check each

### [VERIFIED — re-run the script] Problem B strengthening identities
- B1 bond: `(S⃗i·S⃗j)² = 3/16 − ½(S⃗i·S⃗j)`.
- B2 triangle: `(X₁₂+X₂₃+X₃₁)² = 9/16`.
- B3 shared-site: `{X_ij, X_ik} = ½ X_jk`.
- B4 plaquette Casimir minimal polynomial; commutator `[X₁₂,X₁₃] = i S⃗₁·(S⃗₂×S⃗₃)`.
- **Check:** `python3 verify_identities.py` — all residuals are exactly 0 on the
  full 2ⁿ Hilbert space; eigenvalue spectra match prediction. If any model run
  contradicts these, the model is wrong.

### [CONFIRMED by source] Flag / bisection semantics
- `flag==1` (OPTIMAL) ⇔ gap-SDP feasible ⇔ γ ≤ Γ_{L,d}.
- **Γ_{L,d} = sup{γ : flag==1} = certified UPPER bound on Δ_bulk**, ↘ Δ from
  above as (L,d) ↑. The method **cannot** prove gappedness (semi-decidable).
- **Check:** re-read SpectralGap `example/example.jl` (the `flag==1 ? lb=gamma :
  ub=gamma` loop) + the arXiv:2606.03836 abstract ("certified upper bounds",
  "semi-decidable"). The direction is no longer in doubt.

### [CONFIRMED by source] Orthogonality is encoded by symmetry sector, not literally
- Ground state S=0 singlet, first excitation S=1 triplet → automatically
  orthogonal; the unknown ground state is never represented.
- For the square Heisenberg the separator is **SU(2) spin** (Ising used Z₂,
  kagome used triangle permutation).
- **Check:** SpectralGap `certify_Heisenberg_kagome_gap` uses two `label` blocks;
  QMBCertify `get_basis(L, label, d; lattice="square")` realises the square
  version with `label=0`→S=0, `label∈{1,2,3}`→S=1.

### [CONFIRMED by source] The whole square stack already exists in QMBCertify
- `get_basis(lattice="square")` — per-sector basis, translation+D₄ reduced.
- `reduce4(...; lattice="square")` — the D₄+translation reducer (= Problem C).
- `add_SU2_equality!(...; lattice="square")` — the concrete SU(2) Casimir
  projection (= cross-check A.2).
- **Check:** re-read QMBCertify `src/basic_function.jl`. So the only genuinely
  new code for the gap function is the gap-SDP assembly (port from SpectralGap
  `src/sdp.jl`).

### [INFERENCE — rough] Scaling estimate
- Frontier ≈ L ≤ 4–6 at d=2; d=3 only at L ≤ 3. Order-of-magnitude only.
- **Check:** needs the actual moment-matrix block sizes from a real run; do not
  trust the numbers until measured.

## Things I am NOT sure about (good candidates for the reviewer to dig into)

1. **The QMBCertify label mapping for the gap matrix.** I assert `gpos` uses
   `get_basis(L, 1, d−1; lattice="square")` (one S=1 component). The kagome gap
   uses `label∈[1,2]` after sign reduction — confirm the square analog needs
   only one vector label, or whether momentum/sign reduction changes that.
2. **`gbasis`/bulk-basis split.** SpectralGap kagome couples a separate
   `gbasis` (bulk, d−1) into `gpos`. Whether the square gap needs the same split
   or a single d−1 basis suffices — unspecified by QMBCertify's energy SDP.
   Confirm against how `certify_Heisenberg_kagome_gap` consumes `gbasis`/`gpos`.
3. **Where the function should live.** I recommend inside QMBCertify (native
   `UInt16`/`slabel` convention); Jie Wang may prefer SpectralGap for repo
   consistency. Not my call.
4. **`slabel` dependence is a hard constraint.** QMBCertify's `reduce4`/`get_basis`
   rely on the spiral `slabel` site indexing; row-major will NOT interoperate. I
   flagged this in SPEC §3 — worth double-checking by tracing `reduce4` →
   `location`/`slabel`.

## Calibration anchor (resolves any remaining flag-direction doubt)

**Shastry–Sutherland g=0 has Δ_bulk = 1 exactly** (product of singlets). The g=0
run must recover Γ → 1; whichever side of 1 the finite-(L,d) value sits on
labels the OPTIMAL/INFEASIBLE flag for the rest of the week. (The other session
is running this on remote now.)

## Two errors I caught and fixed during this work (so the reviewer doesn't re-flag)

- **v1 SPEC had the SU(2) label convention backwards** (said label=1→S=0,
  copying SpectralGap kagome; QMBCertify is label=0→S=0). Fixed in v2 (§4 table).
- **L=2 is PBC-degenerate** (|plaq|=1, not 4) — my v1 validation ladder said
  "start at L=2"; corrected to L=3. Verified by enumeration in SPEC §3.
