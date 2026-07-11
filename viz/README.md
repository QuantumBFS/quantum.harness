# lattix

Interactive 3D views of lattices, many-body data, and tensor-network diagrams.
One committed bundle (`dist/lattix.min.js`, no network, no runtime deps)
renders a **scene JSON** into any container:

```html
<div class="lattix" data-height="420">
  <script type="application/json">{ ...scene... }</script>
</div>
<script src="dist/lattix.min.js"></script>
<script>Lattix.mountAll();</script>
```

or programmatically: `Lattix.mount(element, sceneObject)`.

In harness run reports, use the `lattice3d` block (see `skills/report/SKILL.md`) —
`render_report.py` inlines the bundle automatically.

## Scene schema

Required: `nodes`, and `edges` (may be `[]`). Everything else is optional.

| field | meaning |
|---|---|
| `meta.title` | shown nowhere yet; documentation for the file |
| `meta.labels` | `"hover"` (default) or `"always"` — always renders edge `label`s as sprites (tensor networks) |
| `nodes[].id` | unique id (number or string), referenced by edges |
| `nodes[].pos` | `[x, y, z]` — the library never generates geometry |
| `nodes[].value` | scalar → site color via `encode.nodes` |
| `nodes[].vector` | `[x, y, z]` → arrow glyph (e.g. local spin) |
| `nodes[].size` | radius factor, default 1 |
| `nodes[].label`, `nodes[].group` | shown in the hover tooltip |
| `nodes[].virtual` | `true`: no sphere, bare line end (TN dangling legs) |
| `edges[].s`, `edges[].t` | node ids |
| `edges[].type` | key into `types` for styling |
| `edges[].value` | scalar → bond color (and width if `widthByValue`) |
| `edges[].label` | tooltip text; sprite when `meta.labels: "always"` (e.g. `"χ=8"`) |
| `edges[].wrap` | `true`: periodic bond, drawn as faded ghost stubs (UI toggle: arcs) |
| `types.<name>` | `{ color, width, dash }` — `dash: true` renders dashed lines |
| `encode.nodes` | `{ colormap: "diverging"\|"sequential", domain: [lo,hi]\|null, sizeByValue }` |
| `encode.edges` | `{ colormap, domain, widthByValue }` |
| `frames` | `{ labels?, nodes?, vectors?, edges? }` — per-frame dense value arrays, index-aligned with `nodes`/`edges`. Geometry never changes across frames. |

Omitted `domain` is computed from all values across all frames (symmetric
about 0 for `diverging`).

## Limits

Above 50 000 instances (nodes + edges) mesh detail degrades automatically;
above 200 000 the viewer refuses with an error box — coarsen the data.
Keep it to at most ~8 views per page (browser WebGL context limit).

## Examples / eyeball gate

`examples/preview.html` renders one example per capability
(`square-j1j2`, `cubic`, `mc-animation`, `peps-diagram`). Regenerate with
`python3 examples/generate.py` (deterministic — never dirties git).

## Developing

Sources in `src/` (plain ESM; `scene.js`, `overlays.js`, `frames.js` are pure
and unit-tested). `bash build.sh` = npm install + esbuild bundle +
`node --test test.js` + regenerate examples. **Commit the rebuilt
`dist/lattix.min.js` with any `src/` change.** Node is a developer-only
dependency; nothing at render or view time needs it.
