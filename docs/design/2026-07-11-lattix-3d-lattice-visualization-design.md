# Lattix: interactive 3D lattice visualization for many-body reports

**Date:** 2026-07-11
**Status:** Approved design, pre-implementation

## Goal

A general-purpose, physics-agnostic JavaScript library that renders interactive
3D views of many-body computations — lattice geometry, static data overlays,
frame animations, and tensor-network diagrams — and its first consumer: a new
`lattice3d` block kind in the harness's `report` pipeline, so any run report
can embed rotatable, inspectable lattice views while staying a single offline
HTML file.

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Primary purpose | General-purpose library; report integration is the first consumer |
| v1 render scope | Lattice geometry, static overlays, frame animation, TN diagrams |
| 3D dependency | three.js (+ OrbitControls addon), bundled at dev time into one committed file |
| Interface | Dumb renderer: explicit sites/bonds/values JSON; no built-in lattice generators |
| Packaging | In this repo under `viz/`; new `lattice3d` block in `report.json` |
| Architecture | One scene-JSON schema, one viewer module, one code path for all four capabilities |

Explicitly out of scope for v1: moving-geometry animation, built-in lattice
generators, producer helper libraries (Julia/Python), isosurfaces/volumetric
data, a separate npm package.

## File layout

```
viz/
  src/
    main.js          # entry: exposes window.Lattix.mount(container, sceneJson)
    scene.js         # schema validation + defaults
    geometry.js      # instanced meshes for nodes/edges, arrow glyphs, PBC ghost stubs
    overlays.js      # value → color/size/vector mapping, colorbar legend
    animation.js     # frame scrubber, play/pause, interpolation
    controls.js      # orbit/pan/zoom, hover tooltip, node picking
  dist/
    lattix.min.js    # COMMITTED esbuild bundle (three.js included, ~600KB, IIFE)
  examples/
    square-j1j2.json     # geometry + edge types + static overlay
    mc-animation.json    # frames (Monte Carlo snapshots)
    peps-diagram.json    # tensor network with bond-dimension labels, virtual legs
    cubic.json           # genuinely 3D lattice
    preview.html         # renders all examples on one page — the eyeball gate
  build.sh           # esbuild src/main.js --bundle --minify → dist/lattix.min.js
  test.js            # node --test unit tests for pure logic (post-build)
  README.md          # scene schema reference
```

- The bundle is committed so `render_report.py` stays stdlib-only and offline:
  it reads `viz/dist/lattix.min.js` as text and inlines it. Node/esbuild is a
  developer-only dependency for anyone editing `viz/src/`; users never build.
- One global entry point `Lattix.mount(el, scene)`; a page may mount several
  scenes.
- `examples/` doubles as test fixtures and schema documentation.

## Scene JSON schema

Minimal valid scene: `nodes` + `edges`. Everything else optional with defaults.

```jsonc
{
  "meta":   { "title": "6x6 J1-J2 Heisenberg", "units": "" },
  "camera": { "up": "z", "view": "auto" },   // auto-fit; planar scenes → orthographic top view

  "nodes": [
    { "id": 0, "pos": [0,0,0],
      "value": 0.31,             // scalar → colormap
      "vector": [0,0,0.5],       // optional arrow glyph (e.g. local spin)
      "size": 1.0, "label": "A", "group": "sublattice-A",
      "virtual": false }         // true: bare line end, no sphere (TN dangling legs)
  ],
  "edges": [
    { "s": 0, "t": 1, "type": "J1",
      "value": -0.42,            // scalar → edge color/width
      "label": "χ=16",           // shown on hover (or always, style option)
      "wrap": false }            // true: periodic bond → ghost stub pair
  ],

  "types": {                     // per-type visual style
    "J1": { "color": "#4a6fa5", "width": 2 },
    "J2": { "color": "#c0504d", "width": 1, "dash": true }
  },

  "encode": {
    "nodes": { "colormap": "diverging", "domain": [-0.5, 0.5], "sizeByValue": false },
    "edges": { "colormap": "diverging", "domain": [-1, 1], "widthByValue": true }
  },

  "frames": {                    // optional animation; VALUES ONLY, geometry fixed
    "labels": ["sweep 0", "sweep 100"],
    "nodes":   [[0.3, -0.1], [0.1, 0.2]],  // per frame, index-aligned dense arrays
    "vectors": [],                          // optional per-frame arrows
    "edges":   []                           // optional per-frame edge values
  }
}
```

Schema rules:

- **Frames are values-only.** Positions and bonds never change across frames;
  frames swap `value`/`vector` arrays. Keeps MC animations compact and updates
  cheap (instance attribute buffers, no scene rebuild).
- **PBC**: `wrap: true` bonds render as two short faded ghost stubs leaving
  each partner toward its image. A UI toggle switches stubs ↔ full arcs.
- **Tensor networks use the same schema**: tensors are nodes (`group` colors
  by role), bonds are edges with `label` = bond dimension and optional `value`
  (e.g. truncation error); dangling physical legs target `virtual: true` nodes.
- **Auto domain**: if `encode.*.domain` is absent, computed from data across
  all frames (so the colorbar is stable during playback).
- **Dashed types**: `dash: true` edge types render as dashed line segments
  (`LineDashedMaterial`) instead of instanced cylinders — a deliberate visual
  and implementation distinction for secondary couplings like J2.
- **Loud validation**: `scene.js` validates on mount; on failure renders a
  readable error box (first few offending entries) into the container. Never a
  blank canvas or console-only failure.

## Viewer behavior

- **Rendering**: instanced spheres (nodes), instanced cylinders (edges),
  instanced arrow glyphs (vectors) — one draw call per mesh class; tens of
  thousands of instances at 60fps. Fixed three-point lighting, no shadows.
  Background follows the host page theme via `prefers-color-scheme`.
- **2D default**: planar scenes (all z equal) open in an orthographic,
  rotation-locked top view — reads like a figure; a "3D" button unlocks orbit.
- **Interaction**: orbit/pan/zoom (OrbitControls); hover tooltip with
  id/group/label/value; click highlights a node and its incident edges.
  Overlay panel: colorbar with domain ticks, edge-type legend, PBC stub/arc
  toggle, PNG-snapshot button (canvas → download) for static paper figures.
- **Animation**: scrubber with frame labels, play/pause, speed control.
  Linear interpolation between frames during playback, with a discrete toggle;
  discrete is the default (MC snapshots are not continuous).
- **Performance guardrail**: above ~50k instances, sphere/cylinder segment
  counts drop automatically; above ~200k instances the viewer refuses with the
  error box telling the producer to coarsen the data.

## Report-pipeline integration

New block kind in `report.json`:

```json
{ "kind": "lattice3d", "src": "scene_gs.json",
  "caption": "…", "height": 420, "poster": "fig.png" }
```

`render_report.py` changes (stdlib-only, ~40 lines):

- `src` resolved relative to the run dir (same convention as `figures`); scene
  JSON embedded as a `<script type="application/json">` payload per block.
- `viz/dist/lattix.min.js` inlined **once per page**, and only when at least
  one `lattice3d` block exists — lattice-free reports pay nothing.
- Missing scene file degrades to the same small note as a missing figure.
- `poster` (optional but recommended in docs): static image used as the
  pre-mount placeholder and shown in print media, since reports are also
  consumed as PDF-like artifacts.
- Old copies of the renderer skip the unknown kind — backward compatible.

Producer side: run scripts write `scene_*.json` next to their figures.
`skills/report/SKILL.md` gains a `lattice3d` row in the block table and a
short "composing a scene" subsection linking to `viz/README.md`. Captions
follow the existing caption rulebook.

## Error handling and testing

- Schema errors → in-container error box (see above).
- **Unit tests** (`viz/test.js`, `node --test`, run after `build.sh`): schema
  validation accept/reject cases, value→color mapping, auto-domain across
  frames, frame indexing, planar-scene detection. WebGL itself is not
  unit-tested.
- **Eyeball gate**: `examples/preview.html` renders every example scene; a
  human (or screenshot-taking agent) verifies before merging renderer changes.
- **Pipeline fixtures**: a fixture `report.json` with a `lattice3d` block
  renders and the output contains exactly one inlined bundle; a fixture with a
  missing scene file renders the degradation note.

## Success criteria

1. `examples/preview.html` shows all four example scenes correctly (rotatable,
   tooltips, animation scrubber on the MC example, TN labels on hover).
2. A run report with two `lattice3d` blocks is a single offline HTML file that
   opens with no network access and contains one bundle copy.
3. A report with a bad/missing scene shows a readable note, not a blank box.
4. `node --test viz/test.js` passes.
