import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { getInstrument } from '@/domain/instruments';
import { alignedPairs, type Opportunity } from '@/domain/opportunity';
import { formatPercent } from '@/lib/format';

function Cell({ label, children, hint }: { label: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs text-fg-3">{label}</dt>
      <dd className="mt-1 text-base text-fg">{children}</dd>
      {hint && <dd className="mt-0.5 truncate text-xs text-fg-3">{hint}</dd>}
    </div>
  );
}

/** Market-wide summary of the AI analyses — answers "where should I look first?". */
export function SignalSummary({ items }: { items: readonly Opportunity[] }) {
  const detected = items.filter((o) => o.status === 'detected');
  const longs = detected.filter((o) => o.direction === 'long').length;
  const shorts = detected.length - longs;
  const top = [...detected].sort((a, b) => b.probability - a.probability)[0];
  const mean = detected.length ? detected.reduce((s, o) => s + o.probability, 0) / detected.length : null;
  const aligned = alignedPairs(items);

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line lg:grid-cols-4">
      <Cell label="Detected" hint={`of ${items.length} analyses`}>
        <span className="num">{detected.length}</span>
        <span className="ml-3 inline-flex items-center gap-2 text-sm">
          <span className="num inline-flex items-center text-up">
            <ArrowUpRight aria-hidden className="size-3.5" />
            {longs} long
          </span>
          <span className="num inline-flex items-center text-down">
            <ArrowDownRight aria-hidden className="size-3.5" />
            {shorts} short
          </span>
        </span>
      </Cell>
      <Cell label="Highest probability" hint={top ? `${top.direction === 'long' ? 'Long' : 'Short'} · ${top.timeframe}` : 'No detections'}>
        {top ? (
          <>
            {getInstrument(top.symbol).display} <span className="num text-forecast">{formatPercent(top.probability)}</span>
          </>
        ) : (
          '—'
        )}
      </Cell>
      <Cell label="Mean probability" hint="Across detected setups">
        <span className="num text-forecast">{formatPercent(mean)}</span>
      </Cell>
      <Cell
        label="All timeframes aligned"
        hint={aligned.length ? aligned.map((a) => `${getInstrument(a.symbol).display} ${a.direction}`).join(' · ') : '15m, 1h and 4h agree on no pair'}
      >
        <span className="num">{aligned.length}</span> <span className="text-sm text-fg-2">{aligned.length === 1 ? 'pair' : 'pairs'}</span>
      </Cell>
    </dl>
  );
}
