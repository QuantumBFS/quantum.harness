import type { PageTree } from 'fumadocs-core/server';

// Single-page docs — the sidebar lists the three sections as anchors.
// DocsLayout requires a tree; we synthesize one with anchor links.
export const tree: PageTree.Root = {
  name: 'Report',
  children: [
    { type: 'page', name: 'Problem',     url: '#problem' },
    { type: 'page', name: 'Methodology', url: '#methodology' },
    { type: 'page', name: 'Results',     url: '#results' },
  ],
};
