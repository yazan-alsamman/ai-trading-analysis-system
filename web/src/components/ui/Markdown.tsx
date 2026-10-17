import { Fragment, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Minimal, safe Markdown for assistant replies: headings, paragraphs, bold,
 * italic, inline code, bullet/numbered lists, block quotes and pipe tables.
 * It builds React elements only — never innerHTML — so text from a backend or
 * model cannot inject markup or scripts. Links are rendered as plain text.
 */

import { parseMarkdown } from './markdownParser';

/** Inline: **bold**, *italic*, `code`. Everything else is literal text. */
function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(re)) {
    const token = m[0];
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    if (token.startsWith('**')) out.push(<strong key={key++} className="font-semibold text-fg">{token.slice(2, -2)}</strong>);
    else if (token.startsWith('`')) out.push(<code key={key++} className="num rounded-sm bg-inset px-1 text-[0.95em]">{token.slice(1, -1)}</code>);
    else out.push(<em key={key++}>{token.slice(1, -1)}</em>);
    last = at + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Short cells made of figures (prices, ratios, money) get tabular numerals. */
const NUMERIC_CELL = /^[^a-zA-Z]{0,4}[\d][\d\s.,:+−\-–%$€£¥·R()ozlts]*$/;

export function Markdown({ source, className }: { source: string; className?: string }) {
  const blocks = parseMarkdown(source);
  return (
    <div className={cn('flex flex-col gap-2.5 text-sm leading-6 text-fg-2', className)}>
      {blocks.map((b, i) => {
        switch (b.kind) {
          case 'heading':
            return (
              <p key={i} role="heading" aria-level={Math.min(6, b.level + 2)} className="font-semibold text-fg">
                {renderInline(b.text)}
              </p>
            );
          case 'paragraph':
            return <p key={i}>{renderInline(b.text)}</p>;
          case 'quote':
            return (
              <blockquote key={i} className="border-l-2 border-demo/60 pl-3 text-xs text-fg-3">
                {renderInline(b.text)}
              </blockquote>
            );
          case 'list': {
            const L = b.ordered ? 'ol' : 'ul';
            return (
              <L key={i} className={cn('flex flex-col gap-1 pl-5', b.ordered ? 'list-decimal' : 'list-disc marker:text-fg-3')}>
                {b.items.map((it, j) => (
                  <li key={j}>{renderInline(it)}</li>
                ))}
              </L>
            );
          }
          case 'table':
            return (
              <div key={i} className="overflow-x-auto rounded-md border border-line">
                <table className="w-full border-collapse text-xs">
                  <thead className="bg-inset">
                    <tr>
                      {b.header.map((h, j) => (
                        <th key={j} scope="col" className="px-2.5 py-1.5 text-left font-medium text-fg-3">
                          {renderInline(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j} className="border-t border-line">
                        {r.map((c, k) => (
                          <td key={k} className={cn('px-2.5 py-1.5 align-top', k === 0 ? 'text-fg-2' : 'text-fg', k > 0 && NUMERIC_CELL.test(c) && 'num')}>
                            <Fragment>{renderInline(c)}</Fragment>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
