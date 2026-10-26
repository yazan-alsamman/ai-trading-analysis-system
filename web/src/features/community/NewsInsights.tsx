import { useState } from 'react';
import { usePreferences, useServices } from '@/app/contexts';
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ErrorState, Loading, SkeletonRows } from '@/components/ui/StateViews';
import { TableRegion, Td, Th } from '@/components/ui/Table';
import type { SentimentBucket } from '@/domain/marketExtras';
import { useResource } from '@/hooks/useResource';
import { formatDateTime, formatNumber, formatRelative, MISSING } from '@/lib/format';

const WINDOWS = [
  { value: '1h', label: '1 hour' },
  { value: '24h', label: '24 hours' },
  { value: '7d', label: '7 days' },
] as const;
type SentimentWindow = (typeof WINDOWS)[number]['value'];

const score = (v: number | null) => (v === null ? MISSING : `${v > 0 ? '+' : ''}${formatNumber(v, 2)}`);

function Counts({ b }: { b: SentimentBucket }) {
  return (
    <>
      <Td numeric>{b.articles}</Td>
      <Td numeric className="text-up">
        {b.positive}
      </Td>
      <Td numeric>{b.neutral}</Td>
      <Td numeric className="text-down">
        {b.negative}
      </Td>
      <Td numeric>{score(b.meanScore)}</Td>
    </>
  );
}

/**
 * Backend news sentiment per instrument (GET /news/sentiment): counts of the
 * labels the backend's language model gave each article in the window, and
 * the mean score (−1 … +1). An automated reading of headlines, not advice.
 */
export function NewsSentimentPanel() {
  const services = useServices();
  const [win, setWin] = useState<SentimentWindow>('24h');
  const res = useResource(`news-sentiment:${win}`, (signal) => services.marketContext.sentiment(win, null, { signal }));
  return (
    <Panel
      title="News sentiment"
      meta={<span>Scored by the backend’s language model; not advice</span>}
      actions={<SegmentedControl label="Sentiment window" value={win} onChange={setWin} options={WINDOWS} />}
      flush
    >
      {res.status === 'loading' ? (
        <Loading label="Loading sentiment">
          <SkeletonRows rows={2} className="p-4" />
        </Loading>
      ) : res.status === 'error' && !res.data ? (
        <ErrorState error={res.error} onRetry={res.reload} compact />
      ) : res.data ? (
        <TableRegion label="News sentiment by instrument">
          <thead>
            <tr>
              <Th>Instrument</Th>
              <Th numeric>Articles</Th>
              <Th numeric>Positive</Th>
              <Th numeric>Neutral</Th>
              <Th numeric>Negative</Th>
              <Th numeric>Mean score</Th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <Td className="font-medium">All news</Td>
              <Counts b={res.data.overall} />
            </tr>
            {res.data.instruments.map((i) => (
              <tr key={i.instrumentId}>
                <Td>{i.symbol}</Td>
                <Counts b={i} />
              </tr>
            ))}
          </tbody>
        </TableRegion>
      ) : null}
    </Panel>
  );
}

/** The backend's news sources (GET /news/sources): where the articles come from and when each was last read. */
export function NewsSourcesDisclosure() {
  const services = useServices();
  const { timeZone } = usePreferences();
  const [open, setOpen] = useState(false);
  const res = useResource(open ? 'news-sources' : 'news-sources:closed', (signal) => (open ? services.marketContext.newsSources({ signal }) : Promise.resolve([])));
  return (
    <details className="rounded-lg border border-line bg-surface" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-fg">News sources</summary>
      <div className="border-t border-line">
        {res.status === 'loading' ? (
          <Loading label="Loading news sources">
            <SkeletonRows rows={2} className="p-4" />
          </Loading>
        ) : res.status === 'error' ? (
          <ErrorState error={res.error} onRetry={res.reload} compact />
        ) : (
          <TableRegion label="News sources">
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Kind</Th>
                <Th>Language</Th>
                <Th>Status</Th>
                <Th>Last fetched</Th>
                <Th>Last error</Th>
              </tr>
            </thead>
            <tbody>
              {(res.data ?? []).map((s) => (
                <tr key={s.id}>
                  <Td className="font-medium">{s.name}</Td>
                  <Td>{s.kind.toUpperCase()}</Td>
                  <Td>{s.language}</Td>
                  <Td>
                    <Badge tone={s.isActive ? 'up' : 'neutral'}>{s.isActive ? 'Active' : 'Disabled'}</Badge>
                  </Td>
                  <Td title={s.lastFetchedAt ? formatDateTime(s.lastFetchedAt, timeZone) : undefined}>{s.lastFetchedAt ? formatRelative(s.lastFetchedAt) : MISSING}</Td>
                  <Td className="max-w-xs truncate whitespace-nowrap text-fg-2" title={s.lastError ?? undefined}>
                    {s.lastError ?? MISSING}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
        )}
      </div>
    </details>
  );
}
