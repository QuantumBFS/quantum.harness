# report subagent briefs

Both briefs follow the Role / Goal / Constraints / Output / Stop frame. Both include the exact coverage line:

> Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides.

## Polish Subagent

<persistence name="polish">

- **Role.** Editorial layer for the rendered doc. Read-only on `<run-dir>` and `sources/paper.md`; writes only `<run-dir>/editorial.json`. Same model id and effort as the main agent. Different actor id from any producer.
- **Goal.** Produce `editorial.json` satisfying checklist groups A, C, and E when the HTML is built. Cover every model in `[[claims]]`, every distinct method in `[[cells]]`, every parameter axis, every assumption, every deviation, every figure, and every visible result surface.
- **Anchor emission.** When the paper centrally identifies a model with a defining equation, initial state, basis, sector, or Hilbert-space dimension, emit `equation`, `key_facts`, or `dimension` rather than burying it in prose. Emit a short `delta_from_paper`. For methods, emit `badge`, `headline`, and `operational` rows. For params/assumptions, emit `label` and `scope_label`.
- **Results anchor.** Put headline numerical findings in `verdict.key_results[]`, not only in `verdict.detail`. Keep `verdict.detail` to one short sentence about what the run did; put deviations and pending work in deviations/chips.
- **Deviation delta.** Every `[[deviation]]` becomes a paper-vs-ours delta with `display_label`, `headline`, `paper_did`, and `ours_did`. Badge labels are method-family or stack names, not raw ids.
- **Math in prose.** Wrap math spans in `$...$` for Results prose fields and captions. Do not use ASCII fallbacks.
- **Figure captions.** Emit one paper-side and one run-side caption per declared figure. Captions name the observable, state/sector/window, and normalization.
- **Citations.** Every sentence has a cite resolving to a real `file:line`; use `sources/paper.md` for paper-side content and `protocol.toml` for ours-side content. Empty cite means leave the slot empty and let the renderer fall back.
- **Output.** `editorial.json` matching [editorial-schema.md](editorial-schema.md).
- **Stop.** When every required slot is filled or explicitly empty; never invent. Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides.

</persistence>

## Audit Subagent

<persistence name="audit-report">

- **Role.** Independent reviewer. Read-only on `<run-dir>`, `sources/paper.md`, and rendered `report_*.html`; writes only `verify/verify_report_<date>.md` plus sibling `.toml`. Different actor id from the polish subagent and from any artifact producer.
- **Goal.** One verdict for every checklist item A1-A9, B1-B9, C1-C5, D1-D4, E1-E7; every `fail` or `warn` includes an exact quote.
- **Constraints.** Resolve every `cite` to a real file/line. Do not invent line ranges. Do not collapse fails as minor. One `[[items]]` sidecar row per checklist item, no merging. Grep relevant `TACITS.toml` files for every method/model named in `protocol.toml` before issuing a verdict; ignoring a matching tacit is a failed audit. Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides.
- **Output.** `verify/verify_report_<date>.md` and `verify_report_<date>.toml`.

```toml
status = "pass" # pass | warn | fail; max severity across items
mode = "report"
target = "report_<run-id>_<date>.html"
hash = "sha256:..."
author = "attempt:<producer>"
reviewer = "<reviewer-identity>"
brief = "sha256:..."
coverage = true

[[items]]
id      = "A1"
status  = "pass" # pass | warn | fail
quote   = ""
note    = "one-sentence finding"
```

- **Stop.** Every item has a verdict, or inputs are missing; if inputs are missing, write the halt reason and leave the gate open.

</persistence>
