# report audit checklist reference

Read before polish and audit dispatch. The audit subagent returns one verdict for every item below: A1-A9, B1-B9, C1-C5, D1-D4, E1-E7.

## A. Audience

Every user-facing string — visible labels, tooltips, chip text, section headings, captions, popovers, banners, plot labels — must satisfy all A-items.

- **A1. No internal identifiers leaked.** Rewrite ids such as `trust_dimension`, `protocol_hash`, `fig3.special_band`, and `deviation.stack.numpy_scipy` as plain-English phrases.
- **A2. No file paths in user-facing strings.** Hide `.md`, `.toml`, `.json`, `.py`, `scripts/`, `cells/`, `verify/`, `figs/`, `progress/`, and `tools/` except in a dedicated provenance source-link slot.
- **A3. No internal vocabulary.** Forbid `subagent`, `polish subagent`, `audit subagent`, `actor`, `attempt`, `gate`, `kind`, `producer`, `manifest`, `flow`, `protocol_hash`, `freshness sources`, `above-the-fold`, `hero`, `chip`, `popover`, `drawer`, `callout`.
- **A4. No raw check kinds.** Do not show strings like `near (...)`, `exists (...)`, `audit (...)`, or `support (...)`; translate to what was checked.
- **A5. Overrides rendered as reasons.** Show "**Skipped because** <one-sentence non-expert reason>", never "bypassed by <actor>".
- **A6. Snake_case rewritten.** Translate `special_band`, `zero_modes`, `level_statistics`, `dos_zero_modes`, `pr2_scaling`, `fsa_eigenvalues`, etc.
- **A7. Greek and math symbols rendered.** Use Unicode or math markup for α, β, γ, χ, ω, Δ, ≈, ≤, ≥, ± and related math.
- **A8. Panel headings use audience words.** Replace Contract -> What was promised; Discrepancy -> What didn't match; Provenance -> Where this came from; Cell manifest/payload -> Run details; Deviation -> Documented exception; Override/Bypass -> Skipped check.
- **A9. Abbreviations spelled out first.** First occurrence spells out `1σ`, `95% CI`, wall, accept, vs paper, DOS, OBC, PBC, FSA, MC, ED, DMRG, TEBD, QMC.

## B. Structure

- **B1. Paper figure embed.** At least one paper-side PNG is embedded per declared `[[figures]]` entry.
- **B2. Claim line.** Present, non-empty, and <= 200 characters.
- **B3. Side-by-side.** Each `[[figures]]` entry has both paper panel and reproduction panel from `figs/<id>.json`.
- **B4. Verdict band.** Exactly one verdict band appears at top of Results: match, partial, fail, or unknown.
- **B5. Status chip strip.** At least one status chip with visible label and hover/tap popover; both satisfy A.
- **B6. Provenance footer.** Four columns render: Run, Cluster, Source, Harness; each populated from `progress/state.toml`.
- **B7. Page size.** <= 3 MB warning, <= 10 MB hard refuse.
- **B8. Mobile rendering.** No horizontal scroll at 375 px viewport.
- **B9. Three sections present.** Problem, Methodology, Results all visible and reachable. At plan stage, Results says pending; at append stage all three are filled.

## C. Tone

- **C1. Above-the-fold is a result, not a procedure.** The first visible Results block answers what reproduced.
- **C2. Headline <= 100 words.** Claim + verdict + key-number recap stay compact.
- **C3. Every editorial sentence carries a `cite` pointer.** Sentences without cite are dropped or replaced by declared fallback.
- **C4. No hedging unless the paper hedges.** Use `might`, `appears`, `perhaps`, `seems`, `possibly` only when source text does.
- **C5. Caveats after, not before.** Discrepancies and limitations live in the dedicated panel, never in the claim line.

## D. Evidence

- **D1. Every chip is backed by a verify report.** No chip may rely only on hint-class evidence.
- **D2. Audit actor differs from producer actor.** The signer for the chip's check is distinct from the artifact producer.
- **D3. Every figure is rendered from current-run manifests.** Data points reference manifests with `producer = "run"` and current hashes.
- **D4. Provenance footer comes from the ledger.** It reads `progress/state.toml`, not agent memory.

## E. Sourcing

- **E1.** Every `problem.blocks[*].cite` resolves to supporting text in `sources/paper.md`.
- **E2.** Every `methodology.{models,methods}[*].paper.cite` resolves to `sources/paper.md`.
- **E3.** Every `methodology.{models,methods}[*].ours.cite` resolves to `protocol.toml`.
- **E4.** Every `methodology.params[*].why` is non-empty and materially supports the values chosen.
- **E5.** Every `methodology.assumptions[*].why` is non-empty and materially supports the assumption.
- **E6.** Every `[[deviations]].why` in `protocol.toml` is non-empty.
- **E7.** Every model/method id referenced from `[[claims]]` or `[[cells]]` appears exactly once in methodology.

## Example Transformations

- Bad: `near (trust_zero_modes_obc): support holds at L=12..30`
- Good: `Zero-mode count matches the expected value at every chain length we ran (L = 12 through L = 30).`

- Bad: `L=32 manifest fields will land when HPC2 job completes; bypassed by agent:report-skill`
- Good: `Skipped because L = 32 is still computing on the cluster. The other sizes are complete and use the same code.`

- Bad: `fig3.fsa_eigenvalues: matches paper`
- Good: `Forward-scattering approximation eigenvalues match the paper to within about 1%.`
