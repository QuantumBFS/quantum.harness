import { test } from "node:test";
import assert from "node:assert/strict";
import {
  LIMITS, validateScene, applyDefaults, nodeIndex, isPlanar, medianEdgeLength,
} from "./src/scene.js";
import {
  COLORMAPS, valueToColor, collectValues, autoDomain, resolveDomain, legendHTML,
} from "./src/overlays.js";
import { sampleFrames } from "./src/frames.js";

const MIN = {
  nodes: [{ id: 0, pos: [0, 0, 0] }, { id: 1, pos: [1, 0, 0] }],
  edges: [{ s: 0, t: 1 }],
};

test("validateScene accepts a minimal scene", () => {
  assert.deepEqual(validateScene(MIN), []);
});

test("validateScene rejects non-objects and empty nodes", () => {
  assert.equal(validateScene(null).length, 1);
  assert.match(validateScene({ nodes: [], edges: [] })[0], /nodes/);
});

test("validateScene flags duplicate ids, bad pos, unknown edge endpoints", () => {
  const errs = validateScene({
    nodes: [{ id: 0, pos: [0, 0, 0] }, { id: 0, pos: [1, 0] }],
    edges: [{ s: 0, t: 9 }],
  });
  assert.ok(errs.some((e) => e.includes("duplicate id")));
  assert.ok(errs.some((e) => e.includes("pos must be")));
  assert.ok(errs.some((e) => e.includes("unknown target 9")));
});

test("validateScene checks frame lengths against nodes/edges", () => {
  const s = { ...MIN, frames: { labels: ["a"], nodes: [[0.1, 0.2], [0.3]] } };
  const errs = validateScene(s);
  assert.ok(errs.some((e) => e.includes("frames.nodes[1]")));   // wrong inner length
  assert.ok(errs.some((e) => e.includes("frames.labels")));      // 1 label, 2 frames
});

test("validateScene refuses scenes above the instance limit", () => {
  const nodes = Array.from({ length: LIMITS.refuse + 1 },
    (_, i) => ({ id: i, pos: [i, 0, 0] }));
  const errs = validateScene({ nodes, edges: [] });
  assert.ok(errs.some((e) => e.includes("scene too large")));
});

test("applyDefaults fills defaults without mutating input", () => {
  const input = JSON.parse(JSON.stringify(MIN));
  const s = applyDefaults(input);
  assert.deepEqual(input, MIN);                       // untouched
  assert.equal(s.camera.up, "z");
  assert.equal(s.encode.nodes.colormap, "diverging");
  assert.equal(s.encode.edges.widthByValue, false);
  assert.equal(s.nodes[0].size, 1);
  assert.equal(s.nodes[0].virtual, false);
  assert.equal(s.edges[0].wrap, false);
});

test("nodeIndex maps ids to array indices", () => {
  const m = nodeIndex(MIN);
  assert.equal(m.get(1), 1);
});

test("isPlanar detects flat and 3D scenes", () => {
  assert.equal(isPlanar(MIN.nodes), true);
  assert.equal(isPlanar([{ pos: [0, 0, 0] }, { pos: [0, 0, 2] }]), false);
});

test("medianEdgeLength ignores wrap bonds, defaults to 1", () => {
  const s = applyDefaults({
    nodes: [{ id: 0, pos: [0, 0, 0] }, { id: 1, pos: [2, 0, 0] },
            { id: 2, pos: [0, 1, 0] }],
    edges: [{ s: 0, t: 1 }, { s: 0, t: 2 }, { s: 1, t: 2, wrap: true }],
  });
  assert.equal(medianEdgeLength(s), 2);               // sorted [1,2] → index 1
  assert.equal(medianEdgeLength(applyDefaults({ nodes: MIN.nodes, edges: [] })), 1);
});

test("valueToColor hits endpoints and midpoint of diverging map", () => {
  assert.deepEqual(valueToColor(-1, [-1, 1]).map((c) => Math.round(c * 255)),
    [0x21, 0x66, 0xac]);
  assert.deepEqual(valueToColor(0, [-1, 1]).map((c) => Math.round(c * 255)),
    [0xf7, 0xf7, 0xf7]);
  assert.deepEqual(valueToColor(99, [-1, 1]).map((c) => Math.round(c * 255)),
    [0xb2, 0x18, 0x2b]);                               // clamped to hi
});

test("collectValues gathers base values and frame values", () => {
  const s = applyDefaults({
    nodes: [{ id: 0, pos: [0, 0, 0], value: 0.1 }, { id: 1, pos: [1, 0, 0] }],
    edges: [],
    frames: { nodes: [[0.5, -0.5]] },
  });
  assert.deepEqual(collectValues(s, "nodes").sort(), [-0.5, 0.1, 0.5].sort());
});

test("autoDomain: symmetric, plain, degenerate, empty", () => {
  assert.deepEqual(autoDomain([-0.3, 0.5], true), [-0.5, 0.5]);
  assert.deepEqual(autoDomain([2, 5], false), [2, 5]);
  assert.deepEqual(autoDomain([3], false), [2.5, 3.5]);
  assert.deepEqual(autoDomain([], false), [0, 1]);
});

test("resolveDomain: explicit domain wins, diverging auto is symmetric", () => {
  const s = applyDefaults({
    nodes: [{ id: 0, pos: [0, 0, 0], value: -0.2 }, { id: 1, pos: [1, 0, 0], value: 0.6 }],
    edges: [],
    encode: { edges: { domain: [-9, 9] } },
  });
  assert.deepEqual(resolveDomain(s, "nodes"), [-0.6, 0.6]);
  assert.deepEqual(resolveDomain(s, "edges"), [-9, 9]);
});

test("legendHTML renders colorbar gradient and type swatches", () => {
  const s = applyDefaults({
    nodes: [{ id: 0, pos: [0, 0, 0], value: 1 }],
    edges: [],
    types: { J1: { color: "#4a6fa5", width: 2 }, J2: { color: "#c0504d", dash: true } },
  });
  const h = legendHTML(s, [-1, 1], [0, 1]);
  assert.ok(h.includes("linear-gradient"));
  assert.ok(h.includes("J1") && h.includes("J2"));
  assert.ok(h.includes("dashed"));                     // dashed swatch style
  assert.equal(legendHTML(applyDefaults({ nodes: [{ id: 0, pos: [0, 0, 0] }] }),
    [0, 1], [0, 1]), "");                              // nothing to show
});

test("legendHTML escapes attribute-breaking type colors", () => {
  const s = applyDefaults({
    nodes: [{ id: 0, pos: [0, 0, 0] }],
    edges: [],
    types: { X: { color: 'red" onmouseover="alert(1)' } },
  });
  const h = legendHTML(s, [0, 1], [0, 1]);
  assert.ok(!h.includes('onmouseover="alert'));
  assert.ok(h.includes("&quot;"));
});

test("sampleFrames discrete holds the floor frame and clamps", () => {
  const seq = [[0, 10], [2, 20], [4, 40]];
  assert.deepEqual(sampleFrames(seq, 1.9, false), [2, 20]);
  assert.deepEqual(sampleFrames(seq, -3, false), [0, 10]);
  assert.deepEqual(sampleFrames(seq, 99, false), [4, 40]);
  assert.equal(sampleFrames([], 0, false), null);
  assert.equal(sampleFrames(undefined, 0, false), null);
});

test("sampleFrames interpolates scalars and vectors", () => {
  assert.deepEqual(sampleFrames([[0, 10], [2, 20]], 0.5, true), [1, 15]);
  assert.deepEqual(sampleFrames([[[0, 0, 1]], [[0, 0, -1]]], 0.5, true), [[0, 0, 0]]);
  assert.deepEqual(sampleFrames([[0], [2]], 1, true), [2]);   // exact frame
});
