// Value → color mapping and the HTML legend. Pure module: no three.js, no DOM
// objects — legendHTML returns a string.

export const COLORMAPS = {
  diverging: ["#2166ac", "#f7f7f7", "#b2182b"],
  sequential: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
};

function hex2rgb(h) {
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
}

export function valueToColor(v, domain, name = "diverging") {
  const stops = (COLORMAPS[name] || COLORMAPS.diverging).map(hex2rgb);
  const [lo, hi] = domain;
  let t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
  t = Math.min(1, Math.max(0, t));
  const x = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x)), u = x - i;
  return stops[i].map((c, k) => c + u * (stops[i + 1][k] - c));
}

export function collectValues(scene, kind) {
  const out = [];
  for (const o of scene[kind]) if (Number.isFinite(o.value)) out.push(o.value);
  for (const arr of (scene.frames || {})[kind] || [])
    for (const v of arr) if (Number.isFinite(v)) out.push(v);
  return out;
}

export function autoDomain(values, symmetric) {
  if (!values.length) return [0, 1];
  let lo = Infinity, hi = -Infinity;
  for (const v of values) {                            // loop, not Math.min(...):
    if (v < lo) lo = v;                                // spread blows the stack
    if (v > hi) hi = v;                                // on ~200k values
  }
  if (symmetric) {
    const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
    return [-m, m];
  }
  return lo === hi ? [lo - 0.5, hi + 0.5] : [lo, hi];
}

export function resolveDomain(scene, kind) {
  const enc = scene.encode[kind];
  if (Array.isArray(enc.domain) && enc.domain.length === 2) return enc.domain;
  return autoDomain(collectValues(scene, kind), enc.colormap === "diverging");
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmt(x) {
  return Number.isInteger(x) ? String(x) : x.toPrecision(3);
}

function colorbar(title, domain, name) {
  const stops = COLORMAPS[name] || COLORMAPS.diverging;
  const grad = `linear-gradient(to right, ${stops.join(", ")})`;
  return `<div class="lattix-cbar"><span class="t">${esc(title)}</span>
<span class="lo">${fmt(domain[0])}</span>
<span class="bar" style="background:${grad}"></span>
<span class="hi">${fmt(domain[1])}</span></div>`;
}

export function legendHTML(scene, nodeDomain, edgeDomain) {
  let h = "";
  if (collectValues(scene, "nodes").length)
    h += colorbar("sites", nodeDomain, scene.encode.nodes.colormap);
  if (collectValues(scene, "edges").length)
    h += colorbar("bonds", edgeDomain, scene.encode.edges.colormap);
  for (const [name, st] of Object.entries(scene.types)) {
    const border = st.dash ? "dashed" : "solid";
    h += `<div class="lattix-type"><span class="sw" style="border-top:${
      Math.max(2, st.width || 1) + "px"} ${border} ${esc(st.color || "#9aa4b0")}"></span>${esc(name)}</div>`;
  }
  return h && `<div class="lattix-legend">${h}</div>`;
}
