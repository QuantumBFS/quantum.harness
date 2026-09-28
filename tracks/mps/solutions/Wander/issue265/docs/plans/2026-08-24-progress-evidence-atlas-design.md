# Hydrodynamic Evidence Atlas design

## Purpose

The atlas presents the current SCNet convergence results without promoting an
incomplete convergence gate to a validation decision.  It connects numerical
coverage, numerical sensitivity, spin-flip symmetry, scaling tests, and the
controlled effective-equation hierarchy from fluctuating GHD to finite-window
Burgers projections.

The visual system has three reading levels:

1. eight editorial hero figures for the scientific narrative;
2. evidence plates that expose definitions, numerical envelopes, and limits;
3. forensic figures that make every aggregate statement auditable.

## Evidence language

The figures use the following statements exactly:

- `complete artifact`: a final NPZ and run summary are present;
- `checkpointed TIMEOUT`: a readable checkpoint exists but no final artifact;
- `not rejected in available domain`: a candidate description survives only
  the displayed data domain;
- `unresolved`: numerical sensitivity is comparable to or larger than the
  proposed physical effect;
- `gate not accepted`: the frozen convergence audit is absent or not accepted.

Checkpoint data are never extrapolated or drawn as final trajectories.  A
coarse--medium difference is called a numerical envelope, not a confidence
interval.  Theory curves use a distinct dotted style.

## Visual narrative

The master narrative is

```text
microscopic continuity
        -> infinite-mode fluctuating GHD
        -> projected Mori memory equation
        -> low-rank/two-mode or running-coefficient reductions
        -> stochastic KPZ normal mode
        -> deterministic finite-window Burgers surrogate.
```

The four initial states attach to this hierarchy as evidence:

- opposite walls test spin-flip parity and FCS orientation;
- the finite-background wall probes field-dependent transport;
- the double wall tests locality and mode/memory closure;
- coarse, medium, and fine runs quantify numerical sensitivity.

## Output families

### Hero figures

1. Evidence map and gate status.
2. Physical-time coverage and compute cost.
3. Magnetization profiles converge before currents.
4. Four initial states and their distinct scientific questions.
5. Spin inversion and FCS orientation are preserved.
6. Competing diffusion, KPZ, and ballistic scaling compensations.
7. Local closure versus projected memory.
8. Controlled hierarchy and present verdict.

### Evidence plates

Evidence plates use an A3 landscape twelve-column grid.  Each plate has a
conclusion title, an eight-column main panel, a four-column diagnostic panel,
and a provenance footer.  The footer records source files, time and spatial
domains, formulas, evidence status, and limitations.

### Forensic figures

Forensic figures cover window sensitivity, continuity residuals, raw profile
differences, truncation and magnetization drift, FCS fitting sensitivity, and
model residuals.  Each forensic figure answers one question and reuses the
same units, colors, and state encoding.

## Layout systems

Separate layouts are generated for separate uses; no figure is naively scaled
between them.

- Paper: 178 mm width, 7 pt minimum text, white background, vector PDF/SVG.
- Atlas: A3 landscape, 16 mm margins, twelve columns, 5 mm gutters.
- Presentation: 3840 x 2160 pixels, 20 px minimum text.
- Thumbnail: 640 px wide with simplified labels and no small annotations.

Plots reserve a dedicated legend rail.  Legends never use automatic
`loc="best"` placement and never cover data.  Shared-axis small multiples show
axis labels only on the outer panels.

## Typography

- Chinese: Noto Sans CJK SC or Source Han Sans SC.
- Latin text: Source Sans 3, with DejaVu Sans as a tested fallback.
- Mathematics: STIX Two Math.
- Paper sizes: 10--11 pt title, 8.5--9 pt panel title, 7.5--8 pt axes and
  legends, never below 7 pt.

Titles state a conclusion and use at most two lines.  Plot interiors permit
only panel letters, axis labels, and at most three priority data annotations.
Long explanations belong in the caption or evidence footer.

## Color and line grammar

| Meaning | Color |
|---|---|
| magnetization/density | `#2864A5` |
| current | `#D97732` |
| KPZ/scaling | `#168C84` |
| memory/multimode | `#7656A5` |
| numerical risk/TIMEOUT | `#B44545` |
| missing/unresolved | `#8A9099` |

Resolution uses lightness and line style rather than new hues:

- coarse: light, thin solid line;
- medium: standard, thick solid line;
- fine: dark dash-dot line;
- partial/checkpoint-only coverage: hollow marker or hatched track;
- theory: dotted line;
- numerical envelope: translucent fill.

Diverging heat maps are centered at zero.  Comparable panels share limits.
Sequential error maps use perceptually uniform palettes.  Every figure remains
distinguishable under grayscale and common color-vision-deficiency simulation.

## Collision prevention

Text placement is a constrained layout problem, not a final cosmetic pass.

1. A dedicated legend rail is allocated before plotting.
2. Axes have at most six major ticks; time uses 0, 50, 100, 150, 200.
3. Text extents are measured with the final renderer and font.
4. Direct labels are assigned priorities: conclusion, extrema, endpoints,
   auxiliary curves.
5. Colliding labels move outside the axes with leader lines; if they still do
   not fit they become numbered callouts in the evidence footer.
6. Fonts are never reduced below the layout-specific minimum.
7. Rendered PNG, SVG, and PDF outputs are checked for overlap, clipping,
   missing glyphs, and embedded fonts.

## Data and provenance

The atlas ingests a local immutable snapshot of the six final convergence
NPZ files, six run summaries, the authoritative convergence submission JSON,
and a machine-readable partial-run summary extracted from logs.  A snapshot
manifest stores path, size, modification time, and SHA-256 for every input.

Derived metrics include:

- physical-time coverage and compute rate;
- cumulative and maximum discarded weight;
- magnetization drift;
- common-window coarse--medium profile and current differences;
- spin-flip even/odd residuals;
- continuity residuals on the recorded lattice;
- width and effective scaling exponents when their definitions pass boundary
  and normalization checks.

Every plotted metric is serialized to a compact JSON sidecar before rendering.
Figures render from sidecars rather than recomputing hidden quantities.

## Quality gates

A figure is publishable only if:

- every plotted point is finite and within the declared data domain;
- axes, units, state, resolution, and time range are explicit;
- no text, legend, or panel overlaps another element;
- no text or tick label is clipped at final size;
- all fonts are present or embedded;
- color and line style remain distinguishable in grayscale;
- the figure has a provenance entry and evidence-status label;
- the caption states what the figure cannot establish;
- no incomplete result is labeled verified or accepted.

The first implementation milestone is a visual specimen sheet plus the first
four hero figures.  Bulk figure generation begins only after that specimen
passes visual inspection at paper, A3, and 4K presentation sizes.
