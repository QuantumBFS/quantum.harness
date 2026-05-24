import type { ReactNode } from 'react';
import { Math } from './math';

// Render a prose string that may contain inline math spans wrapped in $...$.
// Used throughout Results (verdict.detail, chip labels, figure captions,
// deviation prose) so a single editorial string can mix English and KaTeX
// without the polish step having to emit separate `text_tex` siblings.
//
// Splitting on /(\$[^$]+\$)/g captures the math span as a delimiter so
// inline-text and math parts alternate. Backslash-escaped dollar signs
// would require a real parser; the polish step's contract avoids them.

export function MathInText({ text }: { text?: string | null }): ReactNode {
  if (!text) return null;
  const parts = text.split(/(\$[^$]+\$)/g);
  return parts.map((part, i) => {
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      const tex = part.slice(1, -1);
      return <Math key={i} tex={tex} fallback={tex} />;
    }
    return <span key={i}>{part}</span>;
  });
}
