// Scene schema: validation, defaults, and pure helpers. No three.js imports —
// this module is imported directly by `node --test`.

export const LIMITS = { degrade: 50000, refuse: 200000 };

const ENCODE_DEFAULTS = {
  nodes: { colormap: "diverging", domain: null, sizeByValue: false },
  edges: { colormap: "diverging", domain: null, widthByValue: false },
};

export function validateScene(scene) {
  if (!scene || typeof scene !== "object" || Array.isArray(scene))
    return ["scene: not a JSON object"];
  const errors = [];
  if (!Array.isArray(scene.nodes) || scene.nodes.length === 0)
    errors.push("nodes: must be a non-empty array");
  if (scene.edges !== undefined && !Array.isArray(scene.edges))
    errors.push("edges: must be an array");
  if (errors.length) return errors;

  const ids = new Set();
  scene.nodes.forEach((n, i) => {
    if (n.id === undefined) errors.push(`nodes[${i}]: missing id`);
    else if (ids.has(n.id)) errors.push(`nodes[${i}]: duplicate id ${JSON.stringify(n.id)}`);
    else ids.add(n.id);
    if (!Array.isArray(n.pos) || n.pos.length !== 3 || !n.pos.every(Number.isFinite))
      errors.push(`nodes[${i}]: pos must be three finite numbers`);
  });
  (scene.edges || []).forEach((e, i) => {
    if (!ids.has(e.s)) errors.push(`edges[${i}]: unknown source ${JSON.stringify(e.s)}`);
    if (!ids.has(e.t)) errors.push(`edges[${i}]: unknown target ${JSON.stringify(e.t)}`);
  });

  const f = scene.frames;
  if (f) {
    const counts = { nodes: scene.nodes.length, vectors: scene.nodes.length,
                     edges: (scene.edges || []).length };
    let nframes = null;
    for (const key of ["nodes", "vectors", "edges"]) {
      const seq = f[key];
      if (seq === undefined) continue;
      if (!Array.isArray(seq) || seq.length === 0) {
        errors.push(`frames.${key}: must be a non-empty array of frames`);
        continue;
      }
      if (nframes === null) nframes = seq.length;
      else if (seq.length !== nframes)
        errors.push(`frames.${key}: ${seq.length} frames, others have ${nframes}`);
      seq.forEach((arr, t) => {
        if (!Array.isArray(arr) || arr.length !== counts[key])
          errors.push(`frames.${key}[${t}]: length ${arr && arr.length}, expected ${counts[key]}`);
      });
    }
    if (nframes === null)
      errors.push("frames: needs at least one of nodes/vectors/edges");
    else if (f.labels && f.labels.length !== nframes)
      errors.push(`frames.labels: ${f.labels.length} labels, expected ${nframes}`);
  }

  const total = scene.nodes.length + (scene.edges || []).length;
  if (total > LIMITS.refuse)
    errors.push(`scene too large: ${total} instances (limit ${LIMITS.refuse}); coarsen the data`);
  return errors;
}

export function applyDefaults(scene) {
  const s = {
    meta: {}, camera: {}, types: {}, ...scene,
    camera: { up: "z", view: "auto", ...scene.camera },
  };
  s.encode = {
    nodes: { ...ENCODE_DEFAULTS.nodes, ...(scene.encode || {}).nodes },
    edges: { ...ENCODE_DEFAULTS.edges, ...(scene.encode || {}).edges },
  };
  s.nodes = scene.nodes.map((n) => ({ size: 1, group: "", virtual: false, ...n }));
  s.edges = (scene.edges || []).map((e) => ({ type: "", wrap: false, ...e }));
  return s;
}

export function nodeIndex(scene) {
  const m = new Map();
  scene.nodes.forEach((n, i) => m.set(n.id, i));
  return m;
}

export function isPlanar(nodes) {
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (const n of nodes)
    for (let k = 0; k < 3; k++) {
      lo[k] = Math.min(lo[k], n.pos[k]);
      hi[k] = Math.max(hi[k], n.pos[k]);
    }
  const diag = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  return hi[2] - lo[2] <= 1e-6 * Math.max(diag, 1);
}

export function medianEdgeLength(scene, index = nodeIndex(scene)) {
  const ls = scene.edges
    .filter((e) => !e.wrap)
    .map((e) => {
      const a = scene.nodes[index.get(e.s)].pos, b = scene.nodes[index.get(e.t)].pos;
      return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
    })
    .sort((x, y) => x - y);
  return ls.length ? ls[Math.floor(ls.length / 2)] : 1;
}
