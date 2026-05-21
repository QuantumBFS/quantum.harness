// Minimal 404 — the harness static-exports a single page, so /_not-found is
// only generated to satisfy Next.js's prerender step. Keeping this tiny
// avoids dragging the layout's data-dependent imports into the 404 graph.
export default function NotFound() {
  return null;
}
