# RECON — QMBCertify dual-extension seam (M0-A / M0-B)

QMBCertify commit: `be63c27ece7322effe6d95c69ce6c3c5d8d92c14` (dev checkout,
`.external/QMBCertify`, unmodified). All line refs are into
`src/bound_gsp.jl` at that commit and were read, not guessed.

## M0-A — reviewed structures, verbatim

| structure | ref | verbatim |
|---|---|---|
| coefficient vector | `:230` | `cons = [AffExpr(0) for i=1:length(tsupp)]` |
| main Gram PSD vars | `:240` `:250` `:252` | `gram[i][…] = @variable(model, [1:…,1:…], PSD)` |
| lso multiplier vars | `:380` `:394` | `fr = @variable(model)` (free, one per generated ⟨[H,m]⟩=0 word family) |
| pso Gram (sGram) vars | `:428-430` `:477` | `sgram[i][l] = @variable(model, …, PSD)` / `pos[l,u] = …` |
| rdm PSD blocks | `:536-542` → `rdm_positivity.jl` | `posepsd8!/9!/10!(model, cons, tsupp, L…)` — U(1) blocks C(k,j) |
| bound variable | `:548` | `obj = @variable(model, lower)` |
| objective | `:568` | `@objective(model, Max, obj)` |
| H subtraction | `:569-576` | `cons[Locb] -= coe[i]` per Hamiltonian word |
| λ at identity word | `:578` | `cons[1] += lower` |
| coefficient-matching equalities | `:579` | `@constraint(model, con, cons==zeros(length(tsupp)))` |
| moment recovery | `:601` | `mvar = -dual(con) # extract moments` |

Reading: GSB assembles the **SOHS/dual side** — maximize `lower` subject to
the word-by-word identity Σ(Gram/multiplier contributions) − h_w +
lower·δ_{w,∅} = 0 over `tsupp`; the primal moments are the negated duals of
`con`. Confirmed (correction 1 of Plan v2).

## M0-B — seam inventory

1. **Coefficient basis + monomial index map**: `tsupp` (sorted canonical
   Pauli words, built ~`:14-…`), lookup `bfind(tsupp, word)`; canonical form
   via `reduce!`/`reduce4` (translation + mirror + Pauli algebra).
2. **Coefficient-matching constraints**: the single vector equality at
   `:579`; per-word slots are `cons[Locb]`.
3. **Gram maps**: contributions enter `cons` via
   `add_to_expression!(cons[Locb], coeff, gramvar)` (`:241-270` main family;
   DFT/translation factors `cos(2πr(l−1)/L)` at `:270`).
4. **Hamiltonian coefficient vector**: `supp`/`coe` subtracted at `:569-576`.
5. **THE INSERTION POINT** for the tower is **between `:578` and `:579`** —
   after λ enters `cons[1]`, before `con` is posted. Everything the tower
   adds is:
   - **tower-link multipliers** μ: one free `@variable` per tower equality
     row (the equalities `A_y·y + A_ω·vec(ω) = b` of the primal tower);
   - **y-side adjoint (B*, T* on the physical layer)**: for each tsupp word
     w appearing in ρ₂/ρ₃ (1–3-site contiguous Pauli words),
     `add_to_expression!(cons[bfind(tsupp,w)], (A_yᵀμ)_w)` — coefficients
     code-generated from the W/B tensors, never hand-written;
   - **new PSD dual blocks**: for each tower level M, the μ-affine matrix
     `Z_M := −mat((A_ωᵀμ)|_M)` posted `⪰ 0` via `@constraint(model, Z_M in
     PSDCone())` (sign fixed in THEOREM_CONTRACT §4);
   - **normalization/objective**: unchanged — tower equalities are
     homogeneous in the tower variables; any inhomogeneous row (e.g. trace
     normalization already carried by `cons[1]`) contributes `b·μ` to the
     objective; the generator must emit that term rather than assume b = 0.
6. **Supported envelope of the fork**: `lattice="chain"`, `correlation=false`,
   `energy=[]`, `SU2_symmetry=false`, `writetofile=false`; rdm ∈ {false,8,10},
   pso ∈ {0,3}, lso ∈ {true,false}. The fork throws outside this envelope.
   The M0-C regression gate validates exactly this envelope at N=10/14.

## Internal helpers the fork must qualify (call counts in GSB)

`bfind`(36) `reduce!`(17) `slabel`(16) `update!`(4) `reduce4`(3)
`filter_mons`(3) `posepsd8!/9!/10!`(3) `get_basis`(1); exported: `mosek_para`,
`qmb_data`. Fork binds them as `const bfind = QMBCertify.bfind` etc.

## Patch discipline

One fork function `GSB_cg(…; tower=nothing)` in `cg_hybrid/gsb_cg.jl`,
committed as an auditable file; `tower=nothing` must be behaviorally
identical to stock GSB on the supported envelope (M0-C gate: |ΔE| ≤ 1e-8 at
N=10/14 × {CONFIG A, rdm=8}). Stock GSB and every Track-1 row untouched.

## Scheduling note (timing hygiene)

M0-C's four regression cells (two of them ~34-min CONFIG A constructions)
run Wednesday morning, NOT tonight — the Track-1 queue owns the machine and
its solve_s timings must stay clean.
