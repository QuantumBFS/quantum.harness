// Entry point. Bundled by esbuild as an IIFE with global name `Lattix`.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { validateScene, applyDefaults, isPlanar } from "./scene.js";
import { legendHTML } from "./overlays.js";
import { buildLattice } from "./geometry.js";
import { makeAnimationBar } from "./animation.js";
import { attachPicking } from "./controls.js";

const CSS = `
.lattix{position:relative}
.lattix-view{position:relative;width:100%;border:1px solid rgba(128,128,128,.25);
  border-radius:8px;overflow:hidden}
.lattix-view canvas{display:block}
.lattix-ui{position:absolute;top:8px;right:8px;display:flex;flex-direction:column;
  gap:6px;align-items:flex-end;font:12px/1.35 system-ui,sans-serif;z-index:2}
.lattix-legend{background:rgba(255,255,255,.85);border-radius:6px;padding:6px 8px;
  color:#333}
.lattix-cbar{display:flex;gap:6px;align-items:center}
.lattix-cbar .bar{display:inline-block;width:90px;height:10px;border-radius:3px}
.lattix-cbar .t{min-width:34px;font-weight:600}
.lattix-type{display:flex;gap:6px;align-items:center;margin-top:3px}
.lattix-type .sw{display:inline-block;width:26px;height:0}
.lattix-btns{display:flex;gap:4px}
.lattix-btns button{font:11px system-ui,sans-serif;padding:3px 8px;border-radius:5px;
  border:1px solid rgba(128,128,128,.4);background:rgba(255,255,255,.85);
  color:#333;cursor:pointer}
.lattix-btns button.on{background:#e8a33d;border-color:#e8a33d;color:#222}
.lattix-tip{position:fixed;pointer-events:none;background:rgba(20,22,26,.92);
  color:#eee;font:12px/1.4 ui-monospace,monospace;padding:5px 8px;border-radius:5px;
  z-index:10;display:none;white-space:pre}
.lattix-error{border:1px solid #c0504d;border-radius:8px;padding:10px 14px;
  font:13px/1.5 system-ui,sans-serif;color:#c0504d;background:rgba(192,80,77,.06)}
.lattix-error ul{margin:6px 0 0;padding-left:18px}
.lattix-bar{position:absolute;left:8px;right:8px;bottom:8px;display:flex;gap:8px;
  align-items:center;background:rgba(255,255,255,.85);border-radius:6px;
  padding:4px 8px;font:12px system-ui,sans-serif;color:#333;z-index:2}
.lattix-bar input[type=range]{flex:1}
@media (prefers-color-scheme: dark){
  .lattix-legend,.lattix-btns button,.lattix-bar{background:rgba(30,33,38,.85);color:#ddd}
}
@media print{.lattix-view,.lattix-ui{display:none!important}}
@media print{.lattix-poster{display:block!important}}
`;

function injectCSS() {
  if (document.getElementById("lattix-css")) return;
  const s = document.createElement("style");
  s.id = "lattix-css";
  s.textContent = CSS;
  document.head.appendChild(s);
}

function errorBox(el, errors) {
  const first = errors.slice(0, 8).map((e) => `<li>${e
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")}</li>`).join("");
  const more = errors.length > 8 ? `<div>… and ${errors.length - 8} more</div>` : "";
  el.innerHTML = `<div class="lattix-error"><b>lattix: invalid scene</b>
<ul>${first}</ul>${more}</div>`;
}

export function mount(el, sceneJson) {
  injectCSS();
  const errors = validateScene(sceneJson);
  if (errors.length) { errorBox(el, errors); return { dispose() {} }; }
  let view = null;
  try {
  const scene = applyDefaults(sceneJson);
  const api = buildLattice(scene);

  const height = parseInt(el.dataset.height || "420", 10) || 420;
  view = document.createElement("div");
  view.className = "lattix-view";
  view.style.height = `${height}px`;
  el.appendChild(view);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  view.appendChild(renderer.domElement);
  const scene3 = new THREE.Scene();
  scene3.add(api.group);
  scene3.add(new THREE.AmbientLight(0xffffff, 0.85));
  const d1 = new THREE.DirectionalLight(0xffffff, 0.7); d1.position.set(1, 2, 3);
  const d2 = new THREE.DirectionalLight(0xffffff, 0.35); d2.position.set(-2, -1, -2);
  scene3.add(d1, d2);

  const center = api.bounds.getCenter(new THREE.Vector3());
  const radius = Math.max(api.bounds.getSize(new THREE.Vector3()).length() / 2, api.unit);
  const planar = isPlanar(scene.nodes);
  let camera, controls;

  function setCameraMode(mode) {                        // "2d" | "3d"
    if (controls) controls.dispose();
    const w = view.clientWidth || 600, aspect = w / height;
    if (mode === "2d") {
      const s = radius * 1.15;
      camera = new THREE.OrthographicCamera(-s * aspect, s * aspect, s, -s,
        0.1, 100 * radius);
      camera.position.copy(center).add(new THREE.Vector3(0, 0, 10 * radius));
    } else {
      camera = new THREE.PerspectiveCamera(40, aspect, radius / 100, radius * 100);
      const dist = radius / Math.tan((40 / 2) * Math.PI / 180) * 1.35;
      camera.position.copy(center).add(
        new THREE.Vector3(1.1, -1.4, 0.9).normalize().multiplyScalar(dist));
    }
    camera.up.set(0, mode === "2d" ? 1 : 0, mode === "2d" ? 0 : 1);
    camera.lookAt(center);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.enableRotate = mode !== "2d";
  }
  setCameraMode(planar ? "2d" : "3d");

  // ---- overlay UI ----------------------------------------------------------
  const ui = document.createElement("div");
  ui.className = "lattix-ui";
  ui.innerHTML = legendHTML(scene, api.nodeDomain, api.edgeDomain);
  const btns = document.createElement("div");
  btns.className = "lattix-btns";
  if (planar) {
    const b3d = document.createElement("button");
    b3d.textContent = "3D";
    b3d.onclick = () => {
      const on = b3d.classList.toggle("on");
      setCameraMode(on ? "3d" : "2d");
    };
    btns.appendChild(b3d);
  }
  if (scene.edges.some((e) => e.wrap)) {
    const bw = document.createElement("button");
    bw.textContent = "PBC arcs";
    bw.onclick = () => {
      api.setWrapMode(bw.classList.toggle("on") ? "arc" : "stub");
    };
    btns.appendChild(bw);
  }
  const bp = document.createElement("button");
  bp.textContent = "PNG";
  bp.onclick = () => {
    renderer.render(scene3, camera);                    // fresh buffer, same tick
    const a = document.createElement("a");
    a.href = renderer.domElement.toDataURL("image/png");
    a.download = "lattice.png";
    a.click();
  };
  btns.appendChild(bp);
  ui.appendChild(btns);
  view.appendChild(ui);

  const picking = attachPicking(view, renderer, () => camera, scene, api);

  let bar = null;
  if (scene.frames) bar = makeAnimationBar(view, scene, api);

  // Mount succeeded: hide the pre-mount poster (kept visible in print via CSS).
  el.querySelectorAll(".lattix-poster").forEach((p) => { p.style.display = "none"; });

  // ---- loop + resize -------------------------------------------------------
  let dead = false;
  function resize() {
    const w = view.clientWidth || 600;
    renderer.setSize(w, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    if (camera.isPerspectiveCamera) camera.aspect = w / height;
    else {
      const s = radius * 1.15, aspect = w / height;
      camera.left = -s * aspect; camera.right = s * aspect;
    }
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(view);
  resize();
  (function loop() {
    if (dead) return;
    requestAnimationFrame(loop);
    controls.update();
    renderer.render(scene3, camera);
  })();

  return {
    api, scene, setCameraMode,
    dispose() {
      dead = true;
      ro.disconnect();
      picking.dispose();
      if (bar) bar.dispose();
      renderer.dispose();
      el.removeChild(view);
    },
  };
  } catch (err) {
    if (view && view.parentNode === el) el.removeChild(view);
    errorBox(el, [`viewer failed: ${err.message}`]);
    return { dispose() {} };
  }
}

export function mountAll(root = document) {
  injectCSS();
  root.querySelectorAll(".lattix").forEach((div) => {
    if (div.dataset.lattixMounted) return;
    const tag = div.querySelector('script[type="application/json"]');
    if (!tag) return;
    div.dataset.lattixMounted = "1";
    let scene;
    try { scene = JSON.parse(tag.textContent); }
    catch (e) { errorBox(div, [`scene JSON does not parse: ${e.message}`]); return; }
    try { mount(div, scene); }
    catch (e) { errorBox(div, [`viewer failed: ${e.message}`]); }
  });
}
