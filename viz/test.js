import { test } from "node:test";
import assert from "node:assert/strict";
import {
  LIMITS, validateScene, applyDefaults, nodeIndex, isPlanar, medianEdgeLength,
} from "./src/scene.js";

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
