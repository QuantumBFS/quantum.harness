// Pure frame sampling for the animation scrubber. Frames are values-only:
// geometry never changes, so a frame is one dense array aligned with
// scene.nodes / scene.edges order.

function lerp(a, b, u) {
  return Array.isArray(a) ? a.map((c, k) => c + u * (b[k] - c)) : a + u * (b - a);
}

export function sampleFrames(seq, t, interpolate) {
  if (!seq || !seq.length) return null;
  const last = seq.length - 1;
  const tc = Math.max(0, Math.min(last, t));
  const i = Math.floor(tc);
  if (!interpolate || i === last || tc === i) return seq[i];
  return seq[i].map((a, k) => lerp(a, seq[i + 1][k], tc - i));
}
