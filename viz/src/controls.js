// Raycast picking against the instanced meshes: hover tooltip + click highlight.
// Dashed, wrap, and arrow objects are not pickable (v1).
import * as THREE from "three";

function describe(scene, hit) {
  if (hit.kind === "node") {
    const n = scene.nodes[hit.index];
    return [
      `site ${n.id}`,
      n.group && `group  ${n.group}`,
      n.label && `label  ${n.label}`,
      Number.isFinite(hit.value) && `value  ${hit.value.toPrecision(4)}`,
    ].filter(Boolean).join("\n");
  }
  const e = scene.edges[hit.index];
  return [
    `bond ${e.s} – ${e.t}${e.type ? `  (${e.type})` : ""}`,
    e.label && `label  ${e.label}`,
    Number.isFinite(hit.value) && `value  ${hit.value.toPrecision(4)}`,
  ].filter(Boolean).join("\n");
}

export function attachPicking(view, renderer, getCamera, scene, api) {
  const tip = document.createElement("div");
  tip.className = "lattix-tip";
  document.body.appendChild(tip);
  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2();
  let current = { nodeVals: null, edgeVals: null };
  api.onFrameValues = (nv, ev) => { current = { nodeVals: nv, edgeVals: ev }; };

  function cast(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1,
            -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, getCamera());
    for (const p of api.pickables()) {
      const hits = ray.intersectObject(p.mesh);
      if (hits.length) {
        const index = p.map(hits[0].instanceId);
        const vals = p.kind === "node" ? current.nodeVals : current.edgeVals;
        const base = p.kind === "node" ? scene.nodes : scene.edges;
        return { kind: p.kind, index,
                 value: vals ? vals[index] : base[index].value };
      }
    }
    return null;
  }

  function onMove(ev) {
    const hit = cast(ev);
    if (!hit) { tip.style.display = "none"; return; }
    tip.textContent = describe(scene, hit);
    tip.style.display = "block";
    tip.style.left = `${ev.clientX + 14}px`;
    tip.style.top = `${ev.clientY + 10}px`;
  }
  function onLeave() {
    tip.style.display = "none";
  }
  let selected = null;
  function onClick(ev) {
    const hit = cast(ev);
    selected = hit && hit.kind === "node" && hit.index !== selected
      ? hit.index : null;
    api.setHighlight(selected);
  }
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerleave", onLeave);
  renderer.domElement.addEventListener("click", onClick);

  return {
    dispose() {
      tip.remove();
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      renderer.domElement.removeEventListener("click", onClick);
    },
  };
}
