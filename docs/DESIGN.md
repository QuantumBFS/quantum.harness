# Design System for Harness QMB Reports

> **Attribution.** Sections 1–9 below are vendored from
> [`nexu-io/open-design`](https://github.com/nexu-io/open-design) at
> `design-systems/claude/DESIGN.md` (Apache-2.0 license), commit pin
> `a98096a042388b74e422d4b1a750fce6894f9a5d`. The upstream describes
> Anthropic's Claude visual identity. Harness extensions (sections 10+)
> add components, layout rules, responsive behavior, accessibility, and
> dark-mode specs specific to scientific reproduction reports.
>
> Per the upstream license, this file is redistributed under Apache-2.0
> with attribution preserved.

---

# Design System Inspired by Claude (Anthropic)

> Category: AI & LLM
> Anthropic's AI assistant. Warm terracotta accent, clean editorial layout.

## 1. Visual Theme & Atmosphere

Claude's interface is a literary salon reimagined as a product page — warm, unhurried, and quietly intellectual. The entire experience is built on a parchment-toned canvas (`#f5f4ed`) that deliberately evokes the feeling of high-quality paper rather than a digital surface. Where most AI product pages lean into cold, futuristic aesthetics, Claude's design radiates human warmth, as if the AI itself has good taste in interior design.

The signature move is the custom Anthropic Serif typeface — a medium-weight serif with generous proportions that gives every headline the gravitas of a book title. Combined with organic, hand-drawn-feeling illustrations in terracotta (`#c96442`), black, and muted green, the visual language says "thoughtful companion" rather than "powerful tool." The serif headlines breathe at tight-but-comfortable line-heights (1.10–1.30), creating a cadence that feels more like reading an essay than scanning a product page.

What makes Claude's design truly distinctive is its warm neutral palette. Every gray has a yellow-brown undertone (`#5e5d59`, `#87867f`, `#4d4c48`) — there are no cool blue-grays anywhere. Borders are cream-tinted (`#f0eee6`, `#e8e6dc`), shadows use warm transparent blacks, and even the darkest surfaces (`#141413`, `#30302e`) carry a barely perceptible olive warmth. This chromatic consistency creates a space that feels lived-in and trustworthy.

**Key Characteristics:**
- Warm parchment canvas (`#f5f4ed`) evoking premium paper, not screens
- Custom Anthropic type family: Serif for headlines, Sans for UI, Mono for code
- Terracotta brand accent (`#c96442`) — warm, earthy, deliberately un-tech
- Exclusively warm-toned neutrals — every gray has a yellow-brown undertone
- Organic, editorial illustrations replacing typical tech iconography
- Ring-based shadow system (`0px 0px 0px 1px`) creating border-like depth without visible borders
- Magazine-like pacing with generous section spacing and serif-driven hierarchy

## 2. Color Palette & Roles

### Primary
- **Anthropic Near Black** (`#141413`): The primary text color and dark-theme surface — not pure black but a warm, almost olive-tinted dark that's gentler on the eyes. The warmest "black" in any major tech brand.
- **Terracotta Brand** (`#c96442`): The core brand color — a burnt orange-brown used for primary CTA buttons, brand moments, and the signature accent. Deliberately earthy and un-tech.
- **Coral Accent** (`#d97757`): A lighter, warmer variant of the brand color used for text accents, links on dark surfaces, and secondary emphasis.

### Secondary & Accent
- **Error Crimson** (`#b53333`): A deep, warm red for error states — serious without being alarming.
- **Focus Blue** (`#3898ec`): Standard blue for input focus rings — the only cool color in the entire system, used purely for accessibility.

### Surface & Background
- **Parchment** (`#f5f4ed`): The primary page background — a warm cream with a yellow-green tint that feels like aged paper. The emotional foundation of the entire design.
- **Ivory** (`#faf9f5`): The lightest surface — used for cards and elevated containers on the Parchment background. Barely distinguishable but creates subtle layering.
- **Pure White** (`#ffffff`): Reserved for specific button surfaces and maximum-contrast elements.
- **Warm Sand** (`#e8e6dc`): Button backgrounds and prominent interactive surfaces — a noticeably warm light gray.
- **Dark Surface** (`#30302e`): Dark-theme containers, nav borders, and elevated dark elements — warm charcoal.
- **Deep Dark** (`#141413`): Dark-theme page background and primary dark surface.

### Neutrals & Text
- **Charcoal Warm** (`#4d4c48`): Button text on light warm surfaces — the go-to dark-on-light text.
- **Olive Gray** (`#5e5d59`): Secondary body text — a distinctly warm medium-dark gray.
- **Stone Gray** (`#87867f`): Tertiary text, footnotes, and de-emphasized metadata.
- **Dark Warm** (`#3d3d3a`): Dark text links and emphasized secondary text.
- **Warm Silver** (`#b0aea5`): Text on dark surfaces — a warm, parchment-tinted light gray.

### Semantic & Accent
- **Border Cream** (`#f0eee6`): Standard light-theme border — barely visible warm cream, creating the gentlest possible containment.
- **Border Warm** (`#e8e6dc`): Prominent borders, section dividers, and emphasized containment on light surfaces.
- **Border Dark** (`#30302e`): Standard border on dark surfaces — maintains the warm tone.
- **Ring Warm** (`#d1cfc5`): Shadow ring color for button hover/focus states.
- **Ring Subtle** (`#dedc01`): Secondary ring variant for lighter interactive surfaces.
- **Ring Deep** (`#c2c0b6`): Deeper ring for active/pressed states.

### Gradient System
- Claude's design is **gradient-free** in the traditional sense. Depth and visual richness come from the interplay of warm surface tones, organic illustrations, and light/dark section alternation. The warm palette itself creates a "gradient" effect as the eye moves through cream → sand → stone → charcoal → black sections.

## 3. Typography Rules

### Font Family
- **Headline**: `Anthropic Serif`, with fallback: `Georgia`
- **Body / UI**: `Anthropic Sans`, with fallback: `Arial`
- **Code**: `Anthropic Mono`, with fallback: `Arial`

*Note: These are custom typefaces. For external implementations, Georgia serves as the serif substitute and system-ui/Inter as the sans substitute.*

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Display / Hero | Anthropic Serif | 64px (4rem) | 500 | 1.10 (tight) | normal | Maximum impact, book-title presence |
| Section Heading | Anthropic Serif | 52px (3.25rem) | 500 | 1.20 (tight) | normal | Feature section anchors |
| Sub-heading Large | Anthropic Serif | 36–36.8px (~2.3rem) | 500 | 1.30 | normal | Secondary section markers |
| Sub-heading | Anthropic Serif | 32px (2rem) | 500 | 1.10 (tight) | normal | Card titles, feature names |
| Sub-heading Small | Anthropic Serif | 25–25.6px (~1.6rem) | 500 | 1.20 | normal | Smaller section titles |
| Feature Title | Anthropic Serif | 20.8px (1.3rem) | 500 | 1.20 | normal | Small feature headings |
| Body Serif | Anthropic Serif | 17px (1.06rem) | 400 | 1.60 (relaxed) | normal | Serif body text (editorial passages) |
| Body Large | Anthropic Sans | 20px (1.25rem) | 400 | 1.60 (relaxed) | normal | Intro paragraphs |
| Body / Nav | Anthropic Sans | 17px (1.06rem) | 400–500 | 1.00–1.60 | normal | Navigation links, UI text |
| Body Standard | Anthropic Sans | 16px (1rem) | 400–500 | 1.25–1.60 | normal | Standard body, button text |
| Body Small | Anthropic Sans | 15px (0.94rem) | 400–500 | 1.00–1.60 | normal | Compact body text |
| Caption | Anthropic Sans | 14px (0.88rem) | 400 | 1.43 | normal | Metadata, descriptions |
| Label | Anthropic Sans | 12px (0.75rem) | 400–500 | 1.25–1.60 | 0.12px | Badges, small labels |
| Overline | Anthropic Sans | 10px (0.63rem) | 400 | 1.60 | 0.5px | Uppercase overline labels |
| Micro | Anthropic Sans | 9.6px (0.6rem) | 400 | 1.60 | 0.096px | Smallest text |
| Code | Anthropic Mono | 15px (0.94rem) | 400 | 1.60 | -0.32px | Inline code, terminal |

### Principles
- **Serif for authority, sans for utility**: Anthropic Serif carries all headline content with medium weight (500), giving every heading the gravitas of a published title. Anthropic Sans handles all functional UI text — buttons, labels, navigation — with quiet efficiency.
- **Single weight for serifs**: All Anthropic Serif headings use weight 500 — no bold, no light. This creates a consistent "voice" across all headline sizes, as if the same author wrote every heading.
- **Relaxed body line-height**: Most body text uses 1.60 line-height — significantly more generous than typical tech sites (1.4–1.5). This creates a reading experience closer to a book than a dashboard.
- **Tight-but-not-compressed headings**: Line-heights of 1.10–1.30 for headings are tight but never claustrophobic. The serif letterforms need breathing room that sans-serif fonts don't.
- **Micro letter-spacing on labels**: Small sans text (12px and below) uses deliberate letter-spacing (0.12px–0.5px) to maintain readability at tiny sizes.

## 4. Component Stylings

### Buttons

**Warm Sand (Secondary)**
- Background: Warm Sand (`#e8e6dc`)
- Text: Charcoal Warm (`#4d4c48`)
- Padding: 0px 12px 0px 8px (asymmetric — icon-first layout)
- Radius: comfortably rounded (8px)
- Shadow: ring-based (`#e8e6dc 0px 0px 0px 0px, #d1cfc5 0px 0px 0px 1px`)
- The workhorse button — warm, unassuming, clearly interactive

**White Surface**
- Background: Pure White (`#ffffff`)
- Text: Anthropic Near Black (`#141413`)
- Padding: 8px 16px 8px 12px
- Radius: generously rounded (12px)
- Hover: shifts to secondary background color
- Clean, elevated button for light surfaces

**Dark Charcoal**
- Background: Dark Surface (`#30302e`)
- Text: Ivory (`#faf9f5`)
- Padding: 0px 12px 0px 8px
- Radius: comfortably rounded (8px)
- Shadow: ring-based (`#30302e 0px 0px 0px 0px, ring 0px 0px 0px 1px`)
- The inverted variant for dark-on-light emphasis

**Brand Terracotta**
- Background: Terracotta Brand (`#c96442`)
- Text: Ivory (`#faf9f5`)
- Radius: 8–12px
- Shadow: ring-based (`#c96442 0px 0px 0px 0px, #c96442 0px 0px 0px 1px`)
- The primary CTA — the only button with chromatic color

**Dark Primary**
- Background: Anthropic Near Black (`#141413`)
- Text: Warm Silver (`#b0aea5`)
- Padding: 9.6px 16.8px
- Radius: generously rounded (12px)
- Border: thin solid Dark Surface (`1px solid #30302e`)
- Used on dark theme surfaces

### Cards & Containers
- Background: Ivory (`#faf9f5`) or Pure White (`#ffffff`) on light surfaces; Dark Surface (`#30302e`) on dark
- Border: thin solid Border Cream (`1px solid #f0eee6`) on light; `1px solid #30302e` on dark
- Radius: comfortably rounded (8px) for standard cards; generously rounded (16px) for featured; very rounded (32px) for hero containers and embedded media
- Shadow: whisper-soft (`rgba(0,0,0,0.05) 0px 4px 24px`) for elevated content
- Ring shadow: `0px 0px 0px 1px` patterns for interactive card states
- Section borders: `1px 0px 0px` (top-only) for list item separators

### Inputs & Forms
- Text: Anthropic Near Black (`#141413`)
- Padding: 1.6px 12px (very compact vertical)
- Border: standard warm borders
- Focus: ring with Focus Blue (`#3898ec`) border-color — the only cool color moment
- Radius: generously rounded (12px)

### Navigation
- Sticky top nav with warm background
- Logo: Claude wordmark in Anthropic Near Black
- Links: mix of Near Black (`#141413`), Olive Gray (`#5e5d59`), and Dark Warm (`#3d3d3a`)
- Nav border: `1px solid #30302e` (dark) or `1px solid #f0eee6` (light)
- CTA: Terracotta Brand button or White Surface button
- Hover: text shifts to foreground-primary, no decoration

### Image Treatment
- Product screenshots showing the Claude chat interface
- Generous border-radius on media (16–32px)
- Embedded video players with rounded corners
- Dark UI screenshots provide contrast against warm light canvas
- Organic, hand-drawn illustrations for conceptual sections

### Distinctive Components

**Model Comparison Cards**
- Opus 4.5, Sonnet 4.5, Haiku 4.5 presented in a clean card grid
- Each model gets a bordered card with name, description, and capability badges
- Border Warm (`#e8e6dc`) separation between items

**Organic Illustrations**
- Hand-drawn-feeling vector illustrations in terracotta, black, and muted green
- Abstract, conceptual rather than literal product diagrams
- The primary visual personality — no other AI company uses this style

**Dark/Light Section Alternation**
- The page alternates between Parchment light and Near Black dark sections
- Creates a reading rhythm like chapters in a book
- Each section feels like a distinct environment

## 5. Layout Principles

### Spacing System
- Base unit: 8px
- Scale: 3px, 4px, 6px, 8px, 10px, 12px, 16px, 20px, 24px, 30px
- Button padding: asymmetric (0px 12px 0px 8px) or balanced (8px 16px)
- Card internal padding: approximately 24–32px
- Section vertical spacing: generous (estimated 80–120px between major sections)

### Grid & Container
- Max container width: approximately 1200px, centered
- Hero: centered with editorial layout
- Feature sections: single-column or 2–3 column card grids
- Model comparison: clean 3-column grid
- Full-width dark sections breaking the container for emphasis

### Whitespace Philosophy
- **Editorial pacing**: Each section breathes like a magazine spread — generous top/bottom margins create natural reading pauses.
- **Serif-driven rhythm**: The serif headings establish a literary cadence that demands more whitespace than sans-serif designs.
- **Content island approach**: Sections alternate between light and dark environments, creating distinct "rooms" for each message.

### Border Radius Scale
- Sharp (4px): Minimal inline elements
- Subtly rounded (6–7.5px): Small buttons, secondary interactive elements
- Comfortably rounded (8–8.5px): Standard buttons, cards, containers
- Generously rounded (12px): Primary buttons, input fields, nav elements
- Very rounded (16px): Featured containers, video players, tab lists
- Highly rounded (24px): Tag-like elements, highlighted containers
- Maximum rounded (32px): Hero containers, embedded media, large cards

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat (Level 0) | No shadow, no border | Parchment background, inline text |
| Contained (Level 1) | `1px solid #f0eee6` (light) or `1px solid #30302e` (dark) | Standard cards, sections |
| Ring (Level 2) | `0px 0px 0px 1px` ring shadows using warm grays | Interactive cards, buttons, hover states |
| Whisper (Level 3) | `rgba(0,0,0,0.05) 0px 4px 24px` | Elevated feature cards, product screenshots |
| Inset (Level 4) | `inset 0px 0px 0px 1px` at 15% opacity | Active/pressed button states |

**Shadow Philosophy**: Claude communicates depth through **warm-toned ring shadows** rather than traditional drop shadows. The signature `0px 0px 0px 1px` pattern creates a border-like halo that's softer than an actual border — it's a shadow pretending to be a border, or a border that's technically a shadow. When drop shadows do appear, they're extremely soft (0.05 opacity, 24px blur) — barely visible lifts that suggest floating rather than casting.

### Decorative Depth
- **Light/Dark alternation**: The most dramatic depth effect comes from alternating between Parchment (`#f5f4ed`) and Near Black (`#141413`) sections — entire sections shift elevation by changing the ambient light level.
- **Warm ring halos**: Button and card interactions use ring shadows that match the warm palette — never cool-toned or generic gray.

## 7. Do's and Don'ts

### Do
- Use Parchment (`#f5f4ed`) as the primary light background — the warm cream tone IS the Claude personality
- Use Anthropic Serif at weight 500 for all headlines — the single-weight consistency is intentional
- Use Terracotta Brand (`#c96442`) only for primary CTAs and the highest-signal brand moments
- Keep all neutrals warm-toned — every gray should have a yellow-brown undertone
- Use ring shadows (`0px 0px 0px 1px`) for interactive element states instead of drop shadows
- Maintain the editorial serif/sans hierarchy — serif for content headlines, sans for UI
- Use generous body line-height (1.60) for a literary reading experience
- Alternate between light and dark sections to create chapter-like page rhythm
- Apply generous border-radius (12–32px) for a soft, approachable feel

### Don't
- Don't use cool blue-grays anywhere — the palette is exclusively warm-toned
- Don't use bold (700+) weight on Anthropic Serif — weight 500 is the ceiling for serifs
- Don't introduce saturated colors beyond Terracotta — the palette is deliberately muted
- Don't use sharp corners (< 6px radius) on buttons or cards — softness is core to the identity
- Don't apply heavy drop shadows — depth comes from ring shadows and background color shifts
- Don't use pure white (`#ffffff`) as a page background — Parchment (`#f5f4ed`) or Ivory (`#faf9f5`) are always warmer
- Don't use geometric/tech-style illustrations — Claude's illustrations are organic and hand-drawn-feeling
- Don't reduce body line-height below 1.40 — the generous spacing supports the editorial personality
- Don't use monospace fonts for non-code content — Anthropic Mono is strictly for code
- Don't mix in sans-serif for headlines — the serif/sans split is the typographic identity

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|------|-------|-------------|
| Small Mobile | <479px | Minimum layout, stacked everything, compact typography |
| Mobile | 479–640px | Single column, hamburger nav, reduced heading sizes |
| Large Mobile | 640–767px | Slightly wider content area |
| Tablet | 768–991px | 2-column grids begin, condensed nav |
| Desktop | 992px+ | Full multi-column layout, expanded nav, maximum hero typography (64px) |

### Touch Targets
- Buttons use generous padding (8–16px vertical minimum)
- Navigation links adequately spaced for thumb navigation
- Card surfaces serve as large touch targets
- Minimum recommended: 44x44px

### Collapsing Strategy
- **Navigation**: Full horizontal nav collapses to hamburger on mobile
- **Feature sections**: Multi-column → stacked single column
- **Hero text**: 64px → 36px → ~25px progressive scaling
- **Model cards**: 3-column → stacked vertical
- **Section padding**: Reduces proportionally but maintains editorial rhythm
- **Illustrations**: Scale proportionally, maintain aspect ratios

### Image Behavior
- Product screenshots scale proportionally within rounded containers
- Illustrations maintain quality at all sizes
- Video embeds maintain 16:9 aspect ratio with rounded corners
- No art direction changes between breakpoints

## 9. Agent Prompt Guide

### Quick Color Reference
- Brand CTA: "Terracotta Brand (#c96442)"
- Page Background: "Parchment (#f5f4ed)"
- Card Surface: "Ivory (#faf9f5)"
- Primary Text: "Anthropic Near Black (#141413)"
- Secondary Text: "Olive Gray (#5e5d59)"
- Tertiary Text: "Stone Gray (#87867f)"
- Borders (light): "Border Cream (#f0eee6)"
- Dark Surface: "Dark Surface (#30302e)"

### Example Component Prompts
- "Create a hero section on Parchment (#f5f4ed) with a headline at 64px Anthropic Serif weight 500, line-height 1.10. Use Anthropic Near Black (#141413) text. Add a subtitle in Olive Gray (#5e5d59) at 20px Anthropic Sans with 1.60 line-height. Place a Terracotta Brand (#c96442) CTA button with Ivory text, 12px radius."
- "Design a feature card on Ivory (#faf9f5) with a 1px solid Border Cream (#f0eee6) border and comfortably rounded corners (8px). Title in Anthropic Serif at 25px weight 500, description in Olive Gray (#5e5d59) at 16px Anthropic Sans. Add a whisper shadow (rgba(0,0,0,0.05) 0px 4px 24px)."
- "Build a dark section on Anthropic Near Black (#141413) with Ivory (#faf9f5) headline text in Anthropic Serif at 52px weight 500. Use Warm Silver (#b0aea5) for body text. Borders in Dark Surface (#30302e)."
- "Create a button in Warm Sand (#e8e6dc) with Charcoal Warm (#4d4c48) text, 8px radius, and a ring shadow (0px 0px 0px 1px #d1cfc5). Padding: 0px 12px 0px 8px."
- "Design a model comparison grid with three cards on Ivory surfaces. Each card gets a Border Warm (#e8e6dc) top border, model name in Anthropic Serif at 25px, and description in Olive Gray at 15px Anthropic Sans."

### Iteration Guide
1. Focus on ONE component at a time
2. Reference specific color names — "use Olive Gray (#5e5d59)" not "make it gray"
3. Always specify warm-toned variants — no cool grays
4. Describe serif vs sans usage explicitly — "Anthropic Serif for the heading, Anthropic Sans for the label"
5. For shadows, use "ring shadow (0px 0px 0px 1px)" or "whisper shadow" — never generic "drop shadow"
6. Specify the warm background — "on Parchment (#f5f4ed)" or "on Near Black (#141413)"
7. Keep illustrations organic and conceptual — describe "hand-drawn-feeling" style

---

## 10. Harness Extensions — Components

These components extend the upstream Claude system for scientific reproduction reports. Use them in addition to the upstream's buttons, cards, and inputs (sections 4 and 5). Every component below uses warm-only neutrals (per §2 palette) and ring shadows (per §6 elevation).

### 10.1 Status chip + popover (`chip` + `chip-pop`)

Used to surface verification status at a glance in the report's status strip. Each chip is a one-word label with a one-sentence explanation in a small dark popover that appears on hover (desktop) or tap (mobile).

**HTML:**

```html
<span class="chip ok" role="button" tabindex="0" aria-describedby="chip-pop-1">symmetry sector
  <span class="chip-pop" id="chip-pop-1" role="tooltip">Conserved Z₂ parity respected. Ground state in the expected sector at every cell.</span>
</span>
<span class="chip warn" role="button" tabindex="0">MPS backend
  <span class="chip-pop" role="tooltip">Used MPS at χ=30 instead of TTN. Long-range PBC correlations under-resolved.</span>
</span>
<span class="chip muted" role="button" tabindex="0">cross-method check pending
  <span class="chip-pop" role="tooltip">Independent TTN run at matched parameters — the next obligation.</span>
</span>
```

**CSS:**

```css
.chip {
  font-family: var(--sans); font-size: 12px;
  background: var(--ivory); border: 1px solid var(--border-warm);
  color: var(--charcoal); border-radius: 999px;
  padding: 5px 12px;
  display: inline-flex; align-items: center; gap: 7px;
  cursor: help; position: relative;
  transition: background 150ms ease;
  font-variant-numeric: tabular-nums;
}
.chip:hover { background: var(--sand); }
.chip.ok::before  { content: '✓'; color: var(--olive); font-weight: 500; }
.chip.warn        { border-color: var(--terracotta); color: var(--terracotta); }
.chip.warn::before { content: '⚠'; }
.chip.warn:hover  { background: rgba(201,100,66,0.06); }
.chip.muted       { color: var(--stone); border-color: var(--border-cream); }

.chip-pop {
  position: absolute; bottom: calc(100% + 8px); left: 0;
  background: var(--near-black); color: var(--silver);
  border-radius: 8px; padding: 8px 12px;
  font-size: 12px; line-height: 1.5; max-width: 280px;
  box-shadow: 0 8px 24px rgba(20,20,19,0.18);
  opacity: 0; pointer-events: none;
  transform: translateY(4px);
  transition: opacity 140ms ease, transform 140ms ease;
  white-space: normal; z-index: 30;
}
.chip:hover .chip-pop { opacity: 1; transform: translateY(0); }
```

Tap-fallback (touch devices): see §13 Hover-or-tap.

### 10.2 Glossary tooltip (`glossbox`) — explanation-on-demand pattern

**Why.** A scientific report has two competing audiences: the specialist who already knows the symbols and the visitor who doesn't. Inline definitions in prose ("the subleading SRE term `c_L(h)`, defined as `2M_2(L/2) − M_2(L)`, where `M_2` is the Rényi-2 stabilizer entropy…") satisfy the visitor and bore the specialist; pure jargon does the opposite. The glossbox resolves this: jargon stays terse for the specialist, the visitor hovers (or taps on mobile) to reveal a one-sentence plain-language definition + the formula.

This is the **explanation-on-demand pattern**: the report's prose carries authority and density; the explanations sit one interaction away. Same pattern applies elsewhere in the harness skin — chip popovers, callout dot popups, deviation banner. They all exist so the report doesn't have to choose between density and accessibility.

**Contract**: every project-specific symbol used in any user-visible text (headline, captions, chip popovers, discrepancy prose) **must** have a glossary entry with a matching `key`, and **must** be wrapped via the `[[key|display]]` markup in the editorial JSON. Without the entry, the report ships jargon — the design contract is broken.

Used to define inline scientific symbols (`c_L(h)`, `M_2`, etc.) on hover or tap, without forcing definitions into the prose.

**HTML:**

```html
<span class="sym" data-term="cl">c<sub>L</sub>(h)</span>

<!-- Single tooltip element somewhere in <body>, populated by JS on hover -->
<div class="glossbox" id="glossbox">
  <div class="label">Term</div>
  <div class="term-name" id="gb-name"></div>
  <div id="gb-body"></div>
  <div class="formula" id="gb-formula"></div>
</div>
```

**CSS:**

```css
.sym {
  font-family: var(--serif); font-style: italic;
  border-bottom: 1px dotted var(--stone); cursor: help;
  transition: border-color 150ms ease;
}
.sym:hover { border-bottom-color: var(--terracotta); border-bottom-style: solid; }

.glossbox {
  position: fixed; max-width: 320px;
  background: var(--ivory); border: 1px solid var(--border-warm);
  border-radius: 12px; padding: 14px 16px;
  box-shadow: 0 0 0 1px var(--ring-warm), 0 12px 32px rgba(20,20,19,0.06);
  font-family: var(--sans); font-size: 13.5px; line-height: 1.55;
  color: var(--charcoal);
  opacity: 0; transform: translateY(4px);
  transition: opacity 150ms ease, transform 150ms ease;
  pointer-events: none; z-index: 200;
}
.glossbox.show { opacity: 1; transform: translateY(0); }
.glossbox .label { font-size: 10px; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; color: var(--terracotta); margin-bottom: 6px; }
.glossbox .term-name { font-family: var(--serif); font-size: 17px; color: var(--near-black); margin-bottom: 6px; line-height: 1.25; }
.glossbox .formula { font-family: var(--mono); font-size: 12.5px; color: var(--olive); margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-cream); }
```

JS contract: on `mouseenter` of any `.sym`, populate `#gb-name`, `#gb-body`, `#gb-formula` from a `GLOSS` lookup keyed by `data-term`, position the glossbox below the symbol, add `.show`. On `mouseleave`, remove `.show`.

### 10.3 Hover callout (`callout`)

Dark popover that appears next to a data point when hovered. Shows the cell's identity, observable value, error bar, accept rate, wall time, timestamp, and manifest filename.

**HTML:**

```html
<div class="callout" id="callout"></div>
<!-- Populated dynamically by JS:
  <div class="callout-row"><span>L · h</span><b>64 · 1.00</b></div>
  <div class="callout-divider"></div>
  <div class="callout-row"><span>c_L</span><b>-0.1706</b></div>
  ...
  <div class="callout-meta">2026-05-07 18:05</div>
  <div class="callout-meta">manifest_L64_h1.00.json</div>
-->
```

**CSS:**

```css
.callout {
  position: absolute; pointer-events: none;
  background: var(--near-black); color: var(--silver);
  border-radius: 10px; padding: 12px 14px;
  font-family: var(--sans); font-size: 12px;
  box-shadow: 0 0 0 1px var(--near-black), 0 12px 32px rgba(20,20,19,0.18);
  opacity: 0; transition: opacity 140ms ease, transform 140ms ease;
  transform: translateY(4px); z-index: 50; min-width: 220px;
}
.callout.show { opacity: 1; transform: translateY(0); }
.callout-row { display: flex; justify-content: space-between; gap: 14px; margin: 3px 0; }
.callout-row span { color: var(--silver); }
.callout-row b { color: #ffffff; font-family: var(--mono); font-weight: 400; font-variant-numeric: tabular-nums; }
.callout-divider { height: 1px; background: rgba(255,255,255,0.10); margin: 8px 0; }
.callout-meta { font-family: var(--mono); font-size: 11px; color: var(--silver); margin-top: 4px; }
```

### 10.4 Side drawer (`drawer` + `drawer-backdrop`)

Slides in from the right (desktop) or up from the bottom (mobile) when a cell is clicked, showing the full manifest. Backdrop dims the page; click-backdrop or `Esc` closes.

**HTML:**

```html
<div class="drawer-backdrop" id="backdrop" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer">
  <button class="drawer-close" onclick="closeDrawer()" aria-label="Close cell manifest panel">×</button>
  <div class="label">Cell manifest</div>
  <h3 id="drawer-title">Cell</h3>
  <div class="sub" id="drawer-sub">—</div>
  <!-- Sections populated by JS:
       Result (cL, ±1σ, 95% CI), Run (wall, n_steps, accept, mean_R, finished),
       Settings (chi, pbc, estimator). Each as .drawer-section with .stitle + .drawer-kv rows. -->
</div>
```

**CSS:**

```css
.drawer {
  position: fixed; top: 0; right: 0; bottom: 0; width: 440px;
  background: var(--ivory); border-left: 1px solid var(--border-warm);
  box-shadow: -10px 0 32px rgba(20,20,19,0.08);
  transform: translateX(100%);
  transition: transform 280ms cubic-bezier(0.32, 0.72, 0, 1);
  z-index: 100; overflow-y: auto; padding: 28px 32px;
}
.drawer.open { transform: translateX(0); }
.drawer-close { position: absolute; top: 18px; right: 22px; background: none; border: none; cursor: pointer; color: var(--stone); font-size: 22px; line-height: 1; }
.drawer-close:hover { color: var(--near-black); }
.drawer .label { font-family: var(--sans); font-size: 10px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; color: var(--terracotta); margin-bottom: 8px; }
.drawer h3 { font-family: var(--serif); font-weight: 500; font-size: 22px; line-height: 1.20; color: var(--near-black); margin: 0 0 6px; }
.drawer .sub { font-family: var(--mono); font-size: 11px; color: var(--stone); margin-bottom: 22px; word-break: break-all; }
.drawer-section { margin-bottom: 22px; }
.drawer-section .stitle { font-family: var(--sans); font-size: 11px; font-weight: 500; letter-spacing: 0.10em; text-transform: uppercase; color: var(--olive); margin-bottom: 10px; }
.drawer-kv { display: flex; justify-content: space-between; padding: 8px 0; font-family: var(--sans); font-size: 13.5px; color: var(--charcoal); border-bottom: 1px solid var(--border-cream); }
.drawer-kv b { font-family: var(--mono); font-weight: 400; color: var(--near-black); font-variant-numeric: tabular-nums; }

.drawer-backdrop {
  position: fixed; inset: 0;
  background: rgba(20,20,19,0.18);
  opacity: 0; pointer-events: none;
  transition: opacity 280ms ease; z-index: 99;
}
.drawer-backdrop.show { opacity: 1; pointer-events: auto; }
```

Mobile bottom-sheet variant: see §12 Responsive behavior.

### 10.5 Panel card (`panel-card`)

The container for each side-by-side panel (paper figure on the left, our reproduction on the right).

**HTML:**

```html
<div class="duo">
  <div class="panel-card">
    <div class="panel-head">
      <span class="label ref">Reference · the paper</span>
      <span class="source">arXiv:2305.18541 · Fig 4(a)</span>
    </div>
    <h2 class="panel-title">Tarabunga et al., 2023.</h2>
    <div class="paper-img-wrap">
      <img src="data:image/png;base64,..." alt="Paper Figure 4(a) showing c_L vs h" />
    </div>
    <div class="paper-cap">…one-sentence caption…</div>
  </div>
  <div class="panel-card">
    <!-- our interactive plot panel -->
  </div>
</div>
```

**CSS:**

```css
.duo { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }

.panel-card {
  background: var(--ivory);
  border: 1px solid var(--border-cream);
  border-radius: 24px;
  padding: 24px 26px 18px;
  box-shadow: 0 0 0 1px var(--border-cream), 0 6px 32px rgba(20,20,19,0.05);
  position: relative;
  display: flex; flex-direction: column;
}
.panel-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 14px;
  font-family: var(--sans);
}
.panel-head .label { font-size: 10px; font-weight: 500; letter-spacing: 0.16em; text-transform: uppercase; color: var(--terracotta); }
.panel-head .label.ref { color: var(--olive); }
.panel-head .source { font-family: var(--mono); font-size: 10.5px; color: var(--stone); }
.panel-title {
  font-family: var(--serif); font-weight: 500; font-size: 16px; line-height: 1.30;
  color: var(--near-black); margin: 0 0 14px;
  letter-spacing: -0.005em;
}
.paper-img-wrap {
  background: #fff; border: 1px solid var(--border-cream); border-radius: 12px;
  padding: 18px 22px; flex: 1;
  display: flex; align-items: center; justify-content: center;
  min-height: 360px;
}
.paper-img-wrap img { max-width: 100%; height: auto; display: block; image-rendering: -webkit-optimize-contrast; }
.paper-cap {
  margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-cream);
  font-family: var(--sans); font-size: 12.5px; line-height: 1.6; color: var(--olive);
}
.paper-cap b { color: var(--near-black); font-weight: 500; }
```

`.duo` collapses to single column on mobile (per §12).

### 10.6 Contract grid (`ctr`)

Renders `protocol.toml` sections (sources, scope, claims, deviations, budget) as a 2-column label/value grid in the below-fold "Contract" panel.

**HTML:**

```html
<div class="ctr">
  <div class="k">Source</div>
  <div class="v"><span class="pill">arXiv:2305.18541</span><span class="pill">PRX Quantum 4, 040317</span></div>
  <div class="k">Claims</div>
  <div class="v">
    <div class="claim-line-c"><span class="id">fig4.shape</span><span class="stmt">…claim statement…</span></div>
  </div>
</div>
```

**CSS:**

```css
.ctr { display: grid; grid-template-columns: 110px 1fr; gap: 10px 20px; font-family: var(--sans); font-size: 13px; }
.ctr .k { font-size: 10px; font-weight: 500; letter-spacing: 0.10em; text-transform: uppercase; color: var(--olive); padding-top: 4px; }
.ctr .v { color: var(--charcoal); line-height: 1.55; }
.ctr .v .pill {
  display: inline-block; font-family: var(--mono); font-size: 11px;
  background: var(--sand); border: 1px solid var(--ring-warm);
  border-radius: 4px; padding: 1px 7px; margin: 2px 4px 2px 0;
  color: var(--charcoal);
}
.ctr .v .claim-line-c { padding: 6px 0; border-bottom: 1px dashed var(--border-cream); display: flex; gap: 10px; align-items: baseline; }
.ctr .v .claim-line-c:last-child { border-bottom: none; }
.ctr .v .claim-line-c .id { font-family: var(--mono); font-size: 10.5px; color: var(--stone); flex-shrink: 0; width: 130px; }
.ctr .v .claim-line-c .stmt { color: var(--near-black); font-family: var(--serif); font-size: 14px; line-height: 1.45; }
```

### 10.7 Toggle pill (`toggle`)

Small pill button used for figure-level toggles like "Match paper y-window".

```html
<button class="toggle on" id="toggle-paper">
  <span class="swatch"></span> Paper's range
</button>
```

```css
.toggle {
  font-family: var(--sans); font-size: 11.5px; font-weight: 500;
  background: var(--parchment); border: 1px solid var(--border-warm);
  color: var(--charcoal); border-radius: 999px; padding: 5px 12px;
  cursor: pointer; transition: all 160ms ease;
  display: inline-flex; align-items: center; gap: 7px;
}
.toggle:hover { background: var(--sand); }
.toggle.on { background: var(--near-black); color: var(--ivory); border-color: var(--near-black); }
.toggle .swatch { width: 10px; height: 10px; border-radius: 2px; background: rgba(94,93,89,0.10); border: 1px solid var(--silver); }
.toggle.on .swatch { background: var(--ivory); border-color: var(--ivory); opacity: 0.6; }
```

### 10.8 Legend item (`legend-item`)

Each curve's legend row, with focus/dim hover behavior across `.curve, .pt, .errbar, .legend-item` sharing the same `data-l` (or `data-curve`) attribute.

```html
<div class="legend-row" id="legend">
  <div class="legend-item" data-l="64">
    <span class="legend-swatch" style="background:#c96442;"></span>
    L = 64
    <span class="legend-val">-0.17</span>
  </div>
</div>
```

```css
.legend-row { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-cream); }
.legend-item {
  display: flex; align-items: center; gap: 9px;
  padding: 5px 12px; border-radius: 18px; cursor: pointer;
  font-family: var(--sans); font-size: 13px; color: var(--charcoal);
  transition: background 150ms ease, opacity 150ms ease;
}
.legend-item:hover { background: var(--sand); }
.legend-item.dim { opacity: 0.40; }
.legend-swatch { width: 18px; height: 3px; border-radius: 2px; }
.legend-val { font-family: var(--mono); font-size: 12px; color: var(--stone); }
```

JS: on `mouseenter` of a `.legend-item`, add `.dim` to all `.curve, .pt, .errbar, .legend-item` whose `data-l` differs, and `.focus` to those whose `data-l` matches. On `mouseleave`, remove all classes.

---

## 11. Interactive Plot — Inline SVG Conventions

The interactive figure in the right-side `panel-card` is an inline `<svg>` element directly embedded in the HTML body, **not** a static image and **not** a third-party charting library (no Plotly, D3, or Chart.js — they violate the standalone-deliverable size budget and the warm-only Claude palette). The SVG renders interactively via DOM events (`mouseenter`, `click`, `mouseleave`) on its child elements; CSS class toggles (`.curve.dim`, `.pt.focus`, etc.) drive the focus / dim / hover-callout effects with native browser transitions.

This section locks the structural and class-name conventions so every report renders consistently. The renderer (`tools/skills/report/site/build.mjs`) generates the SVG markup from `figs/<id>.json`; CSS lives here so the visual stays identical across reports.

**Required SVG structure** (background overlays first, then grid, then data on top):

```html
<svg class="plot" viewBox="0 0 720 460" preserveAspectRatio="xMidYMid meet"
     role="img" aria-labelledby="plot-title plot-desc">
  <title id="plot-title">c_L vs h on the 1D TFIM</title>
  <desc id="plot-desc">Reproduction of Tarabunga 2023 Fig 4(a). Four curves L=16, 32, 64, 128 of c_L = 2 M_2(L/2) − M_2(L) across h ∈ [0.8, 1.2].</desc>

  <!-- Background overlays (paper-band, hc-column flash) come first so they're behind data -->
  <rect class="hc-column" id="hc-flash" x="..." y="..." width="..." height="..."/>
  <rect class="paper-window" id="paper-window" x="..." y="..." width="..." height="..."/>
  <text class="paper-window-label" id="paper-window-label" x="..." y="..." text-anchor="end">paper y-window</text>

  <!-- Grid + axes + ticks -->
  <line class="grid" x1="..." x2="..." y1="..." y2="..."/>
  <text class="tick" x="..." y="..." text-anchor="middle">0.8</text>
  <line class="zero" x1="..." x2="..." y1="..." y2="..."/>            <!-- y=0 reference -->
  <line class="hcline" x1="..." x2="..." y1="..." y2="..."/>          <!-- vertical h_c marker -->
  <text class="hclabel" x="..." y="...">h_c = 1</text>
  <line class="axis" x1="..." x2="..." y1="..." y2="..."/>            <!-- x and y axes -->
  <text class="axis-label" x="..." y="..." text-anchor="middle">transverse field h</text>

  <!-- Data: one set per curve. data-l (or data-curve) groups elements that focus/dim together. -->
  <path class="curve draw" data-l="64" stroke="#c96442" d="M ..."/>
  <line class="errbar" data-l="64" stroke="#c96442" x1="..." x2="..." y1="..." y2="..."/>
  <circle class="pt" data-l="64" data-k="3" cx="..." cy="..." r="3.6" fill="#c96442"
          aria-label="L=64, h=1.00, c_L = -0.171 ± 0.061"/>
</svg>
```

**CSS class specs** (full):

```css
svg.plot { width: 100%; height: 460px; user-select: none; display: block; }
svg.plot .grid { stroke: var(--border-warm); stroke-dasharray: 1 4; stroke-width: 0.5; }
svg.plot .axis { stroke: var(--stone); stroke-width: 0.8; }
svg.plot .axis-label { fill: var(--olive); font-size: 13px; font-family: var(--sans); font-weight: 450; }
svg.plot .tick { fill: var(--stone); font-size: 11px; font-family: var(--mono); }
svg.plot .curve { fill: none; stroke-width: 1.7; transition: opacity 220ms ease, stroke-width 220ms ease; }
svg.plot .curve.dim { opacity: 0.18; }
svg.plot .curve.focus { stroke-width: 2.6; }
svg.plot .pt { transition: opacity 200ms ease, r 140ms ease; cursor: pointer; stroke: transparent; stroke-width: 14; paint-order: stroke; }
svg.plot .pt.dim { opacity: 0.18; }
svg.plot .errbar { stroke-width: 1.2; opacity: 0.50; transition: opacity 220ms ease; }
svg.plot .errbar.dim { opacity: 0.10; }
svg.plot .draw {
  stroke-dasharray: 2400; stroke-dashoffset: 2400;
  animation: draw 1100ms cubic-bezier(0.32, 0.72, 0, 1) forwards;
}
svg.plot .zero { stroke: var(--silver); stroke-width: 0.6; opacity: 0.5; }
svg.plot .hcline { stroke: var(--terracotta); stroke-width: 0.6; stroke-dasharray: 4 4; opacity: 0.55; }
svg.plot .hclabel { fill: var(--terracotta); font-family: var(--mono); font-size: 11px; opacity: 0.85; }
svg.plot .paper-window { fill: rgba(94,93,89,0.10); stroke: none; opacity: 0; transition: opacity 320ms ease; pointer-events: none; }
svg.plot .paper-window.on { opacity: 1; }
svg.plot .paper-window-label { fill: var(--olive); font-family: var(--sans); font-size: 11px; font-style: italic; opacity: 0; transition: opacity 320ms ease; }
svg.plot .paper-window-label.on { opacity: 0.85; }
svg.plot .hc-column { fill: var(--terracotta); opacity: 0; transition: opacity 240ms ease; pointer-events: none; }
svg.plot .hc-column.flash { opacity: 0.08; }

@keyframes draw { to { stroke-dashoffset: 0; } }
```

**Touch-friendly hit area on points (mandatory):** `.pt` carries a transparent 14px stroke around the visible 3.6px circle (via `stroke: transparent; stroke-width: 14; paint-order: stroke`). This makes finger taps register on touch devices without precision targeting; the visible dot stays small.

**Curve color palette** (warm clay → terracotta gradient, ordered by curve dimension):

```javascript
const colors = ['#b39c80', '#a87a55', '#c96442', '#7a2a1a'];
```

For 1-4 curves use these in order; for 5+ interpolate between `#b39c80` (lightest clay) and `#7a2a1a` (deepest terracotta). Never reach for cool blues or saturated brights — the palette is restrained.

**Data attribute conventions** (used by the focus/dim JS and by the click-to-drawer handler):

- `data-l="<curve-key>"` (or `data-curve="<curve-key>"`) on every `.curve`, `.errbar`, `.pt`, and `.legend-item`. The value is the value of the `curves.field` from `figs/<id>.json` (e.g. `"64"` for L=64).
- `data-k="<row-index>"` on every `.pt` — index into the `data` array for callout lookup and drawer population.

**Interaction JS (the renderer emits this once at the end of the body):**

```javascript
// Focus/dim by data-l value
function focusL(L) {
  document.querySelectorAll('.curve, .pt, .errbar, .legend-item').forEach(el => el.classList.remove('focus', 'dim'));
  if (L === null) return;
  document.querySelectorAll('[data-l]').forEach(el => {
    if (+el.dataset.l === L) el.classList.add('focus');
    else el.classList.add('dim');
  });
}

// Hover callout on point + click to open drawer
document.querySelectorAll('svg.plot .pt').forEach(pt => {
  pt.addEventListener('mouseenter', e => { focusL(+pt.dataset.l); /* populate + show callout */ });
  pt.addEventListener('mouseleave', () => { focusL(null); /* hide callout */ });
  pt.addEventListener('click', () => { /* populate + open cell drawer */ });
});

// Esc closes drawer
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
```

The renderer composes the full JS from `figs/<id>.json` (data array) + the editorial sidecar (cell-popover labels) + this skeleton.

**Data shape — paper-agnostic.** The plot driver consumes a single `(axes, data)` schema and infers everything (axis labels, ranges, ticks, curve grouping, error bars, drawer payloads) from it. No observable name, lattice symbol, or model is hardcoded in the template. Required and optional fields:

```json
{
  "label": "<figure-id>",
  "axes": {
    "x":      { "field": "<x-key>", "label": "<x-axis-label>",
                "scale": "linear" | "log",
                "refline": { "value": <number>, "label": "<short-label>" } },
    "y":      { "field": "<y-key>", "label": "<y-axis-label>",
                "scale": "linear" | "log",
                "paper_window": { "lo": <number>, "hi": <number> } },
    "curves": { "field": "<group-by-key>", "label_template": "L = {L}" },
    "err":    { "field": "<err-key>" }
  },
  "data": [
    { "<x-key>": ..., "<y-key>": ..., "<group-by-key>": ..., "<err-key>": ...,
      "manifest": "<basename>.json", "wall": <s>, "accept": <0..1>, "when": "<ISO>",
      "<any-other-payload>": ... }
  ]
}
```

- `axes.x.field` and `axes.y.field` are required.
- `axes.curves`, `axes.err` are optional. Without `curves`, the data is a single curve. Without `err`, no error bars render.
- `axes.x.refline` (optional) draws a dashed terracotta vertical line at `value` with `label` (e.g. critical point, transition).
- `axes.y.paper_window` (optional) reveals the **Match paper y-window** toggle, which clamps the y-axis to the paper's display range. When absent, the toggle is hidden. Disabled when `axes.y.scale = "log"`.
- `axes.{x,y}.scale = "log"` (optional, default `"linear"`) switches the axis to base-10 log. Ticks are auto-generated as 1/2/5 multiples per decade. Data points with non-positive values on a log axis are silently skipped.
- The drawer's "Result" section shows `axes.y.field` value + (if present) `axes.err.field` and 95% CI. The "Cell payload" section shows every other key in the row, prettified, in mono.
- Ranges and tick steps are auto-derived (5%/8% padding on x/y for linear; ÷1.2/×1.2 padding on log; "nice" tick step targeting ~5 ticks per linear axis). To pin them, encode the desired range in the data with sentinel rows.

### 11.1 Multi-figure layout

A report with N > 1 figures renders the **featured** figure inside `.hero` (above-the-fold) and additional figures stacked vertically inside a new `<section class="extra-figs">` between the status strip and the scroll hint. Order: featured first (per `protocol.featured_figure` or first `[[figures]]` entry), then the rest in protocol declaration order.

Each additional figure carries an eyebrow label (`Figure N of M · <display_id>`) above its `.duo` block, and a thin top border separates it from the previous figure. The same `.duo` styling and the same plot driver are reused — additional figures look identical to the featured one, just below the chip strip.

**JS contract:** the renderer emits a single `const FIGURES = [{label, axes, data}, ...]` array. The init function `initFig(fig)` is called once per entry; it scopes its DOM lookups to IDs `plot-<label>`, `callout-<label>`, `legend-<label>`, `toggle-window-<label>`, so per-figure state (zoom range, focused curve) does not bleed across figures. The drawer is page-shared (one cell open at a time across all figures).

**Worked examples (non-TFIM):**

```json
// Phase diagram — heatmap-like via nested curves (one curve per pinned axis value)
{
  "label": "phase_diagram_2D",
  "axes": {
    "x": { "field": "U", "label": "U/t" },
    "y": { "field": "gap", "label": "single-particle gap" },
    "curves": { "field": "delta", "label_template": "δ = {delta}" }
  },
  "data": [ { "U": 1.0, "delta": 0.2, "gap": 0.012 }, ... ]
}

// Bond-dim convergence — log-log
{
  "label": "convergence_chi",
  "axes": {
    "x": { "field": "chi", "label": "bond dim χ", "scale": "log" },
    "y": { "field": "energy_error", "label": "|E − E_exact|", "scale": "log" }
  },
  "data": [ { "chi": 16, "energy_error": 1e-3, "manifest": "..." }, ... ]
}

// Order parameter sweep with critical point reference
{
  "label": "magnetization_J",
  "axes": {
    "x": { "field": "J", "label": "J/J_c", "refline": { "value": 1.0, "label": "J_c" } },
    "y": { "field": "m", "label": "magnetization m" },
    "err": { "field": "se" }
  },
  "data": [ { "J": 0.95, "m": 0.42, "se": 0.01 }, ... ]
}
```

For 2D phase diagrams as proper heatmaps (color-mapped z-field), the current driver does not render them — pin one axis and emit one curve per pinned value as shown above, or compose multiple `[[figures]]` entries (one per pinned third axis).

---

## 12. Responsive Behavior

A single HTML file must render cleanly on both desktop (≥ 992px) and mobile (≤ 640px). Three breakpoints with component-specific collapsing rules.

**Required `<head>` element** (mandatory; without it mobile browsers use a default viewport width and the layout breaks):

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

**Required global rule** (suppresses the horizontal scrollbar that off-canvas drawers / glossboxes would otherwise create):

```css
html, body { overflow-x: hidden; }
```

**Breakpoint scale:**

| Width | Name | Layout changes |
|---|---|---|
| ≥ 992px | Desktop | Full layout: side-by-side hero, drawer 440px from right, all hover affordances active |
| 640-991px | Tablet | Tighter padding, drawer 380px, below-fold collapses to single column |
| ≤ 640px | Mobile | Side-by-side **stacks** vertically (paper above, ours below); drawer becomes **bottom sheet** sliding up; hero claim drops 32→22px; chip strip wraps tighter; fig-controls move below panel-title |

**CSS rules (mandatory; copy verbatim into the rendered HTML):**

```css
@media (max-width: 991px) {
  .topbar, .hero, .strip, .scroll-hint, .below { padding-left: 24px; padding-right: 24px; }
  .duo { gap: 14px; }
  .panel-card { padding: 20px 22px 16px; }
  svg.plot { height: 320px; }
  .drawer { width: 380px; }
  .below { grid-template-columns: 1fr; gap: 16px; }
  .panel.full { grid-template-columns: repeat(2, 1fr) !important; }
}

@media (max-width: 640px) {
  .topbar { grid-template-columns: 1fr; padding: 16px 18px; gap: 8px; }
  .topbar .meta { text-align: left; font-size: 10.5px; }
  .topbar .id { display: inline-block; margin-bottom: 4px; }

  .hero { padding: 24px 18px 20px; }
  .claim-line { flex-direction: column; align-items: flex-start; gap: 10px; margin-bottom: 18px; }
  .claim { font-size: 22px; line-height: 1.20; }
  .claim-tag { padding-top: 0; font-size: 10px; }

  .duo { grid-template-columns: 1fr; gap: 14px; }
  .panel-card { padding: 18px 20px 14px; border-radius: 18px; }
  .panel-title { font-size: 14px; margin-bottom: 10px; }
  .paper-img-wrap { padding: 12px 14px; min-height: 200px; }
  .plot-area { min-height: 280px; }
  svg.plot { height: 280px; }
  .ours-controls { position: static; margin-bottom: 10px; }
  .legend-row { gap: 6px; padding-top: 10px; }
  .legend-item { padding: 4px 8px; font-size: 12px; }

  .strip { padding: 0 18px; gap: 6px; margin-top: 14px; }
  .chip { font-size: 11.5px; padding: 6px 12px; min-height: 32px; }
  .chip.spacer { display: none; }
  .chip-pop { left: 0; right: 0; bottom: auto; top: calc(100% + 6px); max-width: none; }

  .scroll-hint { margin-top: 24px; padding: 0 18px; font-size: 10px; }

  .below { padding: 0 18px 56px; margin-top: 40px; gap: 14px; }
  .panel { padding: 18px 20px; border-radius: 14px; }
  .panel h3 { font-size: 18px; }
  .panel.full { grid-template-columns: 1fr !important; gap: 14px; padding: 18px 20px !important; }
  .ctr { grid-template-columns: 90px 1fr; gap: 8px 14px; font-size: 12.5px; }

  /* Drawer becomes a bottom sheet on mobile */
  .drawer {
    top: auto; bottom: 0; left: 0; right: 0; width: 100%;
    max-height: 80vh; border-left: none; border-top: 1px solid var(--border-warm);
    border-radius: 18px 18px 0 0;
    transform: translateY(100%);
  }
  .drawer.open { transform: translateY(0); }
  .drawer-close { top: 14px; right: 18px; font-size: 26px; padding: 4px 10px; }

  .callout { font-size: 11px; min-width: 200px; }
}
```

---

## 13. Hover-or-Tap

Every hover-revealed element MUST also respond to tap on touch devices. Hover-only is forbidden — it makes affordances inaccessible on phones.

**CSS pattern** (suppress hover on `(hover: none)` viewports, enable tap-driven `.tapped` class):

```css
@media (hover: none) {
  .chip { cursor: pointer; }
  .chip-pop { display: none; }
  .chip.tapped .chip-pop { display: block; opacity: 1; transform: translateY(0); }
  .sym { cursor: pointer; }
}
.chip.tapped .chip-pop { opacity: 1; transform: translateY(0); }
```

**JS pattern** (toggle `.tapped` on click; tap-outside dismisses; only one chip open at a time):

```javascript
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', e => {
    e.stopPropagation();
    const wasTapped = chip.classList.contains('tapped');
    document.querySelectorAll('.chip.tapped').forEach(c => c.classList.remove('tapped'));
    if (!wasTapped) chip.classList.add('tapped');
  });
});
document.addEventListener('click', () => {
  document.querySelectorAll('.chip.tapped').forEach(c => c.classList.remove('tapped'));
});
```

Same pattern applies to `.sym` glossary terms. For `.pt` data points: hover shows callout (desktop), tap opens drawer directly (mobile — drawer is a more useful interaction than a transient callout on a small screen).

**Touch target floor: 44×44px.** For data points (visible 3.6px), the 14px transparent stroke specified in §11 brings the effective hit area to ~32×32px — close to the floor; combined with the magnetic-snapping behavior, finger taps are reliable.

---

## 14. Accessibility

WCAG-AA contrast ratios; full keyboard navigation; ARIA semantics on interactive elements.

**Color contrast (verify each pair, minimum 4.5:1 for normal text, 3:1 for large text):**

- Body text (`charcoal #4d4c48` on `parchment #f5f4ed`): 8.2:1 ✓
- Secondary text (`olive #5e5d59` on `parchment`): 6.4:1 ✓
- Tertiary text (`stone #87867f` on `parchment`): 4.0:1 — passes for large text only; do not use for body
- Terracotta accent (`#c96442` on `parchment`): 4.8:1 ✓ (use for emphasis, not body)
- Callout text (`silver #b0aea5` on `near-black #141413`): 9.1:1 ✓

**Keyboard navigation:**

- `Tab` cycles all interactive elements (chips, legend items, toggles, data points, drawer-close, glossbox-dismiss).
- `Esc` closes the drawer, dismisses the glossbox, dismisses any tapped chip.
- All `<button>` and `<a>` elements use the browser's default focus ring (do not suppress `:focus`).
- Custom interactive `<div>` / `<span>` (e.g., `.chip`, `.legend-item`) carry `tabindex="0"` and `role="button"`.

**ARIA semantics (mandatory on interactive elements):**

```html
<span class="chip ok" role="button" tabindex="0" aria-describedby="chip-pop-1">
  symmetry sector
  <span class="chip-pop" id="chip-pop-1" role="tooltip">…description…</span>
</span>

<svg class="plot" role="img" aria-labelledby="plot-title plot-desc">
  <title id="plot-title">c_L vs h on the 1D TFIM</title>
  <desc id="plot-desc">Reproduction of Tarabunga 2023 Fig 4(a). Four curves L=16, 32, 64, 128 of c_L = 2 M_2(L/2) − M_2(L) across h ∈ [0.8, 1.2].</desc>
  <circle class="pt" aria-label="L=64, h=1.00, c_L = -0.171 ± 0.061" .../>
</svg>

<button class="drawer-close" aria-label="Close cell manifest panel">×</button>
```

**Hard rule:** every interactive element must be reachable and operable via keyboard alone, and every non-text element conveying information must have a text alternative.

---

## 15. Agent Prompt Guide — Harness Components

Quick reference for an agent rendering a compliant report HTML. Use these prompts when composing components.

**Status chip** (use for verification trust signals in the strip):

> "Create a `<span class='chip ok'>label<span class='chip-pop'>one-sentence detail</span></span>` with `role='button' tabindex='0' aria-describedby='<id>'`. Use class `ok` for passing checks, `warn` for failures or accepted deviations, `muted` for pending / informational. Hover (desktop) or tap (mobile) reveals the popover; only one chip popover open at a time per §13."

**Glossary tooltip** (use for inline scientific symbols in the hero claim line and prose):

> "Wrap inline symbol in `<span class='sym' data-term='<key>'>c<sub>L</sub>(h)</span>`. The single `<div class='glossbox' id='glossbox'>` element in `<body>` is populated on `mouseenter` / tap from a `GLOSS` JS object keyed by `data-term`. Position fixed below the symbol; opacity transition on `.show` toggle."

**Side-by-side panel-card** (use for paper figure | reproduction):

> "Wrap each side in a `<div class='panel-card'>` with `<div class='panel-head'>` (label + source), `<h2 class='panel-title'>` (one-sentence title), then either `<div class='paper-img-wrap'><img src='data:...' alt='...' /></div>` for the paper or `<svg class='plot'>` for the interactive reproduction. Container is `<div class='duo'>` with `grid-template-columns: 1fr 1fr` (collapses to `1fr` on mobile per §12)."

**Cell drawer** (use for click-to-inspect manifest):

> "Single `<div class='drawer-backdrop' onclick='closeDrawer()'>` + `<div class='drawer'>` per page. Drawer slides in via `transform: translateX(100%) → translateX(0)` on `.open`. Mobile: bottom sheet via `transform: translateY(100%) → translateY(0)`. Always include `<button class='drawer-close' onclick='closeDrawer()' aria-label='Close cell manifest panel'>×</button>`. `Esc` key also closes."

**Hero claim line** (the headline at the top of the report):

> "Use `<h1 class='claim'>` with `font-family: var(--serif); font-weight: 500; font-size: 32px; line-height: 1.18; letter-spacing: -0.012em; text-wrap: balance`. Wrap inline symbols in `.sym` per Glossary. Mobile: `font-size: 22px`. Total above-fold word count ≤ 100 (this is a hard rule, not a guideline)."

**Interactive plot SVG** (the reproduction's data view):

> "Compose an inline `<svg class='plot' viewBox='0 0 720 460' preserveAspectRatio='xMidYMid meet' role='img' aria-labelledby='plot-title plot-desc'>` per §11 conventions. Each curve: `<path class='curve draw' data-l='<L>' stroke='<color>' d='M ...'/>`. Each data point: `<circle class='pt' data-l='<L>' data-k='<index>' cx='...' cy='...' r='3.6' fill='<color>' aria-label='<L=..., x=..., y=... ± ...>'/>`. Use the warm clay → terracotta palette `['#b39c80', '#a87a55', '#c96442', '#7a2a1a']` ordered by curve dimension. Mandatory 14px transparent stroke around each `.pt` for finger-target hit area."

**Hard reject list** (red flags to never produce):

- Cool blue-grays (`#666`, `#aaa`, `#888`, `#eee`) anywhere → use the warm-only palette: `olive #5e5d59`, `stone #87867f`, `silver #b0aea5`, `charcoal #4d4c48`.
- `box-shadow: 0 2px 4px rgba(0,0,0,0.1)` (traditional drop shadow) → use ring shadow `0 0 0 1px var(--ring-warm)` or whisper `0 4px 24px rgba(20,20,19,0.05)`.
- `font-weight: bold` (700+) on serif headlines → all serif headlines use weight 500.
- `font-family: monospace` on body text → `var(--sans)` for body, `var(--mono)` only for code, file paths, and tabular numbers.
- `padding: 8px` on tap targets → minimum 44×44px effective area per §13.
- Hover-only affordances without `(hover: none)` fallback → forbidden per §13.
- Synthesized data, fake error bars, illustrative-only numbers → forbidden; the report renders evidence, never invents it.
- A third-party charting library (Plotly, D3, Chart.js) → forbidden per §11; the inline SVG pattern fits the standalone-deliverable size budget and maintains visual fidelity.
- Pure white (`#ffffff`) as a page background → use `parchment #f5f4ed` (light) or `near-black #141413` (dark).
- Marketing voice, first-person, rhetorical questions, exclamation marks → the report is scientific-confident, declarative, and terse.
