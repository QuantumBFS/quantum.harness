import 'katex/dist/katex.min.css';
import './globals.css';
import { RootProvider } from 'fumadocs-ui/provider';
import { Inter, JetBrains_Mono } from 'next/font/google';
import type { ReactNode } from 'react';

// Fumadocs's house typography: Inter for everything textual, JetBrains Mono
// for code. No serif. The visual identity is monochromatic per fumadocs-ui's
// own design tokens — accent colour only shows up via Callout type variants.
const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });
const mono  = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' });

// Page-level `metadata` lives in app/page.tsx — keeping the per-run data
// import out of the layout's module graph means /_not-found (which inherits
// this layout) never has to pull in @/lib/current-report or its MDX.

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${mono.variable}`}>
      <body className="bg-fd-background text-fd-foreground antialiased">
        <RootProvider theme={{ enabled: false }}>{children}</RootProvider>
      </body>
    </html>
  );
}
