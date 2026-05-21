import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { DocsBody, DocsPage } from 'fumadocs-ui/page';
import { Content, meta } from '@/lib/current-report';
import { tree } from '@/lib/source';

// Tracked, stable shell. The build.mjs pipeline regenerates
// @/lib/current-report on every invocation; this file does not change.
//
// Single-doc DocsLayout. No themeSwitch (we strip JS at snapshot), no search
// (single page). TOC is intentionally off — Fumadocs's article max-width
// bumps from 860 → 1120px when no TOC is present, which is what figure
// comparison panels need.

export const metadata = {
  title: `${meta.paperId} · ${meta.runId} · /report`,
  description: meta.description,
};

export default function ReportPage() {
  return (
    <DocsLayout
      tree={tree}
      nav={{ title: <span className="font-semibold">{meta.paperId}</span> }}
      sidebar={{ collapsible: false }}
    >
      <DocsPage>
        <DocsBody>
          <Content />
        </DocsBody>
      </DocsPage>
    </DocsLayout>
  );
}
