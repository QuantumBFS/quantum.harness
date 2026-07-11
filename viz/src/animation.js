// Frame scrubber. Frames are values-only; every update goes through the
// geometry api's setters (instance attribute writes, no scene rebuild).
import { sampleFrames } from "./frames.js";

const BASE_FPS = 8;

export function makeAnimationBar(view, scene, api) {
  const f = scene.frames;
  const n = (f.nodes || f.vectors || f.edges).length;
  const bar = document.createElement("div");
  bar.className = "lattix-bar";
  bar.innerHTML = `
<button class="play">▶</button>
<input class="pos" type="range" min="0" max="${n - 1}" step="1" value="0">
<span class="lbl"></span>
<select class="spd"><option>0.5</option><option selected>1</option>
<option>2</option><option>4</option></select>
<label><input class="smooth" type="checkbox"> smooth</label>`;
  view.appendChild(bar);

  const play = bar.querySelector(".play"), pos = bar.querySelector(".pos");
  const lbl = bar.querySelector(".lbl"), spd = bar.querySelector(".spd");
  const smooth = bar.querySelector(".smooth");
  let t = 0, playing = false, raf = 0, prev = 0;

  function update() {
    const interp = smooth.checked;
    if (f.nodes) api.setNodeValues(sampleFrames(f.nodes, t, interp));
    if (f.edges) api.setEdgeValues(sampleFrames(f.edges, t, interp));
    if (f.vectors) api.setVectors(sampleFrames(f.vectors, t, interp));
    pos.value = t;
    lbl.textContent = (f.labels && f.labels[Math.round(t)])
      || `frame ${Math.round(t)}/${n - 1}`;
  }

  function tick(now) {
    if (!playing) return;
    t += ((now - prev) / 1000) * BASE_FPS * parseFloat(spd.value);
    prev = now;
    if (t > n - 1) t = 0;                               // loop
    update();
    raf = requestAnimationFrame(tick);
  }

  play.onclick = () => {
    playing = !playing;
    play.textContent = playing ? "⏸" : "▶";
    if (playing) { prev = performance.now(); raf = requestAnimationFrame(tick); }
    else cancelAnimationFrame(raf);
  };
  pos.oninput = () => { t = parseFloat(pos.value); update(); };
  smooth.onchange = () => { pos.step = smooth.checked ? "0.01" : "1"; update(); };
  update();

  return { dispose() { playing = false; cancelAnimationFrame(raf); bar.remove(); } };
}
