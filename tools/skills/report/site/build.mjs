#!/usr/bin/env node
// Orchestrator for /report's HTML deliverable.
//
//   node tools/skills/report/site/build.mjs <run-dir> --stage <plan|append>
//
// Reads:  <run-dir>/protocol.toml, editorial.json, sources/paper.md,
//         cells/*/manifest.json, figs/*.{png,json}.
// Writes: site/lib/runs/<run-id>.ts        (per-run typed data),
//         site/content/<run-id>.mdx        (per-run MDX shell),
//         site/lib/current-report.tsx      (build-generated wrapper:
//                                           static-imports the per-run
//                                           MDX + re-exports `meta`),
//         <run-dir>/report_<run-id>_<YYYY-MM-DD>.html,
//         <run-dir>/report_latest.html     (symlink).
//
// Pipeline: parse → materialize typed data → write per-run files
//           → write current-report wrapper → next build (static export)
//           → inline assets → write HTML.
//
// page.tsx is a tracked, stable file that imports `Content` and `meta`
// from `@/lib/current-report`. Build NEVER overwrites app/page.tsx.
//
// Run-id sanitization: anything outside [A-Za-z0-9_-] is collapsed to `_`
// so the run-id is safe in import paths and filenames.
//
// Single source of truth for the data shape: tools/skills/report/site/lib/types.ts.

import { argv, exit, stderr, stdout } from 'node:process';
import { readFile, writeFile, readdir, stat, mkdir, unlink, symlink, access } from 'node:fs/promises';
import { existsSync, statSync, readFileSync } from 'node:fs';
import { resolve, join, dirname, basename, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import toml from '@iarna/toml';
import { chromium } from 'playwright';

// ─── paths ──────────────────────────────────────────────────────────────────
const SITE_DIR  = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SITE_DIR, '..', '..', '..', '..');
const SOFT_CAP  = 3_000_000;
const HARD_CAP  = 10_000_000;

// ─── cli ────────────────────────────────────────────────────────────────────
function parseArgs() {
  const args = argv.slice(2);
  if (args.length < 1) usage(1);
  const runDir = resolve(args[0]);
  let stage = 'append';
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--stage') stage = args[++i];
    else if (args[i] === '-h' || args[i] === '--help') usage(0);
    else { stderr.write(`build: unknown arg ${args[i]}\n`); exit(2); }
  }
  if (stage !== 'plan' && stage !== 'append') {
    stderr.write(`build: --stage must be 'plan' or 'append' (got: ${stage})\n`);
    exit(2);
  }
  return { runDir, stage };
}
function usage(code) {
  stdout.write(
    `Usage: node build.mjs <run-dir> --stage <plan|append>\n` +
    `       <run-dir>  Path to a reproduction run directory.\n` +
    `       --stage    'plan' before compute (Problem + Methodology only) or\n` +
    `                  'append' after close (all three sections). Default: append.\n`
  );
  exit(code);
}

// ─── helpers ────────────────────────────────────────────────────────────────
async function readJson(p) { return JSON.parse(await readFile(p, 'utf8')); }
async function readToml(p) { return toml.parse(await readFile(p, 'utf8')); }
function exists(p)        { return existsSync(p); }
function todayISO()       { return new Date().toISOString().slice(0, 10); }

// Sanitize a run id for safe use in import paths and filenames.
// Collapses anything outside [A-Za-z0-9_-] to `_`; trims leading/trailing
// underscores; collapses runs of underscores. Empty result → `report`.
function sanitizeRunId(raw) {
  const s = String(raw ?? '')
    .replace(/[^A-Za-z0-9_-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
  return s || 'report';
}

function dataUrl(absPath) {
  const buf = readFileSync(absPath);
  const ext = absPath.toLowerCase().split('.').pop();
  const mime = MIME[ext] ?? 'application/octet-stream';
  return `data:${mime};base64,${buf.toString('base64')}`;
}
const MIME = {
  png:  'image/png',  jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp',
  svg:  'image/svg+xml', gif: 'image/gif',
  woff: 'font/woff', woff2: 'font/woff2', ttf: 'font/ttf', otf: 'font/otf',
  json: 'application/json', css: 'text/css', js: 'text/javascript',
};

// Read every cells/<id>/manifest.json. Returns { count, wall_hours }.
async function summarizeCells(runDir) {
  const cellsDir = join(runDir, 'cells');
  if (!exists(cellsDir)) return { count: 0, wall_hours: 0 };
  let count = 0, wallSec = 0;
  const entries = await readdir(cellsDir, { withFileTypes: true });
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    const m = join(cellsDir, e.name, 'manifest.json');
    if (!exists(m)) continue;
    try {
      const d = JSON.parse(await readFile(m, 'utf8'));
      count++;
      wallSec += Number(d.wall_seconds ?? 0);
    } catch { /* skip parse-failed */ }
  }
  return { count, wall_hours: wallSec / 3600 };
}

// ─── load run ───────────────────────────────────────────────────────────────
async function loadRun({ runDir, stage }) {
  const protocolPath = join(runDir, 'protocol.toml');
  if (!exists(protocolPath)) {
    stderr.write(`build: protocol.toml not found at ${protocolPath}\n`); exit(1);
  }
  const protocol  = await readToml(protocolPath);
  const editorial = exists(join(runDir, 'editorial.json'))
    ? await readJson(join(runDir, 'editorial.json'))
    : {};

  const artifact = protocol.artifact ?? {};
  const runId    = artifact.run_id ?? basename(runDir);
  const paperId  = artifact.paper ?? '';
  const url      = artifact.url ?? null;

  const { count: nCells, wall_hours: wallH } = await summarizeCells(runDir);
  const today  = todayISO();

  // Problem ----------------------------------------------------------------
  const problemBlocks = (editorial.problem?.blocks ?? []).map(b => ({
    kind:  b.kind ?? 'background',
    text:  b.text ?? '',
    cite:  b.cite ?? null,
    scope: b.scope ?? null,
  }));

  // Methodology -----------------------------------------------------------
  // Carry the visual-anchor fields (equation, key_facts, dimension, summary,
  // delta_from_paper, headline, badge, operational, label, scope_label,
  // text_tex, values_tex, …) through verbatim when the polish step emitted
  // them. Renderer falls back to paper/ours prose when absent.
  const m = editorial.methodology ?? {};
  const models = (m.models ?? []).map(x => ({
    id: x.id, name: x.name ?? x.id,
    paper: { text: x.paper?.text ?? '', cite: x.paper?.cite ?? null },
    ours:  { text: x.ours?.text  ?? '', cite: x.ours?.cite  ?? null },
    equation:         x.equation ?? null,
    summary:          x.summary  ?? null,
    key_facts:        x.key_facts ?? [],
    dimension:        x.dimension ?? null,
    delta_from_paper: x.delta_from_paper ?? null,
  }));
  const methods = (m.methods ?? []).map(x => ({
    id: x.id, name: x.name ?? x.id,
    paper: { text: x.paper?.text ?? '', cite: x.paper?.cite ?? null },
    ours:  { text: x.ours?.text  ?? '', cite: x.ours?.cite  ?? null },
    deviation:   x.deviation ?? null,
    headline:    x.headline  ?? null,
    badge:       x.badge     ?? null,
    operational: x.operational ?? [],
  }));
  const params = (m.params ?? []).map(p => ({
    name: p.name, values: p.values ?? [], scope: p.scope ?? null,
    why: { text: p.why?.text ?? '', cite: p.why?.cite ?? null },
    label:          p.label ?? null,
    scope_label:    p.scope_label ?? null,
    values_tex:     p.values_tex ?? null,
    values_unicode: p.values_unicode ?? null,
  }));
  const assumptions = (m.assumptions ?? []).map(a => ({
    text: a.text ?? '', scope: a.scope ?? null,
    why: { text: a.why?.text ?? '', cite: a.why?.cite ?? null },
    label:         a.label ?? null,
    text_tex:      a.text_tex ?? null,
    text_unicode:  a.text_unicode ?? null,
    scope_label:   a.scope_label ?? null,
  }));
  const kb_refs = m.kb_refs ?? [];
  const expected_output_summary = m.expected_output_summary ?? '';
  // Deviation id → { statement, why } so methodology cards can surface the
  // full reason without leaking the raw id (checklist A1). protocol.toml's
  // historical field is `reason`; SKILL.md schema names it `why` — accept
  // both so the `Why?` line is never empty when one is filled.
  const deviations_by_id = Object.fromEntries(
    (protocol.deviations ?? []).map(d => [d.id, {
      statement: d.statement ?? '',
      why:       d.why ?? d.reason ?? '',
    }])
  );

  // Results ---------------------------------------------------------------
  const verdict = {
    status: editorial.verdict?.status ?? (protocol.deviations?.length ? 'partial' : 'unknown'),
    label:  editorial.verdict?.label  ?? (protocol.deviations?.length ? 'Partial' : 'Pending'),
    detail: editorial.verdict?.detail ?? '',
    cite:   editorial.verdict?.cite   ?? null,
    key_results: editorial.verdict?.key_results ?? [],
  };
  const chips = (editorial.chips ?? []).map(c => ({
    id: c.id, label: c.label ?? c.id, popover: c.popover ?? '',
    status: c.status ?? 'muted', cite: c.cite ?? null,
  }));

  const figures = await Promise.all((protocol.figures ?? []).map(async f => {
    const paperPath = resolveFigPath(f.paper_path, runDir);
    const oursPath  = join(runDir, 'figs', `${f.id}.png`);
    const ed = (editorial.figures ?? []).find(e => e.id === f.id || e.label === f.id) ?? {};
    return {
      id: f.id,
      display_id: f.display_id ?? null,
      caption_paper: ed.caption_paper ?? '',
      caption_ours:  ed.caption_ours  ?? '',
      paper_attribution: f.paper_attribution ?? null,
      paper_data_url: exists(paperPath) ? dataUrl(paperPath) : '',
      ours_data_url:  exists(oursPath)  ? dataUrl(oursPath)  : '',
    };
  }));

  const deviations = (protocol.deviations ?? []).map(d => {
    const ed = (editorial.deviations ?? []).find(e => e.id === d.id) ?? {};
    return {
      id: d.id,
      statement: d.statement ?? '',
      // Accept both `why` (schema-canonical) and `reason` (historical protocol field).
      why:    d.why ?? d.reason ?? '',
      reason: d.reason ?? d.why ?? null,
      kind:   d.kind ?? null,
      from:   d.from ?? null,
      to:     d.to ?? null,
      // Polish-step emitted Results-side fields (all optional):
      display_label:         ed.display_label ?? null,
      discrepancy_paragraph: ed.discrepancy_paragraph ?? null,
      headline:              ed.headline ?? null,
      paper_did:             ed.paper_did ?? null,
      ours_did:              ed.ours_did ?? null,
      cite:                  ed.cite ?? null,
    };
  });

  const provenance = {
    run:     { run_id: runId, n_cells: nCells, total_wall_h: wallH },
    cluster: artifact.cluster ?? '',
    source:  { paper_id: paperId, url },
    harness: { report_id: runId, date: today },
  };

  const pending             = stage === 'plan';
  const wallClockEstimate   = protocol.budgets?.wall_clock ?? '';
  const expectedOutput      =
    (m.expected_output_summary ?? editorial.methodology?.expected_output_summary ?? '');

  const meta = {
    paperId,
    runId,
    title: artifact.title || `${paperId} · ${runId}`,
    description: artifact.description ?? '',
    authors: artifact.authors ?? '',
    venue: artifact.venue ?? '',
    url,
    stage,
    toc: [
      { title: 'Problem',     url: '#problem',     depth: 2 },
      { title: 'Methodology', url: '#methodology', depth: 2 },
      { title: 'Results',     url: '#results',     depth: 2 },
    ],
  };

  const headline = editorial.headline ?? { text: '', cite: null };

  return {
    meta,
    headline: { text: headline.text ?? '', cite: headline.cite ?? null },
    problem: { blocks: problemBlocks },
    methodology: { models, methods, params, assumptions, kb_refs, expected_output_summary, deviations_by_id },
    results: {
      verdict, chips, figures, deviations, provenance,
      pending, wall_clock_estimate: wallClockEstimate, expected_output: expectedOutput,
    },
    runId, today,
  };
}

function resolveFigPath(p, runDir) {
  if (!p) return '';
  if (p.startsWith('/')) return p;
  // Try repo-rooted first, then run-dir-rooted.
  const repo = join(REPO_ROOT, p);
  if (exists(repo)) return repo;
  return join(runDir, p);
}

// ─── write per-run artifacts ───────────────────────────────────────────────
// Three files per build, all keyed by the sanitized run id:
//
//   1. site/lib/runs/<slug>.ts          typed data for this run
//   2. site/content/<slug>.mdx          MDX shell that imports the data
//   3. site/lib/current-report.tsx      wrapper that statically imports the
//                                       MDX as Content + re-exports `meta`
//
// `app/page.tsx` is tracked and stable — it imports from
// `@/lib/current-report`, so the only build-time variation is which slug the
// wrapper points at. The MDX file must exist in the compile graph as a
// literal import (Next.js / @next/mdx cannot statically analyze dynamic
// MDX paths), which is exactly what `current-report.tsx` provides.

async function writeRunDataModule(slug, data) {
  const banner = `// AUTO-GENERATED by build.mjs — DO NOT EDIT BY HAND.\n` +
                 `// Source of truth: protocol.toml + editorial.json under the run dir.\n` +
                 `// Re-run \`node build.mjs <run-dir> --stage <plan|append>\` to refresh.\n\n`;
  const body =
    `import type {
  Meta, Headline, ProblemBlock, Model, Method, Param, Assumption,
  Deviation, Verdict, Chip, FigureMeta, Provenance,
} from '@/lib/types';\n\n` +
    `export const meta: Meta = ${JSON.stringify(data.meta, null, 2)};\n\n` +
    `export const headline: Headline = ${JSON.stringify(data.headline, null, 2)};\n\n` +
    `export const problem: { blocks: ProblemBlock[] } = ${JSON.stringify(data.problem, null, 2)};\n\n` +
    `export const methodology: {
  models: Model[];
  methods: Method[];
  params: Param[];
  assumptions: Assumption[];
  kb_refs: string[];
  expected_output_summary: string;
  deviations_by_id: Record<string, { statement: string; why?: string }>;
} = ${JSON.stringify(data.methodology, null, 2)};\n\n` +
    `export const results: {
  verdict: Verdict;
  chips: Chip[];
  figures: FigureMeta[];
  deviations: Deviation[];
  provenance: Provenance;
  pending: boolean;
  wall_clock_estimate: string;
  expected_output: string;
} = ${JSON.stringify(data.results, null, 2)};\n`;
  await mkdir(join(SITE_DIR, 'lib', 'runs'), { recursive: true });
  await writeFile(join(SITE_DIR, 'lib', 'runs', `${slug}.ts`), banner + body);
}

async function writeRunMdx(slug) {
  const body =
`{/*
  AUTO-GENERATED by build.mjs — DO NOT EDIT BY HAND.
  One MDX file per run; data is imported from the matching @/lib/runs/<slug>
  module so this file's identity (slug) carries the per-run provenance.
*/}

import { headline, meta, problem, methodology, results } from '@/lib/runs/${slug}';

<header className="not-prose mb-14 pb-8 border-b border-[color:var(--border-warm)]">
  <div className="eyebrow">{meta.paperId}</div>
  <h1 className="text-[2.75rem] leading-[1.10] font-semibold tracking-[-0.018em] mt-4 mb-5 text-[color:var(--near-black)]">
    {meta.title}
  </h1>
  {(meta.authors || meta.venue) && (
    <p className="text-sm text-[color:var(--olive)] m-0 leading-[1.55]">
      {meta.authors}
      {meta.authors && meta.venue && ' — '}
      <span className="italic">{meta.venue}</span>
      {meta.url && (
        <>
          {' · '}
          <a href={meta.url} className="text-[color:var(--terracotta)] hover:text-[color:var(--coral)] underline decoration-dotted underline-offset-[3px]">
            {meta.url.replace(/^https?:\\/\\//, '')}
          </a>
        </>
      )}
    </p>
  )}
  {headline.text && (
    <p className="text-xl leading-[1.55] font-medium text-[color:var(--near-black)] mt-8 mb-0">
      {headline.text}
    </p>
  )}
</header>

<ProblemSection blocks={problem.blocks} />

<MethodologySection
  models={methodology.models}
  methods={methodology.methods}
  params={methodology.params}
  assumptions={methodology.assumptions}
  kb_refs={methodology.kb_refs}
  expected_output_summary={methodology.expected_output_summary}
  deviations_by_id={methodology.deviations_by_id}
/>

<ResultsSection
  verdict={results.verdict}
  chips={results.chips}
  figures={results.figures}
  deviations={results.deviations}
  provenance={results.provenance}
  pending={results.pending}
  wallClockEstimate={results.wall_clock_estimate}
  expectedOutput={results.expected_output}
  headline={headline}
/>
`;
  await mkdir(join(SITE_DIR, 'content'), { recursive: true });
  await writeFile(join(SITE_DIR, 'content', `${slug}.mdx`), body);
}

async function writeCurrentReportWrapper(slug) {
  const body =
`// AUTO-GENERATED by build.mjs — DO NOT EDIT BY HAND.
// Static import of the current run's MDX + re-export of \`meta\`. This file
// is the only build-time-variable indirection between the tracked
// app/page.tsx shell and the per-run content. Static-import discipline
// is required for @next/mdx; do not change this to a dynamic import.

import Content from '@/content/${slug}.mdx';
export { Content };
export { meta } from '@/lib/runs/${slug}';
`;
  await writeFile(join(SITE_DIR, 'lib', 'current-report.tsx'), body);
}

// ─── shell next build ───────────────────────────────────────────────────────
function runNextBuild() {
  return new Promise((res, rej) => {
    const p = spawn('npx', ['next', 'build'], { cwd: SITE_DIR, stdio: 'inherit' });
    p.on('exit', code => code === 0 ? res() : rej(new Error(`next build exited ${code}`)));
    p.on('error', rej);
  });
}

// ─── serve out/ on a local port (for Playwright to navigate) ───────────────
const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.mjs':  'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg':  'image/svg+xml',
  '.png':  'image/png',
  '.jpg':  'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.ttf':  'font/ttf',  '.otf':   'font/otf',
};
function startStaticServer(rootDir) {
  return new Promise(res => {
    const server = createServer(async (req, res2) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
        if (urlPath.endsWith('/')) urlPath += 'index.html';
        const filePath = join(rootDir, urlPath);
        if (!filePath.startsWith(rootDir)) { res2.statusCode = 403; return res2.end(); }
        if (!exists(filePath))             { res2.statusCode = 404; return res2.end(); }
        const ct = CONTENT_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream';
        res2.setHeader('Content-Type', ct);
        res2.setHeader('Cache-Control', 'no-store');
        res2.end(await readFile(filePath));
      } catch (e) { res2.statusCode = 500; res2.end(String(e)); }
    });
    server.listen(0, '127.0.0.1', () => res({ server, port: server.address().port }));
  });
}

// ─── render in headless Chromium, inline every asset, return one HTML ──────
// Playwright opens the served page, waits for Next.js hydration to settle,
// then walks the live DOM via fetch() in the page context to base64-inline
// every stylesheet, script, image, and font. The returned HTML is fully
// self-contained — no remote URLs, no relative paths.
async function snapshotToOneHtml(outDir) {
  const { server, port } = await startStaticServer(outDir);
  const url = `http://127.0.0.1:${port}/`;
  stdout.write(`build: serving out/ at ${url}\n`);

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1200 } });
    await page.goto(url, { waitUntil: 'networkidle' });

    // Inline every same-origin asset in the page context, then serialize.
    const html = await page.evaluate(async () => {
      const sameOrigin = (u) => {
        try { return new URL(u, location.href).origin === location.origin; }
        catch { return false; }
      };
      const fetchText = async (u) => (await fetch(u)).text();
      const fetchDataUrl = async (u) => {
        const blob = await (await fetch(u)).blob();
        return await new Promise(r => {
          const fr = new FileReader();
          fr.onload = () => r(fr.result);
          fr.readAsDataURL(blob);
        });
      };
      // Recursively inline url(...) inside a CSS string. Skips data: and
      // cross-origin URLs; rewrites same-origin to data URLs so the resulting
      // <style> block is self-contained.
      const inlineCssUrls = async (cssText, baseUrl) => {
        const matches = [...cssText.matchAll(/url\(\s*(['"]?)([^'")]+)\1\s*\)/g)];
        const replacements = await Promise.all(matches.map(async (m) => {
          const u = m[2];
          if (u.startsWith('data:')) return null;
          try {
            const abs = new URL(u, baseUrl).href;
            if (new URL(abs).origin !== location.origin) return null;
            const dataUrl = await fetchDataUrl(abs);
            return [m[0], `url(${dataUrl})`];
          } catch { return null; }
        }));
        let out = cssText;
        for (const r of replacements) if (r) out = out.split(r[0]).join(r[1]);
        return out;
      };

      // <link rel="stylesheet">  →  <style>…</style>  (with url() inlined)
      for (const link of [...document.querySelectorAll('link[rel="stylesheet"]')]) {
        if (!sameOrigin(link.href)) continue;
        const css = await fetchText(link.href);
        const cssInlined = await inlineCssUrls(css, link.href);
        const style = document.createElement('style');
        style.textContent = cssInlined;
        link.replaceWith(style);
      }
      // Existing inline <style> elements: also walk their url() refs.
      for (const style of [...document.querySelectorAll('style')]) {
        if (!style.textContent.includes('url(')) continue;
        style.textContent = await inlineCssUrls(style.textContent, location.href);
      }

      // <script src="…">  →  <script>…</script>
      for (const s of [...document.querySelectorAll('script[src]')]) {
        if (!sameOrigin(s.src)) continue;
        const code = await fetchText(s.src);
        const inline = document.createElement('script');
        if (s.type) inline.type = s.type;
        inline.textContent = code;
        s.replaceWith(inline);
      }

      // <link rel="preload" as="script|font|image"> → drop (loaded already)
      for (const link of [...document.querySelectorAll('link[rel="preload"]')]) {
        if (sameOrigin(link.href)) link.remove();
      }
      // Other <link href> referencing same-origin resources → inline as data URL
      for (const link of [...document.querySelectorAll('link[href]')]) {
        if (link.rel === 'stylesheet') continue;
        if (!sameOrigin(link.href)) continue;
        link.href = await fetchDataUrl(link.href);
      }

      // <img src="…">, <source src="…">  →  data URL
      for (const img of [...document.querySelectorAll('img[src]')]) {
        if (!sameOrigin(img.src) || img.src.startsWith('data:')) continue;
        img.src = await fetchDataUrl(img.src);
      }

      // Hydration is done — the DOM is fully rendered. Strip every <script>
      // so the standalone HTML doesn't try to re-hydrate (and fail, since
      // Next.js's runtime context isn't reconstructible outside the browser
      // session). The doc loses JS-driven interactivity (theme toggle,
      // React-managed popovers); native <details> collapsibles and CSS-only
      // hover/focus still work.
      for (const s of [...document.querySelectorAll('script')]) s.remove();
      // Also drop Next.js's RSC payload script-template and prefetch markers.
      for (const tpl of [...document.querySelectorAll('template[id^="P:"], template[id^="S:"]')]) tpl.remove();

      return '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
    });

    return html;
  } finally {
    await browser.close();
    server.close();
  }
}

// ─── write final HTML + symlink ────────────────────────────────────────────
async function writeFinal(runDir, runId, today, html) {
  const filename = `report_${runId}_${today}.html`;
  const out      = join(runDir, filename);
  await writeFile(out, html);
  const size = (await stat(out)).size;
  if (size > HARD_CAP) { stderr.write(`build: rendered HTML exceeds 10 MB hard cap (${size.toLocaleString()} bytes)\n`); exit(1); }
  if (size > SOFT_CAP)   stderr.write(`build: [warn] rendered HTML exceeds 3 MB soft cap (${size.toLocaleString()} bytes)\n`);

  const link = join(runDir, 'report_latest.html');
  try { await unlink(link); } catch { /* missing is fine */ }
  try { await symlink(filename, link); }
  catch { await writeFile(link, html); }                 // Windows fallback
  stdout.write(`build: wrote ${out}\n`);
  stdout.write(`       size: ${size.toLocaleString()} bytes\n`);
  stdout.write(`       symlink: ${link} → ${filename}\n`);
}

// ─── main ──────────────────────────────────────────────────────────────────
async function main() {
  const { runDir, stage } = parseArgs();
  if (!exists(runDir)) { stderr.write(`build: run-dir not found: ${runDir}\n`); exit(1); }

  stdout.write(`build: loading ${runDir} (stage: ${stage})\n`);
  const data = await loadRun({ runDir, stage });

  const slug = sanitizeRunId(data.runId);
  stdout.write(`build: per-run slug: ${slug}\n`);
  stdout.write(`build: writing site/lib/runs/${slug}.ts\n`);
  await writeRunDataModule(slug, data);
  stdout.write(`build: writing site/content/${slug}.mdx\n`);
  await writeRunMdx(slug);
  stdout.write(`build: writing site/lib/current-report.tsx\n`);
  await writeCurrentReportWrapper(slug);

  stdout.write(`build: running next build\n`);
  await runNextBuild();

  stdout.write(`build: snapshotting out/ via headless Chromium\n`);
  const html = await snapshotToOneHtml(join(SITE_DIR, 'out'));

  await writeFinal(runDir, data.runId, data.today, html);
}

main().catch(err => { stderr.write(`build: ${err.message ?? err}\n`); exit(1); });
