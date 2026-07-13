# Zamolodchikov–Fateev spin-1 chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = \sum_{i=1}^{N}\Big[\, \mathbf{S}_i\cdot\mathbf{S}_{i+1} \;-\; (\mathbf{S}_i\cdot\mathbf{S}_{i+1})^2 \,\Big], \qquad \text{PBC } (\mathbf{S}_{N+1}\equiv\mathbf{S}_1) $$

Conventions: **spin-1** operators (`S=1`, `\mathbf{S}^2 = 2`), coupling unit `1`, nearest-neighbour bonds counted once, `N` even. This is the isotropic bilinear–biquadratic chain `H = \sum[\cos\theta\,(\mathbf{S}_i\cdot\mathbf{S}_{i+1}) + \sin\theta\,(\mathbf{S}_i\cdot\mathbf{S}_{i+1})^2]` at the **integrable point** `θ = -π/4` (equivalently `β = -1` in `H = \sum[(\mathbf{S}_i\cdot\mathbf{S}_{i+1}) + β(\mathbf{S}_i\cdot\mathbf{S}_{i+1})^2]`), up to an overall positive rescaling and additive constant. See `.knowledge/conventions.md`.

No model-zoo sibling under `.knowledge/models/` for this exact point; the physics card `.knowledge/models/spin-1-xxz` covers the Haldane-phase spin-1 chain, a *different* (gapped, non-integrable-generic) region of the same bilinear–biquadratic family.

## Model identification (read this first)

The slug names Zamolodchikov & Fateev, whose 1980 paper "Model factorized S-matrix and an integrable Heisenberg chain with spin 1" [@ZamolodchikovFateev1980] constructed the **isotropic** (SU(2)-symmetric) integrable spin-1 chain via a factorized S-matrix. That Hamiltonian is exactly the one above — the `β = -1` bilinear–biquadratic point — and it is the **same** model later solved by the algebraic/nested Bethe ansatz of Takhtajan [@Takhtajan1982] and Babujian [@Babujian1982; @Babujian1983]. So on the isotropic line **ZF ≡ Takhtajan–Babujian (TB)**: one Hamiltonian, two independent constructions (S-matrix vs. Bethe ansatz). This card covers that isotropic model — the Hamiltonian written above, which is the one whose finite-`L` ED number is pinned below.

Honest naming caveat: there is also a genuinely **distinct** anisotropic generalisation — the **spin-1 XXZ / higher-spin XXZ** chain (a `Δ`-deformed, `q`-deformed relative of the above), sometimes also associated with Fateev–Zamolodchikov. That model carries an anisotropy parameter, is generally gapped/off-critical, and is **not** the Hamiltonian of this card. Where the spec slug blurs "ZF (anisotropic spin-1)" with "TB (isotropic `β=-1`)", we take the **isotropic** Hamiltonian as primary because it is the model ZF (1980) actually solves and the one written above; the anisotropic spin-1 XXZ is out of scope here.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter): the spin-1 R-matrix obtained by fusion of two spin-½ (six-vertex) R-matrices satisfies the Yang–Baxter equation, making this chain integrable; the transfer matrix generates a commuting family and the spectrum follows from a nested/higher-spin Bethe ansatz [@ZamolodchikovFateev1980; @Takhtajan1982; @Babujian1983]. The model is **gapless and critical**: its low-energy theory is the `SU(2)_2` Wess–Zumino–Witten conformal field theory, central charge `c = 3S/(S+1) = 3/2` at `S=1`; elementary excitations are a gapless spin-½ spinon doublet. **Not exact in closed form (Tier B):** as with the other integrable chains in this catalog, the full spectrum and dynamical/finite-`T` quantities require solving the Bethe equations state-by-state or the TBA — integrable but not single closed forms; correlation functions need heavier machinery. Out of this card's scope.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The exact statements are the integrability/universality facts above and the literature results below; the one concrete number this card pins is a single finite-`L` ED ground-state energy for the exact Hamiltonian written above (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Integrable point of the isotropic bilinear–biquadratic spin-1 chain (`β = -1`, `θ = -π/4`), solvable by fusion / higher-spin Bethe ansatz [@ZamolodchikovFateev1980; @Babujian1983]
- Critical, gapless; low-energy CFT is `SU(2)_2` WZW with central charge `c = 3/2` [@Takhtajan1982; @Babujian1983]
- Elementary excitations: a gapless spin-½ spinon doublet (deconfined) [@Takhtajan1982]
- Ground state is a total-spin singlet in the `S^z_{tot}=0` sector (`N` even)

## Benchmarks

`e0 ≡ E/N`; Hamiltonian exactly as written above (coefficient `+1` on the bilinear, `-1` on the biquadratic term), spin-1, PBC.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `E0` (total, ED) | `N=8`, PBC | `-32.6427397329` | finite-`L` ED reference, this card |
| `e0 = E0/N` (ED) | `N=8`, PBC | `-4.0803424666` | finite-`L` ED reference, this card |
| `e0 = E0/N` (ED) | `N=6`, PBC | `-4.1462349785` | finite-`L` ED reference, this card |
| central charge `c` | thermodynamic | `3/2` (`SU(2)_2` WZW) | [@Takhtajan1982; @Babujian1983] |
| `e0` (thermodynamic) | `N→∞` | *no web-verified numeric value quoted here* | [@Babujian1983] |

The `N=6, 8` energies are **finite-`L` ED references for this card, not thermodynamic values** — computed once (spin-1 ED, PBC, Hamiltonian exactly as above) to give future users a pinned check number; they are **not** an extrapolation and the model is gapless, so they still carry an `O(1/N^2)` finite-size correction (`e0(6)=-4.14623`, `e0(8)=-4.08034` rise toward the thermodynamic value as `N` grows). The exact thermodynamic ground-state energy per site is given by Babujian's Bethe-ansatz solution [@Babujian1983]; we do **not** quote a numeric thermodynamic value because no web-verifiable number in this card's exact convention was found — treat [@Babujian1983] as the exact source and the ED numbers above as the pinned finite-size checks.

## Verification recipes

- To check a spin-1 ED/DMRG code against the exact Hamiltonian `H = \sum[\mathbf{S}_i\cdot\mathbf{S}_{i+1} - (\mathbf{S}_i\cdot\mathbf{S}_{i+1})^2]` (PBC): reproduce the pinned `N=8` ground energy `-32.6427397329` (per site `-4.0803424666`) exactly (tolerance `1e-8`). A mismatch usually means a convention slip — wrong sign/coefficient on the biquadratic term, a `(J/4)` normalisation, or Pauli-vs-spin operators.
- To check a critical-exponent / entanglement-entropy measurement: the central charge is `c = 3/2` (`SU(2)_2` WZW); e.g. a bipartite entanglement-entropy scaling `S(ℓ) = (c/3)\ln ℓ + …` at criticality should return `c ≈ 3/2`.
- Confirm gaplessness: the finite-`L` spin gap decreases toward `0` as `N` grows (here `N=6 → 2.226`, `N=8 → 1.662`), not toward a finite Haldane gap — that is the fingerprint distinguishing this integrable point from the generic Haldane-phase spin-1 chain.

## Key reference

[@ZamolodchikovFateev1980] — Zamolodchikov & Fateev, "Model factorized S-matrix and an integrable Heisenberg chain with spin 1", Sov. J. Nucl. Phys. **32**, 298 (1980): the factorized-S-matrix construction of the isotropic integrable spin-1 chain this card covers (a Soviet-era translation journal, no DOI; bibliographic fields best-effort — see `ref.bib` note). The equivalent Bethe-ansatz solution and thermodynamics are Takhtajan [@Takhtajan1982] and Babujian [@Babujian1982; @Babujian1983]; the `c = 3/2` `SU(2)_2` WZW identification is standard for the `β=-1` point. Rendered: _(Wave 3)_.
