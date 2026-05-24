import { Callout } from 'fumadocs-ui/components/callout';
import { Steps, Step } from 'fumadocs-ui/components/steps';
import type { Model, Method, Param, Assumption } from '@/lib/types';
import { Cite } from './cite';
import { Math } from './math';
import { StatChip, MethodBadge } from './stat-chip';

// Methodology sub-page — visual-anchor layout (per the redesign in
// docs/report-methodology-redesign.md and the parallel UX audit):
//
//   Models: one ModelAnchor per model — large KaTeX Hamiltonian as hero,
//   dimension stat callout, key-facts strip, one-sentence summary, optional
//   one-line delta. Paper|ours full prose lives in a <details> for power-readers.
//
//   Methods: MethodAnchor per method — badge + name + math headline + a
//   responsive grid of operational StatChips. Deviations are NOT inline; they
//   are hoisted to a single Notes & exceptions strip at the section bottom
//   (fixes C5 caveats-after).
//
//   Parameters: grouped by audience-readable scope_label (no raw "method:X").
//   Each row: human label · value chips · one-line why.
//
//   Assumptions: Fumadocs <Steps> with KaTeX-rendered math; why + cite per step.

export function MethodologySection({
  models, methods, params, assumptions, kb_refs, expected_output_summary, deviations_by_id,
}: {
  models: Model[];
  methods: Method[];
  params: Param[];
  assumptions: Assumption[];
  kb_refs: string[];
  expected_output_summary: string;
  deviations_by_id: Record<string, { statement: string; why?: string }>;
}) {
  // Collect every distinct scope_label (or scope) that params/assumptions reference,
  // preserving first-seen order, so we can group params by scope below.
  const paramsByScope = new Map<string, { scopeLabel: string; rows: Param[] }>();
  for (const p of params) {
    const key = p.scope ?? '__no_scope__';
    const label = p.scope_label ?? humanizeScope(p.scope) ?? 'Used throughout';
    if (!paramsByScope.has(key)) paramsByScope.set(key, { scopeLabel: label, rows: [] });
    paramsByScope.get(key)!.rows.push(p);
  }

  // Collect deviations referenced by any method, dedup, for the section-end strip.
  const deviationIds = Array.from(new Set(
    methods.map(m => m.deviation).filter(Boolean) as string[]
  ));

  return (
    <section id="methodology" className="page">
      <header>
        <h2>Methodology</h2>
        <span className="subtitle">what we did and why</span>
      </header>
      <div className="space-y-12">

        {/* Models — Hamiltonian-hero anchors */}
        {models.length > 0 && (
          <section>
            <h3 className="text-xl font-semibold mb-5 mt-0 text-[color:var(--near-black)]">Models</h3>
            <div className="not-prose">
              {models.map(m => <ModelAnchor key={m.id} model={m} />)}
            </div>
          </section>
        )}

        {/* Methods — badge + headline + operational chips */}
        {methods.length > 0 && (
          <section>
            <h3 className="text-xl font-semibold mb-5 mt-0 text-[color:var(--near-black)]">Methods</h3>
            <div className="not-prose">
              {methods.map(m => <MethodAnchor key={m.id} method={m} />)}
            </div>
          </section>
        )}

        {/* Parameters — grouped by scope label, chip-strip rows */}
        {params.length > 0 && (
          <section>
            <h3 className="text-xl font-semibold mb-5 mt-0 text-[color:var(--near-black)]">Parameters</h3>
            <div className="not-prose">
              {Array.from(paramsByScope.entries()).map(([key, group]) => (
                <div key={key} className="param-scope-group">
                  <div className="param-scope-eyebrow">For: {group.scopeLabel}</div>
                  {group.rows.map((p, i) => <ParamRow key={i} param={p} />)}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Assumptions — Steps with KaTeX math */}
        {assumptions.length > 0 && (
          <section>
            <h3 className="text-xl font-semibold mb-5 mt-0 text-[color:var(--near-black)]">Assumptions</h3>
            <Steps>
              {assumptions.map((a, i) => (
                <Step key={i}>
                  <div className="assumption-step">
                    {(a.scope_label || a.scope) && (
                      <div className="scope">For: {a.scope_label ?? humanizeScope(a.scope)}</div>
                    )}
                    <div className="label">{a.label ?? a.text}</div>
                    {a.text_tex && (
                      <div className="text-math">
                        <Math display tex={a.text_tex} fallback={a.text_unicode ?? a.text} />
                      </div>
                    )}
                    <p className="why">
                      <span className="why-eyebrow">Why?</span>
                      {a.why.text}
                      <Cite cite={a.why.cite} />
                    </p>
                  </div>
                </Step>
              ))}
            </Steps>
          </section>
        )}

        {/* Notes & exceptions — single bottom strip aggregating deviations */}
        {deviationIds.length > 0 && (
          <section className="not-prose">
            <div className="notes-strip">
              <div className="notes-strip-eyebrow">Notes &amp; exceptions</div>
              {deviationIds.map(devId => {
                const d = deviations_by_id[devId];
                if (!d) return null;
                return (
                  <div key={devId} className="note-row">
                    <strong>{d.statement}</strong>
                    {d.why && (
                      <p className="m-0 mt-2"><span className="why-eyebrow">Why?</span>{d.why}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Anchored-in references + expected-output summary — moved BELOW so
            the visual anchor is the model, not the procedural meta. */}
        {(kb_refs.length > 0 || expected_output_summary) && (
          <section className="space-y-5 not-prose">
            {expected_output_summary && (
              <Callout type="info" title="Expected output">
                {expected_output_summary}
              </Callout>
            )}
            {kb_refs.length > 0 && (
              <div>
                <div className="eyebrow muted mb-2">Anchored in</div>
                <div className="flex flex-wrap">
                  {kb_refs.map(r => <code key={r} className="kb-ref">{humanizeKbRef(r)}</code>)}
                </div>
              </div>
            )}
          </section>
        )}

      </div>
    </section>
  );
}

function ModelAnchor({ model: m }: { model: Model }) {
  const summary = m.summary?.text ?? m.paper.text;
  const summaryCite = m.summary?.cite ?? m.paper.cite;
  const delta = m.delta_from_paper;
  const eqCite = m.equation?.cite ?? m.paper.cite;
  return (
    <article className="model-anchor">
      <header className="model-anchor-head">
        <span className="model-anchor-eyebrow">Model</span>
        <h4>{m.name}</h4>
      </header>

      {m.equation?.tex && (
        <div className="model-equation-frame">
          {eqCite && <Cite cite={eqCite} />}
          <Math display tex={m.equation.tex} fallback={m.equation.unicode_fallback} label={m.name} />
        </div>
      )}

      {/* Key-facts strip + dimension callout (dimension is just a wider StatChip) */}
      {((m.key_facts && m.key_facts.length > 0) || m.dimension) && (
        <div className="stat-chip-strip">
          {(m.key_facts ?? []).map((f, i) => (
            <StatChip
              key={i}
              label={f.label}
              value={f.value}
              value_tex={f.value_tex}
              value_unicode={f.value_unicode}
            />
          ))}
          {m.dimension && (
            <StatChip
              label="Hilbert-space dimension"
              value_tex={m.dimension.value_tex}
              value_unicode={m.dimension.value_unicode}
            />
          )}
        </div>
      )}

      {summary && (
        <p className="model-summary">
          {summary}
          {summaryCite && <Cite cite={summaryCite} />}
        </p>
      )}

      {m.dimension?.at && (
        <p className="text-xs text-[color:var(--stone)] mt-2">{m.dimension.at}</p>
      )}

      {delta && (
        <div className="model-delta">
          <span className="model-delta-eyebrow">Our run</span>
          {delta}
        </div>
      )}

      {/* Power-user reveal: the full paper/ours prose, preserved for deep readers */}
      <details className="method-details">
        <summary>Full paper vs run description</summary>
        <div className="method-details-body">
          <span className="label-paper">Paper</span>
          {m.paper.text}<Cite cite={m.paper.cite} />
          <span className="label-ours">This run</span>
          {m.ours.text}<Cite cite={m.ours.cite} />
        </div>
      </details>
    </article>
  );
}

function MethodAnchor({ method: m }: { method: Method }) {
  const badge = m.badge;
  return (
    <article className="method-anchor">
      <header className="method-anchor-head">
        {badge && <MethodBadge label={badge.label} tone={badge.tone ?? 'primary'} />}
        <h4>{m.name}</h4>
      </header>

      {m.headline?.tex && (
        <div className="method-headline">
          <Math tex={m.headline.tex} fallback={m.headline.unicode_fallback} />
        </div>
      )}

      {m.operational && m.operational.length > 0 && (
        <div className="method-operational">
          {m.operational.map((row, i) => (
            <StatChip
              key={i}
              label={row.name}
              value={row.value}
              value_tex={row.value_tex}
              value_unicode={row.value_unicode}
            />
          ))}
        </div>
      )}

      {!m.headline?.tex && !m.operational?.length && (
        /* fallback when polish step didn't emit anchor fields — show
           the paper/ours pair so we never render an empty card */
        <div className="grid md:grid-cols-2 gap-4 not-prose">
          <div className="panel-card">
            <div className="panel-head"><span className="label">Paper</span></div>
            <p className="text-[0.95rem] leading-[1.65] text-[color:var(--charcoal)] m-0">{m.paper.text}<Cite cite={m.paper.cite} /></p>
          </div>
          <div className="panel-card brand">
            <div className="panel-head"><span className="label brand">This run</span></div>
            <p className="text-[0.95rem] leading-[1.65] text-[color:var(--charcoal)] m-0">{m.ours.text}<Cite cite={m.ours.cite} /></p>
          </div>
        </div>
      )}

      <details className="method-details">
        <summary>Full paper vs run description</summary>
        <div className="method-details-body">
          <span className="label-paper">Paper</span>
          {m.paper.text}<Cite cite={m.paper.cite} />
          <span className="label-ours">This run</span>
          {m.ours.text}<Cite cite={m.ours.cite} />
        </div>
      </details>
    </article>
  );
}

function ParamRow({ param: p }: { param: Param }) {
  const label = p.label ?? p.name;
  const values = p.values_tex
    ? p.values_tex.map((tex, i) => ({ tex, unicode: p.values_unicode?.[i] }))
    : (p.values ?? []).map(v => ({ raw: String(v) }));
  return (
    <div className="param-row">
      <div className="label">{label}</div>
      <div className="values">
        {values.map((v, i) => (
          <span key={i} className="v">
            {('tex' in v && v.tex)
              ? <Math tex={v.tex} fallback={v.unicode ?? ''} />
              : (v as { raw: string }).raw}
          </span>
        ))}
      </div>
      <div className="why-summary">
        {p.why.text}<Cite cite={p.why.cite} />
      </div>
    </div>
  );
}

// Map `method:ed_static` → "ed_static" with underscores hidden when no
// scope_label was emitted (A1/A6 fallback — best-effort, polish step
// should provide scope_label for full A8 compliance).
function humanizeScope(scope: string | null | undefined): string | null {
  if (!scope) return null;
  const [, id] = scope.split(':');
  if (!id) return scope;
  return id.replace(/[._]/g, ' ');
}

// KB references like `.knowledge/methods/ed/METHOD.md` → "ed (method
// card)" so we don't leak file paths (A2). Best-effort fallback.
function humanizeKbRef(ref: string): string {
  const m = ref.match(/methods\/([^/]+)\//);
  if (m) return `${m[1]} method card`;
  const last = ref.split('/').pop()?.replace(/\.md$/, '') ?? ref;
  return last.replace(/[-_]/g, ' ');
}
