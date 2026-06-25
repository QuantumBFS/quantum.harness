// Quantum many-body model characterization & method tables
// Source data: .knowledge/{model-property-checklist, method-property-map, method-survey}.md

#set page(
  paper: "a4",
  margin: (x: 1.5cm, y: 1.7cm),
  numbering: "1",
  footer: context [
    #set text(size: 7.5pt, fill: gray.darken(20%))
    QMB model characterization & methods · generated 2026-06-24
    #h(1fr) #counter(page).display("1 / 1", both: true)
  ],
)
#set text(font: "New Computer Modern", size: 10pt, lang: "en")
#set par(justify: true, leading: 0.6em)
#show heading.where(level: 1): set text(size: 14pt, fill: rgb("#1f3b5c"))
#show heading.where(level: 2): set text(size: 11.5pt, fill: rgb("#1f3b5c"))
#set heading(numbering: "1.")

// --- palette & table helpers -------------------------------------------------
#let ink = rgb("#1f3b5c")
#let bandcol = rgb("#d7e3f0")
#let H(body) = table.cell(fill: ink)[#text(fill: white, weight: "bold", size: 8.5pt)[#body]]
#let band(n, body) = table.cell(colspan: n, fill: bandcol)[#text(weight: "bold", size: 9pt)[#body]]
#let tbl(..args) = [
  #set text(size: 8.4pt)
  #set par(justify: false, leading: 0.5em)
  #table(
    stroke: 0.4pt + rgb("#b9c4d2"),
    inset: (x: 5pt, y: 4pt),
    align: left + top,
    ..args,
  )
]

// --- title -------------------------------------------------------------------
#align(center)[
  #text(size: 19pt, weight: "bold", fill: ink)[Quantum Many-Body Models:\ Characterization & Method Selection]
  #v(2pt)
  #text(size: 10.5pt, fill: gray.darken(30%))[A property checklist and the methods it gates — complexity, applicability, tasks]
]
#v(6pt)

This report characterizes a quantum many-body lattice model by *16 property axes*
(A1–D16) and maps those axes to the numerical methods they enable or block,
including algorithmic complexity expressed in the same property metrics. Companion
sources: `model-property-checklist.md`, `method-property-map.md`, `method-survey.md`.
Complexity exponents were web-verified (2026-06) against the primary literature.

#block(
  fill: rgb("#f4f7fa"), inset: 7pt, radius: 3pt, width: 100%,
  [
    #set text(size: 8.3pt)
    *Cost symbols.*
    $N$ sites/orbitals ·
    $d$ local dim ·
    $D_H = d^N$ Hilbert dim ·
    $D_"blk"$ largest symmetry block ·
    $chi$ MPS bond ·
    $D$ PEPS bond ·
    $chi_"env"$ environment bond ·
    $M$ Chebyshev moments ·
    $N_s$ samples ·
    $N_w$ walkers ·
    $beta$ inverse temp ·
    $N_tau = beta\/Delta tau$ ·
    $tau_"ac"$ autocorr. time ·
    $z$ dyn. exponent ·
    $chevron.l s chevron.r$ avg. sign ·
    $n$ qubits ·
    $N_p$ params ·
    $N_c$ cluster size ·
    $D_c$ thermal bond.
  ],
)

= Model characterization — the 16 property axes

#tbl(
  columns: (1.05fr, 1.35fr, 1.7fr),
  table.header(H[Axis], H[Possible values], H[Why it matters (method gating)]),

  band(3, [A · Geometry & Hilbert space]),
  [*A1* Dimensionality & geometry], [1D / quasi-1D / 2D / 3D / ∞-D; lattice; coordination $Z$], [Master gate — sets entanglement scaling and fluctuation strength, hence the method family.],
  [*A2* Boundary conditions], [OBC / PBC / cylinder / torus / infinite], [Finite-size effects, cut entanglement, access to topological diagnostics.],
  [*A3* Statistics & local dim $d$], [spin / boson / fermion / hard-core / anyon; $d$], [Fermions/anyons → sign; $d$ sets the $d^N$ wall and per-site TN cost.],
  [*A4* Interaction range], [short-range / long-range ($1\/r^alpha$, Coulomb)], [Long-range can violate the area law; needs many-term MPOs.],

  band(3, [B · Phase & entanglement]),
  [*B5* Entanglement scaling], [area / area+log (1D crit.) / volume; TEE], [Decides TN feasibility via $chi gt.tilde e^S$; volume law breaks TN.],
  [*B6* Spectral gap], [gapped (finite $xi$) / gapless–critical], [Gapless inflates $chi$ and worsens finite-size scaling.],
  [*B7* Ground-state order type], [trivial / SSB / SPT / topological / spin liquid], [Sets degeneracy assumptions and diagnostics (order param, ES, MES+TEE).],
  [*B8* Frustration], [none / geometric / interaction / fermionic], [Triggers the QMC sign problem; inflates TN $chi$.],

  band(3, [C · Symmetry & solvability]),
  [*C9* Global / internal symmetry], [U(1) / SU(2) / $Z_2$ / particle-hole / TRS], [Block-diagonalizes $H$ — cheapest cost cut; PH → sign-free at half-filling.],
  [*C10* Spatial / lattice symmetry], [translation ($k$) / point group / inversion], [$tilde N times$ ED reduction; irrep labels for excited states.],
  [*C11* Integrability], [free-fermion / Bethe-ansatz / non-integrable], [Quadratic → $O(N^3)$ exact; analytic benchmarks; forbids thermalization.],
  [*C12* Sign problem], [sign-free / mild / severe], [Gates QMC: $chevron.l s chevron.r tilde e^(-beta N Delta f)$; generically NP-hard.],

  band(3, [D · Regime & complications]),
  [*D13* Computational regime], [ground state / finite-$T$ / real-time], [Real-time → $chi tilde e^t$; finite-$T$ → LTRG/METTS/QMC.],
  [*D14* Filling / doping], [commensurate / incommensurate–doped], [Doping breaks PH symmetry → turns on the fermion sign problem.],
  [*D15* Disorder / MBL], [clean / disordered; ergodic vs MBL], [$times$ realizations; MBL keeps excited-state area law (log-$t$ growth).],
  [*D16* Hermiticity], [Hermitian / non-Hermitian–open], [Non-Hermitian breaks the variational principle; needs density-matrix/trajectory methods.],
)

= Method family overview — "which method when"

#tbl(
  columns: (auto, auto, 1.25fr, 1.2fr, 1.3fr),
  table.header(H[Method], H[Dim], H[Reachable size], H[Regime], H[Hard blocker]),
  [ED], [any], [tiny ($d^N lt.tilde 10^8$)], [GS + full spectrum + dynamics], [Hilbert space $d^N$],
  [MPS / DMRG], [1D, quasi-2D], [large 1D / narrow cylinder], [GS, finite-$T$, dynamics], [1D area law ($chi$)],
  [PEPS], [2D], [moderate], [GS (finite-$T$ harder)], [\#P-hard contraction],
  [QMC], [any], [large], [GS + finite-$T$], [sign problem],
  [VMC / NQS], [any], [large], [GS (+dynamics)], [variational / ansatz bias],
  [MF / HF], [any], [unlimited], [baseline], [neglects correlation],
  [LTRG / XTRG], [1D/2D], [large], [finite-$T$ thermodynamics], [ground state / 3D],
  [MCRG], [any (classical)], [large near $T_c$], [critical exponents], [non-critical / GS],
  [Circuit sim], [—], [$n$ qubits ($2^n$ mem)], [variational circuits / VQE], [state-vector memory],
  [PolyOpt (SDP)], [1D/2D], [\~100 (1D) / 10×10 (2D)], [certified GS bounds], [3D / SDP blow-up],
  [DMFT], [high / ∞-D], [infinite (local)], [finite-$T$, Mott, dynamics], [neglects spatial corr.],
)

= Algorithmic complexity & its driving property

The driving-property column names the axis (A1–D16) that dominates the scaling —
e.g. ED is gated by symmetry (C9/C10), QMC by the sign problem (C12), tensor
networks by entanglement (B5).

#tbl(
  columns: (auto, 1.35fr, 1fr, 1.55fr),
  table.header(H[Method], H[Time (leading)], H[Memory], H[Driving property metric]),

  band(4, [Exact & classical Monte Carlo]),
  [ED — full], [$O(D_"blk"^3)$], [$O(D_"blk"^2)$], [A3 $d^N$, reduced by C9/C10],
  [ED — Lanczos], [$O(n_"it" N D_"blk")$], [$O(D_"blk")$], [C9/C10; B6 → $n_"it"$],
  [FTLM / TPQ], [$O(R n_"it" N D_"blk")$], [$O(D_"blk")$], [C9/C10; D13],
  [KPM], [$O(M R N_"nnz")$], [$O(D_H)$], [A4 sparsity; $M$ = resolution],
  [Classical MC (local)], [$O(N tau_"ac" N_s)$], [$O(N)$], [B6 → $tau_"ac" tilde L^z$ ($z approx 2$)],
  [Cluster MC], [$approx O(N N_s)$ near $T_c$], [$O(N)$], [B8 (breaks clusters)],
  [MCRG], [MC × RG steps], [$O(N)$], [B6],

  band(4, [Tensor networks]),
  [DMRG / MPS], [$O(N w d chi^3)$], [$O(d chi^2)$], [B5/B6/B8 → $chi$; A1 width → $e^(c W)$; C9 ↓],
  [iPEPS], [$O(chi_"env"^3 D^6)$ to $O(D^12)$], [$O(chi_"env"^2 D^4)$], [B5/B8 → $D$; full-update $O(D^10)$],
  [MERA], [$O(chi^7)$ to $O(chi^9)$], [$O(chi^4)$], [B6 criticality → $chi$],
  [TRG / HOTRG], [$O(chi^6)$ / $O(chi^(4d-1))$], [$O(chi^4)$ / $O(chi^(2d))$], [B6 → $chi$; A1 dim → exponent],
  [TEBD / TDVP], [$O(N w d chi(t)^3)$], [$O(d chi^2)$], [D13+B5 → $chi(t) tilde e^(S(t))$; A4 → $w$],
  [purification / METTS], [$O(N d^2 chi^3)$], [$O(d^2 chi^2)$], [D13; low-$T$ → $chi$],
  [LTRG / XTRG], [poly($d, D_c$) × ($beta\/tau$ or $log beta$)], [$O(D_c^2)$], [D13; low-$T$ → $D_c$; A1 (2D ok)],

  band(4, [Quantum Monte Carlo]),
  [SSE / worldline], [$O(N beta \/ chevron.l s chevron.r^2)$], [$O(N beta)$], [C12 $chevron.l s chevron.r$; B6 → updates],
  [DQMC], [$O(beta N^3 \/ chevron.l s chevron.r^2)$], [$O(N^2 N_tau)$], [C12 $chevron.l s chevron.r tilde e^(-beta N Delta f)$],
  [AFQMC / CPMC], [$O(N^3 N_w N_"step")$], [$O(N^2 N_w)$], [C12 (constraint bias)],
  [VMC / NQS], [$O(N_s c_"ev" + N_p^2)$], [$O(N_p)$], [ansatz quality (not C12)],
  [DMC / GFMC], [$O(N_w N_"proj" c_"step")$], [$O(N_w N)$], [C12 (fixed-node bias)],
  [DiagMC], [grows w/ diagram order], [—], [C12 + series convergence],

  band(4, [Embedding, perturbative, mean-field, circuit, certified]),
  [DMFT (+solver)], [loop × solver; cluster $tilde e^(N_c)$], [solver], [A1 $Z$; C12 (solver); $N_c$],
  [DMET], [solver on $2 N_"frag"$], [solver], [fragment size],
  [NRG], [$O(N_"kept"^3)$ / iter], [$O(N_"kept"^2)$], [A3 channels → $N_"kept"$],
  [fRG], [$tilde O(N_"patch"^3)$], [$O(N_"patch"^2)$], [coupling strength (truncation)],
  [CCSD / CCSD(T)], [$O(N^6)$ / $O(N^7)$], [$O(N^4)$], [B7 single-ref validity; $N$ orbitals],
  [GW / RPA / GF2], [$O(N^4)$ / $O(N^4)$ / $O(N^5)$], [$O(N^3)$], [weak coupling; $N$ orbitals],
  [HF / DFT], [$O(N^(3-4))$ / iter], [$O(N^2)$], [A1 $Z$ (accuracy; corr. $tilde 1\/Z$)],
  [Spin-wave (1/S)], [$O(m^3)$ × $k$-points], [$O(m^2)$], [B7 order required; A3 large-$S$],
  [Circuit — state-vector], [$O("gates" dot 2^n)$], [$O(2^n)$], [$n$],
  [Circuit — tensor network], [$O(exp("treewidth"))$], [varies], [B5 / depth → treewidth],
  [Circuit — stabilizer], [$O(n)$/gate, $O(n^2)$/meas.], [$O(n^2)$], [exp. in non-Clifford gates],
  [SDP / NCTSSOS], [high-poly in $O(N^k)$], [$O(N^(2k))$], [level $k$; C9 ↓; A1 dim],
)

= Property → method gate

#tbl(
  columns: (auto, 1.5fr, 1.5fr),
  table.header(H[Property value], H[Favors], H[Blocks / expensive]),
  [A1 = 1D], [MPS (near-exact), ED], [PEPS overkill],
  [A1 = 2D], [PEPS, sign-free QMC, DMRG cylinders], [DMRG $e^(c W)$ wall],
  [A1 = 3D / ∞-D], [QMC, (cluster-)DMFT (∞-D exact)], [DMRG / PEPS impractical],
  [A3 fermions], [AFQMC, DMRG (JW), DMFT], [QMC sign; TN parity bookkeeping],
  [A4 long-range], [TDVP, MPO $W^"II"$; ED], [TEBD; denser ED matrix],
  [B5 area law], [MPS, PEPS], [—],
  [B5 volume law], [ED (small), QMC (eq. finite-$T$), VMC], [tensor networks fail],
  [B6 gapless / critical], [MERA, MCRG, TN at large $chi$], [MF (false transitions)],
  [B7 topological order], [DMRG (MES protocol), ED on torus], [unique-GS methods alone],
  [B8 frustration], [DMRG, VMC/NQS, ED, PolyOpt], [QMC (sign blocked)],
  [C9 / C10 symmetry], [ED & DMRG (large speedup), smaller SDP], [—],
  [C11 integrable], [exact $O(N^3)$ / Bethe / TBA], [(numerics only validates)],
  [C12 sign-free], [QMC (exact at large size)], [—],
  [C12 sign-ful], [MPS / PEPS / VMC, PolyOpt bound], [QMC],
  [D13 finite-$T$], [LTRG/XTRG, thermal QMC, METTS, DMFT], [—],
  [D13 real-time], [TEBD/TDVP (short $t$), ED-Krylov], [QMC (dynamical sign)],
  [D16 non-Hermitian], [density-matrix / trajectory methods], [variational GS methods],
)

= Tasks → methods (and how cost scales)

#tbl(
  columns: (auto, 1.7fr, 1.2fr),
  table.header(H[Task], H[Methods (cheap → expensive, within reach)], H[Cost note]),
  [Ground-state energy], [integrable-exact ≪ MF ≪ DMRG(1D) / sign-free QMC / AFQMC / VMC ≪ iPEPS(2D) ≪ ED], [TN cost ← B5; QMC ← C12],
  [Full spectrum / level statistics], [ED (full) only], [$O(D_"blk"^3)$; needs C9/C10],
  [Few excited states / gap], [ED Lanczos, DMRG (targeted)], [per-state $approx$ GS cost],
  [Finite-$T$ thermodynamics], [classical/quantum MC, LTRG/XTRG, FTLM/TPQ, DMFT, purification/METTS], [low-$T$ raises $chi$ / sign],
  [Real-time dynamics], [ED-Krylov (small), TEBD/TDVP, t-VMC], [entanglement barrier; QMC blocked],
  [Spectral function $S(q,omega)$], [KPM, ED continued-fraction, DMFT, DQMC + anal. cont., TEBD+FT], [analytic continuation ill-posed],
  [Critical exponents / CFT data], [MCRG, TRG/TNR, MERA, finite-size scaling], [needs B6 criticality],
  [Order parameters / phase diagram], [MF, QMC, DMRG/iPEPS, VCA, DMFT], [accuracy vs method bias],
  [Entanglement entropy / spectrum], [DMRG/MPS (free), replica-trick QMC, ED], [SPT/topo diagnostics (B7)],
  [Topological order (TEE, degeneracy)], [DMRG (MES), ED on torus], [needs A2 torus/cylinder],
  [Rigorous energy bracket], [VMC (upper) + SDP/NCTSSOS (lower)], [two-sided; works in C12 sign-ful],
  [Spectra of correlated solids], [DMFT/CDMFT/DCA, GW+DMFT, NRG (impurity)], [momentum needs clusters],
)

#page(flipped: true)[
= Per-model worked examples — the checklist applied

Each column fills in the 16 axes for a canonical harness model; the bottom row
reads off the recommended method(s). Contrast the solvable cases (Heisenberg
chain, TFIM) with the hard frontiers (kagome, doped Hubbard).

#tbl(
  columns: (auto, 1fr, 1fr, 1fr, 1fr, 1fr),
  table.header(
    H[Axis], H[Heisenberg chain (1D, S=1/2)], H[Heisenberg kagome], H[Hubbard square (doped)], H[TFIM (1D)], H[Anderson impurity (symmetric)],
  ),
  band(6, [A · Geometry & Hilbert space]),
  [*A1* dim / geom], [1D chain, $Z=2$], [2D kagome, $Z=4$], [2D square, $Z=4$], [1D chain, $Z=2$], [0D impurity + bath],
  [*A2* boundary], [OBC / PBC], [cylinder / torus], [cylinder / torus], [any], [Wilson chain / finite bath],
  [*A3* stat. & $d$], [spin-1/2, $d=2$], [spin-1/2, $d=2$], [fermion, $d=4$], [spin-1/2, $d=2$], [fermion, $d=4$],
  [*A4* range], [NN], [NN], [NN ($t, t'$)], [NN], [impurity–bath hybridization],
  band(6, [B · Phase & entanglement]),
  [*B5* entanglement], [area+log ($c=1$)], [2D area law; TEE candidate], [2D area law], [area (+log at QCP, $c=1\/2$)], [low (impurity); bath area-law],
  [*B6* gap], [gapless], [contested (gapped vs gapless)], [metallic / pseudogap], [tunable; gapless at $Gamma=J$], [$T_K$ (exp. small)],
  [*B7* order], [algebraic, no SSB], [spin-liquid candidate], [competing stripe / SC / AFM], [$Z_2$ SSB ↔ paramagnet], [Kondo singlet / local moment],
  [*B8* frustration], [none], [geometric (strong)], [fermionic (doping)], [none], [none],
  band(6, [C · Symmetry & solvability]),
  [*C9* global sym], [SU(2)], [SU(2)], [U(1)×U(1), SU(2)], [$Z_2$], [U(1)+SU(2), PH],
  [*C10* spatial sym], [transl., inversion], [transl. + $C_(6v)$], [transl. + $C_(4v)$], [transl., inversion], [— (0D)],
  [*C11* integrability], [Bethe-ansatz], [non-integrable], [non-integrable], [free-fermion (JW)], [Bethe-ansatz (Kondo)],
  [*C12* sign problem], [sign-free (Marshall)], [sign problem], [sign problem (doped)], [sign-free], [sign-free],
  band(6, [D · Regime & complications]),
  [*D13* regime], [GS / any], [GS], [GS / finite-$T$], [any], [GS / finite-$T$ / dynamics],
  [*D14* filling], [— (spin)], [— (spin)], [doped (incommensurate)], [— (spin)], [half (symmetric)],
  [*D15* disorder], [clean], [clean], [clean], [clean], [clean],
  [*D16* hermiticity], [Hermitian], [Hermitian], [Hermitian], [Hermitian], [Hermitian],
  table.cell(fill: bandcol)[*→ Recommended*],
  table.cell(fill: rgb("#eef3f8"))[DMRG (trivial), Bethe-ansatz exact, ED; sign-free QMC],
  table.cell(fill: rgb("#eef3f8"))[DMRG cylinders + VMC/NQS + ED; PolyOpt bound; *QMC blocked*],
  table.cell(fill: rgb("#eef3f8"))[DMRG cylinders, AFQMC (constrained), VMC/NQS, DMET, cluster-DMFT],
  table.cell(fill: rgb("#eef3f8"))[exact Bogoliubov $O(N^3)$; DMRG/TEBD; sign-free QMC; ED],
  table.cell(fill: rgb("#eef3f8"))[NRG (gold standard), ED (finite bath), CT-QMC, DMRG (Wilson chain)],
)
]

#page(flipped: true)[
= Harness method skills

The harness's `method-*` skills, each a route-and-tool selector that hands off to
a tool skill under `skills/`. Scope (what it can solve), computed properties,
leading time complexity, and trade-offs.

#tbl(
  columns: (auto, 1.25fr, 1.2fr, 0.95fr, 1.55fr),
  table.header(H[Skill → tool], H[Scope / models (input)], H[Computes (properties)], H[Time complexity], H[Pros / cons]),
  [`/method-ed`\ → xdiag, quspin], [any finite cluster (spin/fermion/boson), all symmetry sectors; $N lt.tilde 40$–$50$ (spin-1/2)], [full spectrum, GS & excited states, gaps, level statistics, scars/ETH, $S(q,omega)$, finite-$T$ (FTLM/TPQ), entanglement], [full $O(D_"blk"^3)$; Lanczos $O(n_"it" N D_"blk")$], [+ exact, no sign problem, any model, all observables\ − exponential wall, finite cluster only],
  [`/method-mps`\ → mpskit, tenpy, itensors], [1D & quasi-1D (narrow cylinder); finite (DMRG/TEBD) & infinite (VUMPS/iDMRG/TDVP)], [GS energy, order params, correlations, gaps, entanglement spectrum, dynamics, finite-$T$], [$O(N w d chi^3)$; 2D cyl. $chi tilde e^(c W)$], [+ near-exact in 1D, area-law optimal, thermodynamic limit\ − 2D wall, volume-law fails],
  [`/method-peps`\ → pepskit], [2D quantum lattices (GS) + classical partition functions; iPEPS infinite; fermionic], [GS energy, order params, correlation length, free energy], [contraction $O(chi_"env"^3 D^6)$; full update $O(D^10)$], [+ native 2D area law, frustration OK, thermo. limit\ − \#P-hard contraction, steep $D$, dynamics hard],
  [`/method-qmc`\ → sse, cpmc-lab], [SSE: sign-free spin/boson finite-$T$. CPMC/AFQMC: single-band Hubbard GS (CPMC-Lab, pedagogical)], [finite-$T$ thermodynamics, structure factors, stiffness; fermion GS energy & correlations], [SSE $O(N beta)$; DQMC $O(beta N^3)$], [+ any dimension, large sizes, exact when sign-free\ − sign problem (frustration / doping / real-time)],
  [`/method-vmc`\ → netket, jax], [frustrated / 2D / sign-ful regimes; ansatz benchmarks, NQS training (needs `make install netket`)], [variational GS energy (upper bound), observables, some dynamics], [$O(N_s c_"ev" + N_p^2)$ per step], [+ no sign problem, frustration OK, expressive NQS\ − ansatz bias, non-convex, upper bound only],
  [`/method-mf`\ → Julia SCF (no tool skill)], [lattice fermions (HF/UHF), spin models (Weiss decoupling); any dimension], [order parameters, phase diagrams, mean-field bands], [$O(N^(3-4))$ / SCF iter], [+ fast baseline, any dimension, seeds correlated methods\ − no correlation/entanglement, fails in 1D & frustration],
  [`/method-ltrg`\ → itensors (from scratch)], [finite-$T$ thermodynamics of 1D/quasi-1D & 2D quantum lattices; sign-free in 2D], [free energy, internal energy, specific heat, susceptibility], [poly($d, D_c$) × ($beta\/tau$); XTRG $O(log beta)$], [+ finite-$T$ in 2D without sign problem, frustration OK\ − GS / 3D out, low-$T$ error accrues, no dynamics],
  [`/method-mcrg`\ → jax (from scratch)], [classical lattice spin models near criticality; any dimension; quenched-disorder variant], [critical exponents ($y_t, y_h → nu, beta, gamma$), RG flow / fixed point], [MC sampling × RG iterations], [+ direct exponents, large lattices (no critical slowing)\ − critical-point only, not GS / thermo observables],
  [`/method-qcs`\ → tensorcircuit-ng, jax], [parameterized circuits / VQE; differentiable circuit simulation; $H$ as dense / sparse / MPO], [circuit expectation values, VQE energy, gradients, performance profiles], [state-vector $O("gates" dot 2^n)$; TN $O(exp("tw"))$], [+ differentiable, GPU, MPS/TN backends for low entanglement\ − $2^n$ memory wall, classical simulation only],
  [`/method-polyopt`\ → qmbcertify, nctssos], [certified GS lower bounds (1D/2D Heisenberg via qmbcertify; any algebra via nctssos), Bell, state-polynomial], [rigorous energy lower bound, certified observable bounds], [SDP; moment matrix $O(N^k)$], [+ rigorous (complements VMC upper bound), no sign problem, symmetry-reducible\ − no wavefunction, 3D blows up, finite-size],
)

#v(6pt)
#line(length: 100%, stroke: 0.4pt + gray)
#text(size: 7.8pt, fill: gray.darken(20%))[
  *Provenance.* Axes A1–D16 from `model-property-checklist.md`; gating and
  complexity from `method-property-map.md` and `method-survey.md`. Exponents
  web-verified 2026-06 (Schollwöck 2011; Sandvik; Becca–Sorella; Troyer–Wiese;
  Xie et al. HOTRG; Wietek–Läuchli; Georges et al. DMFT; Aaronson–Gottesman;
  Navascués–Pironio–Acín / Wang et al. NCTSSOS). Key corrections folded in: HOTRG
  $O(chi^(4d-1))$; MF corrections $tilde 1\/Z$; ED frontier 48–50 sites.
]
]
