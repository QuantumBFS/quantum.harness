// Builds the three.js objects for one scene: instanced spheres (nodes),
// instanced cylinders (solid edges), dashed line segments (dash types),
// wrap stubs/arcs (PBC), and instanced arrows (vectors).
import * as THREE from "three";
import { LIMITS, nodeIndex, medianEdgeLength } from "./scene.js";
import { valueToColor, resolveDomain, collectValues } from "./overlays.js";

const Y = new THREE.Vector3(0, 1, 0);
const ACCENT = new THREE.Color("#e8a33d");
const NODE_BASE = new THREE.Color("#8892a0");
const EDGE_BASE = new THREE.Color("#9aa4b0");
const DIM = 0.35;                                       // non-highlighted fade

export function buildLattice(scene) {
  const group = new THREE.Group();
  const index = nodeIndex(scene);
  const unit = medianEdgeLength(scene, index);
  const total = scene.nodes.length + scene.edges.length;
  const lod = total > LIMITS.degrade
    ? { sphere: [8, 6], cyl: 5 } : { sphere: [20, 14], cyl: 10 };
  const nodeDomain = resolveDomain(scene, "nodes");
  const edgeDomain = resolveDomain(scene, "edges");
  const posOf = (id) => scene.nodes[index.get(id)].pos;
  const typeOf = (e) => scene.types[e.type] || {};
  const typeColor = new Map(Object.entries(scene.types).map(
    ([k, st]) => [k, new THREE.Color(st.color || "#9aa4b0")]));

  const M = new THREE.Matrix4(), Q = new THREE.Quaternion();
  const V = new THREE.Vector3(), W = new THREE.Vector3(), C = new THREE.Color();

  // ---- nodes ---------------------------------------------------------------
  const solidN = [];                                    // node array indices
  scene.nodes.forEach((n, i) => { if (!n.virtual) solidN.push(i); });
  const nodes = new THREE.InstancedMesh(
    new THREE.SphereGeometry(1, lod.sphere[0], lod.sphere[1]),
    new THREE.MeshLambertMaterial(), solidN.length);

  function nodeRadius(i, val) {
    let r = 0.16 * unit * (scene.nodes[i].size || 1);
    if (scene.encode.nodes.sizeByValue && Number.isFinite(val)) {
      const [lo, hi] = nodeDomain;
      const t = hi > lo ? (val - lo) / (hi - lo) : 0.5;
      r *= 0.5 + Math.min(1, Math.max(0, t));
    }
    return r;
  }

  // ---- edges ---------------------------------------------------------------
  const solidE = [], dashE = [], wrapE = [];
  scene.edges.forEach((e, i) => {
    if (e.wrap) wrapE.push(i);
    else if (typeOf(e).dash) dashE.push(i);
    else solidE.push(i);
  });
  const edges = new THREE.InstancedMesh(
    new THREE.CylinderGeometry(1, 1, 1, lod.cyl, 1, true),
    new THREE.MeshLambertMaterial(), solidE.length);

  function edgeWidth(ei, val) {
    let w = 0.035 * unit * (typeOf(scene.edges[ei]).width || 1);
    if (scene.encode.edges.widthByValue && Number.isFinite(val)) {
      const m = Math.max(Math.abs(edgeDomain[0]), Math.abs(edgeDomain[1])) || 1;
      w *= 0.25 + 1.25 * Math.min(1, Math.abs(val) / m);
    }
    return w;
  }

  function placeEdge(k, ei, val) {
    const e = scene.edges[ei];
    V.set(...posOf(e.s)); W.set(...posOf(e.t));
    const dir = W.clone().sub(V), len = dir.length();
    Q.setFromUnitVectors(Y, dir.normalize());
    const w = edgeWidth(ei, val);
    M.compose(V.add(W).multiplyScalar(0.5), Q, new THREE.Vector3(w, len, w));
    edges.setMatrixAt(k, M);
  }
  solidE.forEach((ei, k) => placeEdge(k, ei, scene.edges[ei].value));
  edges.instanceMatrix.needsUpdate = true;

  // dashed types: one LineSegments per dashed type
  const dashGroup = new THREE.Group();
  const byType = new Map();
  dashE.forEach((ei) => {
    const t = scene.edges[ei].type;
    if (!byType.has(t)) byType.set(t, []);
    byType.get(t).push(ei);
  });
  for (const [t, eis] of byType) {
    const pts = [];
    for (const ei of eis) {
      pts.push(new THREE.Vector3(...posOf(scene.edges[ei].s)),
               new THREE.Vector3(...posOf(scene.edges[ei].t)));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.LineSegments(g, new THREE.LineDashedMaterial({
      color: (scene.types[t] || {}).color || "#9aa4b0",
      dashSize: 0.12 * unit, gapSize: 0.08 * unit,
    }));
    line.computeLineDistances();
    dashGroup.add(line);
  }

  // wrap (PBC) bonds: faded stubs by default, arcs on toggle
  const stubs = new THREE.InstancedMesh(
    new THREE.CylinderGeometry(1, 1, 1, lod.cyl, 1, true),
    new THREE.MeshLambertMaterial({ transparent: true, opacity: 0.45 }),
    wrapE.length * 2);
  const arcs = new THREE.Group();
  arcs.visible = false;
  wrapE.forEach((ei, k) => {
    const e = scene.edges[ei], st = typeOf(e);
    const A = new THREE.Vector3(...posOf(e.s)), B = new THREE.Vector3(...posOf(e.t));
    const w = 0.035 * unit * (st.width || 1), len = 0.35 * unit;
    [[A, B], [B, A]].forEach(([from, other], j) => {
      const dir = from.clone().sub(other).normalize();  // away from the partner
      Q.setFromUnitVectors(Y, dir);
      M.compose(from.clone().add(dir.clone().multiplyScalar(len / 2)), Q,
                new THREE.Vector3(w, len, w));
      stubs.setMatrixAt(2 * k + j, M);
      stubs.setColorAt(2 * k + j, C.set(st.color || "#9aa4b0"));
    });
    const dist = A.distanceTo(B);
    const lift = new THREE.Vector3(0, 0, 1).multiplyScalar(0.25 * dist);
    if (Math.abs(A.z - B.z) > 1e-9 * Math.max(dist, 1))
      lift.set(0.25 * dist, 0, 0);
    const mid = A.clone().add(B).multiplyScalar(0.5).add(lift);
    const curve = new THREE.QuadraticBezierCurve3(A, mid, B);
    const g = new THREE.BufferGeometry().setFromPoints(curve.getPoints(24));
    arcs.add(new THREE.Line(g, new THREE.LineBasicMaterial({
      color: st.color || "#9aa4b0", transparent: true, opacity: 0.45 })));
  });
  stubs.instanceMatrix.needsUpdate = true;

  // ---- always-on edge labels (tensor networks) -----------------------------
  const labels = new THREE.Group();
  if (scene.meta.labels === "always") {
    const cache = new Map();
    const makeSprite = (text) => {
      if (!cache.has(text)) {
        const c = document.createElement("canvas");
        const ctx = c.getContext("2d");
        ctx.font = "48px system-ui, sans-serif";
        c.width = Math.ceil(ctx.measureText(text).width) + 16;
        c.height = 64;
        const ctx2 = c.getContext("2d");
        ctx2.font = "48px system-ui, sans-serif";
        ctx2.fillStyle = "#556";
        ctx2.textBaseline = "middle";
        ctx2.fillText(text, 8, 32);
        cache.set(text, { tex: new THREE.CanvasTexture(c), w: c.width / c.height });
      }
      const { tex, w } = cache.get(text);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({
        map: tex, depthTest: false }));
      sp.scale.set(0.32 * unit * w, 0.32 * unit, 1);
      return sp;
    };
    for (const e of scene.edges) {
      if (!e.label) continue;
      const sp = makeSprite(String(e.label));
      const a = posOf(e.s), b = posOf(e.t);
      sp.position.set((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                      (a[2] + b[2]) / 2 + 0.12 * unit);
      labels.add(sp);
    }
  }

  // ---- vectors (arrows): instanced shaft + instanced head ------------------
  const hasVec = scene.nodes.some((n) => Array.isArray(n.vector))
    || ((scene.frames || {}).vectors || []).length > 0;
  let vmax = 1e-12;
  const norm = (v) => Math.hypot(v[0], v[1], v[2]);
  for (const n of scene.nodes) if (Array.isArray(n.vector)) vmax = Math.max(vmax, norm(n.vector));
  for (const fr of (scene.frames || {}).vectors || [])
    for (const v of fr) vmax = Math.max(vmax, norm(v));
  const shafts = new THREE.InstancedMesh(
    new THREE.CylinderGeometry(1, 1, 1, 6, 1, true),
    new THREE.MeshLambertMaterial({ color: ACCENT }), hasVec ? scene.nodes.length : 0);
  const heads = new THREE.InstancedMesh(
    new THREE.ConeGeometry(1, 1, 8),
    new THREE.MeshLambertMaterial({ color: ACCENT }), hasVec ? scene.nodes.length : 0);
  const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);

  function setVectors(vecs) {                           // vecs: per-node [x,y,z] or null
    if (!hasVec) return;
    scene.nodes.forEach((n, i) => {
      const v = vecs ? vecs[i] : n.vector;
      if (!Array.isArray(v) || norm(v) < 1e-12) {
        shafts.setMatrixAt(i, ZERO); heads.setMatrixAt(i, ZERO); return;
      }
      const L = 0.8 * unit * (norm(v) / vmax);
      const dir = new THREE.Vector3(...v).normalize();
      Q.setFromUnitVectors(Y, dir);
      const base = new THREE.Vector3(...n.pos);
      M.compose(base.clone().add(dir.clone().multiplyScalar(0.5 * 0.72 * L)), Q,
                new THREE.Vector3(0.03 * unit, 0.72 * L, 0.03 * unit));
      shafts.setMatrixAt(i, M);
      M.compose(base.clone().add(dir.clone().multiplyScalar(0.72 * L + 0.14 * L)), Q,
                new THREE.Vector3(0.09 * unit, 0.28 * L, 0.09 * unit));
      heads.setMatrixAt(i, M);
    });
    shafts.instanceMatrix.needsUpdate = true;
    heads.instanceMatrix.needsUpdate = true;
  }

  // ---- painting (colors + value-driven sizes) ------------------------------
  let highlighted = null;                               // node array index or null
  let curNodeVals = null, curEdgeVals = null;           // last frame overrides

  function incident(ni) {
    const set = new Set();
    if (ni === null) return set;
    const id = scene.nodes[ni].id;
    scene.edges.forEach((e, i) => { if (e.s === id || e.t === id) set.add(i); });
    return set;
  }

  function paint() {
    const hot = incident(highlighted);
    solidN.forEach((ni, k) => {
      const val = curNodeVals ? curNodeVals[ni] : scene.nodes[ni].value;
      if (Number.isFinite(val))
        C.setRGB(...valueToColor(val, nodeDomain, scene.encode.nodes.colormap));
      else C.copy(NODE_BASE);
      if (highlighted !== null)
        ni === highlighted ? C.copy(ACCENT) : C.multiplyScalar(DIM);
      nodes.setColorAt(k, C);
      if (scene.encode.nodes.sizeByValue) {
        const r = nodeRadius(ni, val);
        M.compose(V.set(...scene.nodes[ni].pos), Q.identity(),
                  new THREE.Vector3(r, r, r));
        nodes.setMatrixAt(k, M);
      }
    });
    if (nodes.instanceColor) nodes.instanceColor.needsUpdate = true;
    if (scene.encode.nodes.sizeByValue) nodes.instanceMatrix.needsUpdate = true;
    solidE.forEach((ei, k) => {
      const e = scene.edges[ei];
      const val = curEdgeVals ? curEdgeVals[ei] : e.value;
      if (Number.isFinite(val))
        C.setRGB(...valueToColor(val, edgeDomain, scene.encode.edges.colormap));
      else C.copy(typeColor.get(e.type) || EDGE_BASE);
      if (highlighted !== null)
        hot.has(ei) ? C.copy(ACCENT) : C.multiplyScalar(DIM);
      edges.setColorAt(k, C);
      if (scene.encode.edges.widthByValue) placeEdge(k, ei, val);
    });
    if (edges.instanceColor) edges.instanceColor.needsUpdate = true;
    if (scene.encode.edges.widthByValue) edges.instanceMatrix.needsUpdate = true;
  }

  // initial pass: radii need base values even without sizeByValue
  solidN.forEach((ni, k) => {
    const r = nodeRadius(ni, scene.nodes[ni].value);
    M.compose(V.set(...scene.nodes[ni].pos), Q.identity(),
              new THREE.Vector3(r, r, r));
    nodes.setMatrixAt(k, M);
  });
  nodes.instanceMatrix.needsUpdate = true;
  paint();
  setVectors(null);

  group.add(nodes, edges, dashGroup, stubs, arcs, labels, shafts, heads);
  const bounds = new THREE.Box3();
  for (const n of scene.nodes) bounds.expandByPoint(V.set(...n.pos));

  return {
    group, unit, bounds, nodeDomain, edgeDomain,
    setNodeValues(vals) { curNodeVals = vals; paint();
      if (this.onFrameValues) this.onFrameValues(curNodeVals, curEdgeVals); },
    setEdgeValues(vals) { curEdgeVals = vals; paint();
      if (this.onFrameValues) this.onFrameValues(curNodeVals, curEdgeVals); },
    setVectors,
    setHighlight(ni) { highlighted = ni; paint(); },
    setWrapMode(mode) { stubs.visible = mode !== "arc"; arcs.visible = mode === "arc"; },
    pickables: () => [
      { mesh: nodes, kind: "node", map: (i) => solidN[i] },
      { mesh: edges, kind: "edge", map: (i) => solidE[i] },
    ],
  };
}
